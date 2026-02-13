"""Fetch recently modified Google Drive docs."""

import difflib
import json
from datetime import datetime, timezone, timedelta
from io import BytesIO


def fetch_recent_docs(
    drive_service,
    sheets_service,
    folder_ids: list[str],
    lookback_days: int = 7,
) -> list[dict]:
    """Fetch recently modified Google Docs and Sheets from specified folders.

    Returns list of dicts with keys: name, content, modified_time, mime_type, content_type.
    content_type is "diff" (Google Docs with old revision) or "full" (new Docs, all Sheets).
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)
    cutoff_str = cutoff.strftime("%Y-%m-%dT%H:%M:%S")

    all_docs = []

    for folder_id in folder_ids:
        query = (
            f"'{folder_id}' in parents"
            f" and modifiedTime > '{cutoff_str}'"
            f" and trashed = false"
            f" and ("
            f"mimeType = 'application/vnd.google-apps.document'"
            f" or mimeType = 'application/vnd.google-apps.spreadsheet'"
            f")"
        )

        resp = drive_service.files().list(
            q=query,
            fields="files(id, name, mimeType, modifiedTime)",
            pageSize=100,
        ).execute()

        files = resp.get("files", [])

        for f in files:
            result = _process_file(drive_service, sheets_service, f, lookback_days)
            if result is not None:
                all_docs.append(result)

    return all_docs


def _process_file(drive_service, sheets_service, file_info: dict, lookback_days: int) -> dict | None:
    """Process a single file — diff for Docs, diff for Sheets (with snapshot)."""
    mime = file_info["mimeType"]

    if mime == "application/vnd.google-apps.document":
        return _process_google_doc(drive_service, file_info, lookback_days)
    elif mime == "application/vnd.google-apps.spreadsheet":
        return _process_google_sheet(drive_service, sheets_service, file_info)
    return None


def _process_google_doc(drive_service, file_info: dict, lookback_days: int) -> dict | None:
    """Fetch current content and diff against old revision if available."""
    file_id = file_info["id"]

    # Get current content
    current_bytes = drive_service.files().export(
        fileId=file_id, mimeType="text/plain",
    ).execute()
    current_text = current_bytes.decode("utf-8") if isinstance(current_bytes, bytes) else str(current_bytes)

    # Try to get old revision
    old_text = _get_old_revision_text(drive_service, file_id, lookback_days)

    if old_text is not None:
        diff = _compute_diff(old_text, current_text)
        if not diff:
            # No actual content changes — skip this doc
            return None
        return {
            "name": file_info["name"],
            "content": diff,
            "modified_time": file_info["modifiedTime"],
            "mime_type": file_info["mimeType"],
            "content_type": "diff",
        }
    else:
        # New doc or revision history unavailable — send full content
        return {
            "name": file_info["name"],
            "content": current_text,
            "modified_time": file_info["modifiedTime"],
            "mime_type": file_info["mimeType"],
            "content_type": "full",
        }


def _process_google_sheet(drive_service, sheets_service, file_info: dict) -> dict | None:
    """Fetch Sheet content, diff against snapshot if available, save new snapshot."""
    if not sheets_service:
        print(f"  Warning: Sheets service not available, skipping {file_info['name']}")
        return None

    sheet_id = file_info["id"]

    # Get current data
    resp = sheets_service.spreadsheets().values().get(
        spreadsheetId=sheet_id,
        range="A:ZZ",
    ).execute()
    current_rows = resp.get("values", [])

    if not current_rows:
        return None

    # Try to load previous snapshot
    old_rows = _load_sheet_snapshot(drive_service, sheet_id)

    # Save current data as new snapshot (do this regardless of diff result)
    _save_sheet_snapshot(drive_service, sheet_id, current_rows)

    if old_rows is not None:
        diff = _compute_sheet_diff(old_rows, current_rows)
        if not diff:
            return None  # No changes
        return {
            "name": file_info["name"],
            "content": diff,
            "modified_time": file_info["modifiedTime"],
            "mime_type": file_info["mimeType"],
            "content_type": "diff",
        }
    else:
        # No snapshot — first run for this sheet, send full content
        return {
            "name": file_info["name"],
            "content": "\n".join(["\t".join(row) for row in current_rows]),
            "modified_time": file_info["modifiedTime"],
            "mime_type": file_info["mimeType"],
            "content_type": "full",
        }


def _get_old_revision_text(drive_service, file_id: str, lookback_days: int) -> str | None:
    """Fetch the text of the most recent revision before the lookback cutoff.

    Returns None if no such revision exists or if the API call fails.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)

    try:
        resp = drive_service.revisions().list(
            fileId=file_id, fields="revisions(id, modifiedTime)",
        ).execute()
    except Exception as e:
        print(f"  Warning: Could not fetch revisions for {file_id}: {e}")
        return None

    revisions = resp.get("revisions", [])

    # Find the most recent revision before the cutoff
    candidates = []
    for rev in revisions:
        rev_time = datetime.fromisoformat(rev["modifiedTime"].replace("Z", "+00:00"))
        if rev_time < cutoff:
            candidates.append((rev_time, rev["id"]))

    if not candidates:
        return None

    # Sort by time descending, pick the most recent
    candidates.sort(reverse=True)
    best_rev_id = candidates[0][1]

    try:
        content = drive_service.revisions().get(
            fileId=file_id, revisionId=best_rev_id, alt="media",
        ).execute()
        if isinstance(content, bytes):
            return content.decode("utf-8")
        return str(content)
    except Exception as e:
        print(f"  Warning: Could not export revision {best_rev_id}: {e}")
        return None


