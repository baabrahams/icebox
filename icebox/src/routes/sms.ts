import { Router } from "express";
import type { Request, Response } from "express";
import twilio from "twilio";
import pool from "../db/connection.js";
import { findOrCreateByPhone } from "../db/users.js";
import { loadUserContext } from "../context.js";
import { chat } from "../claude.js";
import { executeActions } from "../actions.js";
import { addMessage } from "../db/conversation.js";

const router = Router();

// Twilio signature validation middleware
function validateTwilio(req: Request, res: Response, next: () => void) {
  if (process.env.NODE_ENV === "test" || process.env.NODE_ENV !== "production") return next();

  const signature = req.headers["x-twilio-signature"] as string;
  const url = `${req.protocol}://${req.get("host")}${req.originalUrl}`;
  const valid = twilio.validateRequest(
    process.env.TWILIO_AUTH_TOKEN!,
    signature,
    url,
    req.body
  );

  if (!valid) {
    res.status(403).send("Invalid signature");
    return;
  }
  next();
}

// Rate limiting: simple in-memory counter per phone number
const rateLimits = new Map<string, { count: number; resetAt: number }>();

function checkRateLimit(phone: string): boolean {
  const now = Date.now();
  const entry = rateLimits.get(phone);
  if (!entry || now > entry.resetAt) {
    rateLimits.set(phone, { count: 1, resetAt: now + 3600000 });
    return true;
  }
  entry.count++;
  return entry.count <= 30;
}

async function downloadImage(mediaUrl: string): Promise<string> {
  const accountSid = process.env.TWILIO_ACCOUNT_SID!;
  const authToken = process.env.TWILIO_AUTH_TOKEN!;
  const response = await fetch(mediaUrl, {
    headers: {
      Authorization: "Basic " + Buffer.from(`${accountSid}:${authToken}`).toString("base64"),
    },
  });
  const buffer = await response.arrayBuffer();
  return Buffer.from(buffer).toString("base64");
}

router.post("/sms", validateTwilio, async (req: Request, res: Response) => {
  const from: string = req.body.From;
  const body: string = req.body.Body || "";
  const numMedia = parseInt(req.body.NumMedia || "0", 10);

  if (!checkRateLimit(from)) {
    const twiml = new twilio.twiml.MessagingResponse();
    twiml.message("You're sending too many messages. Please try again later.");
    res.type("text/xml").send(twiml.toString());
    return;
  }

  try {
    // Find or create user
    const user = await findOrCreateByPhone(pool, from);

    // Download image if MMS
    let imageBase64: string | undefined;
    if (numMedia > 0) {
      const mediaUrl = req.body.MediaUrl0;
      imageBase64 = await downloadImage(mediaUrl);
    }

    // Load context
    const ctx = await loadUserContext(pool, user.id);

    // Save inbound message
    await addMessage(pool, user.id, "user", body, numMedia > 0 ? req.body.MediaUrl0 : undefined);

    // Call Claude
    const { reply, actions } = await chat(ctx, body, imageBase64);

    // Execute any actions
    if (actions) {
      await executeActions(pool, user.id, actions);
    }

    // Save outbound message
    await addMessage(pool, user.id, "assistant", reply);

    // Reply via TwiML
    const twiml = new twilio.twiml.MessagingResponse();
    twiml.message(reply);
    res.type("text/xml").send(twiml.toString());
  } catch (error) {
    console.error("SMS handler error:", error);
    const twiml = new twilio.twiml.MessagingResponse();
    twiml.message("Sorry, my brain is foggy right now - try again in a few minutes.");
    res.type("text/xml").send(twiml.toString());
  }
});

export default router;
