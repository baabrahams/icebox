# Icebox Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build an SMS-based dinner assistant that manages pantry inventory via photos/text and conducts nightly dinner interviews, all through Twilio SMS/MMS powered by Claude API.

**Architecture:** Stateless Express server receives Twilio webhooks, loads user context from PostgreSQL, calls Claude API with structured context + conversation history, parses Claude's response for actions (pantry updates, dinner logs, preference changes) and a natural language reply, executes actions against DB, replies via Twilio. A cron endpoint triggers nightly interviews.

**Tech Stack:** Node.js 22, TypeScript, Express, PostgreSQL (via `pg` + raw SQL migrations), Twilio SDK, Anthropic SDK, Vitest for testing, dotenv for config.

---

### Task 1: Project Scaffolding

**Files:**
- Create: `package.json`
- Create: `tsconfig.json`
- Create: `.env.example`
- Create: `.gitignore`
- Create: `src/index.ts`

**Step 1: Set Node version and initialize project**

```bash
cd /Users/benabrahams/icebox
echo "v22.14.0" > .nvmrc
export NVM_DIR="$HOME/.nvm" && . "$NVM_DIR/nvm.sh" && nvm use
npm init -y
```

**Step 2: Install dependencies**

```bash
npm install express twilio @anthropic-ai/sdk pg dotenv uuid
npm install -D typescript @types/express @types/pg @types/node @types/uuid vitest tsx
```

**Step 3: Create tsconfig.json**

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "NodeNext",
    "moduleResolution": "NodeNext",
    "outDir": "./dist",
    "rootDir": "./src",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true,
    "resolveJsonModule": true,
    "declaration": true
  },
  "include": ["src/**/*"],
  "exclude": ["node_modules", "dist"]
}
```

**Step 4: Create .env.example**

```
DATABASE_URL=postgresql://localhost:5432/icebox
TWILIO_ACCOUNT_SID=your_account_sid
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_PHONE_NUMBER=+1234567890
ANTHROPIC_API_KEY=your_anthropic_api_key
PORT=3000
CRON_SECRET=your_cron_secret
```

**Step 5: Create .gitignore**

```
node_modules/
dist/
.env
*.js.map
```

**Step 6: Create minimal src/index.ts**

```typescript
import "dotenv/config";
import express from "express";

const app = express();
app.use(express.urlencoded({ extended: false }));
app.use(express.json());

app.get("/health", (_req, res) => {
  res.json({ status: "ok" });
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`Icebox listening on port ${PORT}`);
});

export default app;
```

**Step 7: Add scripts to package.json**

Update the `scripts` section:
```json
{
  "scripts": {
    "dev": "tsx watch src/index.ts",
    "build": "tsc",
    "start": "node dist/index.js",
    "test": "vitest run",
    "test:watch": "vitest"
  }
}
```

**Step 8: Verify it compiles and runs**

```bash
npx tsx src/index.ts &
sleep 2
curl http://localhost:3000/health
kill %1
```

Expected: `{"status":"ok"}`

**Step 9: Commit**

```bash
git add -A
git commit -m "feat: project scaffolding with Express, TypeScript, and dependencies"
```

---

### Task 2: Database Schema and Migrations

**Files:**
- Create: `src/db/connection.ts`
- Create: `src/db/migrate.ts`
- Create: `src/db/migrations/001_initial_schema.sql`

**Step 1: Create database connection module**

`src/db/connection.ts`:
```typescript
import pg from "pg";

const pool = new pg.Pool({
  connectionString: process.env.DATABASE_URL,
});

export default pool;
```

**Step 2: Create migration runner**

`src/db/migrate.ts`:
```typescript
import "dotenv/config";
import fs from "fs";
import path from "path";
import pool from "./connection.js";

async function migrate() {
  await pool.query(`
    CREATE TABLE IF NOT EXISTS migrations (
      id SERIAL PRIMARY KEY,
      name TEXT NOT NULL UNIQUE,
      run_at TIMESTAMPTZ DEFAULT NOW()
    )
  `);

  const migrationsDir = path.join(import.meta.dirname, "migrations");
  const files = fs.readdirSync(migrationsDir).sort();

  for (const file of files) {
    if (!file.endsWith(".sql")) continue;
    const { rows } = await pool.query("SELECT 1 FROM migrations WHERE name = $1", [file]);
    if (rows.length > 0) continue;

    const sql = fs.readFileSync(path.join(migrationsDir, file), "utf-8");
    await pool.query(sql);
    await pool.query("INSERT INTO migrations (name) VALUES ($1)", [file]);
    console.log(`Migrated: ${file}`);
  }

  await pool.end();
  console.log("Migrations complete.");
}

migrate().catch((err) => {
  console.error("Migration failed:", err);
  process.exit(1);
});
```

**Step 3: Create initial schema migration**

`src/db/migrations/001_initial_schema.sql`:
```sql
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  phone_number TEXT NOT NULL UNIQUE,
  household_size INTEGER,
  interview_time TIME DEFAULT '17:00',
  timezone TEXT DEFAULT 'America/New_York',
  onboarding_complete BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_users_phone ON users(phone_number);

CREATE TABLE dietary_restrictions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  type TEXT NOT NULL CHECK (type IN ('allergy', 'dislike', 'diet')),
  value TEXT NOT NULL,
  source TEXT NOT NULL CHECK (source IN ('onboarding', 'learned'))
);

CREATE INDEX idx_dietary_user ON dietary_restrictions(user_id);

