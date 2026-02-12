"""Fetch recently modified Google Drive docs."""

from datetime import datetime, timezone, timedelta


def fetch_recent_docs(
    drive_service,
    sheets_service,
    folder_ids: list[str],
    lookback_days: int = 7,
) -> list[dict]:
    """Fetch recently modified Google Docs and Sheets from specified folders.

    Returns list of dicts with keys: name, content, modified_time, mime_type.
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
            content = _extract_content(drive_service, sheets_service, f)
            if content is not None:
                all_docs.append({
                    "name": f["name"],
                    "content": content,
                    "modified_time": f["modifiedTime"],
                    "mime_type": f["mimeType"],
                })

    return all_docs


def _extract_content(drive_service, sheets_service, file_info: dict) -> str | None:
    """Extract text content from a Google Doc or Sheet."""
    file_id = file_info["id"]
    mime = file_info["mimeType"]

    if mime == "application/vnd.google-apps.document":
        content_bytes = drive_service.files().export(
            fileId=file_id,
            mimeType="text/plain",
        ).execute()
        if isinstance(content_bytes, bytes):
            return content_bytes.decode("utf-8")
        return str(content_bytes)

    elif mime == "application/vnd.google-apps.spreadsheet":
        if not sheets_service:
            print(f"  Warning: Sheets service not available, skipping {file_info['name']}")
            return None
        resp = sheets_service.spreadsheets().values().get(
            spreadsheetId=file_id,
            range="A:ZZ",
        ).execute()
        rows = resp.get("values", [])
        return "\n".join(["\t".join(row) for row in rows])

    return None
