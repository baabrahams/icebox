# tests/test_google_auth.py
import os
import json
import tempfile
from unittest.mock import MagicMock, patch, mock_open
from google_auth import get_google_credentials, SCOPES

TOKEN_DIR = os.path.expanduser("~/.weekly-update")


@patch("google_auth.InstalledAppFlow")
@patch("google_auth.os.makedirs")
@patch("google_auth.os.path.exists")
def test_first_run_triggers_browser_auth(mock_exists, mock_makedirs, mock_flow_class):
    """First run with no saved token should trigger browser auth flow."""
    mock_exists.return_value = False  # No token file exists

    mock_flow = MagicMock()
    mock_flow_class.from_client_secrets_file.return_value = mock_flow
    mock_creds = MagicMock()
    mock_creds.valid = True
    mock_flow.run_local_server.return_value = mock_creds

    with patch("builtins.open", mock_open()):
        result = get_google_credentials("client_secret.json")

    mock_flow_class.from_client_secrets_file.assert_called_once_with(
        "client_secret.json", SCOPES
    )
    mock_flow.run_local_server.assert_called_once_with(port=0)
    assert result == mock_creds


@patch("google_auth.Credentials")
@patch("google_auth.os.path.exists")
def test_existing_valid_token_is_reused(mock_exists, mock_creds_class):
    """If a valid token exists, it should be loaded without browser auth."""
    mock_exists.return_value = True  # Token file exists

    mock_creds = MagicMock()
    mock_creds.valid = True
    mock_creds_class.from_authorized_user_file.return_value = mock_creds

    result = get_google_credentials("client_secret.json")

    mock_creds_class.from_authorized_user_file.assert_called_once()
    assert result == mock_creds


@patch("google_auth.Request")
@patch("google_auth.Credentials")
@patch("google_auth.os.path.exists")
def test_expired_token_is_refreshed(mock_exists, mock_creds_class, mock_request_class):
    """If token exists but is expired, it should be refreshed."""
    mock_exists.return_value = True

    mock_creds = MagicMock()
    mock_creds.valid = False
    mock_creds.expired = True
    mock_creds.refresh_token = "some_refresh_token"
    mock_creds_class.from_authorized_user_file.return_value = mock_creds

    with patch("builtins.open", mock_open()):
        result = get_google_credentials("client_secret.json")

    mock_creds.refresh.assert_called_once_with(mock_request_class())
    assert result == mock_creds


@patch("google_auth.InstalledAppFlow")
@patch("google_auth.Credentials")
@patch("google_auth.os.makedirs")
@patch("google_auth.os.path.exists")
def test_expired_token_no_refresh_triggers_browser(mock_exists, mock_makedirs, mock_creds_class, mock_flow_class):
    """If token exists but can't be refreshed, trigger browser auth."""
    mock_exists.return_value = True

    mock_old_creds = MagicMock()
    mock_old_creds.valid = False
    mock_old_creds.expired = True
    mock_old_creds.refresh_token = None  # Can't refresh
    mock_creds_class.from_authorized_user_file.return_value = mock_old_creds

    mock_flow = MagicMock()
    mock_flow_class.from_client_secrets_file.return_value = mock_flow
    mock_new_creds = MagicMock()
    mock_new_creds.valid = True
    mock_flow.run_local_server.return_value = mock_new_creds

    with patch("builtins.open", mock_open()):
        result = get_google_credentials("client_secret.json")

    mock_flow.run_local_server.assert_called_once()
    assert result == mock_new_creds


def test_scopes_include_appdata():
    """SCOPES must include drive.appdata for snapshot storage."""
    assert "https://www.googleapis.com/auth/drive.appdata" in SCOPES
