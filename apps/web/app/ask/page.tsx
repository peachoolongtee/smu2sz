"use client";

import { useRouter } from "next/navigation";
import { HeadButton } from "@/components/chat/chat-panel";
import { ChatView } from "@/components/chat/chat-view";
import { FlowMark } from "@/components/chat/flow-mark";
import { CollapseIcon, NewChatIcon } from "@/components/icons";
import { askReturn, newConversation, openPanelOnArrival, useChat } from "@/lib/chat";
import { useI18n } from "@/lib/i18n";

/**
 * Ask FLOW as a full page (the owner's redesign, 17 Oct, option B): the side panel expanded into a centred column. It is the owner's conversation, the same one the panel shows
 * (lib/chat.ts keeps it per tab, so it survives a reload by the existing session rules); an empty one shows a greeting and four questions as cards. "Back to the side panel"
 * returns to the page Expand was pressed on with the panel open on the same conversation.
 * The conversation sits in one white card (the owner's choice, 18 Oct, option A): the page's waves stay outside it, the thread scrolls inside it and the composer is pinned at its
 * foot, so no answer is ever drawn over the background.
 */
export default function AskPage() {
  const { t } = useI18n();
  const router = useRouter();
  const conv = useChat().convs.OWNER;
  return (
    <div
      className="f-card f-card-white mx-auto flex h-[calc(100dvh-8.5rem)] min-h-[26rem] w-full max-w-3xl flex-col overflow-hidden border border-line max-sm:h-[calc(100dvh-12rem)]"
      data-testid="ask-page"
    >
      <header className="flex shrink-0 items-center gap-2 border-b border-line px-4 py-2.5 sm:px-5">
        <FlowMark size="md" />
        <h1 className="min-w-0 flex-1 truncate font-display text-xl font-bold tracking-[-0.01em] text-f-ink">{t("ask.title")}</h1>
        <HeadButton label={t("chat.new")} testId="chat-new" onClick={() => newConversation("OWNER")} disabled={conv.messages.length === 0 && !conv.busy && conv.sessionId === null}>
          <NewChatIcon width={18} height={18} />
        </HeadButton>
        <HeadButton
          label={t("ask.collapse")}
          testId="chat-collapse"
          onClick={() => {
            openPanelOnArrival();
            router.push(askReturn());
          }}
        >
          <CollapseIcon width={18} height={18} />
        </HeadButton>
      </header>
      <div className="flex min-h-0 flex-1 flex-col px-3 pb-3 pt-2 sm:px-5 sm:pb-4">
        <ChatView variant="full" />
      </div>
    </div>
  );
}
