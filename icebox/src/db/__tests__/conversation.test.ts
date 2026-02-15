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
