"use client";

import { usePathname } from "next/navigation";
import { useEffect, useRef } from "react";
import { XIcon, ChatIcon } from "@/components/icons";
import { setPanelOpen, useChat } from "@/lib/chat";
import { useI18n } from "@/lib/i18n";
import { ChatView } from "./chat-view";

/**
 * Chat from every page: a floating button opens a slide-over with the same conversation as /chat.
 * A native modal <dialog> gives focus trapping, Esc to close and focus return for free.
 */
export function ChatPanel() {
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

  const onChatPage = pathname === "/chat";

  return (
    <>
      {onChatPage ? null : (
        <button
          type="button"
          aria-haspopup="dialog"
          onClick={() => setPanelOpen(true)}
          data-testid="chat-open"
          className="fixed bottom-28 right-4 z-40 inline-flex min-h-11 items-center gap-2 rounded-full bg-brand-600 px-4 text-sm font-semibold text-white shadow-lg hover:bg-brand-700 lg:bottom-6 lg:right-6"
        >
          <ChatIcon />
          {t("chat.open")}
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
        className="fixed inset-y-0 left-auto right-0 m-0 h-dvh max-h-dvh w-full max-w-lg border-l border-line bg-surface p-0 text-ink shadow-2xl backdrop:bg-ink/30 open:animate-[tl-slide-in_0.18s_ease-out]"
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
                className="grid size-10 place-items-center rounded-md border border-line-strong text-ink-2 hover:bg-subtle"
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
