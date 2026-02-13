"""Generate weekly update via Claude API using two-pass extract-then-summarize."""

import os
from datetime import datetime

EXTRACTION_TEMPLATE = os.path.join(os.path.dirname(__file__), "extraction_prompt.txt")
SUMMARY_TEMPLATE = os.path.join(os.path.dirname(__file__), "prompt_template.txt")


def _format_sources(
    slack_data: dict[str, list[dict]],
    gdrive_data: list[dict],
    lookback_days: int,
) -> str:
    """Format raw Slack and Google Drive data into labeled source text."""
    sources_parts = []

    for channel, messages in slack_data.items():
        if not messages:
            continue
        lines = [f"=== SLACK: {channel} ==="]
        for msg in messages:
            ts = datetime.fromtimestamp(float(msg["timestamp"])).strftime("%Y-%m-%d %H:%M")
            lines.append(f"[{ts}] {msg['author']}: {msg['text']}")
            for reply in msg.get("replies", []):
                rts = datetime.fromtimestamp(float(reply["timestamp"])).strftime("%Y-%m-%d %H:%M")
                lines.append(f"  ↳ [{rts}] {reply['author']}: {reply['text']}")
        sources_parts.append("\n".join(lines))

    for doc in gdrive_data:
        if doc.get("content_type") == "diff":
            if doc.get("mime_type") == "application/vnd.google-apps.spreadsheet":
                header = f'=== GOOGLE SHEET: "{doc["name"]}" (changes since last run) ==='
            else:
                header = f'=== GOOGLE DOC: "{doc["name"]}" (changes from last {lookback_days} days) ==='
        else:
            if doc.get("mime_type") == "application/vnd.google-apps.spreadsheet":
                header = f'=== GOOGLE SHEET: "{doc["name"]}" (modified {doc["modified_time"][:10]}) ==='
            else:
                header = f'=== GOOGLE DOC: "{doc["name"]}" (modified {doc["modified_time"][:10]}) ==='
        sources_parts.append(f"{header}\n{doc['content']}")

    if not sources_parts:
        return "(No Slack messages or Google Docs found for this period.)"
    return "\n\n".join(sources_parts)


def build_extraction_prompt(
    slack_data: dict[str, list[dict]],
    gdrive_data: list[dict],
    lookback_days: int,
) -> str:
    """Build the extraction prompt from raw sources."""
    with open(EXTRACTION_TEMPLATE) as f:
        template = f.read()

    sources_text = _format_sources(slack_data, gdrive_data, lookback_days)
    return template.replace("{lookback_days}", str(lookback_days)).replace("{sources}", sources_text)


def build_summary_prompt(extracted_items: str) -> str:
    """Build the summary prompt from extracted items."""
    with open(SUMMARY_TEMPLATE) as f:
        template = f.read()

    return template.replace("{extracted_items}", extracted_items)


def extract_items(
    client,
    slack_data: dict[str, list[dict]],
    gdrive_data: list[dict],
    lookback_days: int,
) -> str:
    """Pass 1: Extract and rank all notable items from raw sources."""
    prompt = build_extraction_prompt(slack_data, gdrive_data, lookback_days)
    response = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=2048,
        temperature=0,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


def generate_summary(client, extracted_items: str) -> str:
    """Pass 2: Generate the weekly update from extracted items."""
    prompt = build_summary_prompt(extracted_items)
    response = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text
