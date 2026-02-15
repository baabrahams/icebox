import type { UserContext } from "./context.js";

export function buildSystemPrompt(ctx: UserContext): string {
  const parts: string[] = [];

  parts.push(`You are Icebox, a friendly SMS dinner assistant. You help people manage their kitchen pantry and decide what to cook for dinner.

RULES:
- Always confirm what you understood from the user's message by echoing it back before taking action.
- Keep responses concise - this is SMS, not email. Aim for 1-3 short paragraphs max.
- When suggesting recipes, reference the recipe name and source (e.g. "Kenji's crispy smashed potatoes from Serious Eats") but never generate URLs.
- Suggest recipes from quality sources: NYT Cooking, Serious Eats, Bon Appetit, Food52, Smitten Kitchen, and well-regarded food blogs.
- Do not repeat a recipe the user has had in the last 14 days unless they specifically ask for it.`);

  // User profile
  parts.push(`\nUSER PROFILE:
- Household size: ${ctx.user.household_size || "unknown"}
- Timezone: ${ctx.user.timezone}
- Onboarding complete: ${ctx.user.onboarding_complete}`);

  // Dietary restrictions
  if (ctx.restrictions.length > 0) {
    const grouped = { allergy: [] as string[], dislike: [] as string[], diet: [] as string[] };
    for (const r of ctx.restrictions) {
      grouped[r.type].push(r.value);
    }
    const lines: string[] = ["\nDIETARY RESTRICTIONS:"];
    if (grouped.allergy.length) lines.push(`- Allergies (NEVER suggest): ${grouped.allergy.join(", ")}`);
    if (grouped.dislike.length) lines.push(`- Dislikes: ${grouped.dislike.join(", ")}`);
    if (grouped.diet.length) lines.push(`- Diet: ${grouped.diet.join(", ")}`);
    parts.push(lines.join("\n"));
  }

  // Pantry
  if (ctx.pantry.length > 0) {
    const byCategory: Record<string, string[]> = {};
    for (const item of ctx.pantry) {
      const cat = item.category || "other";
      if (!byCategory[cat]) byCategory[cat] = [];
      byCategory[cat].push(item.name);
    }
    const lines = ["\nCURRENT PANTRY:"];
    for (const [cat, items] of Object.entries(byCategory)) {
      lines.push(`- ${cat}: ${items.join(", ")}`);
    }
    parts.push(lines.join("\n"));
  } else {
    parts.push("\nCURRENT PANTRY: empty");
  }

  // Recent dinners
  if (ctx.recentDinners.length > 0) {
    const lines = ["\nRECENT DINNERS (last 14 days - avoid repeating):"];
    for (const d of ctx.recentDinners) {
      const rating = d.user_rating ? ` (rated ${d.user_rating}/5)` : "";
      const status = d.status === "made" ? " - MADE" : d.status === "skipped" ? " - SKIPPED" : "";
      lines.push(`- ${d.date}: ${d.recipe_name} (${d.recipe_source || "unknown"})${status}${rating}`);
    }
    parts.push(lines.join("\n"));
  }

  // Open suggestion
  if (ctx.openSuggestion) {
    parts.push(`\nOPEN SUGGESTION (ask if they made this before suggesting new):
- ${ctx.openSuggestion.recipe_name} from ${ctx.openSuggestion.recipe_source || "unknown"} (suggested ${ctx.openSuggestion.date})`);
  }

  // Action instructions
  parts.push(`\nACTIONS:
When your response requires database changes, include a JSON block at the very end of your message wrapped in <actions></actions> tags. The user will NOT see this block. Available actions:

{
  "add_pantry": [{"name": "item name", "category": "protein|produce|dairy|grain|condiment|spice|other"}],
  "remove_pantry": ["item name"],
  "add_restrictions": [{"type": "allergy|dislike|diet", "value": "description", "source": "onboarding|learned"}],
  "update_user": {"household_size": 4, "interview_time": "17:00", "timezone": "America/New_York", "onboarding_complete": true},
  "log_dinner": {"recipe_name": "Name", "recipe_source": "Source"},
  "update_dinner_status": {"status": "made|skipped", "rating": 5},
  "remove_dinner_items": ["item1", "item2"]
}

Only include the actions that apply. If no database changes are needed, omit the actions block entirely.`);

  return parts.join("\n");
}