CREATE TABLE pantry_items (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  category TEXT,
  added_at TIMESTAMPTZ DEFAULT NOW(),
  last_confirmed_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_pantry_user ON pantry_items(user_id);

CREATE TABLE conversation_history (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
  content TEXT NOT NULL,
  media_url TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_convo_user_time ON conversation_history(user_id, created_at DESC);

CREATE TABLE dinner_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  date DATE NOT NULL DEFAULT CURRENT_DATE,
  recipe_name TEXT NOT NULL,
  recipe_source TEXT,
  status TEXT NOT NULL CHECK (status IN ('suggested', 'made', 'skipped')) DEFAULT 'suggested',
  user_rating INTEGER CHECK (user_rating BETWEEN 1 AND 5),
  items_used TEXT[]
);

CREATE INDEX idx_dinner_user_date ON dinner_logs(user_id, date DESC);
```

**Step 4: Add migrate script to package.json**

```json
"migrate": "tsx src/db/migrate.ts"
```

**Step 5: Create local database and run migration**

```bash
createdb icebox 2>/dev/null || true
echo "DATABASE_URL=postgresql://localhost:5432/icebox" > .env
npm run migrate
```

Expected: `Migrated: 001_initial_schema.sql` then `Migrations complete.`

**Step 6: Commit**

```bash
git add -A
git commit -m "feat: database schema and migration runner"
```

---

### Task 3: User Repository

**Files:**
- Create: `src/db/users.ts`
- Create: `src/db/__tests__/users.test.ts`
- Create: `vitest.config.ts`
- Create: `src/db/test-helpers.ts`

**Step 1: Create vitest config**

`vitest.config.ts`:
```typescript
import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    globals: true,
    environment: "node",
    setupFiles: [],
  },
});
```

**Step 2: Create test helpers for DB tests**

`src/db/test-helpers.ts`:
```typescript
import pg from "pg";

const TEST_DB_URL = process.env.DATABASE_URL || "postgresql://localhost:5432/icebox_test";

export function getTestPool() {
  return new pg.Pool({ connectionString: TEST_DB_URL });
}

export async function cleanDb(pool: pg.Pool) {
  await pool.query("DELETE FROM dinner_logs");
  await pool.query("DELETE FROM conversation_history");
  await pool.query("DELETE FROM pantry_items");
  await pool.query("DELETE FROM dietary_restrictions");
  await pool.query("DELETE FROM users");
}
```

**Step 3: Write failing test for findOrCreateByPhone**

`src/db/__tests__/users.test.ts`:
```typescript
import { describe, it, expect, beforeAll, afterAll, beforeEach } from "vitest";
import { findOrCreateByPhone } from "../users.js";
import { getTestPool, cleanDb } from "../test-helpers.js";
import type pg from "pg";

let pool: pg.Pool;

beforeAll(async () => {
  pool = getTestPool();
});

afterAll(async () => {
  await pool.end();
});

beforeEach(async () => {
  await cleanDb(pool);
});

describe("findOrCreateByPhone", () => {
  it("creates a new user for unknown phone number", async () => {
    const user = await findOrCreateByPhone(pool, "+15551234567");
    expect(user.phone_number).toBe("+15551234567");
    expect(user.onboarding_complete).toBe(false);
    expect(user.id).toBeDefined();
  });

  it("returns existing user for known phone number", async () => {
    const first = await findOrCreateByPhone(pool, "+15551234567");
    const second = await findOrCreateByPhone(pool, "+15551234567");
    expect(first.id).toBe(second.id);
  });
});
```

**Step 4: Run test to verify it fails**

```bash
createdb icebox_test 2>/dev/null || true
DATABASE_URL=postgresql://localhost:5432/icebox_test npm run migrate
npm test -- src/db/__tests__/users.test.ts
```

Expected: FAIL - `findOrCreateByPhone` not found

**Step 5: Implement users repository**

`src/db/users.ts`:
```typescript
import type pg from "pg";

export interface User {
  id: string;
  phone_number: string;
  household_size: number | null;
  interview_time: string;
  timezone: string;
  onboarding_complete: boolean;
  created_at: Date;
  updated_at: Date;
}

export async function findOrCreateByPhone(pool: pg.Pool, phone: string): Promise<User> {
  const existing = await pool.query<User>("SELECT * FROM users WHERE phone_number = $1", [phone]);
  if (existing.rows.length > 0) return existing.rows[0];

  const result = await pool.query<User>(
    "INSERT INTO users (phone_number) VALUES ($1) RETURNING *",
    [phone]
  );
  return result.rows[0];
}

export async function updateUser(
  pool: pg.Pool,
  userId: string,
  fields: Partial<Pick<User, "household_size" | "interview_time" | "timezone" | "onboarding_complete">>
): Promise<User> {
  const sets: string[] = [];
  const values: unknown[] = [];
  let idx = 1;

  for (const [key, value] of Object.entries(fields)) {
    sets.push(`${key} = $${idx}`);
    values.push(value);
    idx++;
  }
  sets.push(`updated_at = NOW()`);
  values.push(userId);

  const result = await pool.query<User>(
    `UPDATE users SET ${sets.join(", ")} WHERE id = $${idx} RETURNING *`,
    values
  );
  return result.rows[0];
}
```

**Step 6: Run test to verify it passes**

```bash
npm test -- src/db/__tests__/users.test.ts
```

Expected: PASS

**Step 7: Commit**

```bash
git add -A
git commit -m "feat: user repository with findOrCreateByPhone"
```

---

### Task 4: Pantry Repository

**Files:**
- Create: `src/db/pantry.ts`
- Create: `src/db/__tests__/pantry.test.ts`

**Step 1: Write failing tests**

`src/db/__tests__/pantry.test.ts`:
```typescript
import { describe, it, expect, beforeAll, afterAll, beforeEach } from "vitest";
import { addItems, removeItems, getItems } from "../pantry.js";
import { findOrCreateByPhone } from "../users.js";
import { getTestPool, cleanDb } from "../test-helpers.js";
import type pg from "pg";

let pool: pg.Pool;

beforeAll(async () => {
  pool = getTestPool();
});

afterAll(async () => {
  await pool.end();
});

beforeEach(async () => {
  await cleanDb(pool);
});

describe("pantry", () => {
  it("adds items and retrieves them", async () => {
    const user = await findOrCreateByPhone(pool, "+15551234567");
    await addItems(pool, user.id, [
      { name: "chicken", category: "protein" },
      { name: "rice", category: "grain" },
    ]);
    const items = await getItems(pool, user.id);
    expect(items).toHaveLength(2);
    expect(items.map((i) => i.name).sort()).toEqual(["chicken", "rice"]);
  });

  it("removes items by name", async () => {
    const user = await findOrCreateByPhone(pool, "+15551234567");
    await addItems(pool, user.id, [
      { name: "chicken", category: "protein" },
      { name: "rice", category: "grain" },
    ]);
    await removeItems(pool, user.id, ["chicken"]);
    const items = await getItems(pool, user.id);
    expect(items).toHaveLength(1);
    expect(items[0].name).toBe("rice");
  });

  it("confirms existing items by updating last_confirmed_at", async () => {
    const user = await findOrCreateByPhone(pool, "+15551234567");
    await addItems(pool, user.id, [{ name: "chicken", category: "protein" }]);
    const before = await getItems(pool, user.id);
    // Small delay to ensure timestamp difference
    await new Promise((r) => setTimeout(r, 50));
    await addItems(pool, user.id, [{ name: "chicken", category: "protein" }]);
    const after = await getItems(pool, user.id);
    expect(after).toHaveLength(1);
    expect(after[0].last_confirmed_at.getTime()).toBeGreaterThanOrEqual(
      before[0].last_confirmed_at.getTime()
    );
  });
});
```

**Step 2: Run test to verify it fails**

```bash
npm test -- src/db/__tests__/pantry.test.ts
```

Expected: FAIL

**Step 3: Implement pantry repository**

`src/db/pantry.ts`:
```typescript
import type pg from "pg";

