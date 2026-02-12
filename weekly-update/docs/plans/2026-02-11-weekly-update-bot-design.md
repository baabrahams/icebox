# Weekly Update Bot — Design

## Overview

A local Python CLI script that synthesizes the past week's Slack messages and Google Docs/Sheets activity into a structured department weekly update. The draft is sent as a Slack DM for review before posting.

## Architecture

```
[Slack API] ──┐
              ├──▶ [Gather & Format] ──▶ [Claude API] ──▶ [Slack DM to you]
[Google Drive API] ┘
```

### Core Flow

1. Fetch the last 7 days of messages from configured Slack channels
2. Query Google Drive for recently modified Docs/Sheets in configured folders
3. Extract full text content from those docs
4. Bundle everything into a structured prompt for Claude
5. Claude generates the weekly update
6. Bot sends the draft to you as a Slack DM

### Project Structure

```
weekly-update/
├── config.yaml          # Channel list, folder IDs, Slack user ID
├── main.py              # CLI entrypoint
├── sources/
│   ├── slack.py         # Fetch channel history
│   └── gdrive.py        # Fetch recent docs/sheets content
├── summarizer.py        # Claude API prompt + call
├── delivery.py          # Send Slack DM
├── prompt_template.txt  # Editable prompt template
└── requirements.txt
```

## Data Sources

### Slack

- Fetch messages from a small set (2-5) of configured channels
- Uses `conversations.history` with a 7-day lookback
- Messages include author and timestamp for attribution

### Google Drive

- Query `files.list` scoped to configured folder IDs
- Filter by `modifiedTime` > 7 days ago
- Export Google Docs as plain text via Drive API `export` endpoint
- Read Google Sheets cell data via Sheets API
- Full document content is sent to Claude (no truncation)

## Output Format

Four-section structure, pithy bullets, ~10-15 lines total:

- **Wins & Releases** — ship celebrations, milestones hit
- **Key Decisions** — decisions made and their rationale
- **Next Week's Focus** — what's ahead
- **Risks & Blockers** — anything the audience should know about

## Authentication & Configuration

### Secrets (environment variables)

- `SLACK_BOT_TOKEN` — Slack app bot token
- `ANTHROPIC_API_KEY` — Claude API key
- `GOOGLE_SERVICE_ACCOUNT_KEY` — path to service account JSON

### Slack App Scopes

- `channels:history` — read channel messages
- `chat:write` — send DMs
- `im:write` — open DM conversations

### Google Cloud

- Service Account with read-only access
- APIs enabled: Drive, Docs, Sheets
- Target folders shared with the service account email

### Config File (`config.yaml`)

```yaml
slack:
  channels:
    - "#engineering"
    - "#product"
    - "#launches"
  my_user_id: "U12345678"

google:
  folder_ids:
    - "1aBcDeFgHiJkLmNoPqRsTuVwXyZ"

lookback_days: 7
```

## Claude Prompt

- Prompt template lives in `prompt_template.txt` for easy editing
- Raw sources are labeled by origin (channel name, doc title + modified date)
- Claude is instructed to produce the four-section format with short punchy bullets

## Error Handling

- No messages in a channel — skip it, note in terminal
- No recently modified Google Docs — skip Google section, generate from Slack only
- Doc too large for context window — warn in terminal with doc name/size, skip
- Auth failures — fail fast with clear error identifying which credential
- Rate limits — simple retries with backoff
- Claude API errors — retry once, then fail with error message

## Dependencies

```
slack-sdk
google-api-python-client
google-auth
anthropic
pyyaml
```

## Audience

Department team + a few cross-functional stakeholders.

## Future Considerations

- Move to a scheduled cloud function (Lambda/Cloud Function) for automation
- Add Google Docs revision diffing for more precise change detection
