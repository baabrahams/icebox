from unittest.mock import MagicMock, patch
from sources.gdrive import fetch_recent_docs, _get_old_revision_text, _compute_diff


def _mock_drive_service(files_list_result, export_content=b"Document text content here", revisions=None):
    """Helper to create a mock Google Drive service."""
    service = MagicMock()
    files_mock = MagicMock()
    service.files.return_value = files_mock
    list_mock = MagicMock()
    files_mock.list.return_value = list_mock
    list_mock.execute.return_value = files_list_result

    # Mock export for Docs (current content)
    export_mock = MagicMock()
    files_mock.export.return_value = export_mock
    export_mock.execute.return_value = export_content

    # Mock revisions API
    revisions_mock = MagicMock()
    service.revisions.return_value = revisions_mock
    rev_list_mock = MagicMock()
    revisions_mock.list.return_value = rev_list_mock
    if revisions is not None:
        rev_list_mock.execute.return_value = {"revisions": revisions}
        rev_get_mock = MagicMock()
        revisions_mock.get.return_value = rev_get_mock
        rev_get_mock.execute.return_value = b"Old document content"
    else:
        # No revisions — simulates new doc
        rev_list_mock.execute.return_value = {"revisions": []}

    return service


def _mock_sheets_service(values):
    service = MagicMock()
    spreadsheets = MagicMock()
    service.spreadsheets.return_value = spreadsheets
    values_mock = MagicMock()
    spreadsheets.values.return_value = values_mock
    get_mock = MagicMock()
    values_mock.get.return_value = get_mock
    get_mock.execute.return_value = {"values": values}
    return service


def test_fetch_recent_docs_google_doc_with_diff():
    """Google Doc with an old revision should return a diff."""
    drive_service = _mock_drive_service(
        files_list_result={
            "files": [{
                "id": "doc123",
                "name": "Q1 Roadmap",
                "mimeType": "application/vnd.google-apps.document",
                "modifiedTime": "2026-02-10T12:00:00Z",
            }],
        },
        export_content=b"Line one\nLine two changed\nLine three",
        revisions=[
            {"id": "rev1", "modifiedTime": "2026-01-15T10:00:00Z"},
        ],
    )

    results = fetch_recent_docs(
        drive_service=drive_service,
        sheets_service=None,
        folder_ids=["folder_abc"],
        lookback_days=7,
    )

    assert len(results) == 1
    assert results[0]["name"] == "Q1 Roadmap"
    assert results[0]["content_type"] == "diff"
    assert "---" in results[0]["content"]  # unified diff header


def test_fetch_recent_docs_new_google_doc_full_content():
    """Google Doc with no old revision should return full content."""
    drive_service = _mock_drive_service(
        files_list_result={
            "files": [{
                "id": "doc123",
                "name": "New Doc",
                "mimeType": "application/vnd.google-apps.document",
                "modifiedTime": "2026-02-10T12:00:00Z",
            }],
        },
        export_content=b"Brand new document content",
        revisions=[],  # No revisions before cutoff
    )

    results = fetch_recent_docs(
        drive_service=drive_service,
        sheets_service=None,
        folder_ids=["folder_abc"],
        lookback_days=7,
    )

    assert len(results) == 1
    assert results[0]["name"] == "New Doc"
    assert results[0]["content_type"] == "full"
    assert results[0]["content"] == "Brand new document content"


def test_fetch_recent_docs_google_sheet():
    """Sheet with no snapshot should return full content (first run)."""
    drive_service = _mock_drive_service(
        files_list_result={
            "files": [{
                "id": "sheet456",
                "name": "Sprint Tracker",
                "mimeType": "application/vnd.google-apps.spreadsheet",
                "modifiedTime": "2026-02-09T08:00:00Z",
            }],
        },
    )
    # Mock appDataFolder calls — no snapshot exists
    original_list = drive_service.files().list
    def list_side_effect(**kwargs):
        mock = MagicMock()
        if "appDataFolder" in kwargs.get("spaces", ""):
            mock.execute.return_value = {"files": []}
        else:
            mock.execute.return_value = {
                "files": [{
                    "id": "sheet456",
                    "name": "Sprint Tracker",
                    "mimeType": "application/vnd.google-apps.spreadsheet",
                    "modifiedTime": "2026-02-09T08:00:00Z",
                }],
            }
        return mock
    drive_service.files().list.side_effect = list_side_effect

    # Mock create for saving new snapshot
    drive_service.files().create.return_value.execute.return_value = {"id": "new_snap"}

    sheets_service = _mock_sheets_service([
        ["Task", "Status"],
        ["Build API", "Done"],
        ["Write docs", "In Progress"],
    ])

    results = fetch_recent_docs(
        drive_service=drive_service,
        sheets_service=sheets_service,
        folder_ids=["folder_abc"],
        lookback_days=7,
    )

    assert len(results) == 1
    assert results[0]["name"] == "Sprint Tracker"
    assert results[0]["content_type"] == "full"
    assert "Build API" in results[0]["content"]


def test_fetch_recent_docs_empty_folder():
    drive_service = _mock_drive_service({"files": []})

    results = fetch_recent_docs(
        drive_service=drive_service,
        sheets_service=None,
        folder_ids=["folder_abc"],
        lookback_days=7,
    )

    assert results == []


