import type pg from "pg";

export interface Message {
  id: string;
  user_id: string;
  role: "user" | "assistant";
  content: string;
  media_url: string | null;
  created_at: Date;
}

export async function addMessage(
  pool: pg.Pool,
  userId: string,
  role: "user" | "assistant",
  content: string,
  mediaUrl?: string
): Promise<void> {
  await pool.query(
    "INSERT INTO conversation_history (user_id, role, content, media_url) VALUES ($1, $2, $3, $4)",
    [userId, role, content, mediaUrl || null]
  );
}

export async function getRecentMessages(pool: pg.Pool, userId: string, limit: number): Promise<Message[]> {
  const result = await pool.query<Message>(
    `SELECT * FROM (
       SELECT * FROM conversation_history WHERE user_id = $1 ORDER BY created_at DESC LIMIT $2
     ) sub ORDER BY created_at ASC`,
    [userId, limit]
  );
  return result.rows;
}
