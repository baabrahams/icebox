import pg from "pg";

const TEST_DB_URL = process.env.DATABASE_URL || "postgresql://localhost:5432/icebox_test";

export function getTestPool() {
  return new pg.Pool({ connectionString: TEST_DB_URL });
}

export async function cleanDb(pool: pg.Pool) {
  await pool.query("DELETE FROM recipe_sources");
  await pool.query("DELETE FROM dinner_logs");
  await pool.query("DELETE FROM conversation_history");
  await pool.query("DELETE FROM pantry_items");
  await pool.query("DELETE FROM dietary_restrictions");
  await pool.query("DELETE FROM users");
}
