"use client";

import Link from "next/link";
import { useState } from "react";
import { AssistantTurn } from "@/components/chat/assistant-turn";
import { approvalHref } from "@/components/operation-result";
import { Badge, Button, Card, ErrorState, LoadingBlock } from "@/components/ui";
import { getApprovals, nlOpener } from "@/lib/api";
import { appendOwnerOpener, ensureOwnerSession, sendOwnerTurn, useChat } from "@/lib/chat";
import { bump } from "@/lib/demo-store";
import { useI18n } from "@/lib/i18n";
import type { NlResponse } from "@/lib/types";
import { useAsync } from "@/lib/use-async";

/**
 * The agent speaks first. POST /nl/opener runs on load and after every clock advance or executed action; its pending cure
 * waits in the owner's chat session, so "Go ahead" here is the same turn as "go ahead" in the chat panel.
 */
export function NeedsCard({ answer, onAnswer }: { answer: NlResponse | null; onAnswer: (r: NlResponse | null) => void }) {
  const { t, lang } = useI18n();
  const opener = useAsync(async () => {
    const r = await nlOpener(ensureOwnerSession(), lang);
    if (r.has_news) appendOwnerOpener(r);
    return r;
  }, [lang]);
  // A cure already queued for the owner (an alert's operation waiting in the approvals queue): the opener must not offer to queue it again.
  const approvals = useAsync(getApprovals, []);
  const queued = approvals.data?.find((a) => a.status === "PENDING" && Boolean(a.op_id?.startsWith("alert:"))) ?? null;
  const [sending, setSending] = useState(false);
  const conv = useChat().convs.OWNER;
  const last = conv.messages.at(-1);
  const sendError = last?.from === "error" ? last.text : null;
  const r = opener.data;

  async function send(text: string, display: string) {
    setSending(true);
    try {
      const reply = await sendOwnerTurn(text, display);
      if (reply) onAnswer(reply);
    } finally {
      setSending(false);
      bump();
    }
  }

  const zh = r?.lang === "zh";
  return (
    <Card
      id="home-needs"
      title={t("home.needs")}
      subtitle={t("home.needs.sub")}
      tone={r?.has_news ? "warn" : undefined}
      actions={r ? <Badge tone="brand">{t("home.needs.agent")}</Badge> : undefined}
    >
      <div className="space-y-4">
        {answer ? (
          <section aria-label={t("home.needs.result")} data-testid="home-answer">
            <h3 className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-ink-3">{t("home.needs.result")}</h3>
            <AssistantTurn response={answer} active={false} busy={false} onSend={() => undefined} />
          </section>
        ) : null}

        {opener.error ? (
          <ErrorState error={opener.error} onRetry={opener.reload} />
        ) : !r ? (
          <LoadingBlock rows={2} />
        ) : r.has_news ? (
          <div className="space-y-3" data-testid="home-opener" data-news="true">
            <p className="whitespace-pre-wrap break-words text-base font-medium leading-relaxed text-ink" data-testid="home-opener-reply">
              {r.reply}
            </p>
            {r.awaiting_confirmation && queued ? (
              <div className="rounded-md border border-warn-line bg-warn-bg px-3 py-2 text-sm text-warn-fg" role="status" data-testid="home-waiting-approval">
                <p className="font-semibold">{t("alerts.waiting", { id: queued.id })}</p>
                <p className="mt-0.5 text-xs">{t("alerts.waiting.body")}</p>
                <Link href={approvalHref(queued.id)} className="mt-1 inline-block text-xs font-medium underline underline-offset-2" data-testid="home-approval-link">
                  {t("alerts.waiting.open")}
                </Link>
              </div>
            ) : r.awaiting_confirmation ? (
              <div className="flex flex-wrap gap-2">
                <Button variant="primary" loading={sending} disabled={sending} onClick={() => void send(zh ? "执行" : "go ahead", t("chat.goahead"))} data-testid="home-goahead">
                  {t("chat.goahead")}
                </Button>
                <Button disabled={sending} onClick={() => void send(zh ? "取消" : "cancel", t("home.needs.notNow"))} data-testid="home-notnow">
                  {t("home.needs.notNow")}
                </Button>
              </div>
            ) : null}
          </div>
        ) : (
          <p className="text-sm text-ink-3" data-testid="home-opener" data-news="false">
            {r.reply}
          </p>
        )}

        {sendError ? <ErrorState error={sendError} /> : null}
      </div>
    </Card>
  );
}
