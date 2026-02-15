import "dotenv/config";
import fs from "fs";
import path from "path";
import pool from "./connection.js";

async function migrate() {
  await pool.query(`
    CREATE TABLE IF NOT EXISTS migrations (
      id SERIAL PRIMARY KEY,
      name TEXT NOT NULL UNIQUE,
      run_at TIMESTAMPTZ DEFAULT NOW()
    )
  `);

  const migrationsDir = path.join(import.meta.dirname, "migrations");
  const files = fs.readdirSync(migrationsDir).sort();

  for (const file of files) {
    if (!file.endsWith(".sql")) continue;
    const { rows } = await pool.query("SELECT 1 FROM migrations WHERE name = $1", [file]);
    if (rows.length > 0) continue;

    const sql = fs.readFileSync(path.join(migrationsDir, file), "utf-8");
    await pool.query(sql);
    await pool.query("INSERT INTO migrations (name) VALUES ($1)", [file]);
    console.log(`Migrated: ${file}`);
  }

  await pool.end();
  console.log("Migrations complete.");
}

migrate().catch((err) => {
  console.error("Migration failed:", err);
  process.exit(1);
});
