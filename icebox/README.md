# Icebox

SMS-based dinner assistant that helps you figure out what to cook. Text it a photo of your fridge, and it suggests recipes based on what you have.

## How It Works

1. **Onboarding** — Text the number and answer 5 quick questions: household size, allergies, cooking time budget, recipe subscriptions, and preferred dinner time.

2. **Pantry photos** — Send a photo of your fridge or pantry anytime. Icebox uses Claude's vision API to identify items and track your inventory.

3. **Nightly interview** — At your preferred time each evening, Icebox texts you to ask what you're in the mood for and suggests a recipe based on your pantry, dietary restrictions, time budget, and recent meals.

4. **Learning** — Icebox tracks what you make, what you skip, and how you rate recipes to improve suggestions over time.

## Tech Stack

- **Runtime:** Node.js 22, TypeScript, Express 5
- **AI:** Claude API (Sonnet 4.5) for conversation and vision
- **SMS:** Twilio
- **Database:** PostgreSQL
- **Hosting:** Railway

## Project Structure

```
src/
├── index.ts              # Express server
├── claude.ts             # Claude API calls + action parsing
├── prompts.ts            # System prompt builder
├── context.ts            # User context loader
├── actions.ts            # Database action executor
├── routes/
│   ├── sms.ts            # Twilio SMS/MMS webhook
│   └── cron.ts           # Nightly interview trigger
└── db/
    ├── connection.ts     # PostgreSQL pool
    ├── migrate.ts        # Migration runner
    ├── users.ts          # User CRUD
    ├── pantry.ts         # Pantry items
    ├── dietary.ts        # Dietary restrictions
    ├── recipe-sources.ts # Recipe source preferences
    ├── dinner-logs.ts    # Dinner history
    └── conversation.ts   # Message history
```

## Setup

```bash
# Install dependencies
npm install

# Set up environment variables
cp .env.example .env
# Fill in: DATABASE_URL, TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN,
#          TWILIO_PHONE_NUMBER, ANTHROPIC_API_KEY, CRON_SECRET

# Create database and run migrations
createdb icebox
npm run migrate

# Start dev server
npm run dev
```

## Scripts

| Command | Description |
|---------|-------------|
| `npm run dev` | Start dev server with hot reload |
| `npm run build` | Compile TypeScript |
| `npm start` | Run production server |
| `npm test` | Run tests |
| `npm run test:watch` | Run tests in watch mode |
| `npm run migrate` | Run database migrations |

## API Endpoints

- `POST /sms` — Twilio webhook for incoming SMS/MMS
- `POST /cron/nightly` — Nightly dinner interview trigger (requires `x-cron-secret` header)
- `GET /health` — Health check

## Testing

Tests use a separate `icebox_test` database:

```bash
createdb icebox_test
DATABASE_URL=postgresql://localhost:5432/icebox_test npm run migrate
npm test
```
