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
