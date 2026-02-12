"""Fetch recently modified Google Drive docs."""

import difflib
from datetime import datetime, timezone, timedelta


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
    """Process a single file — diff for Docs, full content for Sheets."""
    mime = file_info["mimeType"]

    if mime == "application/vnd.google-apps.document":
        return _process_google_doc(drive_service, file_info, lookback_days)
    elif mime == "application/vnd.google-apps.spreadsheet":
        return _process_google_sheet(sheets_service, file_info)
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


def _process_google_sheet(sheets_service, file_info: dict) -> dict | None:
    """Fetch full Sheet content (no diffing)."""
    if not sheets_service:
        print(f"  Warning: Sheets service not available, skipping {file_info['name']}")
        return None
    resp = sheets_service.spreadsheets().values().get(
        spreadsheetId=file_info["id"],
        range="A:ZZ",
    ).execute()
    rows = resp.get("values", [])
    return {
        "name": file_info["name"],
        "content": "\n".join(["\t".join(row) for row in rows]),
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