def _compute_diff(old_text: str, new_text: str) -> str:
    """Compute a unified diff between old and new text.

    Returns empty string if there are no changes.
    """
    diff_lines = list(difflib.unified_diff(
        old_text.splitlines(),
        new_text.splitlines(),
        fromfile="7 days ago",
        tofile="current",
        lineterm="",
    ))

    if not diff_lines:
        return ""

    return "\n".join(diff_lines)


def _load_sheet_snapshot(drive_service, sheet_id: str) -> list[list[str]] | None:
    """Load a sheet snapshot from appDataFolder.

    Returns the row data as a list of lists, or None if no snapshot exists.
    """
    try:
        resp = drive_service.files().list(
            spaces="appDataFolder",
            q=f"name = 'sheet_snapshot_{sheet_id}.json'",
            fields="files(id)",
        ).execute()
    except Exception as e:
        print(f"  Warning: Could not search for sheet snapshot: {e}")
        return None

    files = resp.get("files", [])
    if not files:
        return None

    snapshot_id = files[0]["id"]
    try:
        content = drive_service.files().get_media(fileId=snapshot_id).execute()
        if isinstance(content, bytes):
            data = json.loads(content.decode("utf-8"))
        else:
            data = json.loads(str(content))
        return data.get("rows", None)
    except Exception as e:
        print(f"  Warning: Could not load sheet snapshot: {e}")
        return None


def _save_sheet_snapshot(drive_service, sheet_id: str, rows: list[list[str]]) -> None:
    """Save a sheet snapshot to appDataFolder. Creates or updates."""
    snapshot = {
        "sheet_id": sheet_id,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "rows": rows,
    }
    content = json.dumps(snapshot).encode("utf-8")
    media = BytesIO(content)

    # Check if snapshot already exists
    try:
        resp = drive_service.files().list(
            spaces="appDataFolder",
            q=f"name = 'sheet_snapshot_{sheet_id}.json'",
            fields="files(id)",
        ).execute()
    except Exception as e:
        print(f"  Warning: Could not save sheet snapshot: {e}")
        return

    files = resp.get("files", [])

    try:
        from googleapiclient.http import MediaIoBaseUpload
        media_upload = MediaIoBaseUpload(media, mimetype="application/json")

        if files:
            drive_service.files().update(
                fileId=files[0]["id"],
                media_body=media_upload,
            ).execute()
        else:
            drive_service.files().create(
                body={
                    "name": f"sheet_snapshot_{sheet_id}.json",
                    "parents": ["appDataFolder"],
                },
                media_body=media_upload,
            ).execute()
    except Exception as e:
        print(f"  Warning: Could not save sheet snapshot: {e}")


def _compute_sheet_diff(old_rows: list[list[str]], new_rows: list[list[str]]) -> str:
    """Compute a row-level diff between old and new sheet data.

    Matches rows by first column value. Falls back to positional matching
    for duplicate first-column values. Returns empty string if no changes.
    """
    if not old_rows and not new_rows:
        return ""

    # Get headers from whichever has them
    headers = new_rows[0] if new_rows else old_rows[0] if old_rows else []

    # Build lookup from first column to rows
    def build_row_map(rows):
        row_map = {}
        duplicates = set()
        for i, row in enumerate(rows):
            if not row:
                continue
            key = row[0]
            if key in row_map:
                duplicates.add(key)
            row_map.setdefault(key, []).append((i, row))
        return row_map, duplicates

    old_map, old_dupes = build_row_map(old_rows)
    new_map, new_dupes = build_row_map(new_rows)
    all_dupes = old_dupes | new_dupes

    changes = []

    # Find changed and removed rows (iterate old rows)
    matched_new_keys = set()
    for key, old_entries in old_map.items():
        if key in all_dupes:
            # Positional matching for duplicates
            new_entries = new_map.get(key, [])
            for idx, (old_i, old_row) in enumerate(old_entries):
                if idx < len(new_entries):
                    new_i, new_row = new_entries[idx]
                    _compare_rows(old_row, new_row, old_i, headers, changes)
                else:
                    changes.append(f"Row {old_i + 1} removed: {old_row}")
            matched_new_keys.add(key)
        elif key in new_map:
            # Unique key — match by first column
            old_row = old_entries[0][1]
            new_i, new_row = new_map[key][0]
            _compare_rows(old_row, new_row, new_i, headers, changes)
            matched_new_keys.add(key)
        else:
            # Row removed
            old_i, old_row = old_entries[0]
            changes.append(f"Row {old_i + 1} removed: {old_row}")

    # Find added rows (in new but not matched)
    for key, new_entries in new_map.items():
        if key in matched_new_keys:
            if key in all_dupes:
                # Check for extra new entries beyond what was matched positionally
                old_count = len(old_map.get(key, []))
                for idx in range(old_count, len(new_entries)):
                    new_i, new_row = new_entries[idx]
                    changes.append(f"Row {new_i + 1} added: {new_row}")
            continue
        for new_i, new_row in new_entries:
            changes.append(f"Row {new_i + 1} added: {new_row}")

    return "\n".join(changes)


def _compare_rows(old_row: list[str], new_row: list[str], row_num: int, headers: list[str], changes: list[str]) -> None:
    """Compare two rows and append change descriptions to the changes list."""
    row_key = old_row[0] if old_row else new_row[0] if new_row else ""
    max_cols = max(len(old_row), len(new_row))
    for col_idx in range(max_cols):
        old_val = old_row[col_idx] if col_idx < len(old_row) else ""
        new_val = new_row[col_idx] if col_idx < len(new_row) else ""
        if old_val != new_val:
            col_name = headers[col_idx] if col_idx < len(headers) else f"Column {col_idx + 1}"
            changes.append(f'Row {row_num + 1} ({row_key}): "{col_name}" changed from "{old_val}" to "{new_val}"')
