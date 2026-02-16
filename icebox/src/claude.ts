import Anthropic from "@anthropic-ai/sdk";
import type { UserContext } from "./context.js";
import { buildSystemPrompt } from "./prompts.js";

const anthropic = new Anthropic();

interface ClaudeResponse {
  reply: string;
  actions: Actions | null;
}

export interface Actions {
  add_pantry?: { name: string; category: string }[];
  remove_pantry?: string[];
  add_restrictions?: { type: "allergy" | "dislike" | "diet"; value: string; source: "onboarding" | "learned" }[];
  update_user?: Partial<{
    household_size: number;
    interview_time: string;
    weeknight_time_minutes: number;
    timezone: string;
    onboarding_complete: boolean;
  }>;
  log_dinner?: { recipe_name: string; recipe_source?: string };
  update_dinner_status?: { status: "made" | "skipped"; rating?: number };
  remove_dinner_items?: string[];
  add_recipe_source?: string[];
  remove_recipe_source?: string[];
}

export async function chat(
  ctx: UserContext,
  userMessage: string,
  imageBase64?: string
): Promise<ClaudeResponse> {
  const systemPrompt = buildSystemPrompt(ctx);

  // Build messages from conversation history + current message
  const messages: Anthropic.MessageParam[] = ctx.recentMessages.map((m) => ({
    role: m.role,
    content: m.content,
  }));

  // Add current user message
  if (imageBase64) {
    messages.push({
      role: "user",
      content: [
        { type: "image", source: { type: "base64", media_type: "image/jpeg", data: imageBase64 } },
        { type: "text", text: userMessage || "What food items do you see in this photo?" },
      ],
    });
  } else {
    messages.push({ role: "user", content: userMessage });
  }

  const timeoutMs = imageBase64 ? 45000 : 30000;

  const response = await Promise.race([
    anthropic.messages.create({
      model: "claude-sonnet-4-5-20250929",
      max_tokens: 1024,
      system: systemPrompt,
      messages,
    }),
    new Promise<never>((_, reject) =>
      setTimeout(() => reject(new Error("Claude API timeout")), timeoutMs)
    ),
  ]);

  const fullText = response.content
    .filter((b): b is Anthropic.TextBlock => b.type === "text")
    .map((b) => b.text)
    .join("");

  // Extract actions block if present
  const actionsMatch = fullText.match(/<actions>([\s\S]*?)<\/actions>/);
  let actions: Actions | null = null;
  let reply = fullText;

  if (actionsMatch) {
    try {
      actions = JSON.parse(actionsMatch[1]);
    } catch {
      // If JSON parsing fails, ignore actions
    }
    reply = fullText.replace(/<actions>[\s\S]*?<\/actions>/, "").trim();
  }

  return { reply, actions };
}

export async function generateNightlyOpener(ctx: UserContext): Promise<ClaudeResponse> {
  const prompt = ctx.openSuggestion
    ? `Start the nightly dinner interview. You previously suggested "${ctx.openSuggestion.recipe_name}" - ask if they made it.`
    : "Start the nightly dinner interview. Ask what they're in the mood for tonight.";

  return chat(ctx, prompt);
}
