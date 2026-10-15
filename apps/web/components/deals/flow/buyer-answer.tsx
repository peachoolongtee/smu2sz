"use client";

import { useEffect, useId, useState } from "react";
import { useRouter } from "next/navigation";
import { Button, ErrorState, LoadingBlock, textareaClass } from "@/components/ui";
import { ActionGroup } from "@/components/ui/action-group";
import { buyerAccepted, buyerReply, getBuyerMessage, messageRefusal } from "@/lib/api";
import { bump } from "@/lib/demo-store";
import { errorText } from "@/lib/error-text";
import { useI18n } from "@/lib/i18n";
import type { BuyerAcceptedResult, BuyerReplyResult } from "@/lib/types";
import { useAsync } from "@/lib/use-async";
import { quietLink } from "./flow-parts";

/** A buyer's reply, as POST /offers/{id}/buyer-reply bounds one (SEC-17). */
export const REPLY_MAX = 4000;

/** The server's sentence for a pasted reply, kept for the reply's own deal, which the page opens next (the answered deal's pane is gone by then). */
const arrivals = new Map<string, string>();
export const arrivalText = (decision: string): string | null => arrivals.get(decision) ?? null;

/**
 * A deal waiting for the buyer's answer to a counter the owner sent outside FLOW (record state AWAITING_BUYER): the buyer's answer is the owner's to record, in one of two ways.
 *   "The buyer accepted": a review (the message that was sent, in the language it was sent in, and the day it is open until), then one button that records the yes. The agreement is made
 *     under the owner's authority (or queued for approval where its tier asks); the server's receipt and status come back (`onAccepted`).
 *   "Paste the buyer's reply": the reply as the buyer wrote it (at most 4000 characters). The server reads it as a request of its own and this deal closes as answered; the page then opens
 *     that request (`reply_href`). A reply with no terms in it is refused (NO_TERMS_IN_REPLY) and nothing is stored.
 * Both bind to the sent message: the verdict, the counter and the message's hash come from the message read (its `offered` record). Every sentence and label is the server's or the dictionary's.
 */
