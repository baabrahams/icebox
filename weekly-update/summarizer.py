"""Generate weekly update via Claude API."""

from datetime import datetime


def build_prompt(
    slack_data: dict[str, list[dict]],
    gdrive_data: list[dict],
    template_path: str,
    lookback_days: int,
) -> str:
    """Build the full prompt from Slack messages and Google Drive docs."""
    with open(template_path) as f:
        template = f.read()

    sources_parts = []

    # Add Slack data
    for channel, messages in slack_data.items():
        if not messages:
            continue
        lines = [f"=== SLACK: {channel} ==="]
        for msg in messages:
            ts = datetime.fromtimestamp(float(msg["timestamp"])).strftime("%Y-%m-%d %H:%M")
            lines.append(f"[{ts}] {msg['author']}: {msg['text']}")
        sources_parts.append("\n".join(lines))

    # Add Google Drive data
    for doc in gdrive_data:
        header = f'=== GOOGLE DOC: "{doc["name"]}" (modified {doc["modified_time"][:10]}) ==='
        sources_parts.append(f"{header}\n{doc['content']}")

    if not sources_parts:
        sources_text = "(No Slack messages or Google Docs found for this period.)"
    else:
        sources_text = "\n\n".join(sources_parts)

    return template.replace("{lookback_days}", str(lookback_days)).replace("{sources}", sources_text)


def generate_summary(client, prompt: str) -> str:
    """Call Claude API to generate the weekly update."""
    response = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text
