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
 */
export default function AskPage() {
  const { t } = useI18n();
  const router = useRouter();
  const conv = useChat().convs.OWNER;
  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-3" data-testid="ask-page">
      <header className="flex items-center gap-2">
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
      <ChatView variant="full" />
    </div>
  );
}
