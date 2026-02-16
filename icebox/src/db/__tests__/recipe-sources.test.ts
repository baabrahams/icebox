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
