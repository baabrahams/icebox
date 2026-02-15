import type pg from "pg";

export interface DietaryRestriction {
  id: string;
  user_id: string;
  type: "allergy" | "dislike" | "diet";
  value: string;
  source: "onboarding" | "learned";
}

interface NewRestriction {
  type: DietaryRestriction["type"];
  value: string;
  source: DietaryRestriction["source"];
}

export async function addRestriction(pool: pg.Pool, userId: string, r: NewRestriction): Promise<void> {
  await pool.query(
    "INSERT INTO dietary_restrictions (user_id, type, value, source) VALUES ($1, $2, $3, $4)",
    [userId, r.type, r.value.toLowerCase().trim(), r.source]
  );
}

export async function getRestrictions(pool: pg.Pool, userId: string): Promise<DietaryRestriction[]> {
  const result = await pool.query<DietaryRestriction>(
    "SELECT * FROM dietary_restrictions WHERE user_id = $1 ORDER BY type, value",
    [userId]
  );
  return result.rows;
}
