from unittest.mock import MagicMock
from summarizer import build_extraction_prompt, build_summary_prompt, extract_items, generate_summary


def test_build_extraction_prompt_includes_slack_and_docs():
    slack_data = {
        "#engineering": [
            {"author": "Alice", "text": "Shipped v2.0", "timestamp": "1707500000"},
        ],
    }
    gdrive_data = [
        {
            "name": "Q1 Roadmap",
            "content": "Launch feature X by March",
            "modified_time": "2026-02-10T12:00:00Z",
            "content_type": "full",
        },
    ]

    prompt = build_extraction_prompt(
        slack_data=slack_data,
        gdrive_data=gdrive_data,
        lookback_days=7,
    )

    assert "=== SLACK: #engineering ===" in prompt
    assert "Alice" in prompt
    assert "Shipped v2.0" in prompt
    assert '=== GOOGLE DOC: "Q1 Roadmap"' in prompt
    assert "Launch feature X by March" in prompt
    assert "CATEGORY:RANK" in prompt  # extraction instructions present


def test_build_extraction_prompt_labels_diff_content():
    gdrive_data = [
        {
            "name": "Q1 Roadmap",
            "content": "--- 7 days ago\n+++ current\n@@ -1,2 +1,2 @@\n-old line\n+new line",
            "modified_time": "2026-02-10T12:00:00Z",
            "content_type": "diff",
        },
    ]

    prompt = build_extraction_prompt(
        slack_data={},
        gdrive_data=gdrive_data,
        lookback_days=7,
    )

    assert "changes from last 7 days" in prompt
    assert "+new line" in prompt


def test_build_extraction_prompt_labels_full_content():
    gdrive_data = [
        {
            "name": "New Doc",
            "content": "Full document text here",
            "modified_time": "2026-02-10T12:00:00Z",
            "content_type": "full",
        },
    ]

    prompt = build_extraction_prompt(
        slack_data={},
        gdrive_data=gdrive_data,
        lookback_days=7,
    )

    assert "modified 2026-02-10" in prompt
    assert "Full document text here" in prompt


def test_build_extraction_prompt_empty_sources():
    prompt = build_extraction_prompt(
        slack_data={},
        gdrive_data=[],
        lookback_days=7,
    )

    assert "No Slack messages" in prompt or "sources" in prompt.lower()


def test_build_extraction_prompt_labels_sheet_diff():
    gdrive_data = [
        {
            "name": "Sprint Tracker",
            "content": 'Row 2: "Status" changed from "In Progress" to "Done"',
            "modified_time": "2026-02-10T12:00:00Z",
            "content_type": "diff",
            "mime_type": "application/vnd.google-apps.spreadsheet",
        },
    ]

    prompt = build_extraction_prompt(
        slack_data={},
        gdrive_data=gdrive_data,
        lookback_days=7,
    )

    assert 'GOOGLE SHEET: "Sprint Tracker"' in prompt
    assert "changes since last run" in prompt
    assert "changed from" in prompt


def test_build_extraction_prompt_includes_doc_url_in_header():
    """Source headers should include the doc URL when present."""
    gdrive_data = [
        {
            "name": "Q1 Roadmap",
            "content": "Launch feature X by March",
            "modified_time": "2026-02-10T12:00:00Z",
            "content_type": "full",
            "url": "https://docs.google.com/document/d/abc123",
        },
    ]

    prompt = build_extraction_prompt(
        slack_data={},
        gdrive_data=gdrive_data,
        lookback_days=7,
    )

    assert "https://docs.google.com/document/d/abc123" in prompt


def test_build_extraction_prompt_includes_sheet_url_in_header():
    """Sheet source headers should include the sheet URL when present."""
    gdrive_data = [
        {
            "name": "Sprint Tracker",
            "content": 'Row 2: "Status" changed from "In Progress" to "Done"',
            "modified_time": "2026-02-10T12:00:00Z",
            "content_type": "diff",
            "mime_type": "application/vnd.google-apps.spreadsheet",
            "url": "https://docs.google.com/spreadsheets/d/sheet456",
        },
    ]

    prompt = build_extraction_prompt(
        slack_data={},
        gdrive_data=gdrive_data,
        lookback_days=7,
    )

    assert "https://docs.google.com/spreadsheets/d/sheet456" in prompt


def test_build_extraction_prompt_no_url_field_still_works():
    """Docs without a url field should still format correctly (backwards compat)."""
    gdrive_data = [
        {
            "name": "Old Doc",
            "content": "Some content",
            "modified_time": "2026-02-10T12:00:00Z",
            "content_type": "full",
        },
    ]

    prompt = build_extraction_prompt(
        slack_data={},
        gdrive_data=gdrive_data,
        lookback_days=7,
    )

    assert '=== GOOGLE DOC: "Old Doc"' in prompt
    assert "Some content" in prompt


def test_build_summary_prompt_includes_extracted_items():
    extracted = "- [WIN:MAJOR] Shipped v2.0\n- [RISK:MINOR] CI flaky"

    prompt = build_summary_prompt(extracted)

    assert "Shipped v2.0" in prompt
    assert "CI flaky" in prompt
    assert "EVERY item tagged MAJOR" in prompt  # prioritization rules present
    assert "*Wins & Releases*" in prompt  # section headers present


def test_extract_items_calls_claude_with_temperature_zero():
    mock_client = MagicMock()
    mock_client.messages.create.return_value = MagicMock(
        content=[MagicMock(text="- [WIN:MAJOR] Shipped v2.0")]
    )

    result = extract_items(
        client=mock_client,
        slack_data={"#eng": [{"author": "A", "text": "hi", "timestamp": "1707500000"}]},
        gdrive_data=[],
        lookback_days=7,
    )

    call_kwargs = mock_client.messages.create.call_args[1]
    assert call_kwargs["temperature"] == 0
    assert call_kwargs["model"] == "claude-sonnet-4-5-20250929"
    assert result == "- [WIN:MAJOR] Shipped v2.0"


def test_generate_summary_calls_claude():
    mock_client = MagicMock()
    mock_client.messages.create.return_value = MagicMock(
        content=[MagicMock(text="*Wins & Releases*\n- Shipped v2.0")]
    )

    result = generate_summary(mock_client, "- [WIN:MAJOR] Shipped v2.0")

    mock_client.messages.create.assert_called_once()
    call_kwargs = mock_client.messages.create.call_args[1]
    assert call_kwargs["model"] == "claude-sonnet-4-5-20250929"
    assert result == "*Wins & Releases*\n- Shipped v2.0"