export function BuyerAnswer({
  offerId,
  counterId,
  onAccepted,
  onReplied,
  onBusy,
}: {
  offerId: string;
  counterId: string;
  onAccepted: (r: BuyerAcceptedResult) => void;
  onReplied: (r: BuyerReplyResult) => void;
  onBusy?: (busy: boolean) => void;
}) {
  const { t, lang } = useI18n();
  const uid = useId();
  const router = useRouter();
  const read = useAsync(() => getBuyerMessage(offerId, counterId, lang), [offerId, counterId, lang]);
  const m = read.data;
  const sentLang = m?.offered?.lang ?? lang;
  // The message as it was sent, in the buyer's language (the page's read carries the words around it).
  const sentRead = useAsync(() => (m && sentLang !== lang ? getBuyerMessage(offerId, counterId, sentLang) : Promise.resolve(null)), [offerId, counterId, sentLang, lang, Boolean(m)]);
  const sentText = sentLang === lang ? m?.text : sentRead.data?.text;
  const [open, setOpen] = useState<"accept" | "reply" | null>(null);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [refused, setRefused] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    onBusy?.(busy);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- reports the flight, not the callback
  }, [busy]);

  const show = (which: "accept" | "reply" | null) => {
    setOpen(which);
    setRefused(null);
    setError(null);
  };

  async function run<T>(call: () => Promise<T>, done: (r: T) => void) {
    setBusy(true);
    setRefused(null);
    setError(null);
    try {
      done(await call());
    } catch (e) {
      const no = messageRefusal(e);
      if (no) setRefused(no.message_when ?? no.message);
      else setError(errorText(e, t));
    } finally {
      setBusy(false);
    }
  }

  const accept = () =>
    run(
      () => buyerAccepted(offerId, counterId, { verdict_id: m!.verdict_id, state_version: m!.state_version, message_hash: m!.offered!.message_hash }),
      (r) => {
        onAccepted(r);
        bump();
      },
    );
  const reply = () =>
    run(
      () => buyerReply(offerId, { verdict_id: m!.verdict_id, counter_id: counterId, text }),
      (r) => {
        arrivals.set(r.reply_decision_id, r.message_when);
        onReplied(r);
        bump();
        router.push(r.reply_href);
      },
    );

  if (read.error && !m) {
    // The message cannot be read (the books moved, the offer closed): the server's words when it refused, Retry otherwise.
    const no = messageRefusal(read.error);
    return no ? (
      <p role="status" className="max-w-[68ch] text-sm text-ink-2" data-testid="buyer-answer-closed">
        {no.message_when ?? no.message}
      </p>
    ) : (
      <ErrorState error={errorText(read.error, t)} onRetry={read.reload} />
    );
  }
  if (!m) return <LoadingBlock rows={2} label={t("bm.reading")} />;
  if (!m.offered) return null;
  const ready = Boolean(text.trim()) && text.length <= REPLY_MAX;
  return (
    <div className="space-y-4" data-testid="buyer-answer">
      {open === null ? (
        <ActionGroup testId="buyer-answer-actions" label={t("bm.answer")}>
          <Button variant="primary" onClick={() => show("accept")} data-testid="buyer-accepted-open">
            {m.accepted_label}
          </Button>
          <Button onClick={() => show("reply")} data-testid="buyer-reply-open">
            {m.reply_label}
          </Button>
        </ActionGroup>
      ) : open === "accept" ? (
        <section aria-labelledby={`${uid}-accept`} className="space-y-3" data-testid="buyer-accepted-review">
          <h3 id={`${uid}-accept`} className="font-display text-base font-extrabold leading-snug text-ink">
            {t("bm.accept.title")}
          </h3>
          <div>
            <h4 className="mb-1 text-supporting font-bold text-ink-2">{t("bm.sentAs")}</h4>
            {sentText ? (
              <p
                lang={sentLang === "zh" ? "zh-CN" : "en"}
                className="m-0 max-w-[72ch] whitespace-pre-wrap break-words rounded-tile border border-line bg-subtle px-3.5 py-3 text-[15px] leading-relaxed text-ink"
                data-testid="buyer-accepted-message"
              >
                {sentText}
              </p>
            ) : (
              <LoadingBlock rows={2} />
            )}
          </div>
          <p className="text-sm" data-testid="buyer-accepted-until">
            <span className="mr-2 text-supporting font-bold text-ink-3">{t("bm.validUntil")}</span>
            <span className="text-ink">{m.offered.valid_until_when}</span>
          </p>
          <ActionGroup testId="buyer-accepted-commit" label={t("bm.accept.title")}>
            <Button variant="primary" loading={busy} onClick={() => void accept()} data-testid="buyer-accepted-confirm">
              {t("bm.accept.confirm")}
            </Button>
            <button type="button" onClick={() => show(null)} disabled={busy} className={`${quietLink} disabled:opacity-50`} data-testid="buyer-answer-cancel">
              {t("bm.cancel")}
            </button>
          </ActionGroup>
        </section>
      ) : (
        <section aria-labelledby={`${uid}-reply`} className="space-y-3" data-testid="buyer-reply-form">
          <h3 id={`${uid}-reply`} className="font-display text-base font-extrabold leading-snug text-ink">
            {t("bm.reply.title")}
          </h3>
          <label htmlFor={`${uid}-reply-text`} className="block text-sm font-medium text-ink-2">
            {t("bm.reply.label")}
          </label>
          <textarea
            id={`${uid}-reply-text`}
            value={text}
            maxLength={REPLY_MAX}
            rows={6}
            onChange={(e) => setText(e.target.value)}
            aria-describedby={`${uid}-reply-count`}
            className={`${textareaClass} w-full max-w-[72ch]`}
            data-testid="buyer-reply-text"
          />
          <p id={`${uid}-reply-count`} className="text-supporting tabular-nums text-ink-3" data-testid="buyer-reply-count">
            {t("bm.reply.count", { n: text.length, max: REPLY_MAX })}
          </p>
          <ActionGroup testId="buyer-reply-commit" label={t("bm.reply.title")}>
            <Button variant="primary" loading={busy} disabled={!ready} onClick={() => void reply()} data-testid="buyer-reply-submit">
              {t("bm.reply.submit")}
            </Button>
            <button type="button" onClick={() => show(null)} disabled={busy} className={`${quietLink} disabled:opacity-50`} data-testid="buyer-answer-cancel">
              {t("bm.cancel")}
            </button>
          </ActionGroup>
        </section>
      )}
      {refused ? (
        <p role="alert" className="max-w-[68ch] rounded-tile border border-warn-line bg-warn-bg px-3.5 py-2.5 text-sm text-ink" data-testid="buyer-answer-refused">
          {refused}
        </p>
      ) : null}
      {error ? <ErrorState error={error} /> : null}
    </div>
  );
}
