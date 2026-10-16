"use client";

import { useEffect, useId, useState, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { Disclosure } from "@/components/business/kit";
import { Button, ButtonLink, ErrorState, textareaClass } from "@/components/ui";
import { ActionGroup } from "@/components/ui/action-group";
import { ArrowsExchangeIcon, CheckIcon, ClockIcon, XCircleIcon, XIcon } from "@/components/icons";
import { buyerAccepted, buyerDeclined, buyerReply, getBuyerMessage, messageRefusal } from "@/lib/api";
import { bump } from "@/lib/demo-store";
import { errorText } from "@/lib/error-text";
import { useI18n } from "@/lib/i18n";
import type { BuyerAcceptedResult, BuyerDeclinedResult, BuyerReplyResult, DealHistoryEntry, DeclineReason, OutboundView } from "@/lib/types";
import { HistoryList } from "./deal-history";

/** A buyer's reply, as POST /offers/{id}/buyer-reply bounds one (SEC-17). */
export const REPLY_MAX = 4000;

/** The server's sentence for a pasted reply, kept for the reply's own deal, which the page opens next (the answered deal's pane is gone by then). */
const arrivals = new Map<string, string>();
export const arrivalText = (decision: string): string | null => arrivals.get(decision) ?? null;

type Answer = "accept" | "counter" | "decline";

/** The tile colours: green the buyer's yes, lavender their counter, neutral their no (the FLOW palette). */
const TILE: Record<Answer, { on: string; icon: string }> = {
  accept: { on: "border-f-green-ink bg-f-green", icon: "bg-f-green text-f-green-ink" },
  counter: { on: "border-f-purple bg-f-purple-soft", icon: "bg-f-purple-soft text-f-purple-ink" },
  decline: { on: "border-f-muted bg-subtle", icon: "bg-subtle text-ink-2" },
};

const card = "rounded-[20px] border border-line bg-card p-5 sm:p-6";

/**
 * A deal waiting for the buyer's answer to the counter the owner sent outside FLOW (record state AWAITING_BUYER; the record's `outbound`, answer null): a lavender banner (who it waits for,
 * when it closes, how far through the window it is, what happens if nobody answers), the "You sent" card (the counter's terms and the message as it was sent), and the question with its
 * three answers as tiles. Picking a tile opens what recording it does, with its one filled button:
 *   accept   the agreement's terms, cost and authority, then POST .../buyer-accepted (bound to the verdict, the books and the sent message);
 *   counter  the buyer's reply as they wrote it (at most 4000 characters), then POST /offers/{id}/buyer-reply: it becomes a request of its own, which the page opens;
 *   decline  the reason they gave, if any, as a code (NO_REASON by default), and what is funded instead, then POST .../buyer-declined.
 * Every sentence and label is the server's (the `outbound` block), but for the dictionary's few headings.
 */
export function OutboundWaiting({
  offerId,
  outbound,
  onAccepted,
  onDeclined,
  onReplied,
  onBusy,
}: {
  offerId: string;
  outbound: OutboundView;
  onAccepted: (r: BuyerAcceptedResult) => void;
  onDeclined: (r: BuyerDeclinedResult) => void;
  onReplied: (r: BuyerReplyResult) => void;
  onBusy?: (busy: boolean) => void;
}) {
  const { t, lang } = useI18n();
  const uid = useId();
  const router = useRouter();
  const actions = outbound.actions;
  const [open, setOpen] = useState<Answer | null>(null);
  const [text, setText] = useState("");
  const [reason, setReason] = useState<DeclineReason>("NO_REASON");
  const [busy, setBusy] = useState(false);
  const [refused, setRefused] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    onBusy?.(busy);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- reports the flight, not the callback
  }, [busy]);

  const pick = (a: Answer) => {
    setOpen((x) => (x === a ? null : a));
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
      async () => {
        // The books' version the owner records the yes on: the message read carries it (the record does not).
        const m = await getBuyerMessage(offerId, outbound.counter_id, outbound.lang, lang);
        return buyerAccepted(offerId, outbound.counter_id, { verdict_id: outbound.verdict_id, state_version: m.state_version, message_hash: outbound.message_hash });
      },
      (r) => {
        onAccepted(r);
        bump();
      },
    );
  const decline = () =>
    run(
      () => buyerDeclined(offerId, outbound.counter_id, { verdict_id: outbound.verdict_id, message_hash: outbound.message_hash, reason }),
      (r) => {
        onDeclined(r);
        bump();
      },
    );
  const reply = () =>
    run(
      () => buyerReply(offerId, { verdict_id: outbound.verdict_id, counter_id: outbound.counter_id, text }),
      (r) => {
        arrivals.set(r.reply_decision_id, r.message_when);
        onReplied(r);
        bump();
        router.push(r.reply_href);
      },
    );

  const progress = Math.round(Math.min(1, Math.max(0, outbound.progress ?? 0)) * 100);
  const ready = Boolean(text.trim()) && text.length <= REPLY_MAX;
  const tiles: { key: Answer; label: string; hint: string; icon: ReactNode }[] = actions
    ? [
        { key: "accept", label: actions.accept.label, hint: actions.accept.hint_text, icon: <CheckIcon width={18} height={18} /> },
        { key: "counter", label: actions.counter.label, hint: actions.counter.hint_text, icon: <ArrowsExchangeIcon width={18} height={18} /> },
        { key: "decline", label: actions.decline.label, hint: actions.decline.hint_text, icon: <XIcon width={18} height={18} /> },
      ]
    : [];
  return (
    <div className="space-y-4" data-testid="outbound-waiting">
      <section className="rounded-[20px] bg-f-purple-soft px-5 py-4 text-f-purple-ink sm:px-6" data-testid="outbound-banner" aria-labelledby={`${uid}-banner`}>
        <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
          <h2 id={`${uid}-banner`} className="flex items-center gap-2 font-display text-base font-extrabold">
            <ClockIcon width={18} height={18} />
            {outbound.title_text}
          </h2>
          {outbound.closes_text ? (
            <p className="text-sm font-semibold tabular-nums" data-testid="outbound-closes">
              {outbound.closes_text}
            </p>
          ) : null}
        </div>
        <div className="mt-3 h-1.5 overflow-hidden rounded-pill bg-card/70" role="progressbar" aria-label={outbound.closes_text ?? outbound.title_text} aria-valuemin={0} aria-valuemax={100} aria-valuenow={progress} data-testid="outbound-progress">
          <div className="h-full rounded-pill bg-f-purple" style={{ width: `${Math.max(progress, 3)}%` }} />
        </div>
        <p className="mt-2.5 text-sm" data-testid="outbound-text">
          {outbound.text}
        </p>
      </section>

      <section className={card} aria-labelledby={`${uid}-sent`} data-testid="outbound-sent">
        <h3 id={`${uid}-sent`} className="text-supporting font-bold text-ink-3">
          {t("bm.youSent")}
        </h3>
        <p className="mt-1 text-[15px] font-semibold text-ink" data-testid="outbound-sent-text">
          {outbound.sent_text}
        </p>
        {outbound.terms.length ? (
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-ink-2" data-testid="outbound-sent-terms">
            {outbound.terms.map((x, i) => (
              <li key={i}>{x}</li>
            ))}
          </ul>
        ) : null}
        {outbound.message_same && outbound.message_text ? (
          <Disclosure testId="outbound-sent-message" summary={t("bm.viewSent")} className="mt-3 border-t border-line pt-1">
            <p lang={outbound.lang === "zh" ? "zh-CN" : "en"} className="mt-2 max-w-[72ch] whitespace-pre-wrap break-words rounded-tile border border-line bg-card px-4 py-3 text-[15px] leading-relaxed text-ink" data-testid="outbound-sent-message-text">
              {outbound.message_text}
            </p>
          </Disclosure>
        ) : null}
      </section>

      {actions ? (
        <section className={card} aria-labelledby={`${uid}-q`} data-testid="outbound-answer">
          <h3 id={`${uid}-q`} className="font-display text-base font-extrabold text-ink">
            {actions.question_text}
          </h3>
          <div className="mt-3 grid gap-3 sm:grid-cols-3" role="group" aria-labelledby={`${uid}-q`}>
            {tiles.map((x) => {
              const on = open === x.key;
              return (
                <button
                  key={x.key}
                  type="button"
                  aria-pressed={on}
                  aria-controls={`${uid}-confirm`}
                  disabled={busy}
                  onClick={() => pick(x.key)}
                  className={`motion-press flex min-h-20 items-start gap-3 rounded-tile border px-4 py-3 text-left transition-colors disabled:opacity-60 ${on ? TILE[x.key].on : "border-line bg-card hover:border-ink-3"}`}
                  data-testid={`outbound-tile-${x.key}`}
                >
                  <span aria-hidden className={`grid size-9 shrink-0 place-items-center rounded-pill ${TILE[x.key].icon}`}>
                    {x.icon}
                  </span>
                  <span className="min-w-0">
                    <span className="block text-[15px] font-bold text-ink">{x.label}</span>
                    <span className="mt-0.5 block text-sm text-ink-2">{x.hint}</span>
                  </span>
                </button>
              );
            })}
          </div>

          <div id={`${uid}-confirm`} className="mt-4 empty:hidden">
            {open === "accept" ? (
              <div className="space-y-3 border-t border-line pt-4" data-testid="outbound-confirm-accept">
                {actions.accept.review?.terms?.length ? (
                  <dl className="m-0 divide-y divide-line rounded-tile border border-line" data-testid="outbound-accept-terms">
                    {actions.accept.review.terms
                      .filter((r) => r.value_text)
                      .map((r) => (
                        <div key={r.key} className="grid gap-x-4 px-4 py-2.5 sm:grid-cols-[12rem_1fr]">
                          <dt className="text-sm font-semibold text-ink-2">{r.label}</dt>
                          <dd className="m-0 text-sm text-ink">{r.value_text}</dd>
                        </div>
                      ))}
                  </dl>
                ) : actions.accept.terms.length ? (
                  <ul className="list-disc space-y-1 pl-5 text-sm text-ink" data-testid="outbound-accept-terms">
                    {actions.accept.terms.map((x, i) => (
                      <li key={i}>{x}</li>
                    ))}
                  </ul>
                ) : null}
                {actions.accept.review?.cost_display ? (
                  <p className="text-sm" data-testid="outbound-accept-cost">
                    <span className={`font-bold tabular-nums ${actions.accept.review.needs_owner ? "text-ink" : "text-f-green-ink"}`}>{actions.accept.review.cost_display}</span>
                    {actions.accept.review.cost_note ? <span className="text-ink-2"> · {actions.accept.review.cost_note}</span> : null}
                  </p>
                ) : null}
                {actions.accept.authority_text ? (
                  <p className="text-sm text-ink-2" data-testid="outbound-accept-authority">
                    {actions.accept.authority_text}
                  </p>
                ) : null}
                <ActionGroup label={actions.accept.label}>
                  <Button variant="primary" loading={busy} onClick={() => void accept()} data-testid="outbound-confirm">
                    {actions.accept.confirm_label}
                  </Button>
                </ActionGroup>
              </div>
            ) : open === "counter" ? (
              <div className="space-y-3 border-t border-line pt-4" data-testid="outbound-confirm-counter">
                <label htmlFor={`${uid}-reply`} className="sr-only">
                  {actions.counter.placeholder_text}
                </label>
                <textarea
                  id={`${uid}-reply`}
                  value={text}
                  maxLength={REPLY_MAX}
                  rows={6}
                  placeholder={actions.counter.placeholder_text}
                  onChange={(e) => setText(e.target.value)}
                  aria-describedby={`${uid}-reply-count`}
                  className={`${textareaClass} w-full max-w-[72ch]`}
                  data-testid="outbound-reply-text"
                />
                <p id={`${uid}-reply-count`} className="flex flex-wrap justify-between gap-2 text-supporting text-ink-3">
                  <span>{actions.counter.effect_text}</span>
                  <span className="tabular-nums" data-testid="outbound-reply-count">
                    {t("bm.reply.count", { n: text.length, max: REPLY_MAX })}
                  </span>
                </p>
                <ActionGroup label={actions.counter.label}>
                  <Button variant="primary" loading={busy} disabled={!ready} onClick={() => void reply()} data-testid="outbound-confirm">
                    {actions.counter.confirm_label}
                  </Button>
                </ActionGroup>
              </div>
            ) : open === "decline" ? (
              <div className="space-y-3 border-t border-line pt-4" data-testid="outbound-confirm-decline">
                <fieldset className="m-0 min-w-0 border-0 p-0">
                  <legend className="mb-2 text-sm font-semibold text-ink-2">{actions.decline.reasons_label_text}</legend>
                  <div className="flex flex-wrap gap-2" data-testid="outbound-reasons">
                    {actions.decline.reasons.map((r) => (
                      <label
                        key={r.code}
                        className={`motion-press relative inline-flex min-h-9 cursor-pointer items-center rounded-pill border px-3.5 text-sm font-medium has-focus-visible:outline-2 has-focus-visible:outline-offset-2 has-focus-visible:outline-focus ${reason === r.code ? "border-f-ink bg-f-ink text-f-btn-ink" : "border-line-ui bg-card text-ink hover:border-ink-3"}`}
                        data-testid={`outbound-reason-${r.code}`}
                      >
                        <input type="radio" name={`${uid}-reason`} value={r.code} checked={reason === r.code} onChange={() => setReason(r.code)} className="absolute inset-0 cursor-pointer opacity-0" />
                        {r.text}
                      </label>
                    ))}
                  </div>
                </fieldset>
                <p className="max-w-[68ch] text-sm text-ink-2" data-testid="outbound-decline-effect">
                  {actions.decline.effect_text}
                </p>
                <ActionGroup label={actions.decline.label}>
                  <Button variant="primary" loading={busy} onClick={() => void decline()} data-testid="outbound-confirm">
                    {actions.decline.confirm_label}
                  </Button>
                </ActionGroup>
              </div>
            ) : null}
          </div>
          {refused ? (
            <p role="alert" className="mt-3 max-w-[68ch] rounded-tile border border-warn-line bg-warn-bg px-3.5 py-2.5 text-sm text-ink" data-testid="outbound-refused">
              {refused}
            </p>
          ) : null}
          {error ? (
            <div className="mt-3">
              <ErrorState error={error} />
            </div>
          ) : null}
        </section>
      ) : null}
    </div>
  );
}

