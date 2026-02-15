# Icebox - SMS Dinner Assistant

## Overview

Icebox is an SMS/MMS-based dinner assistant that manages a user's pantry inventory and helps them decide what to cook each night. All interaction happens over text through a single Twilio phone number. Users send photos of their fridge and pantry, the system identifies what they have, and each evening it interviews them to figure out what to make for dinner.

## Tech Stack

- **Backend:** Node.js / TypeScript (Express)
- **AI:** Claude API (vision + conversation)
- **SMS:** Twilio (inbound/outbound SMS/MMS)
- **Database:** PostgreSQL
- **Deployment:** Railway (with built-in Postgres addon and cron jobs)

## Data Model

### users

| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| phone_number | string | Unique, indexed. Primary user identifier. |
| household_size | integer | |
| interview_time | time | Default '17:00' |
| timezone | string | Default 'America/New_York' |
| onboarding_complete | boolean | |
| created_at | timestamp | |
| updated_at | timestamp | |

### dietary_restrictions

| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| user_id | uuid | FK → users |
| type | enum | allergy, dislike, diet |
| value | string | e.g. "peanuts", "vegan", "no cilantro" |
| source | enum | onboarding, learned |

### pantry_items

| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| user_id | uuid | FK → users |
| name | string | e.g. "chicken breast", "soy sauce" |
| category | string | e.g. "protein", "condiment", "produce" |
| added_at | timestamp | |
| last_confirmed_at | timestamp | |

### conversation_history

| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| user_id | uuid | FK → users |
| role | enum | user, assistant |
| content | text | |
| media_url | string | Nullable. For MMS photos. |
| created_at | timestamp | |

### dinner_logs

| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| user_id | uuid | FK → users |
| date | date | |
| recipe_name | string | |
| recipe_source | string | e.g. "Serious Eats", "NYT Cooking" |
| status | enum | suggested, made, skipped |
| user_rating | integer | Nullable. For learning preferences. |
| items_used | text[] | For pantry deduction. |

## Conversation Flows

### Onboarding (first text from a new number)

1. User texts anything to the Twilio number.
2. Bot: "Hey! I'm Icebox - I help you figure out what to make for dinner. A few quick questions to get started."
3. Bot asks how many people they usually cook for. User responds. Bot confirms: "Got it, cooking for 4."
4. Bot asks about food allergies or things they absolutely won't eat. User responds. Bot confirms: "Great, I'll record that you're allergic to peanuts and don't like cilantro."
5. Bot asks what time they usually start thinking about dinner, with a 5pm default. User responds or skips. Bot confirms the time.
6. Bot: "You're all set! Send me a photo of your fridge or pantry anytime and I'll keep track of what you have. Or just text me a list of items."

All responses are echoed back for confirmation before being stored.

### Photo Intake (user sends MMS)

1. User sends a photo of their fridge, pantry, spice rack, etc.
2. Server downloads the image from Twilio's MediaUrl.
3. Image sent to Claude vision along with the user's current pantry list.
4. Bot responds with what it sees: "Here's what I see: chicken thighs, butter, cheddar cheese, milk, sriracha, leftover rice, spinach, eggs. Anything wrong or missing?"
5. User corrects: "that's not cheddar, it's gruyere. Also there's yogurt behind the milk"
6. Bot confirms: "Got it - swapped cheddar for gruyere and added yogurt."
7. Pantry updated with smart merge logic (see Photo Processing below).

Multiple photos can be sent in sequence. Each one adds/confirms items incrementally.

### Manual Entry

User texts naturally - no special syntax required:
- "add chicken, rice, broccoli" → Bot: "Added chicken, rice, and broccoli to your pantry."
- "remove eggs" or "I used the chicken" → Bot: "Got it, removed eggs from your pantry."
- "I bought salmon and lemons" → Bot: "Added salmon and lemons to your pantry."

Claude interprets the intent from natural language.

### Nightly Dinner Interview

This flow is triggered both by the nightly cron and by ad-hoc requests (e.g. user texts "what should I make tonight?").

**Step 1 - Resolve last recommendation (if one exists with status=suggested):**

- Bot: "Hey! Did you end up making that tomato butter pasta last night?"
- **If yes:** Bot: "Nice! How was it?" Then: "Should I remove anything you used up? Like the canned tomatoes or butter?" User responds, bot confirms changes.
- **If no:** Bot: "No worries! Have you added or removed anything from your kitchen since we last talked?" User responds, bot confirms changes.

**Step 2 - Tonight's suggestion:**

