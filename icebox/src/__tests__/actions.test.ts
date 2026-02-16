import { describe, it, expect, beforeAll, afterAll, beforeEach } from "vitest";
import { executeActions } from "../actions.js";
import { findOrCreateByPhone } from "../db/users.js";
import { getItems } from "../db/pantry.js";
import { getRestrictions } from "../db/dietary.js";
import { createLog, getOpenSuggestion } from "../db/dinner-logs.js";
import { getSourcesForUser } from "../db/recipe-sources.js";
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
});
