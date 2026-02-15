import type pg from "pg";

export interface PantryItem {
  id: string;
  user_id: string;
  name: string;
  category: string | null;
  added_at: Date;
  last_confirmed_at: Date;
}

interface NewItem {
  name: string;
  category: string | null;
}

export async function addItems(pool: pg.Pool, userId: string, items: NewItem[]): Promise<void> {
  for (const item of items) {
    const normalizedName = item.name.toLowerCase().trim();
    await pool.query(
      `INSERT INTO pantry_items (user_id, name, category)
       VALUES ($1, $2, $3)
       ON CONFLICT (user_id, LOWER(name)) DO UPDATE SET last_confirmed_at = NOW()`,
      [userId, normalizedName, item.category]
    );
  }
}

export async function removeItems(pool: pg.Pool, userId: string, names: string[]): Promise<void> {
  for (const name of names) {
    await pool.query(
      "DELETE FROM pantry_items WHERE user_id = $1 AND LOWER(name) = $2",
      [userId, name.toLowerCase().trim()]
    );
  }
}

export async function getItems(pool: pg.Pool, userId: string): Promise<PantryItem[]> {
  const result = await pool.query<PantryItem>(
    "SELECT * FROM pantry_items WHERE user_id = $1 ORDER BY category, name",
    [userId]
  );
  return result.rows;
}
