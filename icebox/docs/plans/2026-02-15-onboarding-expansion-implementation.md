# Onboarding Expansion Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add weeknight time budget and recipe source preferences to onboarding, so the bot makes better recipe recommendations from day one.

**Architecture:** New `recipe_sources` table + `weeknight_time_minutes` column on `users`. New DB module for recipe sources, wired into context, actions, and the system prompt. Onboarding prompt updated with two new questions.

**Tech Stack:** TypeScript, PostgreSQL, Vitest, Express

---

### Task 1: Database Migration

**Files:**
- Create: `src/db/migrations/003_onboarding_expansion.sql`

**Step 1: Write the migration SQL**

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

**Step 2: Run the migration against the test database**

Run: `DATABASE_URL=postgresql://localhost:5432/icebox_test npx tsx src/db/migrate.ts`
Expected: `Migrated: 003_onboarding_expansion.sql` followed by `Migrations complete.`

**Step 3: Commit**

```bash
git add src/db/migrations/003_onboarding_expansion.sql
git commit -m "feat: add migration for weeknight_time_minutes and recipe_sources"
```

---

### Task 2: Recipe Sources DB Module

**Files:**
- Create: `src/db/recipe-sources.ts`
- Create: `src/db/__tests__/recipe-sources.test.ts`
- Modify: `src/db/test-helpers.ts` (add recipe_sources to cleanDb)

**Step 1: Add recipe_sources to cleanDb**

In `src/db/test-helpers.ts`, add `await pool.query("DELETE FROM recipe_sources");` as the first delete statement (before dinner_logs), since recipe_sources references users.

```typescript
export async function cleanDb(pool: pg.Pool) {
  await pool.query("DELETE FROM recipe_sources");
  await pool.query("DELETE FROM dinner_logs");
  await pool.query("DELETE FROM conversation_history");
  await pool.query("DELETE FROM pantry_items");
  await pool.query("DELETE FROM dietary_restrictions");
  await pool.query("DELETE FROM users");
}
```

**Step 2: Write the failing tests**

Create `src/db/__tests__/recipe-sources.test.ts`:

```typescript
import { describe, it, expect, beforeAll, afterAll, beforeEach } from "vitest";
import { addSource, removeSource, getSourcesForUser } from "../recipe-sources.js";
import { findOrCreateByPhone } from "../users.js";
import { getTestPool, cleanDb } from "../test-helpers.js";
import type pg from "pg";

let pool: pg.Pool;

beforeAll(async () => { pool = getTestPool(); });
afterAll(async () => { await pool.end(); });
beforeEach(async () => { await cleanDb(pool); });

describe("recipe sources", () => {
  it("adds and retrieves sources for a user", async () => {
    const user = await findOrCreateByPhone(pool, "+15551234567");
    await addSource(pool, user.id, "NYT Cooking");
    await addSource(pool, user.id, "Bon Appetit");
    const sources = await getSourcesForUser(pool, user.id);
    expect(sources).toEqual(["bon appetit", "nyt cooking"]);
  });

  it("normalizes source names to lowercase", async () => {
    const user = await findOrCreateByPhone(pool, "+15551234567");
    await addSource(pool, user.id, "NYT Cooking");
    const sources = await getSourcesForUser(pool, user.id);
    expect(sources).toEqual(["nyt cooking"]);
  });

  it("ignores duplicate sources (case-insensitive)", async () => {
    const user = await findOrCreateByPhone(pool, "+15551234567");
    await addSource(pool, user.id, "NYT Cooking");
    await addSource(pool, user.id, "nyt cooking");
    const sources = await getSourcesForUser(pool, user.id);
    expect(sources).toEqual(["nyt cooking"]);
  });

  it("removes a source", async () => {
    const user = await findOrCreateByPhone(pool, "+15551234567");
    await addSource(pool, user.id, "NYT Cooking");
    await addSource(pool, user.id, "Bon Appetit");
    await removeSource(pool, user.id, "NYT Cooking");
    const sources = await getSourcesForUser(pool, user.id);
    expect(sources).toEqual(["bon appetit"]);
  });
});
```

**Step 3: Run tests to verify they fail**

Run: `npx vitest run src/db/__tests__/recipe-sources.test.ts`
Expected: FAIL — module `../recipe-sources.js` not found

**Step 4: Write the implementation**

Create `src/db/recipe-sources.ts`:

