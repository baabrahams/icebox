import { describe, it, expect, beforeAll, afterAll, beforeEach } from "vitest";
import { loadUserContext } from "../context.js";
import { findOrCreateByPhone } from "../db/users.js";
import { addItems } from "../db/pantry.js";
import { addRestriction } from "../db/dietary.js";
import { addSource } from "../db/recipe-sources.js";
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

  it("includes recipe sources and weeknight time", async () => {
    const user = await findOrCreateByPhone(pool, "+15551234567");
    await addSource(pool, user.id, "NYT Cooking");
    await addSource(pool, user.id, "Bon Appetit");

    const ctx = await loadUserContext(pool, user.id);
    expect(ctx.recipeSources).toEqual(["bon appetit", "nyt cooking"]);
    expect(ctx.user.weeknight_time_minutes).toBe(30); // default
  });
});
