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