export interface PantryItem {
  id: string;
  user_id: string;
  name: string;
  category: string | null;
  added_at: Date;
  last_confirmed_at: Date;
}

interface NewItem {
  name: string;
  category: string | null;
}

export async function addItems(pool: pg.Pool, userId: string, items: NewItem[]): Promise<void> {
  for (const item of items) {
    const normalizedName = item.name.toLowerCase().trim();
    await pool.query(
      `INSERT INTO pantry_items (user_id, name, category)
       VALUES ($1, $2, $3)
       ON CONFLICT DO NOTHING`,
      [userId, normalizedName, item.category]
    );
    // Update last_confirmed_at if it already exists
    await pool.query(
      `UPDATE pantry_items SET last_confirmed_at = NOW()
       WHERE user_id = $1 AND LOWER(name) = $2`,
      [userId, normalizedName]
    );
  }
}

export async function removeItems(pool: pg.Pool, userId: string, names: string[]): Promise<void> {
  for (const name of names) {
    await pool.query(
      "DELETE FROM pantry_items WHERE user_id = $1 AND LOWER(name) = $2",
      [userId, name.toLowerCase().trim()]
    );
  }
}

export async function getItems(pool: pg.Pool, userId: string): Promise<PantryItem[]> {
  const result = await pool.query<PantryItem>(
    "SELECT * FROM pantry_items WHERE user_id = $1 ORDER BY category, name",
    [userId]
  );
  return result.rows;
}
```

Note: The `ON CONFLICT` in `addItems` needs a unique constraint on `(user_id, LOWER(name))`. We need to add this to the migration. Add to `001_initial_schema.sql` or create a new migration `002_pantry_unique.sql`:

`src/db/migrations/002_pantry_unique.sql`:
```sql
CREATE UNIQUE INDEX idx_pantry_user_name ON pantry_items (user_id, LOWER(name));
```

**Step 4: Run migration and tests**

```bash
npm run migrate
DATABASE_URL=postgresql://localhost:5432/icebox_test npm run migrate
npm test -- src/db/__tests__/pantry.test.ts
```

Expected: PASS

**Step 5: Commit**

```bash
git add -A
git commit -m "feat: pantry repository with add, remove, get, and smart merge"
```

---

### Task 5: Dietary Restrictions and Dinner Log Repositories

**Files:**
- Create: `src/db/dietary.ts`
- Create: `src/db/dinner-logs.ts`
- Create: `src/db/__tests__/dietary.test.ts`
- Create: `src/db/__tests__/dinner-logs.test.ts`

**Step 1: Write failing tests for dietary restrictions**

`src/db/__tests__/dietary.test.ts`:
```typescript
import { describe, it, expect, beforeAll, afterAll, beforeEach } from "vitest";
import { addRestriction, getRestrictions } from "../dietary.js";
import { findOrCreateByPhone } from "../users.js";
import { getTestPool, cleanDb } from "../test-helpers.js";
import type pg from "pg";

let pool: pg.Pool;

beforeAll(async () => { pool = getTestPool(); });
afterAll(async () => { await pool.end(); });
beforeEach(async () => { await cleanDb(pool); });

describe("dietary restrictions", () => {
  it("adds and retrieves restrictions", async () => {
    const user = await findOrCreateByPhone(pool, "+15551234567");
    await addRestriction(pool, user.id, { type: "allergy", value: "peanuts", source: "onboarding" });
    await addRestriction(pool, user.id, { type: "dislike", value: "cilantro", source: "onboarding" });
    const restrictions = await getRestrictions(pool, user.id);
    expect(restrictions).toHaveLength(2);
  });
});
```

**Step 2: Write failing tests for dinner logs**

`src/db/__tests__/dinner-logs.test.ts`:
```typescript
import { describe, it, expect, beforeAll, afterAll, beforeEach } from "vitest";
import { createLog, getRecentLogs, getOpenSuggestion, updateLogStatus } from "../dinner-logs.js";
import { findOrCreateByPhone } from "../users.js";
import { getTestPool, cleanDb } from "../test-helpers.js";
import type pg from "pg";

let pool: pg.Pool;

beforeAll(async () => { pool = getTestPool(); });
afterAll(async () => { await pool.end(); });
beforeEach(async () => { await cleanDb(pool); });

describe("dinner logs", () => {
  it("creates a log and retrieves it", async () => {
    const user = await findOrCreateByPhone(pool, "+15551234567");
    await createLog(pool, user.id, { recipe_name: "Pasta Carbonara", recipe_source: "Serious Eats" });
    const logs = await getRecentLogs(pool, user.id, 14);
    expect(logs).toHaveLength(1);
    expect(logs[0].status).toBe("suggested");
  });

  it("finds open suggestion", async () => {
    const user = await findOrCreateByPhone(pool, "+15551234567");
    await createLog(pool, user.id, { recipe_name: "Pasta Carbonara", recipe_source: "Serious Eats" });
    const open = await getOpenSuggestion(pool, user.id);
    expect(open).toBeDefined();
    expect(open!.recipe_name).toBe("Pasta Carbonara");
  });

  it("updates log status", async () => {
    const user = await findOrCreateByPhone(pool, "+15551234567");
    await createLog(pool, user.id, { recipe_name: "Pasta Carbonara", recipe_source: "Serious Eats" });
    const open = await getOpenSuggestion(pool, user.id);
    await updateLogStatus(pool, open!.id, "made", 4);
    const logs = await getRecentLogs(pool, user.id, 14);
    expect(logs[0].status).toBe("made");
    expect(logs[0].user_rating).toBe(4);
  });
});
```

**Step 3: Run tests to verify they fail**

```bash
npm test -- src/db/__tests__/dietary.test.ts src/db/__tests__/dinner-logs.test.ts
```

**Step 4: Implement dietary repository**

`src/db/dietary.ts`:
```typescript
import type pg from "pg";