/** The ending's chip: its icon in the tone's colours (green the agreement, lavender a new request, neutral no deal). */
const ENDING: Record<string, { chip: string; icon: ReactNode }> = {
  accepted: { chip: "bg-f-green text-f-green-ink", icon: <CheckIcon width={20} height={20} /> },
  countered: { chip: "bg-f-purple-soft text-f-purple-ink", icon: <ArrowsExchangeIcon width={20} height={20} /> },
  declined: { chip: "bg-subtle text-ink-2", icon: <XCircleIcon width={20} height={20} /> },
  no_answer: { chip: "bg-subtle text-ink-2", icon: <ClockIcon width={20} height={20} /> },
  closed: { chip: "bg-subtle text-ink-2", icon: <XCircleIcon width={20} height={20} /> },
};

/**
 * What came of the counter the owner sent outside FLOW (`outbound.answer`): accepted, countered, declined, no answer or closed. An icon chip in the tone's colour, the server's title and
 * sentence, the reason the buyer gave (declined) or their reply as they wrote it (countered), the server's links (its primary one filled), then the deal's history. `children` (the
 * agreement's receipt, when accepted) sits under the history.
 */
export function OutboundEnding({ outbound, history, children }: { outbound: OutboundView; history: DealHistoryEntry[] | undefined; children?: ReactNode }) {
  const answer = outbound.answer ?? "closed";
  const look = ENDING[answer] ?? ENDING.closed;
  const tone = outbound.tone === "ok" ? "ok" : outbound.tone === "waiting" ? "waiting" : "neutral";
  return (
    <section className={`${card} space-y-5`} data-testid="outbound-ending" data-answer={answer} data-tone={tone} aria-labelledby="outbound-ending-title">
      <div className="flex items-start gap-4">
        <span aria-hidden className={`grid size-11 shrink-0 place-items-center rounded-pill ${look.chip}`}>
          {look.icon}
        </span>
        <div className="min-w-0 space-y-1.5">
          <h2 id="outbound-ending-title" className="font-display text-lg font-extrabold leading-snug text-ink" data-testid="outbound-ending-title">
            {outbound.title_text}
          </h2>
          <p className="text-[15px] text-ink-2" data-testid="outbound-ending-text">
            {outbound.text}
          </p>
          {outbound.reason_text ? (
            <p className="inline-flex rounded-pill bg-subtle px-3 py-1 text-sm font-medium text-ink" data-testid="outbound-ending-reason" data-reason={outbound.reason_code ?? ""}>
              {outbound.reason_text}
            </p>
          ) : null}
          {outbound.reply_quote ? (
            <blockquote className="m-0 mt-1 max-w-[68ch] border-l-2 border-f-purple pl-3 text-[15px] leading-snug text-ink" data-testid="outbound-ending-quote">
              “{outbound.reply_quote}”
            </blockquote>
          ) : null}
        </div>
      </div>
      {outbound.links.length ? (
        <ActionGroup testId="outbound-ending-links">
          {outbound.links.map((l) => (
            <ButtonLink key={l.href} href={l.href} variant={l.primary ? "primary" : "secondary"} data-testid={l.primary ? "outbound-ending-primary" : undefined}>
              {l.label}
            </ButtonLink>
          ))}
        </ActionGroup>
      ) : null}
      <div className="border-t border-line pt-4">
        <HistoryList entries={history} />
      </div>
      {children}
    </section>
  );
}
