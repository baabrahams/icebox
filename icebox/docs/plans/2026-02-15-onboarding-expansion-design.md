# Onboarding Expansion: Time Budget & Recipe Sources

**Date:** 2026-02-15
**Goal:** Improve recipe recommendation quality by collecting two additional data points during onboarding.

## Expanded Onboarding Flow

The onboarding grows from 3 questions to 5. Order is intentional — start with the easiest/most personal, end with the most specific:

1. **Household size** (existing) — "How many people do you usually cook for?"
2. **Allergies/dislikes** (existing) — "Any food allergies or things you absolutely won't eat?"
3. **Weeknight time budget** (new) — "How much time do you usually have for a weeknight dinner — 15 minutes, 30, or 60+?"
4. **Recipe sources** (new) — "Do you have access to any recipe sites like NYT Cooking, Bon Appetit, or others? I'll prioritize recipes from your sources, but I'll still suggest great ones from elsewhere too."
5. **Preferred dinner time** (existing, moved to last) — "What time do you usually start thinking about dinner?"

## How the New Data Gets Used

### Time Budget

- Stored on the `users` table as `weeknight_time_minutes INTEGER`
- Included in the system prompt context so Claude knows to suggest quick meals vs. slow braises
- Not a hard filter — if someone says "I have all night tonight" during a nightly interview, the bot adapts in the moment

### Recipe Sources

- New `recipe_sources` table stores which sites/subscriptions the user has access to
- Included in the system prompt as a prioritized list
- **Soft preference:** the prompt instructs Claude to favor these sources but not exclude others. When suggesting from an unsubscribed source, Claude mentions it — "This one's from NYT Cooking, not sure if you have access — want me to suggest something else?"
- If the user confirms access to a new source mid-conversation, the bot adds it via a new `add_recipe_source` action

Both values feed into the system prompt alongside existing context (pantry, dietary restrictions, dinner history) so Claude makes better-informed suggestions without hard-coded filtering logic.

## What We Decided Not to Ask

- **Cooking skill level** — time budget is a better proxy; self-reported skill is unreliable
- **Cuisine preferences** — the bot learns these fast from dinner log ratings and acceptance patterns
- **Kitchen equipment** — most recipes need basic stovetop/oven; edge cases (Instant Pot, grill) surface naturally in conversation

## Schema Changes

### Migration 003

```sql
-- Add time budget to users
ALTER TABLE users ADD COLUMN weeknight_time_minutes INTEGER DEFAULT 30;

-- Recipe sources table
CREATE TABLE recipe_sources (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  source_name TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX idx_recipe_sources_user_source
  ON recipe_sources (user_id, LOWER(source_name));
```

## Code Changes

### New DB module: `src/db/recipe-sources.ts`

- `addSource(userId, sourceName)` — insert with lowercase normalization
- `removeSource(userId, sourceName)`
- `getSourcesForUser(userId)` — returns list of source names

### Actions (`src/actions.ts`)

- Add `add_recipe_source` and `remove_recipe_source` action types

### Context (`src/context.ts`)

- Include `recipeSources: string[]` and `weeknightTimeMinutes: number` in `UserContext`

### Prompts (`src/prompts.ts`)

- Add time budget to user profile section
- Add recipe sources list with soft-preference instruction: "Prioritize recipes from the user's sources, but don't exclude other sources. When suggesting from a source not on their list, mention it."

### Onboarding prompt update

- Add the two new questions to the onboarding sequence in the system prompt
- Update `update_user` action to accept `weeknight_time_minutes`
