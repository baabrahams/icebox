import type pg from "pg";

export interface User {
  id: string;
  phone_number: string;
  household_size: number | null;
  interview_time: string;
  timezone: string;
  onboarding_complete: boolean;
  created_at: Date;
  updated_at: Date;
}

export async function findOrCreateByPhone(pool: pg.Pool, phone: string): Promise<User> {
  const existing = await pool.query<User>("SELECT * FROM users WHERE phone_number = $1", [phone]);
  if (existing.rows.length > 0) return existing.rows[0];

  const result = await pool.query<User>(
    "INSERT INTO users (phone_number) VALUES ($1) RETURNING *",
    [phone]
  );
  return result.rows[0];
}

export async function updateUser(
  pool: pg.Pool,
  userId: string,
  fields: Partial<Pick<User, "household_size" | "interview_time" | "timezone" | "onboarding_complete">>
): Promise<User> {
  const sets: string[] = [];
  const values: unknown[] = [];
  let idx = 1;

  for (const [key, value] of Object.entries(fields)) {
    sets.push(`${key} = $${idx}`);
    values.push(value);
    idx++;
  }
  sets.push(`updated_at = NOW()`);
  values.push(userId);

  const result = await pool.query<User>(
    `UPDATE users SET ${sets.join(", ")} WHERE id = $${idx} RETURNING *`,
    values
  );
  return result.rows[0];
}