def test_get_old_revision_text_finds_revision_before_cutoff():
    """Should find the most recent revision before the cutoff and export its text."""
    service = MagicMock()
    files_mock = MagicMock()
    service.files.return_value = files_mock

    # Mock revisions().list()
    revisions_mock = MagicMock()
    service.revisions.return_value = revisions_mock
    list_mock = MagicMock()
    revisions_mock.list.return_value = list_mock
    list_mock.execute.return_value = {
        "revisions": [
            {"id": "rev1", "modifiedTime": "2026-01-20T10:00:00Z"},
            {"id": "rev2", "modifiedTime": "2026-02-03T10:00:00Z"},
            {"id": "rev3", "modifiedTime": "2026-02-08T10:00:00Z"},
        ],
    }

    # Mock revisions().get() with media download
    get_mock = MagicMock()
    revisions_mock.get.return_value = get_mock
    get_mock.execute.return_value = b"Old document content"

    # Cutoff is Feb 4 — rev2 (Feb 3) is the most recent before cutoff
    result = _get_old_revision_text(service, "doc123", lookback_days=7)

    assert result == "Old document content"
    revisions_mock.get.assert_called_once_with(
        fileId="doc123", revisionId="rev2", alt="media",
    )


def test_get_old_revision_text_no_revision_before_cutoff():
    """If all revisions are within the lookback period, return None (doc is new)."""
    service = MagicMock()
    revisions_mock = MagicMock()
    service.revisions.return_value = revisions_mock
    list_mock = MagicMock()
    revisions_mock.list.return_value = list_mock
    list_mock.execute.return_value = {
        "revisions": [
            {"id": "rev1", "modifiedTime": "2026-02-08T10:00:00Z"},
            {"id": "rev2", "modifiedTime": "2026-02-10T10:00:00Z"},
        ],
    }

    result = _get_old_revision_text(service, "doc123", lookback_days=7)

    assert result is None


def test_get_old_revision_text_api_error_returns_none():
    """If the Revisions API fails, return None gracefully."""
    service = MagicMock()
    revisions_mock = MagicMock()
    service.revisions.return_value = revisions_mock
    list_mock = MagicMock()
    revisions_mock.list.return_value = list_mock
    list_mock.execute.side_effect = Exception("Revisions API error")

    result = _get_old_revision_text(service, "doc123", lookback_days=7)

    assert result is None


def test_compute_diff_returns_unified_diff():
    old_text = "Line one\nLine two\nLine three"
    new_text = "Line one\nLine two modified\nLine three\nLine four added"

    diff = _compute_diff(old_text, new_text)

    assert "-Line two" in diff
    assert "+Line two modified" in diff
    assert "+Line four added" in diff


def test_compute_diff_no_changes_returns_empty():
    text = "Line one\nLine two"
    diff = _compute_diff(text, text)

    assert diff == ""


def test_fetch_recent_docs_sheet_with_diff():
    """Sheet with an existing snapshot should return a row-level diff."""
    drive_service = _mock_drive_service(
        files_list_result={
            "files": [{
                "id": "sheet456",
                "name": "Sprint Tracker",
                "mimeType": "application/vnd.google-apps.spreadsheet",
                "modifiedTime": "2026-02-09T08:00:00Z",
            }],
        },
    )
    # Mock appDataFolder snapshot lookup — snapshot exists
    snapshot_data = {
        "sheet_id": "sheet456",
        "captured_at": "2026-02-02T12:00:00Z",
        "rows": [
            ["Task", "Status"],
            ["Build API", "In Progress"],
        ],
    }
    import json
    # Override the files().list() to return different results based on call
    original_list = drive_service.files().list
    def list_side_effect(**kwargs):
        mock = MagicMock()
        if "appDataFolder" in kwargs.get("spaces", ""):
            mock.execute.return_value = {"files": [{"id": "snap_123"}]}
        else:
            mock.execute.return_value = {
                "files": [{
                    "id": "sheet456",
                    "name": "Sprint Tracker",
                    "mimeType": "application/vnd.google-apps.spreadsheet",
                    "modifiedTime": "2026-02-09T08:00:00Z",
                }],
            }
        return mock
    drive_service.files().list.side_effect = list_side_effect

    # Mock get_media for snapshot download
    get_media_mock = MagicMock()
    drive_service.files().get_media.return_value = get_media_mock
    get_media_mock.execute.return_value = json.dumps(snapshot_data).encode("utf-8")

    # Mock create/update for saving snapshot
    drive_service.files().update.return_value.execute.return_value = {"id": "snap_123"}

    sheets_service = _mock_sheets_service([
        ["Task", "Status"],
        ["Build API", "Done"],
    ])

    results = fetch_recent_docs(
        drive_service=drive_service,
        sheets_service=sheets_service,
        folder_ids=["folder_abc"],
        lookback_days=7,
    )

    assert len(results) == 1
    assert results[0]["name"] == "Sprint Tracker"
    assert results[0]["content_type"] == "diff"
    assert '"Status" changed from "In Progress" to "Done"' in results[0]["content"]
