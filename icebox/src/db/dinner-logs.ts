import type pg from "pg";

export interface DinnerLog {
  id: string;
  user_id: string;
  date: string;
  recipe_name: string;
  recipe_source: string | null;
  status: "suggested" | "made" | "skipped";
  user_rating: number | null;
  items_used: string[] | null;
}

interface NewLog {
  recipe_name: string;
  recipe_source?: string;
}

export async function createLog(pool: pg.Pool, userId: string, log: NewLog): Promise<DinnerLog> {
  const result = await pool.query<DinnerLog>(
    "INSERT INTO dinner_logs (user_id, recipe_name, recipe_source) VALUES ($1, $2, $3) RETURNING *",
    [userId, log.recipe_name, log.recipe_source || null]
  );
  return result.rows[0];
}

export async function getRecentLogs(pool: pg.Pool, userId: string, days: number): Promise<DinnerLog[]> {
  const result = await pool.query<DinnerLog>(
    "SELECT * FROM dinner_logs WHERE user_id = $1 AND date >= CURRENT_DATE - $2::integer ORDER BY date DESC",
    [userId, days]
  );
  return result.rows;
}

export async function getOpenSuggestion(pool: pg.Pool, userId: string): Promise<DinnerLog | null> {
  const result = await pool.query<DinnerLog>(
    "SELECT * FROM dinner_logs WHERE user_id = $1 AND status = 'suggested' ORDER BY date DESC LIMIT 1",
    [userId]
  );
  return result.rows[0] || null;
}

export async function updateLogStatus(
  pool: pg.Pool,
  logId: string,
  status: "made" | "skipped",
  rating?: number
): Promise<void> {
  await pool.query(
    "UPDATE dinner_logs SET status = $1, user_rating = $2 WHERE id = $3",
    [status, rating || null, logId]
  );
}
