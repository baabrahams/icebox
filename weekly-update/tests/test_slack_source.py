from unittest.mock import MagicMock, patch
from datetime import datetime, timezone, timedelta
from sources.slack import fetch_channel_messages


def test_fetch_channel_messages_returns_formatted_messages():
    mock_client = MagicMock()

    # Mock conversations_list to resolve channel name to ID
    mock_client.conversations_list.return_value = {
        "channels": [{"name": "engineering", "id": "C123"}],
        "response_metadata": {"next_cursor": ""},
    }

    # Mock conversations_history
    mock_client.conversations_history.return_value = {
        "messages": [
            {
                "user": "U111",
                "text": "Shipped the new dashboard",
                "ts": "1707500000.000000",
            },
            {
                "user": "U222",
                "text": "Decided to use Postgres",
                "ts": "1707500100.000000",
            },
        ],
        "has_more": False,
    }

    # Mock users_info for name resolution
    def mock_users_info(user):
        names = {"U111": "Alice", "U222": "Bob"}
        return {"user": {"real_name": names.get(user, "Unknown")}}

    mock_client.users_info.side_effect = mock_users_info

    result = fetch_channel_messages(mock_client, "#engineering", lookback_days=7)

    assert len(result) == 2
    assert result[0]["author"] == "Alice"
    assert result[0]["text"] == "Shipped the new dashboard"
    assert result[1]["author"] == "Bob"


def test_fetch_channel_messages_empty_channel():
    mock_client = MagicMock()
    mock_client.conversations_list.return_value = {
        "channels": [{"name": "engineering", "id": "C123"}],
        "response_metadata": {"next_cursor": ""},
    }
    mock_client.conversations_history.return_value = {
        "messages": [],
        "has_more": False,
    }

    result = fetch_channel_messages(mock_client, "#engineering", lookback_days=7)
    assert result == []
