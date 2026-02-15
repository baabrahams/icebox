import { Router } from "express";
import type { Request, Response } from "express";
import twilio from "twilio";
import pool from "../db/connection.js";
import { loadUserContext } from "../context.js";
import { generateNightlyOpener } from "../claude.js";
import { executeActions } from "../actions.js";
import { addMessage } from "../db/conversation.js";

const router = Router();

const twilioClient = twilio(process.env.TWILIO_ACCOUNT_SID, process.env.TWILIO_AUTH_TOKEN);

router.post("/cron/nightly", async (req: Request, res: Response) => {
  // Verify cron secret to prevent unauthorized triggers
  const secret = req.headers["x-cron-secret"] || req.body.secret;
  if (secret !== process.env.CRON_SECRET) {
    res.status(403).json({ error: "Unauthorized" });
    return;
  }

  try {
    // Find users whose interview time matches now in their timezone
    const { rows: users } = await pool.query(`
      SELECT * FROM users
      WHERE onboarding_complete = true
        AND TO_CHAR(NOW() AT TIME ZONE timezone, 'HH24:MI') = TO_CHAR(interview_time, 'HH24:MI')
    `);

    const results = [];

    for (const user of users) {
      try {
        const ctx = await loadUserContext(pool, user.id);
        const { reply, actions } = await generateNightlyOpener(ctx);

        if (actions) {
          await executeActions(pool, user.id, actions);
        }

        await addMessage(pool, user.id, "assistant", reply);

        await twilioClient.messages.create({
          body: reply,
          from: process.env.TWILIO_PHONE_NUMBER!,
          to: user.phone_number,
        });

        results.push({ phone: user.phone_number, status: "sent" });
      } catch (err) {
        console.error(`Nightly interview failed for ${user.phone_number}:`, err);
        results.push({ phone: user.phone_number, status: "failed" });
      }
    }

    res.json({ triggered: users.length, results });
  } catch (error) {
    console.error("Cron handler error:", error);
    res.status(500).json({ error: "Internal error" });
  }
});

export default router;
