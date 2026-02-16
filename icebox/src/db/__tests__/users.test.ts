import { describe, it, expect, beforeAll, afterAll, beforeEach } from "vitest";
import { findOrCreateByPhone, updateUser } from "../users.js";
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

describe("updateUser", () => {
  it("updates weeknight_time_minutes", async () => {
    const user = await findOrCreateByPhone(pool, "+15551234567");
    const updated = await updateUser(pool, user.id, { weeknight_time_minutes: 15 });
    expect(updated.weeknight_time_minutes).toBe(15);
  });
});
