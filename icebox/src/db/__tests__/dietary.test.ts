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