```typescript
import type pg from "pg";

export async function addSource(pool: pg.Pool, userId: string, sourceName: string): Promise<void> {
  const normalized = sourceName.toLowerCase().trim();
  await pool.query(
    `INSERT INTO recipe_sources (user_id, source_name)
     VALUES ($1, $2)
     ON CONFLICT (user_id, LOWER(source_name)) DO NOTHING`,
    [userId, normalized]
  );
}

export async function removeSource(pool: pg.Pool, userId: string, sourceName: string): Promise<void> {
  await pool.query(
    "DELETE FROM recipe_sources WHERE user_id = $1 AND LOWER(source_name) = $2",
    [userId, sourceName.toLowerCase().trim()]
  );
}

export async function getSourcesForUser(pool: pg.Pool, userId: string): Promise<string[]> {
  const result = await pool.query<{ source_name: string }>(
    "SELECT source_name FROM recipe_sources WHERE user_id = $1 ORDER BY source_name",
    [userId]
  );
  return result.rows.map((r) => r.source_name);
}
```

**Step 5: Run tests to verify they pass**

Run: `npx vitest run src/db/__tests__/recipe-sources.test.ts`
Expected: All 4 tests PASS

**Step 6: Commit**

```bash
git add src/db/recipe-sources.ts src/db/__tests__/recipe-sources.test.ts src/db/test-helpers.ts
git commit -m "feat: add recipe-sources DB module with tests"
```

---

### Task 3: Update User Type and updateUser for weeknight_time_minutes

**Files:**
- Modify: `src/db/users.ts` (add `weeknight_time_minutes` to `User` interface and `updateUser` allowed fields)
- Modify: `src/db/__tests__/users.test.ts` (add test for new field)

**Step 1: Write the failing test**

Add to `src/db/__tests__/users.test.ts`, inside a new describe block after the existing one:

```typescript
import { findOrCreateByPhone, updateUser } from "../users.js";

// ... existing tests ...

describe("updateUser", () => {
  it("updates weeknight_time_minutes", async () => {
    const user = await findOrCreateByPhone(pool, "+15551234567");
    const updated = await updateUser(pool, user.id, { weeknight_time_minutes: 15 });
    expect(updated.weeknight_time_minutes).toBe(15);
  });
});
```

**Step 2: Run test to verify it fails**

Run: `npx vitest run src/db/__tests__/users.test.ts`
Expected: FAIL — `weeknight_time_minutes` not in the type

**Step 3: Update the User interface and updateUser function**

In `src/db/users.ts`:

Add `weeknight_time_minutes: number;` to the `User` interface (after `interview_time`):

```typescript
export interface User {
  id: string;
  phone_number: string;
  household_size: number | null;
  interview_time: string;
  weeknight_time_minutes: number;
  timezone: string;
  onboarding_complete: boolean;
  created_at: Date;
  updated_at: Date;
}
```

Update the `updateUser` fields type to include `weeknight_time_minutes`:

```typescript
export async function updateUser(
  pool: pg.Pool,
  userId: string,
  fields: Partial<Pick<User, "household_size" | "interview_time" | "weeknight_time_minutes" | "timezone" | "onboarding_complete">>
): Promise<User> {
```

**Step 4: Run tests to verify they pass**

Run: `npx vitest run src/db/__tests__/users.test.ts`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/db/users.ts src/db/__tests__/users.test.ts
git commit -m "feat: add weeknight_time_minutes to User type and updateUser"
```

---

### Task 4: Update Context to Include Recipe Sources and Time Budget

**Files:**
- Modify: `src/context.ts` (add `recipeSources` to `UserContext`, fetch in `loadUserContext`)
- Modify: `src/__tests__/context.test.ts` (add test for new fields)

**Step 1: Write the failing test**

Add a new test case to `src/__tests__/context.test.ts`:

```typescript
import { addSource } from "../db/recipe-sources.js";

// ... inside describe("loadUserContext") ...

  it("includes recipe sources and weeknight time", async () => {
    const user = await findOrCreateByPhone(pool, "+15551234567");
    await addSource(pool, user.id, "NYT Cooking");
    await addSource(pool, user.id, "Bon Appetit");

    const ctx = await loadUserContext(pool, user.id);
    expect(ctx.recipeSources).toEqual(["bon appetit", "nyt cooking"]);
    expect(ctx.user.weeknight_time_minutes).toBe(30); // default
  });