export interface DietaryRestriction {
  id: string;
  user_id: string;
  type: "allergy" | "dislike" | "diet";
  value: string;
  source: "onboarding" | "learned";
}

interface NewRestriction {
  type: DietaryRestriction["type"];
  value: string;
  source: DietaryRestriction["source"];
}

export async function addRestriction(pool: pg.Pool, userId: string, r: NewRestriction): Promise<void> {
  await pool.query(
    "INSERT INTO dietary_restrictions (user_id, type, value, source) VALUES ($1, $2, $3, $4)",
    [userId, r.type, r.value.toLowerCase().trim(), r.source]
  );
}

export async function getRestrictions(pool: pg.Pool, userId: string): Promise<DietaryRestriction[]> {
  const result = await pool.query<DietaryRestriction>(
    "SELECT * FROM dietary_restrictions WHERE user_id = $1 ORDER BY type, value",
    [userId]
  );
  return result.rows;
}
```

**Step 5: Implement dinner logs repository**

`src/db/dinner-logs.ts`:
```typescript
import type pg from "pg";

export interface DinnerLog {
  id: string;
  user_id: string;
  date: string;
  recipe_name: string;
  recipe_source: string | null;
  status: "suggested" | "made" | "skipped";
  user_rating: number | null;
  items_used: string[] | null;
}

interface NewLog {
  recipe_name: string;
  recipe_source?: string;
}

export async function createLog(pool: pg.Pool, userId: string, log: NewLog): Promise<DinnerLog> {
  const result = await pool.query<DinnerLog>(
    "INSERT INTO dinner_logs (user_id, recipe_name, recipe_source) VALUES ($1, $2, $3) RETURNING *",
    [userId, log.recipe_name, log.recipe_source || null]
  );
  return result.rows[0];
}

export async function getRecentLogs(pool: pg.Pool, userId: string, days: number): Promise<DinnerLog[]> {
  const result = await pool.query<DinnerLog>(
    "SELECT * FROM dinner_logs WHERE user_id = $1 AND date >= CURRENT_DATE - $2::integer ORDER BY date DESC",
    [userId, days]
  );
  return result.rows;
}

export async function getOpenSuggestion(pool: pg.Pool, userId: string): Promise<DinnerLog | null> {
  const result = await pool.query<DinnerLog>(
    "SELECT * FROM dinner_logs WHERE user_id = $1 AND status = 'suggested' ORDER BY date DESC LIMIT 1",
    [userId]
  );
  return result.rows[0] || null;
}

export async function updateLogStatus(
  pool: pg.Pool,
  logId: string,
  status: "made" | "skipped",
  rating?: number
): Promise<void> {
  await pool.query(
    "UPDATE dinner_logs SET status = $1, user_rating = $2 WHERE id = $3",
    [status, rating || null, logId]
  );
}
```

**Step 6: Run tests to verify they pass**

```bash
npm test -- src/db/__tests__/dietary.test.ts src/db/__tests__/dinner-logs.test.ts
```

Expected: PASS

**Step 7: Commit**

```bash
git add -A
git commit -m "feat: dietary restrictions and dinner log repositories"
```

---

### Task 6: Conversation History Repository

**Files:**
- Create: `src/db/conversation.ts`
- Create: `src/db/__tests__/conversation.test.ts`

**Step 1: Write failing test**

`src/db/__tests__/conversation.test.ts`:
```typescript
import { describe, it, expect, beforeAll, afterAll, beforeEach } from "vitest";
import { addMessage, getRecentMessages } from "../conversation.js";
import { findOrCreateByPhone } from "../users.js";
import { getTestPool, cleanDb } from "../test-helpers.js";
import type pg from "pg";

let pool: pg.Pool;

beforeAll(async () => { pool = getTestPool(); });
afterAll(async () => { await pool.end(); });
beforeEach(async () => { await cleanDb(pool); });

describe("conversation history", () => {
  it("stores and retrieves messages in order", async () => {
    const user = await findOrCreateByPhone(pool, "+15551234567");
    await addMessage(pool, user.id, "user", "hello");
    await addMessage(pool, user.id, "assistant", "hi there!");
    const messages = await getRecentMessages(pool, user.id, 20);
    expect(messages).toHaveLength(2);
    expect(messages[0].role).toBe("user");
    expect(messages[1].role).toBe("assistant");
  });

  it("limits to N most recent messages", async () => {
    const user = await findOrCreateByPhone(pool, "+15551234567");
    for (let i = 0; i < 5; i++) {
      await addMessage(pool, user.id, "user", `msg ${i}`);
    }
    const messages = await getRecentMessages(pool, user.id, 3);
    expect(messages).toHaveLength(3);
    expect(messages[0].content).toBe("msg 2");
  });
});
```

**Step 2: Run test to verify it fails**

```bash
npm test -- src/db/__tests__/conversation.test.ts
```

**Step 3: Implement conversation repository**

`src/db/conversation.ts`:
```typescript
import type pg from "pg";

export interface Message {
  id: string;
  user_id: string;
  role: "user" | "assistant";
  content: string;
  media_url: string | null;
  created_at: Date;
}

export async function addMessage(
  pool: pg.Pool,
  userId: string,
  role: "user" | "assistant",
  content: string,
  mediaUrl?: string
): Promise<void> {
  await pool.query(
    "INSERT INTO conversation_history (user_id, role, content, media_url) VALUES ($1, $2, $3, $4)",
    [userId, role, content, mediaUrl || null]
  );
}

