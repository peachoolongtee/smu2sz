/**
 * The one state vocabulary (components/ui/state-word.tsx draws it): twelve states, each with the tone and the glyph it always has. The server writes the word
 * (a `collection_state_text`, a `basis_text`, a financing step); this table only says how that word looks, so "overdue" is red with an alert mark on every page and
 * colour is never the only channel. Plain data and one function, so a unit test reads them without a browser (scripts/w12-design-system.test.mjs).
 */

export const STATE_KEYS = ["planned", "arranged", "received", "repaid", "owed", "scheduled", "agreed", "pending", "current", "due_soon", "overdue", "promise_missed"] as const;
export type StateKey = (typeof STATE_KEYS)[number];

export type StateTone = "neutral" | "ok" | "warn" | "bad" | "info";

/** The glyph names; components/ui/state-word.tsx maps each to an icon of components/icons.tsx. */
export type StateGlyph = "dashed-ring" | "ring-dot" | "ring" | "check" | "check-circle" | "calendar" | "clock" | "alert" | "cross" | "hourglass" | "document" | "rings";

export interface StateLook {
  tone: StateTone;
  glyph: StateGlyph;
}

/**
 * Every state has a glyph of its own (twelve states, twelve marks), so a state is told by its mark and its word as well as by its colour.
 * Blue is the plan and the arrangement (nothing has moved yet), green what has happened or is safe, amber what is waiting or close, red a breach, grey what is only
 * on the books. A planned or arranged state is blue, not green: it is not money yet.
 */
export const STATE_LOOK: Record<StateKey, StateLook> = {
  planned: { tone: "info", glyph: "dashed-ring" },
  arranged: { tone: "info", glyph: "ring-dot" },
  received: { tone: "ok", glyph: "check" },
  repaid: { tone: "ok", glyph: "check-circle" },
  owed: { tone: "neutral", glyph: "document" },
  scheduled: { tone: "neutral", glyph: "calendar" },
  agreed: { tone: "info", glyph: "rings" },
  pending: { tone: "warn", glyph: "hourglass" },
  current: { tone: "ok", glyph: "ring" },
  due_soon: { tone: "warn", glyph: "clock" },
  overdue: { tone: "bad", glyph: "alert" },
  promise_missed: { tone: "bad", glyph: "cross" },
};

/**
 * The glyph of a status that is a tone and not one of the twelve states (an approval's result, a deal's "Needs your response", an authority sentence): the server
 * chose the tone, this is its mark. Tone and glyph always travel together, so such a word is also icon, colour and word.
 */
export const TONE_GLYPH: Record<StateTone, StateGlyph> = { ok: "check", warn: "alert", bad: "cross", info: "ring-dot", neutral: "ring" };

/**
 * The state a server enum names: a collection state (CURRENT, DUE_SOON, OVERDUE, PROMISE_MISSED), a financing state (ARRANGED, RECEIVED, REPAID), a receipt basis
 * (OWED, SCHEDULED, AGREED, PENDING) or the state's own key. Anything else (NONE, an unknown word from a newer server) is null: the caller then draws no state word
 * rather than guess one.
 */
export function stateKey(raw: string | null | undefined): StateKey | null {
  if (!raw) return null;
  const key = raw.trim().toLowerCase();
  return (STATE_KEYS as readonly string[]).includes(key) ? (key as StateKey) : null;
}

/** The text colour of a tone on white: the -fg token that is 4.5:1 there (neutral is the quiet ink). */
export const TONE_INK: Record<StateTone, string> = {
  neutral: "text-ink-2",
  ok: "text-ok-fg",
  warn: "text-warn-fg",
  bad: "text-bad-fg",
  info: "text-info-fg",
};

/** The glyph's colour: the -solid token (3:1 on white), for a mark that must be seen. */
export const TONE_MARK: Record<StateTone, string> = {
  neutral: "text-ink-3",
  ok: "text-ok-solid",
  warn: "text-warn-solid",
  bad: "text-bad-solid",
  info: "text-info-solid",
};