```

**Step 2: Run test to verify it fails**

Run: `npx vitest run src/__tests__/context.test.ts`
Expected: FAIL — `recipeSources` not on `UserContext`

**Step 3: Update context.ts**

Add import for recipe sources and update the interface and loader:

```typescript
import { getSourcesForUser } from "./db/recipe-sources.js";

export interface UserContext {
  user: User;
  pantry: PantryItem[];
  restrictions: DietaryRestriction[];
  recipeSources: string[];
  recentDinners: DinnerLog[];
  openSuggestion: DinnerLog | null;
  recentMessages: Message[];
}

export async function loadUserContext(pool: pg.Pool, userId: string): Promise<UserContext> {
  const userResult = await pool.query<User>("SELECT * FROM users WHERE id = $1", [userId]);
  const user = userResult.rows[0];

  const [pantry, restrictions, recipeSources, recentDinners, openSuggestion, recentMessages] = await Promise.all([
    getItems(pool, userId),
    getRestrictions(pool, userId),
    getSourcesForUser(pool, userId),
    getRecentLogs(pool, userId, 14),
    getOpenSuggestion(pool, userId),
    getRecentMessages(pool, userId, 20),
  ]);

  return { user, pantry, restrictions, recipeSources, recentDinners, openSuggestion, recentMessages };
}
```

**Step 4: Run tests to verify they pass**

Run: `npx vitest run src/__tests__/context.test.ts`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/context.ts src/__tests__/context.test.ts
git commit -m "feat: add recipeSources to UserContext"
```

---

### Task 5: Update Actions to Support Recipe Source Add/Remove

**Files:**
- Modify: `src/claude.ts` (add `add_recipe_source` and `remove_recipe_source` to `Actions` interface)
- Modify: `src/actions.ts` (handle new action types)
- Modify: `src/__tests__/actions.test.ts` (add tests)

**Step 1: Write the failing tests**

Add to `src/__tests__/actions.test.ts`:

```typescript
import { getSourcesForUser } from "../db/recipe-sources.js";

// ... inside describe("executeActions") ...

  it("adds recipe sources", async () => {
    const user = await findOrCreateByPhone(pool, "+15551234567");
    await executeActions(pool, user.id, { add_recipe_source: ["NYT Cooking", "Bon Appetit"] });
    const sources = await getSourcesForUser(pool, user.id);
    expect(sources).toEqual(["bon appetit", "nyt cooking"]);
  });

  it("removes recipe sources", async () => {
    const user = await findOrCreateByPhone(pool, "+15551234567");
    await executeActions(pool, user.id, { add_recipe_source: ["NYT Cooking", "Bon Appetit"] });
    await executeActions(pool, user.id, { remove_recipe_source: ["NYT Cooking"] });
    const sources = await getSourcesForUser(pool, user.id);
    expect(sources).toEqual(["bon appetit"]);
  });
```

**Step 2: Run tests to verify they fail**

Run: `npx vitest run src/__tests__/actions.test.ts`
Expected: FAIL — `add_recipe_source` not in `Actions` type

**Step 3: Add to Actions interface in claude.ts**

In `src/claude.ts`, add to the `Actions` interface:

```typescript
export interface Actions {
  add_pantry?: { name: string; category: string }[];
  remove_pantry?: string[];
  add_restrictions?: { type: "allergy" | "dislike" | "diet"; value: string; source: "onboarding" | "learned" }[];
  update_user?: Partial<{
    household_size: number;
    interview_time: string;
    weeknight_time_minutes: number;
    timezone: string;
    onboarding_complete: boolean;
  }>;
  log_dinner?: { recipe_name: string; recipe_source?: string };
  update_dinner_status?: { status: "made" | "skipped"; rating?: number };
  remove_dinner_items?: string[];
  add_recipe_source?: string[];
  remove_recipe_source?: string[];
}
```

**Step 4: Handle new actions in actions.ts**

In `src/actions.ts`, add import and handlers:

```typescript
import { addSource, removeSource } from "./db/recipe-sources.js";
```

Add at the end of `executeActions`, before the closing brace:

```typescript
  if (actions.add_recipe_source?.length) {
    for (const source of actions.add_recipe_source) {
      await addSource(pool, userId, source);
    }
  }

  if (actions.remove_recipe_source?.length) {
    for (const source of actions.remove_recipe_source) {
      await removeSource(pool, userId, source);
    }
  }
```

**Step 5: Run tests to verify they pass**

