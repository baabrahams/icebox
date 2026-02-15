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