export async function getRecentMessages(pool: pg.Pool, userId: string, limit: number): Promise<Message[]> {
  const result = await pool.query<Message>(
    `SELECT * FROM (
       SELECT * FROM conversation_history WHERE user_id = $1 ORDER BY created_at DESC LIMIT $2
     ) sub ORDER BY created_at ASC`,
    [userId, limit]
  );
  return result.rows;
}
```

**Step 4: Run test to verify it passes**

```bash
npm test -- src/db/__tests__/conversation.test.ts
```

Expected: PASS

**Step 5: Commit**

```bash
git add -A
git commit -m "feat: conversation history repository"
```

---

### Task 7: User Context Loader

**Files:**
- Create: `src/context.ts`
- Create: `src/__tests__/context.test.ts`

This module loads all the context Claude needs for a given user in one call.

**Step 1: Write failing test**

`src/__tests__/context.test.ts`:
```typescript
import { describe, it, expect, beforeAll, afterAll, beforeEach } from "vitest";
import { loadUserContext } from "../context.js";
import { findOrCreateByPhone } from "../db/users.js";
import { addItems } from "../db/pantry.js";
import { addRestriction } from "../db/dietary.js";
import { getTestPool, cleanDb } from "../db/test-helpers.js";
import type pg from "pg";

let pool: pg.Pool;

beforeAll(async () => { pool = getTestPool(); });
afterAll(async () => { await pool.end(); });
beforeEach(async () => { await cleanDb(pool); });

describe("loadUserContext", () => {
  it("loads all user data for Claude prompt", async () => {
    const user = await findOrCreateByPhone(pool, "+15551234567");
    await addItems(pool, user.id, [{ name: "chicken", category: "protein" }]);
    await addRestriction(pool, user.id, { type: "allergy", value: "peanuts", source: "onboarding" });

    const ctx = await loadUserContext(pool, user.id);
    expect(ctx.user.phone_number).toBe("+15551234567");
    expect(ctx.pantry).toHaveLength(1);
    expect(ctx.restrictions).toHaveLength(1);
    expect(ctx.recentDinners).toHaveLength(0);
    expect(ctx.openSuggestion).toBeNull();
    expect(ctx.recentMessages).toHaveLength(0);
  });
});
```

**Step 2: Run test to verify it fails**

```bash
npm test -- src/__tests__/context.test.ts
```

**Step 3: Implement context loader**

`src/context.ts`:
```typescript
import type pg from "pg";
import type { User } from "./db/users.js";
import type { PantryItem } from "./db/pantry.js";
import type { DietaryRestriction } from "./db/dietary.js";
import type { DinnerLog } from "./db/dinner-logs.js";
import type { Message } from "./db/conversation.js";
import { getItems } from "./db/pantry.js";
import { getRestrictions } from "./db/dietary.js";
import { getRecentLogs, getOpenSuggestion } from "./db/dinner-logs.js";
import { getRecentMessages } from "./db/conversation.js";

export interface UserContext {
  user: User;
  pantry: PantryItem[];
  restrictions: DietaryRestriction[];
  recentDinners: DinnerLog[];
  openSuggestion: DinnerLog | null;
  recentMessages: Message[];
}

export async function loadUserContext(pool: pg.Pool, userId: string): Promise<UserContext> {
  const userResult = await pool.query<User>("SELECT * FROM users WHERE id = $1", [userId]);
  const user = userResult.rows[0];

  const [pantry, restrictions, recentDinners, openSuggestion, recentMessages] = await Promise.all([
    getItems(pool, userId),
    getRestrictions(pool, userId),
    getRecentLogs(pool, userId, 14),
    getOpenSuggestion(pool, userId),
    getRecentMessages(pool, userId, 20),
  ]);

  return { user, pantry, restrictions, recentDinners, openSuggestion, recentMessages };
}
```

**Step 4: Run test to verify it passes**

```bash
npm test -- src/__tests__/context.test.ts
```

Expected: PASS

**Step 5: Commit**

```bash
git add -A
git commit -m "feat: user context loader for Claude prompts"
```

---

### Task 8: Claude Service - System Prompt and API Integration

**Files:**
- Create: `src/claude.ts`
- Create: `src/prompts.ts`

**Step 1: Create the system prompt builder**

`src/prompts.ts`:
```typescript
import type { UserContext } from "./context.js";

export function buildSystemPrompt(ctx: UserContext): string {
  const parts: string[] = [];

  parts.push(`You are Icebox, a friendly SMS dinner assistant. You help people manage their kitchen pantry and decide what to cook for dinner.

RULES:
- Always confirm what you understood from the user's message by echoing it back before taking action.
- Keep responses concise - this is SMS, not email. Aim for 1-3 short paragraphs max.
- When suggesting recipes, reference the recipe name and source (e.g. "Kenji's crispy smashed potatoes from Serious Eats") but never generate URLs.
- Suggest recipes from quality sources: NYT Cooking, Serious Eats, Bon Appetit, Food52, Smitten Kitchen, and well-regarded food blogs.
- Do not repeat a recipe the user has had in the last 14 days unless they specifically ask for it.`);

  // User profile
  parts.push(`\nUSER PROFILE:
- Household size: ${ctx.user.household_size || "unknown"}
- Timezone: ${ctx.user.timezone}
- Onboarding complete: ${ctx.user.onboarding_complete}`);

  // Dietary restrictions
  if (ctx.restrictions.length > 0) {
    const grouped = { allergy: [] as string[], dislike: [] as string[], diet: [] as string[] };
    for (const r of ctx.restrictions) {
      grouped[r.type].push(r.value);
    }
    const lines: string[] = ["\nDIETARY RESTRICTIONS:"];
    if (grouped.allergy.length) lines.push(`- Allergies (NEVER suggest): ${grouped.allergy.join(", ")}`);
    if (grouped.dislike.length) lines.push(`- Dislikes: ${grouped.dislike.join(", ")}`);
    if (grouped.diet.length) lines.push(`- Diet: ${grouped.diet.join(", ")}`);
    parts.push(lines.join("\n"));
  }

  // Pantry
  if (ctx.pantry.length > 0) {
    const byCategory: Record<string, string[]> = {};
    for (const item of ctx.pantry) {
      const cat = item.category || "other";
      if (!byCategory[cat]) byCategory[cat] = [];
      byCategory[cat].push(item.name);
    }
    const lines = ["\nCURRENT PANTRY:"];
    for (const [cat, items] of Object.entries(byCategory)) {
      lines.push(`- ${cat}: ${items.join(", ")}`);
    }
    parts.push(lines.join("\n"));
  } else {
    parts.push("\nCURRENT PANTRY: empty");
  }

  // Recent dinners
  if (ctx.recentDinners.length > 0) {
    const lines = ["\nRECENT DINNERS (last 14 days - avoid repeating):"];
    for (const d of ctx.recentDinners) {
      const rating = d.user_rating ? ` (rated ${d.user_rating}/5)` : "";
      const status = d.status === "made" ? " - MADE" : d.status === "skipped" ? " - SKIPPED" : "";
      lines.push(`- ${d.date}: ${d.recipe_name} (${d.recipe_source || "unknown"})${status}${rating}`);
    }
    parts.push(lines.join("\n"));
  }

  // Open suggestion
  if (ctx.openSuggestion) {
    parts.push(`\nOPEN SUGGESTION (ask if they made this before suggesting new):
- ${ctx.openSuggestion.recipe_name} from ${ctx.openSuggestion.recipe_source || "unknown"} (suggested ${ctx.openSuggestion.date})`);
  }

  // Action instructions
  parts.push(`\nACTIONS:
When your response requires database changes, include a JSON block at the very end of your message wrapped in <actions></actions> tags. The user will NOT see this block. Available actions:

{
  "add_pantry": [{"name": "item name", "category": "protein|produce|dairy|grain|condiment|spice|other"}],
  "remove_pantry": ["item name"],
  "add_restrictions": [{"type": "allergy|dislike|diet", "value": "description", "source": "onboarding|learned"}],
  "update_user": {"household_size": 4, "interview_time": "17:00", "timezone": "America/New_York", "onboarding_complete": true},
  "log_dinner": {"recipe_name": "Name", "recipe_source": "Source"},
  "update_dinner_status": {"status": "made|skipped", "rating": 5},
  "remove_dinner_items": ["item1", "item2"]
}

Only include the actions that apply. If no database changes are needed, omit the actions block entirely.`);

  return parts.join("\n");
}
```

**Step 2: Create Claude API service**

`src/claude.ts`:
```typescript
import Anthropic from "@anthropic-ai/sdk";
import type { UserContext } from "./context.js";
import { buildSystemPrompt } from "./prompts.js";

