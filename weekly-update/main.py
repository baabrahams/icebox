"""Weekly update bot CLI entrypoint."""

import os
import sys

from config import load_config
from sources.slack import fetch_channel_messages
from sources.gdrive import fetch_recent_docs
from summarizer import build_prompt, generate_summary
from delivery import send_dm


def run(config, slack_client, drive_service, sheets_service, anthropic_client):
    """Run the weekly update pipeline."""
    lookback = config["lookback_days"]

    # 1. Fetch Slack messages
    print("Fetching Slack messages...")
    slack_data = {}
    for channel in config["slack"]["channels"]:
        print(f"  {channel}")
        messages = fetch_channel_messages(slack_client, channel, lookback_days=lookback)
        if messages:
            slack_data[channel] = messages
        else:
            print(f"    No messages found, skipping.")

    # 2. Fetch Google Drive docs
    print("Fetching Google Drive docs...")
    gdrive_data = fetch_recent_docs(
        drive_service=drive_service,
        sheets_service=sheets_service,
        folder_ids=config["google"]["folder_ids"],
        lookback_days=lookback,
    )
    for doc in gdrive_data:
        print(f"  Found: {doc['name']} (modified {doc['modified_time'][:10]})")
    if not gdrive_data:
        print("  No recently modified docs found.")

    # 3. Build prompt and generate summary
    print("Generating weekly update with Claude...")
    prompt = build_prompt(
        slack_data=slack_data,
        gdrive_data=gdrive_data,
        template_path="prompt_template.txt",
        lookback_days=lookback,
    )
    summary = generate_summary(anthropic_client, prompt)

    # 4. Send DM
    print("Sending draft to Slack DM...")
    send_dm(slack_client, user_id=config["slack"]["my_user_id"], message=summary)
    print("Done! Check your Slack DMs for the weekly update draft.")


def main():
    """CLI entrypoint — initialize clients and run."""
    config = load_config()

    # Initialize Slack client
    from slack_sdk import WebClient
    slack_token = os.environ.get("SLACK_BOT_TOKEN")
    if not slack_token:
        print("Error: SLACK_BOT_TOKEN environment variable not set.")
        sys.exit(1)
    slack_client = WebClient(token=slack_token)

    # Initialize Google services
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    sa_key_path = os.environ.get("GOOGLE_SERVICE_ACCOUNT_KEY")
    if not sa_key_path:
        print("Error: GOOGLE_SERVICE_ACCOUNT_KEY environment variable not set.")
        sys.exit(1)
    creds = service_account.Credentials.from_service_account_file(
        sa_key_path,
        scopes=[
            "https://www.googleapis.com/auth/drive.readonly",
            "https://www.googleapis.com/auth/spreadsheets.readonly",
        ],
    )
    drive_service = build("drive", "v3", credentials=creds)
    sheets_service = build("sheets", "v4", credentials=creds)

    # Initialize Anthropic client
    import anthropic
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("Error: ANTHROPIC_API_KEY environment variable not set.")
        sys.exit(1)
    anthropic_client = anthropic.Anthropic(api_key=api_key)

    run(config, slack_client, drive_service, sheets_service, anthropic_client)


if __name__ == "__main__":
    main()
