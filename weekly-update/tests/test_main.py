from unittest.mock import MagicMock, patch
from main import run


@patch("main.send_dm")
@patch("main.generate_summary")
@patch("main.build_prompt")
@patch("main.fetch_recent_docs")
@patch("main.fetch_channel_messages")
def test_run_wires_everything_together(
    mock_fetch_slack, mock_fetch_docs, mock_build_prompt, mock_generate, mock_send_dm
):
    config = {
        "slack": {
            "channels": ["#engineering"],
            "my_user_id": "U12345678",
        },
        "google": {
            "folder_ids": ["folder_abc"],
        },
        "lookback_days": 7,
    }

    mock_fetch_slack.return_value = [
        {"author": "Alice", "text": "Shipped v2", "timestamp": "1707500000"},
    ]
    mock_fetch_docs.return_value = [
        {"name": "Roadmap", "content": "stuff", "modified_time": "2026-02-10", "mime_type": "doc"},
    ]
    mock_build_prompt.return_value = "the prompt"
    mock_generate.return_value = "*Wins*\n- Shipped v2"

    run(
        config=config,
        slack_client=MagicMock(),
        drive_service=MagicMock(),
        sheets_service=MagicMock(),
        anthropic_client=MagicMock(),
    )

    mock_fetch_slack.assert_called_once()
    mock_fetch_docs.assert_called_once()
    mock_build_prompt.assert_called_once()
    mock_generate.assert_called_once()
    mock_send_dm.assert_called_once_with(
        mock_send_dm.call_args[0][0],  # client
        user_id="U12345678",
        message="*Wins*\n- Shipped v2",
    )
