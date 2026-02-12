from unittest.mock import MagicMock, patch
from summarizer import build_prompt, generate_summary


def test_build_prompt_includes_slack_and_docs():
    slack_data = {
        "#engineering": [
            {"author": "Alice", "text": "Shipped v2.0", "timestamp": "1707500000"},
        ],
    }
    gdrive_data = [
        {"name": "Q1 Roadmap", "content": "Launch feature X by March", "modified_time": "2026-02-10T12:00:00Z"},
    ]

    prompt = build_prompt(
        slack_data=slack_data,
        gdrive_data=gdrive_data,
        template_path="prompt_template.txt",
        lookback_days=7,
    )

    assert "=== SLACK: #engineering ===" in prompt
    assert "Alice" in prompt
    assert "Shipped v2.0" in prompt
    assert '=== GOOGLE DOC: "Q1 Roadmap"' in prompt
    assert "Launch feature X by March" in prompt


def test_build_prompt_empty_sources():
    prompt = build_prompt(
        slack_data={},
        gdrive_data=[],
        template_path="prompt_template.txt",
        lookback_days=7,
    )

    assert "No Slack messages" in prompt or "sources" in prompt.lower()


def test_generate_summary_calls_claude():
    mock_client = MagicMock()
    mock_client.messages.create.return_value = MagicMock(
        content=[MagicMock(text="*Wins & Releases*\n- Shipped v2.0")]
    )

    result = generate_summary(mock_client, "the prompt text")

    mock_client.messages.create.assert_called_once()
    call_kwargs = mock_client.messages.create.call_args[1]
    assert call_kwargs["model"] == "claude-sonnet-4-5-20250929"
    assert result == "*Wins & Releases*\n- Shipped v2.0"
