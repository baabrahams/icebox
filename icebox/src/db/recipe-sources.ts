import type pg from "pg";

export async function addSource(pool: pg.Pool, userId: string, sourceName: string): Promise<void> {
  const normalized = sourceName.toLowerCase().trim();
  await pool.query(
    `INSERT INTO recipe_sources (user_id, source_name)
     VALUES ($1, $2)
     ON CONFLICT (user_id, LOWER(source_name)) DO NOTHING`,
    [userId, normalized]
  );
}

export async function removeSource(pool: pg.Pool, userId: string, sourceName: string): Promise<void> {
  await pool.query(
    "DELETE FROM recipe_sources WHERE user_id = $1 AND LOWER(source_name) = $2",
    [userId, sourceName.toLowerCase().trim()]
  );
}

export async function getSourcesForUser(pool: pg.Pool, userId: string): Promise<string[]> {
  const result = await pool.query<{ source_name: string }>(
    "SELECT source_name FROM recipe_sources WHERE user_id = $1 ORDER BY source_name",
    [userId]
  );
  return result.rows.map((r) => r.source_name);
}
