from unittest.mock import MagicMock, patch
from sources.gdrive import fetch_recent_docs


def _mock_drive_service(files_list_result):
    """Helper to create a mock Google Drive service."""
    service = MagicMock()
    files_mock = MagicMock()
    service.files.return_value = files_mock
    list_mock = MagicMock()
    files_mock.list.return_value = list_mock
    list_mock.execute.return_value = files_list_result

    # Mock export for Docs
    export_mock = MagicMock()
    files_mock.export.return_value = export_mock
    export_mock.execute.return_value = b"Document text content here"

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


def test_fetch_recent_docs_google_doc():
    drive_service = _mock_drive_service({
        "files": [{
            "id": "doc123",
            "name": "Q1 Roadmap",
            "mimeType": "application/vnd.google-apps.document",
            "modifiedTime": "2026-02-10T12:00:00Z",
        }],
    })

    results = fetch_recent_docs(
        drive_service=drive_service,
        sheets_service=None,
        folder_ids=["folder_abc"],
        lookback_days=7,
    )

    assert len(results) == 1
    assert results[0]["name"] == "Q1 Roadmap"
    assert results[0]["content"] == "Document text content here"


def test_fetch_recent_docs_google_sheet():
    drive_service = _mock_drive_service({
        "files": [{
            "id": "sheet456",
            "name": "Sprint Tracker",
            "mimeType": "application/vnd.google-apps.spreadsheet",
            "modifiedTime": "2026-02-09T08:00:00Z",
        }],
    })
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
