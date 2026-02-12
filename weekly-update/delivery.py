"""Send weekly update draft via Slack DM."""


def send_dm(client, user_id: str, message: str) -> None:
    """Open a DM with the user and send the weekly update draft."""
    resp = client.conversations_open(users=[user_id])
    dm_channel = resp["channel"]["id"]
    client.chat_postMessage(channel=dm_channel, text=message)
