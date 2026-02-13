# tests/test_sheet_snapshots.py
import json
from unittest.mock import MagicMock, call
from sources.gdrive import _load_sheet_snapshot, _save_sheet_snapshot


def _mock_drive_for_snapshot(snapshot_data=None):
    """Helper to mock Drive API for appDataFolder operations."""
    service = MagicMock()
    files_mock = MagicMock()
    service.files.return_value = files_mock

    # Mock files().list() for searching snapshots
    list_mock = MagicMock()
    files_mock.list.return_value = list_mock

    if snapshot_data is not None:
        # Snapshot exists
        list_mock.execute.return_value = {
            "files": [{"id": "snap_file_123"}],
        }
        # Mock files().get() for downloading
        get_mock = MagicMock()
        files_mock.get_media.return_value = get_mock
        get_mock.execute.return_value = json.dumps(snapshot_data).encode("utf-8")
    else:
        # No snapshot
        list_mock.execute.return_value = {"files": []}

    # Mock files().create() and files().update() for saving
    create_mock = MagicMock()
    files_mock.create.return_value = create_mock
    create_mock.execute.return_value = {"id": "new_snap_123"}

    update_mock = MagicMock()
    files_mock.update.return_value = update_mock
    update_mock.execute.return_value = {"id": "snap_file_123"}

    return service


def test_load_snapshot_found():
    """Should return row data when a snapshot exists."""
    snapshot_data = {
        "sheet_id": "sheet456",
        "captured_at": "2026-02-04T12:00:00Z",
        "rows": [
            ["Task", "Status"],
            ["Build API", "Done"],
        ],
    }
    drive_service = _mock_drive_for_snapshot(snapshot_data)

    result = _load_sheet_snapshot(drive_service, "sheet456")

    assert result == [["Task", "Status"], ["Build API", "Done"]]
    drive_service.files().list.assert_called_once_with(
        spaces="appDataFolder",
        q="name = 'sheet_snapshot_sheet456.json'",
        fields="files(id)",
    )


def test_load_snapshot_not_found():
    """Should return None when no snapshot exists."""
    drive_service = _mock_drive_for_snapshot(None)

    result = _load_sheet_snapshot(drive_service, "sheet456")

    assert result is None


def test_load_snapshot_api_error_returns_none():
    """Should return None gracefully on API error."""
    service = MagicMock()
    service.files.return_value.list.return_value.execute.side_effect = Exception("API error")

    result = _load_sheet_snapshot(service, "sheet456")

    assert result is None


def test_save_snapshot_creates_new():
    """Should create a new snapshot file when none exists."""
    drive_service = _mock_drive_for_snapshot(None)
    rows = [["Task", "Status"], ["Build API", "Done"]]

    _save_sheet_snapshot(drive_service, "sheet456", rows)

    drive_service.files().create.assert_called_once()
    call_kwargs = drive_service.files().create.call_args[1]
    assert call_kwargs["body"]["name"] == "sheet_snapshot_sheet456.json"
    assert call_kwargs["body"]["parents"] == ["appDataFolder"]


def test_save_snapshot_updates_existing():
    """Should update existing snapshot file when one exists."""
    old_data = {"sheet_id": "sheet456", "captured_at": "old", "rows": []}
    drive_service = _mock_drive_for_snapshot(old_data)
    rows = [["Task", "Status"], ["Build API", "Done"]]

    _save_sheet_snapshot(drive_service, "sheet456", rows)

    drive_service.files().update.assert_called_once()
    call_kwargs = drive_service.files().update.call_args[1]
    assert call_kwargs["fileId"] == "snap_file_123"