const anthropic = new Anthropic();

interface ClaudeResponse {
  reply: string;
  actions: Actions | null;
}

export interface Actions {
  add_pantry?: { name: string; category: string }[];
  remove_pantry?: string[];
  add_restrictions?: { type: "allergy" | "dislike" | "diet"; value: string; source: "onboarding" | "learned" }[];
  update_user?: Partial<{
    household_size: number;
    interview_time: string;
    timezone: string;
    onboarding_complete: boolean;
  }>;
  log_dinner?: { recipe_name: string; recipe_source?: string };
  update_dinner_status?: { status: "made" | "skipped"; rating?: number };
  remove_dinner_items?: string[];
}

export async function chat(
  ctx: UserContext,
  userMessage: string,
  imageBase64?: string
): Promise<ClaudeResponse> {
  const systemPrompt = buildSystemPrompt(ctx);

  // Build messages from conversation history + current message
  const messages: Anthropic.MessageParam[] = ctx.recentMessages.map((m) => ({
    role: m.role,
    content: m.content,
  }));

  // Add current user message
  if (imageBase64) {
    messages.push({
      role: "user",
      content: [
        { type: "image", source: { type: "base64", media_type: "image/jpeg", data: imageBase64 } },
        { type: "text", text: userMessage || "What food items do you see in this photo?" },
      ],
    });
  } else {
    messages.push({ role: "user", content: userMessage });
  }

  const timeoutMs = imageBase64 ? 45000 : 30000;

  const response = await Promise.race([
    anthropic.messages.create({
      model: "claude-sonnet-4-5-20250929",
      max_tokens: 1024,
      system: systemPrompt,
      messages,
    }),
    new Promise<never>((_, reject) =>
      setTimeout(() => reject(new Error("Claude API timeout")), timeoutMs)
    ),
  ]);

  const fullText = response.content
    .filter((b): b is Anthropic.TextBlock => b.type === "text")
    .map((b) => b.text)
    .join("");

  // Extract actions block if present
  const actionsMatch = fullText.match(/<actions>([\s\S]*?)<\/actions>/);
  let actions: Actions | null = null;
  let reply = fullText;

  if (actionsMatch) {
    try {
      actions = JSON.parse(actionsMatch[1]);
    } catch {
      // If JSON parsing fails, ignore actions
    }
    reply = fullText.replace(/<actions>[\s\S]*?<\/actions>/, "").trim();
  }

  return { reply, actions };
}

export async function generateNightlyOpener(ctx: UserContext): Promise<ClaudeResponse> {
  const prompt = ctx.openSuggestion
    ? `Start the nightly dinner interview. You previously suggested "${ctx.openSuggestion.recipe_name}" - ask if they made it.`
    : "Start the nightly dinner interview. Ask what they're in the mood for tonight.";

  return chat(ctx, prompt);
}
```

**Step 3: Commit**

```bash
git add -A
git commit -m "feat: Claude API service with system prompt builder and action parsing"
```

---

### Task 9: Action Executor

**Files:**
- Create: `src/actions.ts`
- Create: `src/__tests__/actions.test.ts`

**Step 1: Write failing test**

`src/__tests__/actions.test.ts`:
```typescript
import { describe, it, expect, beforeAll, afterAll, beforeEach } from "vitest";
import { executeActions } from "../actions.js";
import { findOrCreateByPhone } from "../db/users.js";
import { getItems } from "../db/pantry.js";
import { getRestrictions } from "../db/dietary.js";
import { createLog, getOpenSuggestion } from "../db/dinner-logs.js";
import { getTestPool, cleanDb } from "../db/test-helpers.js";
import type pg from "pg";
import type { Actions } from "../claude.js";

let pool: pg.Pool;

beforeAll(async () => { pool = getTestPool(); });
afterAll(async () => { await pool.end(); });
beforeEach(async () => { await cleanDb(pool); });

