from unittest.mock import MagicMock
from delivery import send_dm


def test_send_dm_opens_conversation_and_posts():
    mock_client = MagicMock()
    mock_client.conversations_open.return_value = {"channel": {"id": "D999"}}
    mock_client.chat_postMessage.return_value = {"ok": True}

    send_dm(mock_client, user_id="U12345678", message="*Wins & Releases*\n- Shipped v2.0")

    mock_client.conversations_open.assert_called_once_with(users=["U12345678"])
    mock_client.chat_postMessage.assert_called_once_with(
        channel="D999",
        text="*Wins & Releases*\n- Shipped v2.0",
    )
