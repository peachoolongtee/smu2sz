"use client";

import { useEffect, useId, useRef, useState } from "react";
import { ChatIcon } from "@/components/icons";
import { getWorklist } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { sendMessage, setPanelOpen } from "@/lib/chat";
import { useI18n } from "@/lib/i18n";
import { useAsync } from "@/lib/use-async";
import { useReducedMotion } from "@/lib/use-reduced-motion";

const TYPE_MS = 38;
const HOLD_MS = 1700;

/**
 * The placeholder's typewriter: each example is typed a letter at a time and held, then the next; the last, "Ask FLOW anything…", is typed and rests (no further cycling until the next page load).
 * It stops (showing the whole line) while the input has focus or holds text, and under reduced motion it is the resting line, whole, and nothing moves.
 */
function useTypewriter(lines: string[], paused: boolean, still: boolean): string {
  const [i, setI] = useState(0);
  const [n, setN] = useState(1);
  const last = lines.length - 1;
  const full = lines[Math.min(i, last)] ?? "";
  useEffect(() => {
    if (paused || still) return;
    if (n < full.length) {
      const id = window.setTimeout(() => setN(n + 1), TYPE_MS);
      return () => window.clearTimeout(id);
    }
    if (i >= last) return; // the resting line holds
    const id = window.setTimeout(() => {
      setI(i + 1);
      setN(1);
    }, HOLD_MS);
    return () => window.clearTimeout(id);
  }, [n, i, full, paused, still, last]);
  if (still) return lines[last] ?? "";
  if (paused) return full;
  return full.slice(0, n);
}

/**
 * Ask FLOW in the Business header (from `lg`; a phone keeps the bottom bar's "Ask"): a rounded 36 px input in the centre of the header (the viewport's centre), 420 px wide and 520 px on focus (a
 * little narrower at `lg` so the header fits), its placeholder a typewriter over six questions the chat answers, ending on "Ask FLOW anything…". Focus widens it from its centre (`--dur-fast`). Enter
 * sends what was typed to Ask FLOW (under the page's scope: the Home's address, see lib/chat-context.ts) and opens the Ask FLOW panel with the question already sent; the input clears. The icon at its
 * right opens the panel without a question; pressing it never blurs the input (so the input does not narrow under the pointer). The late-payment example names the first worklist customer in the
 * server's word when there is one.
 */
export function AskHeaderInput() {
  const { t, lang } = useI18n();
  const { token } = useAuth();
  const reduced = useReducedMotion();
  const [text, setText] = useState("");
  const [focused, setFocused] = useState(false);
  const id = useId();
  const ref = useRef<HTMLInputElement>(null);
  const worklist = useAsync(() => (token ? getWorklist(lang, null).catch(() => null) : Promise.resolve(null)), [lang, Boolean(token)]);
  const name = worklist.data?.customers[0]?.short || t("ask.ph.name");
  const placeholder = useTypewriter(
    [t("ask.ph.1"), t("ask.ph.2"), t("ask.ph.3"), t("ask.ph.4", { name }), t("ask.ph.5"), t("ask.ph.rest")],
    focused || text !== "",
    reduced,
  );
  function submit() {
    const q = text.trim();
    if (!q) return;
    setText("");
    setPanelOpen(true);
    void sendMessage(q, undefined, "OWNER");
  }
  return (
    <div className="relative z-20 hidden h-9 w-[340px] shrink-0 items-center justify-center lg:flex xl:w-[520px]">
      <form
        role="search"
        aria-label={t("ask.input")}
        onSubmit={(e) => {
          e.preventDefault();
          submit();
        }}
        className={`flex h-9 items-center rounded-pill border border-line-ui bg-card pl-4 pr-1 transition-[width] duration-(--dur-fast) focus-within:border-ink ${focused ? "w-full" : "w-[300px] xl:w-[420px]"}`}
        data-testid="ask-header"
      >
        <label htmlFor={id} className="sr-only">
          {t("ask.input")}
        </label>
        <input
          id={id}
          ref={ref}
          type="text"
          value={text}
          maxLength={4000}
          autoComplete="off"
          placeholder={placeholder}
          onChange={(e) => setText(e.target.value)}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          onKeyDown={(e) => {
            // Enter sends; Enter while an IME (Chinese input) is composing only confirms the candidate.
            if (e.key === "Enter" && e.nativeEvent.isComposing) e.preventDefault();
          }}
          className="h-full min-w-0 flex-1 bg-transparent pr-2 text-sm text-ink outline-none placeholder:text-ink-3"
          data-testid="ask-input"
        />
        <button
          type="button"
          aria-haspopup="dialog"
          aria-label={t("chat.open")}
          onMouseDown={(e) => e.preventDefault()}
          onClick={() => setPanelOpen(true)}
          data-testid="chat-open"
          className="motion-press grid size-7 shrink-0 place-items-center rounded-pill text-ink hover:bg-panel"
        >
          <ChatIcon className="size-4" />
        </button>
      </form>
    </div>
  );
}
