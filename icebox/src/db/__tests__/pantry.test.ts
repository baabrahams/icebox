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
    await new Promise((r) => setTimeout(r, 50));
    await addItems(pool, user.id, [{ name: "chicken", category: "protein" }]);
    const after = await getItems(pool, user.id);
    expect(after).toHaveLength(1);
    expect(after[0].last_confirmed_at.getTime()).toBeGreaterThanOrEqual(
      before[0].last_confirmed_at.getTime()
    );
  });
});
