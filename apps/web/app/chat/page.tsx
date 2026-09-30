"use client";

import { ChatView } from "@/components/chat/chat-view";
import { PageHeader } from "@/components/ui";
import { useI18n } from "@/lib/i18n";

export default function ChatPage() {
  const { t } = useI18n();
  return (
    <>
      <PageHeader title={t("chat.title")} subtitle={t("chat.subtitle")} />
      <div className="max-w-3xl">
        <ChatView variant="page" />
      </div>
    </>
  );
}
