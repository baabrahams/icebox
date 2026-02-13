"""Google OAuth 2.0 authentication for Drive and Sheets access."""

import os

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/spreadsheets.readonly",
]

TOKEN_PATH = os.path.expanduser("~/.weekly-update/google_token.json")


def get_google_credentials(client_secret_path: str) -> Credentials:
    """Get Google OAuth credentials, prompting for browser auth if needed.

    Checks for a saved token at ~/.weekly-update/google_token.json.
    If no valid token exists, opens a browser for the user to sign in.
    Saves the token for future runs.
    """
    creds = None

    # Try to load existing token
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)

    # If token is expired but has a refresh token, refresh it
    if creds and not creds.valid:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            _save_token(creds)
        else:
            creds = None  # Can't refresh, need new auth

    # No valid credentials — run browser auth flow
    if not creds:
        flow = InstalledAppFlow.from_client_secrets_file(client_secret_path, SCOPES)
        creds = flow.run_local_server(port=0)
        _save_token(creds)

    return creds


def _save_token(creds: Credentials) -> None:
    """Save credentials to the token file."""
    token_dir = os.path.dirname(TOKEN_PATH)
    os.makedirs(token_dir, exist_ok=True)
    with open(TOKEN_PATH, "w") as f:
        f.write(creds.to_json())