describe("executeActions", () => {
  it("adds pantry items", async () => {
    const user = await findOrCreateByPhone(pool, "+15551234567");
    const actions: Actions = {
      add_pantry: [
        { name: "chicken", category: "protein" },
        { name: "rice", category: "grain" },
      ],
    };
    await executeActions(pool, user.id, actions);
    const items = await getItems(pool, user.id);
    expect(items).toHaveLength(2);
  });

  it("removes pantry items", async () => {
    const user = await findOrCreateByPhone(pool, "+15551234567");
    await executeActions(pool, user.id, { add_pantry: [{ name: "chicken", category: "protein" }] });
    await executeActions(pool, user.id, { remove_pantry: ["chicken"] });
    const items = await getItems(pool, user.id);
    expect(items).toHaveLength(0);
  });

  it("updates user fields", async () => {
    const user = await findOrCreateByPhone(pool, "+15551234567");
    await executeActions(pool, user.id, { update_user: { household_size: 4, onboarding_complete: true } });
    const result = await pool.query("SELECT * FROM users WHERE id = $1", [user.id]);
    expect(result.rows[0].household_size).toBe(4);
    expect(result.rows[0].onboarding_complete).toBe(true);
  });

  it("logs a dinner suggestion", async () => {
    const user = await findOrCreateByPhone(pool, "+15551234567");
    await executeActions(pool, user.id, { log_dinner: { recipe_name: "Pasta", recipe_source: "NYT" } });
    const open = await getOpenSuggestion(pool, user.id);
    expect(open).toBeDefined();
    expect(open!.recipe_name).toBe("Pasta");
  });

  it("updates dinner status and removes used items", async () => {
    const user = await findOrCreateByPhone(pool, "+15551234567");
    await executeActions(pool, user.id, { add_pantry: [{ name: "pasta", category: "grain" }] });
    await createLog(pool, user.id, { recipe_name: "Pasta", recipe_source: "NYT" });
    await executeActions(pool, user.id, {
      update_dinner_status: { status: "made", rating: 4 },
      remove_dinner_items: ["pasta"],
    });
    const open = await getOpenSuggestion(pool, user.id);
    expect(open).toBeNull();
    const items = await getItems(pool, user.id);
    expect(items).toHaveLength(0);
  });
});
```

**Step 2: Run test to verify it fails**

```bash
npm test -- src/__tests__/actions.test.ts
```

**Step 3: Implement action executor**

`src/actions.ts`:
```typescript
import type pg from "pg";
import type { Actions } from "./claude.js";
import { addItems, removeItems } from "./db/pantry.js";
import { addRestriction } from "./db/dietary.js";
import { updateUser } from "./db/users.js";
import { createLog, getOpenSuggestion, updateLogStatus } from "./db/dinner-logs.js";

export async function executeActions(pool: pg.Pool, userId: string, actions: Actions): Promise<void> {
  if (actions.add_pantry?.length) {
    await addItems(pool, userId, actions.add_pantry);
  }

  if (actions.remove_pantry?.length) {
    await removeItems(pool, userId, actions.remove_pantry);
  }

  if (actions.add_restrictions?.length) {
    for (const r of actions.add_restrictions) {
      await addRestriction(pool, userId, r);
    }
  }

  if (actions.update_user) {
    await updateUser(pool, userId, actions.update_user);
  }

  if (actions.log_dinner) {
    await createLog(pool, userId, actions.log_dinner);
  }

  if (actions.update_dinner_status) {
    const open = await getOpenSuggestion(pool, userId);
    if (open) {
      await updateLogStatus(pool, open.id, actions.update_dinner_status.status, actions.update_dinner_status.rating);
    }
  }

  if (actions.remove_dinner_items?.length) {
    await removeItems(pool, userId, actions.remove_dinner_items);
  }
}
```

**Step 4: Run test to verify it passes**

```bash
npm test -- src/__tests__/actions.test.ts
```

Expected: PASS

**Step 5: Commit**

```bash
git add -A
git commit -m "feat: action executor for Claude response processing"
```

---

### Task 10: Twilio Webhook Handler

**Files:**
- Create: `src/routes/sms.ts`
- Modify: `src/index.ts`

**Step 1: Create the SMS webhook handler**

`src/routes/sms.ts`:
```typescript
import { Router } from "express";
import type { Request, Response } from "express";
import twilio from "twilio";
import pool from "../db/connection.js";
import { findOrCreateByPhone } from "../db/users.js";
import { loadUserContext } from "../context.js";
import { chat } from "../claude.js";
import { executeActions } from "../actions.js";
import { addMessage } from "../db/conversation.js";

const router = Router();

// Twilio signature validation middleware
function validateTwilio(req: Request, res: Response, next: () => void) {
  if (process.env.NODE_ENV === "test") return next();

  const signature = req.headers["x-twilio-signature"] as string;
  const url = `${req.protocol}://${req.get("host")}${req.originalUrl}`;
  const valid = twilio.validateRequest(
    process.env.TWILIO_AUTH_TOKEN!,
    signature,
    url,
    req.body
  );

  if (!valid) {
    res.status(403).send("Invalid signature");
    return;
  }
  next();
}

// Rate limiting: simple in-memory counter per phone number
const rateLimits = new Map<string, { count: number; resetAt: number }>();

function checkRateLimit(phone: string): boolean {
  const now = Date.now();
  const entry = rateLimits.get(phone);
  if (!entry || now > entry.resetAt) {
    rateLimits.set(phone, { count: 1, resetAt: now + 3600000 });
    return true;
  }
  entry.count++;
  return entry.count <= 30;
}

async function downloadImage(mediaUrl: string): Promise<string> {
  const accountSid = process.env.TWILIO_ACCOUNT_SID!;
  const authToken = process.env.TWILIO_AUTH_TOKEN!;
  const response = await fetch(mediaUrl, {
    headers: {
      Authorization: "Basic " + Buffer.from(`${accountSid}:${authToken}`).toString("base64"),
    },
  });
  const buffer = await response.arrayBuffer();
  return Buffer.from(buffer).toString("base64");
}

router.post("/sms", validateTwilio, async (req: Request, res: Response) => {
  const from: string = req.body.From;
  const body: string = req.body.Body || "";
  const numMedia = parseInt(req.body.NumMedia || "0", 10);

  if (!checkRateLimit(from)) {
    const twiml = new twilio.twiml.MessagingResponse();
    twiml.message("You're sending too many messages. Please try again later.");
    res.type("text/xml").send(twiml.toString());
    return;
  }

  try {
    // Find or create user
    const user = await findOrCreateByPhone(pool, from);

    // Download image if MMS
    let imageBase64: string | undefined;
    if (numMedia > 0) {
      const mediaUrl = req.body.MediaUrl0;
      imageBase64 = await downloadImage(mediaUrl);
    }

    // Load context
    const ctx = await loadUserContext(pool, user.id);

    // Save inbound message
    await addMessage(pool, user.id, "user", body, numMedia > 0 ? req.body.MediaUrl0 : undefined);

    // Call Claude
    const { reply, actions } = await chat(ctx, body, imageBase64);

    // Execute any actions
    if (actions) {
      await executeActions(pool, user.id, actions);
    }

    // Save outbound message
    await addMessage(pool, user.id, "assistant", reply);

    // Reply via TwiML
    const twiml = new twilio.twiml.MessagingResponse();
    twiml.message(reply);
    res.type("text/xml").send(twiml.toString());
  } catch (error) {
    console.error("SMS handler error:", error);
    const twiml = new twilio.twiml.MessagingResponse();
    twiml.message("Sorry, my brain is foggy right now - try again in a few minutes.");
    res.type("text/xml").send(twiml.toString());
  }
});

