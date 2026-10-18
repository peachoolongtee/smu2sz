"use client";

import { usePathname, useRouter } from "next/navigation";
import { Suspense, useEffect, useRef, type ReactNode } from "react";
import { XIcon, ChatIcon, ExpandIcon, NewChatIcon } from "@/components/icons";
import { newConversation, setAskReturn, setPanelOpen, takePanelOnArrival, useChat } from "@/lib/chat";
import { useClearScopeOnRouteChange } from "@/lib/chat-scope";
import { useI18n } from "@/lib/i18n";
import { useBusinessShell } from "@/lib/use-business-today";
import { ChatView } from "./chat-view";
import { FlowMark } from "./flow-mark";

/**
 * Chat from every page: a quiet outline pill (never a filled button: the page's commit area owns the one filled primary, ticket #129) opens a slide-over with the same conversation as /chat
 * and /ask. The button never floats over the content: on a phone it is the last cell of the bottom bar (the Business tab bar and the Demo stepper leave it free), from `sm` a pill above
 * the bar with the page's bottom padding sized to clear it (`.ask-trigger` and `.dock-pad` in globals.css). A native modal <dialog> gives focus trapping, Esc to close and focus return.
 *
 * Its header (the owner's redesign, 17 Oct): FLOW's mark and "Ask FLOW", then three icon buttons, each named and with a tooltip: New conversation (ends the server session, lib/chat.ts),
 * Open as a full page (/ask, the same conversation), Close.
 */
/** Renders nothing; it lives in its own Suspense because it reads the address's search keys. */
function ScopeRouteWatcher() {
  useClearScopeOnRouteChange();
  return null;
}

/** A header icon button: its name is its label for a screen reader and its tooltip for a pointer. */
export function HeadButton({ label, onClick, testId, disabled, children }: { label: string; onClick: () => void; testId: string; disabled?: boolean; children: ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-label={label}
      title={label}
      data-testid={testId}
      className="motion-press grid size-10 place-items-center rounded-pill text-ink-2 hover:bg-subtle hover:text-ink disabled:cursor-not-allowed disabled:opacity-40 touch:size-11"
    >
      {children}
    </button>
  );
}

export function ChatPanel({ headerEntry = false }: { headerEntry?: boolean } = {}) {
  const { t } = useI18n();
  const pathname = usePathname();
  const router = useRouter();
  const business = useBusinessShell();
  const { panelOpen, role, convs } = useChat();
  const ref = useRef<HTMLDialogElement>(null);
  // The Business shell shows the owner's conversation whatever role a Demo visit left (as ChatView does).
  const shown = business ? "OWNER" : role;
  const conv = convs[shown];

  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (panelOpen && !d.open) d.showModal();
    if (!panelOpen && d.open) d.close();
  }, [panelOpen]);

  // The Ask FLOW page is the panel expanded: the panel never opens over it, and it closes when the page opens.
  const onAskPage = pathname === "/ask";
  useEffect(() => {
    if (onAskPage) setPanelOpen(false);
    else if (takePanelOnArrival()) setPanelOpen(true); // "Back to the side panel" from the Ask FLOW page
  }, [onAskPage, pathname]);

  // The Business header carries Ask FLOW from `lg` (components/ask-header.tsx): no floating pill there; on the chat pages themselves there is none either.
  const onChatPage = pathname === "/chat" || onAskPage || headerEntry;

  function expand() {
    setAskReturn(`${window.location.pathname}${window.location.search}`);
    setPanelOpen(false);
    router.push("/ask");
  }

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
            <div className="flex items-center gap-2 border-b border-line py-2 pl-4 pr-2">
              <FlowMark />
              <h2 id="chat-panel-title" className="min-w-0 flex-1 truncate text-base font-semibold">
                {t("chat.panel")}
              </h2>
              <HeadButton label={t("chat.new")} testId="chat-new" onClick={() => newConversation(shown)} disabled={conv.messages.length === 0 && !conv.busy && conv.sessionId === null}>
                <NewChatIcon width={18} height={18} />
              </HeadButton>
              <HeadButton label={t("ask.expand")} testId="chat-expand" onClick={expand}>
                <ExpandIcon width={18} height={18} />
              </HeadButton>
              <HeadButton label={t("chat.close")} testId="chat-close" onClick={() => setPanelOpen(false)}>
                <XIcon width={18} height={18} />
              </HeadButton>
            </div>
            <div className="min-h-0 flex-1 px-3 pb-3 pt-2 sm:px-4">
              <ChatView variant="panel" />
            </div>
          </div>
        ) : null}
      </dialog>
    </>
  );
}