Run: `npx vitest run src/__tests__/actions.test.ts`
Expected: All tests PASS

**Step 6: Commit**

```bash
git add src/claude.ts src/actions.ts src/__tests__/actions.test.ts
git commit -m "feat: add recipe source add/remove actions"
```

---

### Task 6: Update System Prompt

**Files:**
- Modify: `src/prompts.ts` (add time budget, recipe sources, updated onboarding questions, and actions docs)

**Step 1: Update the user profile section**

In `src/prompts.ts`, update the USER PROFILE section to include weeknight time:

```typescript
  parts.push(`\nUSER PROFILE:
- Household size: ${ctx.user.household_size || "unknown"}
- Weeknight time budget: ${ctx.user.weeknight_time_minutes} minutes
- Timezone: ${ctx.user.timezone}
- Onboarding complete: ${ctx.user.onboarding_complete}`);
```

**Step 2: Add recipe sources section after dietary restrictions**

After the dietary restrictions block, add:

```typescript
  // Recipe sources
  if (ctx.recipeSources.length > 0) {
    parts.push(`\nRECIPE SOURCES (user has access to these — prioritize them, but don't exclude other sources. When suggesting from a source not on this list, mention it):
- ${ctx.recipeSources.join("\n- ")}`);
  }
```

**Step 3: Update the RULES section**

Replace the hardcoded recipe source rule. Change:
```
- Suggest recipes from quality sources: NYT Cooking, Serious Eats, Bon Appetit, Food52, Smitten Kitchen, and well-regarded food blogs.
```
To:
```
- Suggest recipes from quality sources like Serious Eats, Food52, Smitten Kitchen, and well-regarded food blogs. Prioritize the user's subscribed sources when available.
```

**Step 4: Update the onboarding instructions**

Add a new section after the RULES, before USER PROFILE, that appears only when onboarding is not complete:

```typescript
  if (!ctx.user.onboarding_complete) {
    parts.push(`
ONBOARDING:
You are onboarding this user. Ask these questions ONE AT A TIME, in order. Wait for each answer before asking the next. Echo back what you understood before moving on.
1. "How many people do you usually cook for?"
2. "Any food allergies or things you absolutely won't eat?"
3. "How much time do you usually have for a weeknight dinner — 15 minutes, 30, or 60+?"
4. "Do you have access to any recipe sites like NYT Cooking, Bon Appetit, or others? I'll prioritize recipes from your sources, but I'll still suggest great ones from elsewhere too."
5. "What time do you usually start thinking about dinner?" (default: 5pm)
After all questions are answered, set onboarding_complete to true.`);
  }
```

**Step 5: Update the actions documentation in the prompt**

Add the two new actions to the JSON example in the ACTIONS section:

```typescript
  parts.push(`\nACTIONS:
When your response requires database changes, include a JSON block at the very end of your message wrapped in <actions></actions> tags. The user will NOT see this block. Available actions:

{
  "add_pantry": [{"name": "item name", "category": "protein|produce|dairy|grain|condiment|spice|other"}],
  "remove_pantry": ["item name"],
  "add_restrictions": [{"type": "allergy|dislike|diet", "value": "description", "source": "onboarding|learned"}],
  "update_user": {"household_size": 4, "interview_time": "17:00", "weeknight_time_minutes": 30, "timezone": "America/New_York", "onboarding_complete": true},
  "log_dinner": {"recipe_name": "Name", "recipe_source": "Source"},
  "update_dinner_status": {"status": "made|skipped", "rating": 5},
  "remove_dinner_items": ["item1", "item2"],
  "add_recipe_source": ["NYT Cooking", "Bon Appetit"],
  "remove_recipe_source": ["Source Name"]
}

Only include the actions that apply. If no database changes are needed, omit the actions block entirely.`);
```

**Step 6: Run all tests to make sure nothing is broken**

Run: `npx vitest run`
Expected: All tests PASS

**Step 7: Commit**

```bash
git add src/prompts.ts
git commit -m "feat: update system prompt with time budget, recipe sources, and expanded onboarding"
```

---

### Task 7: Run Full Test Suite and Verify

**Step 1: Run full test suite**

Run: `npx vitest run`
Expected: All tests PASS

**Step 2: Run TypeScript type check**

Run: `npx tsc --noEmit`
Expected: No errors

**Step 3: Final commit if any fixes were needed**

If any fixes were applied, commit them. Otherwise, nothing to do.