export default router;
```

**Step 2: Update index.ts to use the router**

Replace `src/index.ts` with:
```typescript
import "dotenv/config";
import express from "express";
import smsRouter from "./routes/sms.js";

const app = express();
app.use(express.urlencoded({ extended: false }));
app.use(express.json());

app.get("/health", (_req, res) => {
  res.json({ status: "ok" });
});

app.use(smsRouter);

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`Icebox listening on port ${PORT}`);
});

export default app;
```

**Step 3: Commit**

```bash
git add -A
git commit -m "feat: Twilio SMS webhook handler with image download and rate limiting"
```

---

### Task 11: Cron Endpoint for Nightly Interviews

**Files:**
- Create: `src/routes/cron.ts`
- Modify: `src/index.ts`

**Step 1: Create the cron handler**

`src/routes/cron.ts`:
```typescript
import { Router } from "express";
import type { Request, Response } from "express";
import twilio from "twilio";
import pool from "../db/connection.js";
import { loadUserContext } from "../context.js";
import { generateNightlyOpener } from "../claude.js";
import { executeActions } from "../actions.js";
import { addMessage } from "../db/conversation.js";

const router = Router();

const twilioClient = twilio(process.env.TWILIO_ACCOUNT_SID, process.env.TWILIO_AUTH_TOKEN);

router.post("/cron/nightly", async (req: Request, res: Response) => {
  // Verify cron secret to prevent unauthorized triggers
  const secret = req.headers["x-cron-secret"] || req.body.secret;
  if (secret !== process.env.CRON_SECRET) {
    res.status(403).json({ error: "Unauthorized" });
    return;
  }

  try {
    // Find users whose interview time matches now in their timezone
    const { rows: users } = await pool.query(`
      SELECT * FROM users
      WHERE onboarding_complete = true
        AND TO_CHAR(NOW() AT TIME ZONE timezone, 'HH24:MI') = TO_CHAR(interview_time, 'HH24:MI')
    `);

    const results = [];

    for (const user of users) {
      try {
        const ctx = await loadUserContext(pool, user.id);
        const { reply, actions } = await generateNightlyOpener(ctx);

        if (actions) {
          await executeActions(pool, user.id, actions);
        }

        await addMessage(pool, user.id, "assistant", reply);

        await twilioClient.messages.create({
          body: reply,
          from: process.env.TWILIO_PHONE_NUMBER!,
          to: user.phone_number,
        });

        results.push({ phone: user.phone_number, status: "sent" });
      } catch (err) {
        console.error(`Nightly interview failed for ${user.phone_number}:`, err);
        results.push({ phone: user.phone_number, status: "failed" });
      }
    }

    res.json({ triggered: users.length, results });
  } catch (error) {
    console.error("Cron handler error:", error);
    res.status(500).json({ error: "Internal error" });
  }
});

export default router;
```

**Step 2: Add cron router to index.ts**

Add to `src/index.ts` after smsRouter:
```typescript
import cronRouter from "./routes/cron.js";
// ...
app.use(cronRouter);
```

**Step 3: Commit**

```bash
git add -A
git commit -m "feat: cron endpoint for nightly dinner interview trigger"
```

---

### Task 12: End-to-End Manual Test

**Files:** None new - this is a manual integration test.

**Step 1: Ensure .env is configured**

Verify `.env` has real values for:
- `DATABASE_URL` (local Postgres)
- `TWILIO_ACCOUNT_SID`
- `TWILIO_AUTH_TOKEN`
- `TWILIO_PHONE_NUMBER`
- `ANTHROPIC_API_KEY`
- `CRON_SECRET` (any random string)

**Step 2: Run migrations and start server**

```bash
npm run migrate
npm run dev
```

**Step 3: Use ngrok to expose locally for Twilio**

```bash
npx ngrok http 3000
```

Set the Twilio phone number's webhook URL to `https://<ngrok-url>/sms`.

**Step 4: Test flows**

1. Text the Twilio number from your phone → should trigger onboarding
2. Complete onboarding, verify user is created in DB
3. Send a photo of your fridge → should identify items and ask for confirmation
4. Text "add chicken and rice" → should add to pantry
5. Text "what's in my pantry?" → should list items
6. Text "what should I make tonight?" → should start dinner interview
7. Trigger nightly cron: `curl -X POST http://localhost:3000/cron/nightly -H "x-cron-secret: YOUR_SECRET" -H "Content-Type: application/json"`

**Step 5: Commit any fixes from testing**

```bash
git add -A
git commit -m "fix: adjustments from end-to-end testing"
```

---

### Task 13: Railway Deployment

**Files:**
- Create: `Procfile` (if needed)
- Create: `railway.json` (if needed)

**Step 1: Prepare for deployment**

Add to `package.json`:
```json
"engines": {
  "node": "22.x"
}
```

**Step 2: Deploy to Railway**

1. Create a Railway project
2. Add PostgreSQL plugin
3. Connect GitHub repo
4. Set environment variables (all from `.env.example`)
5. Railway auto-detects Node.js and runs `npm run build` then `npm start`

**Step 3: Run migrations on Railway**

```bash
railway run npm run migrate
```

**Step 4: Set up cron job on Railway**

Create a Railway cron service that hits `POST /cron/nightly` with the `x-cron-secret` header every minute.

**Step 5: Update Twilio webhook**

Point the Twilio phone number's webhook to the Railway URL: `https://your-app.railway.app/sms`

**Step 6: Verify production**

Text the Twilio number and confirm the full flow works.

**Step 7: Commit any deployment config**

```bash
git add -A
git commit -m "feat: deployment configuration for Railway"
```
