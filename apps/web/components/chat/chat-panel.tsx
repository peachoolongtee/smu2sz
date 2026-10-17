"use client";

import { usePathname } from "next/navigation";
import { Suspense, useEffect, useRef } from "react";
import { XIcon, ChatIcon } from "@/components/icons";
import { setPanelOpen, useChat } from "@/lib/chat";
import { useClearScopeOnRouteChange } from "@/lib/chat-scope";
import { useI18n } from "@/lib/i18n";
import { ChatView } from "./chat-view";

/**
 * Chat from every page: a quiet outline pill (never a filled button: the page's commit area owns the one filled primary, ticket #129) opens a slide-over with the same conversation as /chat. The button never floats over the content:
 * on a phone it is the last cell of the bottom bar (the Business tab bar and the Demo stepper leave it free), from `sm` a pill
 * above the bar with the page's bottom padding sized to clear it (`.ask-trigger` and `.dock-pad` in globals.css).
 * A native modal <dialog> gives focus trapping, Esc to close and focus return for free.
 */
/** Renders nothing; it lives in its own Suspense because it reads the address's search keys. */
function ScopeRouteWatcher() {
  useClearScopeOnRouteChange();
  return null;
}

export function ChatPanel({ headerEntry = false }: { headerEntry?: boolean } = {}) {
  const { t } = useI18n();
  const pathname = usePathname();
  const { panelOpen } = useChat();
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (panelOpen && !d.open) d.showModal();
    if (!panelOpen && d.open) d.close();
  }, [panelOpen]);

  // The Business header carries Ask FLOW from `lg` (components/ask-header.tsx): no floating pill there; on the chat page itself there is none either.
  const onChatPage = pathname === "/chat" || headerEntry;

  return (
    <>
      <Suspense fallback={null}>
        <ScopeRouteWatcher />
      </Suspense>
      {onChatPage ? null : (
        <button
          type="button"
          aria-haspopup="dialog"
          aria-label={t("chat.open")}
          onClick={() => setPanelOpen(true)}
          data-testid="chat-open"
          className="ask-trigger motion-press fixed z-40 flex min-h-10 flex-col items-center justify-center gap-0.5 text-meta font-medium text-ink-2 hover:text-ink touch:min-h-11 sm:flex-row sm:gap-1.5 sm:whitespace-nowrap sm:rounded-pill sm:border sm:border-line-ui sm:bg-card sm:px-4 sm:text-sm sm:text-ink sm:shadow-f sm:hover:bg-panel sm:hover:text-ink"
        >
          <ChatIcon className="size-5 text-brand-600 sm:size-4" />
          {/* A phone's cell is 56 px wide: the short word there, the full name from sm (the button's name is always the full one). */}
          <span aria-hidden className="sm:hidden">{t("chat.open.short")}</span>
          <span aria-hidden className="ask-label hidden sm:inline">{t("chat.open")}</span>
        </button>
      )}
      <dialog
        ref={ref}
        aria-labelledby="chat-panel-title"
        data-testid="chat-panel"
        onClose={() => setPanelOpen(false)}
        onClick={(e) => {
          if (e.target === e.currentTarget) setPanelOpen(false);
        }}
        className="fixed inset-y-0 left-auto right-0 m-0 h-dvh max-h-dvh w-full max-w-[min(32rem,100vw)] overflow-x-hidden border-l border-line bg-surface p-0 text-ink outline-none focus-own shadow-pop backdrop:bg-ink/30 motion-panel"
      >
        {panelOpen ? (
          <div className="flex h-full flex-col">
            <div className="flex items-center justify-between gap-3 border-b border-line px-4 py-3">
              <h2 id="chat-panel-title" className="text-base font-semibold">
                {t("chat.panel")}
              </h2>
              <button
                type="button"
                onClick={() => setPanelOpen(false)}
                aria-label={t("chat.close")}
                data-testid="chat-close"
                className="motion-press grid size-10 place-items-center rounded-pill border border-line-ui text-ink-2 hover:bg-subtle touch:size-11"
              >
                <XIcon />
              </button>
            </div>
            <div className="min-h-0 flex-1 p-4">
              <ChatView variant="panel" />
            </div>
          </div>
        ) : null}
      </dialog>
    </>
  );
}
