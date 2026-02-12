"""Fetch Slack channel history."""

from datetime import datetime, timezone, timedelta


def fetch_channel_messages(client, channel_name: str, lookback_days: int = 7) -> list[dict]:
    """Fetch messages from a Slack channel for the past N days.

    Returns list of dicts with keys: author, text, timestamp.
    """
    clean_name = channel_name.lstrip("#")

    # Resolve channel name to ID
    channel_id = None
    cursor = ""
    while True:
        resp = client.conversations_list(cursor=cursor, limit=200)
        for ch in resp["channels"]:
            if ch["name"] == clean_name:
                channel_id = ch["id"]
                break
        if channel_id or not resp["response_metadata"].get("next_cursor"):
            break
        cursor = resp["response_metadata"]["next_cursor"]

    if not channel_id:
        print(f"  Warning: Channel {channel_name} not found, skipping.")
        return []

    oldest = datetime.now(timezone.utc) - timedelta(days=lookback_days)
    oldest_ts = str(oldest.timestamp())

    resp = client.conversations_history(channel=channel_id, oldest=oldest_ts, limit=1000)
    messages = resp.get("messages", [])

    # Resolve user IDs to names (cache to avoid repeat lookups)
    user_cache = {}
    results = []
    for msg in messages:
        if msg.get("subtype"):
            continue  # Skip bot messages, join/leave, etc.

        user_id = msg.get("user", "")
        if user_id not in user_cache:
            try:
                info = client.users_info(user=user_id)
                user_cache[user_id] = info["user"]["real_name"]
            except Exception:
                user_cache[user_id] = user_id

        results.append({
            "author": user_cache[user_id],
            "text": msg["text"],
            "timestamp": msg["ts"],
        })

    # Sort chronologically (oldest first)
    results.sort(key=lambda m: float(m["timestamp"]))
    return results
