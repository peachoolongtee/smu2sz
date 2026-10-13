"use client";

import { useEffect, useId, useRef, useState } from "react";
import { ChatIcon } from "@/components/icons";
import { sendMessage, setPanelOpen } from "@/lib/chat";
import type { DictKey } from "@/lib/dictionary";
import { useI18n } from "@/lib/i18n";
import { useReducedMotion } from "@/lib/use-reduced-motion";

const EXAMPLES: DictKey[] = ["ask.ph.1", "ask.ph.2", "ask.ph.3"];
const TYPE_MS = 42;
const HOLD_MS = 1900;

/**
 * The placeholder's typewriter: each example is typed a letter at a time, held, then the next one is typed. It stops (and shows the whole example) while the input has focus or holds text, and
 * there is no animation at all under reduced motion (the first example, whole). The words are the dictionary's (en and zh); the placeholder is a hint, the input's name is "Ask FLOW".
 */
function useTypewriter(
  examples: string[],
  paused: boolean,
  still: boolean,
): string {
  const [i, setI] = useState(0);
  const [n, setN] = useState(0);
  const full = examples[i % examples.length] ?? "";
  useEffect(() => {
    if (paused || still) return;
    if (n < full.length) {
      const id = window.setTimeout(() => setN(n + 1), TYPE_MS);
      return () => window.clearTimeout(id);
    }
    const id = window.setTimeout(() => {
      setI((v) => (v + 1) % examples.length);
      setN(0);
    }, HOLD_MS);
    return () => window.clearTimeout(id);
  }, [n, full, paused, still, examples.length]);
  if (still || paused) return full;
  return full.slice(0, n);
}

/**
 * Ask FLOW in the Business header (from `lg`; a phone keeps the bottom bar's "Ask"): a rounded input left of the mode switch, its placeholder cycling through example questions as a quiet typewriter.
 * Focus widens it (`--dur-fast`). Enter sends what was typed to Ask FLOW (under the page's scope: the Home's address, see lib/chat-context.ts) and opens the Ask FLOW panel with the question already
 * sent; the input clears. The icon opens the panel without a question (it is the entry the floating pill used to be).
 */
export function AskHeaderInput() {
  const { t } = useI18n();
  const reduced = useReducedMotion();
  const [text, setText] = useState("");
  const [focused, setFocused] = useState(false);
  const id = useId();
  const ref = useRef<HTMLInputElement>(null);
  const placeholder = useTypewriter(
    EXAMPLES.map((k) => t(k)),
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
  // The slot keeps the closed width and the right edge, so the header around it never moves: focus widens the input to the left over the quiet items beside it, and the opener
  // sits at the right edge (a pointer that presses it blurs the input, which narrows again, and must still be over it when the button is released).
  return (
    <div className="relative z-20 hidden h-10 w-56 shrink-0 lg:block xl:w-72">
      <form
        role="search"
        aria-label={t("ask.input")}
        onSubmit={(e) => {
          e.preventDefault();
          submit();
        }}
        className={`absolute right-0 top-0 flex h-10 items-center rounded-pill border border-line-ui bg-card pl-4 pr-1 transition-[width] duration-(--dur-fast) focus-within:border-ink ${focused ? "w-[22rem] xl:w-[26rem]" : "w-full"}`}
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
            if (e.key === "Enter" && e.nativeEvent.isComposing)
              e.preventDefault();
          }}
          className="h-full min-w-0 flex-1 bg-transparent pr-2 text-sm text-ink outline-none placeholder:text-ink-3"
          data-testid="ask-input"
        />
        <button
          type="button"
          aria-haspopup="dialog"
          aria-label={t("chat.open")}
          onClick={() => setPanelOpen(true)}
          data-testid="chat-open"
          className="motion-press grid size-8 shrink-0 place-items-center rounded-pill text-ink hover:bg-panel"
        >
          <ChatIcon className="size-4" />
        </button>
      </form>
    </div>
  );
}