- Bot: "So, what are you feeling for tonight?"
- User might say: "something quick", "Italian", "I want to use up that spinach", "no idea", "only what I have at home"
- Bot suggests a meal from quality sources (NYT Cooking, Serious Eats, well-regarded blogs, etc.) using Claude's knowledge. References recipe name and source but does not generate URLs.
- If user says "only what I have" → suggestions strictly constrained to current pantry items. Otherwise, bot prioritizes pantry items but may suggest picking up 1-2 things.
- Conversation continues until user confirms or bails.
- Once confirmed, logged to dinner_logs with status=suggested. Bot: "Enjoy! Let me know how it turned out later if you want."

### Pantry Query

User texts "what's in my pantry?" or "what do I have?" and the bot responds with a categorized list.

### Ad-hoc Queries

User can text anytime with questions or requests. Claude handles intent detection naturally from the message content.

## Photo Processing Pipeline

### Inbound MMS Handling

1. Twilio webhook includes `MediaUrl0`, `MediaContentType0`, etc.
2. Server downloads the image from Twilio's temporary URL.
3. Image sent to Claude vision with:
   - The user's current pantry list (for diffing)
   - Instructions to identify all visible food items by common name
   - Instructions to categorize items (produce, protein, dairy, condiment, grain, etc.)

### Smart Merge Logic

- Items Claude sees that aren't in the pantry → added as new
- Items Claude sees that are already in the pantry → `last_confirmed_at` updated
- Items in the pantry that Claude doesn't see → **not automatically removed** (food could be on a different shelf, in a cabinet, etc.)
- Removals happen explicitly: user says "remove X" or confirms used items during the nightly interview check-in

## Technical Architecture

### Server (Express on Railway)

- Single Twilio webhook endpoint: `POST /sms`
- Twilio request signature verification on all inbound requests
- Stateless: all state pulled from DB on each inbound message, no in-memory state
- On each inbound message:
  1. Look up user by `From` phone number (or create if new → onboarding)
  2. Load context: pantry items, dietary restrictions, recent conversation, last open dinner_log
  3. If MMS, download image from Twilio MediaUrl
  4. Build Claude API call with full context + message (+ image if present)
  5. Parse Claude's response for structured actions (add/remove pantry items, log dinner, update preferences) and natural language reply
  6. Execute actions against the database
  7. Send reply via Twilio

### Claude Context (per call)

Every Claude API call includes:

1. **System prompt** - Personality, behavioral rules (always confirm inputs, echo back, check-in flow)
2. **User profile** - Household size, timezone, dietary restrictions, learned preferences
3. **Pantry** - Current item list with categories
4. **Dinner history** - Last 14 days of suggestions, what was actually made, ratings. Instructs Claude to avoid repeating recent suggestions.
5. **Conversation window** - Last 20 messages for conversational continuity

The taste profile comes from structured DB data (restrictions, dinner_logs, ratings), not from the conversation window. The conversation window is only for short-term conversational flow.

### Recipe Sourcing

Claude's training data includes extensive knowledge of recipes from quality sources: NYT Cooking, Serious Eats, Bon Appetit, Food52, Smitten Kitchen, and more. The system leverages this knowledge directly. Claude references recipe names and sources in suggestions but does not generate URLs (to avoid hallucinated links).

### Cron Job (Railway Cron)

- Runs every minute
- Queries for users whose `interview_time` matches the current time in their timezone
- Sends outbound SMS via Twilio to start the nightly interview
- Opening message generated by Claude with the user's full context (including any unresolved recommendation)

## Error Handling

### Twilio Failures
- Outbound SMS failure: log error, retry once. Don't retry nightly interviews - skip that night.
- Image download failure: reply "I couldn't load that photo - mind sending it again?"

### Claude API Failures
- Timeout or downtime: reply "Sorry, my brain is foggy right now - try again in a few minutes."
- Timeout limits: 30s for text calls, 45s for vision calls.

### Photo Edge Cases
- Non-food photo: Claude responds naturally ("That looks like a nice cat but I can't find any food items!")
- Blurry/dark photos: Claude notes low confidence, asks user to confirm more carefully
- Multiple images in one MMS: process each, combine results into one confirmation message

### Rate Limiting
- Per-number rate limit: 30 messages per hour to prevent abuse
- Claude API vision calls are the main cost driver - one photo = one vision call

### Timezone Handling
- Stored per user, asked during onboarding
- Can infer from area code as a starting default
- All cron comparisons done in the user's local timezone
