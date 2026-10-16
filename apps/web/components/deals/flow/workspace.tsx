"use client";

import Link from "next/link";
import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { Button, ButtonLink, ErrorState, textareaClass } from "@/components/ui";
import { ActionGroup } from "@/components/ui/action-group";
import { CommitmentReceipt } from "@/components/ui/commitment-receipt";
import { buyerAccepted, buyerDeclined, buyerReply, getBuyerMessage, messageRefusal, withdrawOffered } from "@/lib/api";
import { bump } from "@/lib/demo-store";
import { errorText } from "@/lib/error-text";
import type { DictKey } from "@/lib/dictionary";
import { useI18n } from "@/lib/i18n";
import type { CommitmentReceiptView, DealHistoryEntry, DecisionView, DeclineReason, OutboundView, PicturePath } from "@/lib/types";
import { quietLink } from "./flow-parts";

/**
 * A confirmation said once and then gone (the mark just recorded): announced to a screen reader (`aria-live`) and shown for a few seconds, never a permanent line beside the status that
 * already says the same. A new text shows again; leaving the deal clears it.
 */
export function TransientNote({ text, testId, ms = 6000 }: { text: string | null; testId?: string; ms?: number }) {
  const [shown, setShown] = useState<string | null>(null);
  const [last, setLast] = useState<string | null>(null);
  if (text !== last) {
    setLast(text);
    setShown(text);
  }
  useEffect(() => {
    if (!shown) return;
    const id = window.setTimeout(() => setShown(null), ms);
    return () => window.clearTimeout(id);
  }, [shown, ms]);
  return (
    <p role="status" aria-live="polite" className="min-h-0 text-sm text-ink-3 motion-fade empty:hidden" data-testid={shown ? testId : undefined}>
      {shown ?? ""}
    </p>
  );
}

/** A buyer's reply, as POST /offers/{id}/buyer-reply bounds one (SEC-17); the acceptance's evidence is bounded the same. */
export const REPLY_MAX = 4000;

/** The server's sentence for a pasted reply, kept for the reply's own deal, which the page opens next (the answered deal's pane is gone by then). */
const arrivals = new Map<string, string>();
export const arrivalText = (decision: string): string | null => arrivals.get(decision) ?? null;

const section = "px-5 py-5 sm:px-7 sm:py-6";
const sectionTitle = "text-supporting font-bold uppercase tracking-wide text-ink-3";

// ---------------------------------------------------------------- the workspace

/**
 * One negotiation, one workspace (round three): the same skeleton in every state, one white card with open sections divided by hairlines, never a card in a card.
 *   reply to  on a request that is a buyer's reply, the counter it answers (`reply_to`), linking back;
 *   current   the current step: one short sentence and one filled action (the children);
 *   terms     what they asked against what FLOW proposes, compact rows;
 *   history   the deal's one timeline (`history`), folded after four lines;
 *   original  the buyer's request as they wrote it, behind "The original ask", as evidence.
 */
export function Workspace({
  record,
  terms,
  termsTitle,
  original,
  focusKey,
  focusOnMount = false,
  children,
}: {
  record: DecisionView | null;
  /** The relevant terms section's body; nothing when there are none. */
  terms?: ReactNode;
  /** The terms section's heading in the server's words (`terms_title_text`); "Terms" when it sends none. */
  termsTitle?: string | null;
  /** The original ask's fold. */
  original?: ReactNode;
  /** Changes when the state changes: the current step's heading then takes the focus (a screen reader hears the new state). */
  focusKey: string;
  /** The deal moved to this state while the owner was on it (the workspace mounts with it): the heading takes the focus at once. */
  focusOnMount?: boolean;
  children: ReactNode;
}) {
  const { t } = useI18n();
  const ref = useRef<HTMLDivElement>(null);
  const first = useRef(true);
  useEffect(() => {
    if (first.current) {
      first.current = false;
      if (!focusOnMount) return;
    }
    ref.current?.querySelector<HTMLElement>("[data-step-heading]")?.focus({ preventScroll: false });
    // eslint-disable-next-line react-hooks/exhaustive-deps -- once per state (whether to focus on mount is read on the first run only)
  }, [focusKey]);
  const replyTo = record?.reply_to ?? null;
  return (
    <div className="overflow-hidden rounded-[24px] bg-card shadow-(--shadow-f)" data-testid="deal-workspace" data-step={focusKey}>
      {replyTo ? (
        <p className="border-b border-line bg-f-purple-soft/50 px-5 py-3 text-sm sm:px-7" data-testid="deal-reply-to">
          <Link href={replyTo.href} className={`${quietLink} px-0`}>
            {replyTo.title_text}
          </Link>
        </p>
      ) : null}
      <div ref={ref} className={`${section} motion-fade`} data-testid="deal-current-step" key={focusKey}>
        {children}
      </div>
      {terms ? (
        <section className={`${section} border-t border-line`} aria-label={termsTitle ?? t("ws.terms")} data-testid="deal-terms-section">
          <h3 className={sectionTitle} data-testid="deal-terms-title">
            {termsTitle ?? t("ws.terms")}
          </h3>
          <div className="mt-3">{terms}</div>
        </section>
      ) : null}
      {record?.history?.length ? (
        <section className={`${section} border-t border-line`} aria-label={t("hist.title")}>
          <Timeline entries={record.history} />
        </section>
      ) : null}
      {original ? <div className="border-t border-line px-5 pb-2 sm:px-7 [&>*]:mt-0 [&>*]:border-t-0">{original}</div> : null}
    </div>
  );
}

/** The current step's heading: it takes the focus when the state changes. */
export function StepHeading({ children, testId }: { children: ReactNode; testId?: string }) {
  return (
    <h2 tabIndex={-1} data-step-heading className="font-display text-xl font-extrabold leading-snug text-ink outline-none" data-testid={testId}>
      {children}
    </h2>
  );
}

// ---------------------------------------------------------------- terms and history

export interface TermRow {
  key: string;
  label: string;
  /** What they asked (the ask's own cell), or the server's "instead of …" when only that is known. */
  asked: string | null;
  proposed: string | null;
  changed?: boolean;
}

/** "They asked → FLOW proposes", one open row per term with a hairline between them. */
export function TermsRows({ rows, askedHead, proposedHead, testId = "deal-terms-rows" }: { rows: TermRow[]; askedHead?: string; proposedHead?: string; testId?: string }) {
  const { t } = useI18n();
  if (!rows.length) return null;
  return (
    <dl className="divide-y divide-line" data-testid={testId}>
      <div aria-hidden className="hidden grid-cols-[minmax(8rem,0.8fr)_1fr_1fr] gap-x-6 pb-2 text-supporting font-semibold text-ink-3 sm:grid">
        <span />
        <span>{askedHead ?? t("ws.asked")}</span>
        <span>{proposedHead ?? t("ws.proposes")}</span>
      </div>
      {rows.map((r) => (
        <div key={r.key} className="grid gap-x-6 gap-y-0.5 py-2.5 sm:grid-cols-[minmax(8rem,0.8fr)_1fr_1fr]" data-testid={`term-row-${r.key}`} data-changed={r.changed ? "true" : undefined}>
          <dt className="text-sm font-semibold text-ink-2">{r.label}</dt>
          <dd className="text-sm text-ink-2" data-testid="term-asked">
            <span className="sr-only">{askedHead ?? t("ws.asked")}: </span>
            {r.asked ?? ""}
          </dd>
          <dd className={`text-sm ${r.changed ? "font-bold text-f-purple-ink" : "font-semibold text-ink"}`} data-testid="term-proposed">
            <span className="sr-only">{proposedHead ?? t("ws.proposes")}: </span>
            <span aria-hidden className="mr-1 text-ink-3 sm:hidden">→</span>
            {r.proposed ?? ""}
            {r.changed ? <span className="ml-2 rounded-pill bg-f-purple-soft px-2 py-0.5 text-supporting font-semibold">{t("ws.changed")}</span> : null}
          </dd>
        </div>
      ))}
    </dl>
  );
}

/** Term sentences, when the server gives the terms as sentences only. */
export function TermSentences({ terms, testId = "deal-terms-list" }: { terms: string[]; testId?: string }) {
  if (!terms.length) return null;
  return (
    <ul className="list-disc space-y-1 pl-5 text-sm text-ink" data-testid={testId}>
      {terms.map((x, i) => (
        <li key={i}>{x}</li>
      ))}
    </ul>
  );
}

const DOT: Record<string, string> = {
  ok: "border-f-green-ink bg-f-green",
  waiting: "border-f-purple bg-f-purple-soft",
  neutral: "border-f-muted bg-f-line",
};


/** Who did it, as a quiet tag after the line (the server's `source`). */
const SOURCE: Record<string, DictKey> = { buyer: "hist.by.buyer", flow: "hist.by.flow", owner: "hist.by.owner", simulator: "hist.by.simulator" };

/** The deal's one timeline, oldest first: date and the server's sentence. Folded after four lines (the latest ones are what the owner needs; "Show all" opens the rest). */
export function Timeline({ entries }: { entries: DealHistoryEntry[] }) {
  const { t } = useI18n();
  const uid = useId();
  const [all, setAll] = useState(false);
  const shown = all || entries.length <= 4 ? entries : entries.slice(-4);
  const hidden = entries.length - shown.length;
  return (
    <div data-testid="deal-history">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 id={`${uid}-h`} className={sectionTitle}>
          {t("hist.title")}
        </h3>
        {entries.length > 4 ? (
          <button type="button" className={quietLink} aria-expanded={all} aria-controls={`${uid}-list`} onClick={() => setAll((x) => !x)} data-testid="deal-history-toggle">
            {all ? t("hist.fewer") : t("hist.all", { n: entries.length })}
          </button>
        ) : null}
      </div>
      <ol id={`${uid}-list`} aria-labelledby={`${uid}-h`} className="mt-3 list-none space-y-2 p-0" data-hidden={hidden}>
        {shown.map((h, i) => (
          <li key={`${h.kind}-${i}`} className="grid grid-cols-[0.75rem_7.5rem_1fr] items-start gap-x-3 text-sm sm:grid-cols-[0.75rem_9rem_1fr]" data-testid={`deal-history-${h.kind}`}>
            <span aria-hidden className={`mt-1.5 size-2.5 rounded-pill border-2 ${DOT[h.tone] ?? "border-f-ink bg-f-ink"}`} />
            <span className="tabular-nums text-ink-3">{h.date}</span>
            <span className="min-w-0 text-ink">
              {h.text}
              {h.source && SOURCE[h.source] ? (
                <span className="ml-2 text-supporting text-ink-3" data-testid="deal-history-source" data-source={h.source}>
                  {t(SOURCE[h.source])}
                </span>
              ) : null}
            </span>
          </li>
        ))}
      </ol>
    </div>
  );
}

// ---------------------------------------------------------------- waiting for the buyer, and recording their answer

type Answer = "accept" | "counter" | "unclear" | "decline";

async function run<T>(set: { busy: (b: boolean) => void; refused: (s: string | null) => void; error: (s: string | null) => void }, t: Parameters<typeof errorText>[1], call: () => Promise<T>, done: (r: T) => void) {
  set.busy(true);
  set.refused(null);
  set.error(null);
  try {
    done(await call());
  } catch (e) {
    const no = messageRefusal(e);
    if (no) set.refused(no.message_when ?? no.message);
    else set.error(errorText(e, t));
  } finally {
    set.busy(false);
  }
}

/**
 * The buyer's turn (record state AWAITING_BUYER, `outbound.answer` null): the server's "Waiting for …" and its one line of what was sent, when and that FLOW cannot confirm delivery;
 * [View sent message] and the one filled [Record their response]; "I marked it sent by mistake" as a quiet link when the server offers it. Recording opens a compact choice (accepted,
 * proposed different terms, unclear or a question, declined), each revealing only its own form.
 */
export function WaitingStep({
  offerId,
  outbound,
  asked,
  marked,
  onWithdrawn,
  onBusy,
}: {
  offerId: string;
  outbound: OutboundView;
  /** The offer picture's asked path: the ask's own words for each term ("They asked"). */
  asked?: PicturePath | null;
  /** The server's sentence for the mark just made, said once. */
  marked?: string | null;
  /** Told with the server's sentence once the mark is withdrawn (the deal is a counter ready again: this step is gone). */
  onWithdrawn?: (text: string) => void;
  onBusy?: (busy: boolean) => void;
}) {
  const { t, lang } = useI18n();
  const uid = useId();
  const router = useRouter();
  const actions = outbound.actions;
  const [viewing, setViewing] = useState(false);
  const [recording, setRecording] = useState(false);
  const [answer, setAnswer] = useState<Answer | null>(null);
  const [text, setText] = useState("");
  const [evidence, setEvidence] = useState("");
  const [reason, setReason] = useState<DeclineReason>("NO_REASON");
  const [withdrawing, setWithdrawing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [refused, setRefused] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    onBusy?.(busy);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- reports the flight, not the callback
  }, [busy]);
  const setters = { busy: setBusy, refused: setRefused, error: setError };

  const accept = () =>
    run(
      setters,
      t,
      async () => {
        // The books' version the yes is recorded on: the message read carries it (the record does not).
        const m = await getBuyerMessage(offerId, outbound.counter_id, outbound.lang, lang);
        return buyerAccepted(offerId, outbound.counter_id, {
          verdict_id: outbound.verdict_id,
          state_version: m.state_version,
          message_hash: outbound.message_hash,
          ...(evidence.trim() ? { evidence_text: evidence } : {}),
        });
      },
      () => bump(),
    );
  const decline = () => run(setters, t, () => buyerDeclined(offerId, outbound.counter_id, { verdict_id: outbound.verdict_id, message_hash: outbound.message_hash, reason }), () => bump());
  const reply = () =>
    run(
      setters,
      t,
      () => buyerReply(offerId, { verdict_id: outbound.verdict_id, counter_id: outbound.counter_id, text }),
      (r) => {
        arrivals.set(r.reply_decision_id, r.message_when);
        bump();
        router.push(r.reply_href);
      },
    );
  const withdraw = () =>
    run(
      setters,
      t,
      () => withdrawOffered(offerId, outbound.counter_id, { verdict_id: outbound.verdict_id, message_hash: outbound.message_hash }),
      (r) => {
        onWithdrawn?.(r.message_when);
        bump();
      },
    );

  const choices: { key: Answer; label: string }[] = actions
    ? ([
        { key: "accept", label: actions.accept.label },
        { key: "counter", label: actions.counter.label },
        ...(actions.unclear ? [{ key: "unclear" as const, label: actions.unclear.label }] : []),
        { key: "decline", label: actions.decline.label },
      ] satisfies { key: Answer; label: string }[])
    : [];
  const paste = answer === "counter" ? actions?.counter : answer === "unclear" ? actions?.unclear : null;
  const ready = Boolean(text.trim()) && text.length <= REPLY_MAX;
  const review = actions?.accept.review ?? null;
  return (
    <div className="space-y-4" data-testid="outbound-waiting">
      <div className="space-y-1.5">
        <StepHeading testId="outbound-title">{outbound.title_text}</StepHeading>
        <p className="max-w-[72ch] text-[15px] text-ink-2" data-testid="outbound-status">
          {outbound.status_text ?? outbound.sent_text}
        </p>
        {outbound.status_text && outbound.text ? (
          <p className="max-w-[72ch] text-sm text-ink-3" data-testid="outbound-expiry">
            {outbound.text}
          </p>
        ) : null}
        <TransientNote text={marked ?? null} testId="deal-marked-sent" />
      </div>
      <ActionGroup testId="outbound-actions" label={outbound.title_text}>
        {outbound.message_same && outbound.message_text ? (
          <Button aria-expanded={viewing} aria-controls={`${uid}-sent`} onClick={() => setViewing((x) => !x)} data-testid="outbound-view-sent">
            {actions?.view_message_label ?? t("ws.viewSent")}
          </Button>
        ) : null}
        {actions ? (
          <Button
            variant={recording ? "secondary" : "primary"}
            aria-expanded={recording}
            aria-controls={`${uid}-record`}
            onClick={() => {
              setRecording((x) => !x);
              setRefused(null);
              setError(null);
            }}
            data-testid="outbound-record"
          >
            {actions.record_label ?? t("ws.record")}
          </Button>
        ) : null}
      </ActionGroup>
      {viewing && outbound.message_text ? (
        <p id={`${uid}-sent`} lang={outbound.lang === "zh" ? "zh-CN" : "en"} className="max-w-[80ch] whitespace-pre-wrap break-words rounded-tile border border-line bg-panel px-4 py-3 text-[15px] leading-relaxed text-ink" data-testid="outbound-sent-message-text">
          {outbound.message_text}
        </p>
      ) : null}

      {recording && actions ? (
        <section id={`${uid}-record`} aria-labelledby={`${uid}-q`} className="space-y-4 border-t border-line pt-4" data-testid="outbound-answer">
          <h3 id={`${uid}-q`} className="text-[15px] font-bold text-ink">
            {actions.question_text}
          </h3>
          <div role="radiogroup" aria-labelledby={`${uid}-q`} className="flex flex-wrap gap-2" data-testid="outbound-choice">
            {choices.map((c) => (
              <label
                key={c.key}
                className={`motion-press relative inline-flex min-h-10 cursor-pointer items-center rounded-control border px-4 text-sm font-semibold transition-colors has-focus-visible:outline-2 has-focus-visible:outline-offset-2 has-focus-visible:outline-focus ${answer === c.key ? "border-f-ink bg-card text-ink shadow-[inset_0_0_0_1px_var(--color-f-ink)]" : "border-line-ui bg-card text-ink-2 hover:border-ink-3 hover:text-ink"}`}
                data-testid={`outbound-tile-${c.key}`}
                data-selected={answer === c.key ? "true" : "false"}
              >
                <input
                  type="radio"
                  name={`${uid}-answer`}
                  value={c.key}
                  checked={answer === c.key}
                  onChange={() => {
                    setAnswer(c.key);
                    setRefused(null);
                    setError(null);
                  }}
                  className="absolute inset-0 cursor-pointer opacity-0"
                />
                {c.label}
              </label>
            ))}
          </div>

          {answer === "accept" ? (
            <div className="space-y-3 motion-fade" data-testid="outbound-confirm-accept">
              <h4 className="text-[15px] font-bold text-ink">{actions.accept.title_text ?? t("ws.confirmAccept")}</h4>
              {review?.terms?.length ? (
                <TermsRows rows={reviewRows(review.terms, asked)} testId="outbound-accept-terms" />
              ) : (
                <TermSentences terms={actions.accept.terms} testId="outbound-accept-terms" />
              )}
              {review?.cost_text ? (
                <p className={`text-sm font-semibold ${review.needs_owner ? "text-ink" : "text-f-green-ink"}`} data-testid="outbound-accept-cost">
                  {review.cost_text}
                </p>
              ) : review?.cost_display ? (
                <p className="text-sm" data-testid="outbound-accept-cost">
                  <span className={`font-bold tabular-nums ${review.needs_owner ? "text-ink" : "text-f-green-ink"}`}>{review.cost_display}</span>
                  {review.cost_note ? <span className="text-ink-2"> · {review.cost_note}</span> : null}
                </p>
              ) : null}
              {actions.accept.binding_text ? (
                <p className="max-w-[72ch] text-sm text-ink" data-testid="outbound-accept-binding">
                  {actions.accept.binding_text}
                </p>
              ) : null}
              {actions.accept.authority_text ? (
                <p className="max-w-[72ch] text-sm text-ink-2" data-testid="outbound-accept-authority">
                  {actions.accept.authority_text}
                </p>
              ) : null}
              {actions.accept.evidence_label ? (
                <div className="space-y-1.5">
                  <label htmlFor={`${uid}-evidence`} className="block text-sm font-semibold text-ink-2">
                    {actions.accept.evidence_label}
                  </label>
                  <textarea
                    id={`${uid}-evidence`}
                    value={evidence}
                    maxLength={REPLY_MAX}
                    rows={3}
                    placeholder={actions.accept.evidence_placeholder ?? undefined}
                    onChange={(e) => setEvidence(e.target.value)}
                    aria-describedby={actions.accept.evidence_hint_text ? `${uid}-evidence-hint` : undefined}
                    className={`${textareaClass} w-full max-w-[80ch]`}
                    data-testid="outbound-evidence-text"
                  />
                  {actions.accept.evidence_hint_text ? (
                    <p id={`${uid}-evidence-hint`} className="text-supporting text-ink-3" data-testid="outbound-evidence-hint">
                      {actions.accept.evidence_hint_text}
                    </p>
                  ) : null}
                </div>
              ) : null}
              <ActionGroup label={actions.accept.label}>
                <Button variant="primary" loading={busy} onClick={() => void accept()} data-testid="outbound-confirm">
                  {actions.accept.confirm_label}
                </Button>
              </ActionGroup>
            </div>
          ) : paste ? (
            <div className="space-y-3 motion-fade" data-testid={`outbound-confirm-${answer}`}>
              <label htmlFor={`${uid}-reply`} className="sr-only">
                {paste.placeholder_text}
              </label>
              <textarea
                id={`${uid}-reply`}
                value={text}
                maxLength={REPLY_MAX}
                rows={6}
                placeholder={paste.placeholder_text}
                onChange={(e) => setText(e.target.value)}
                aria-describedby={`${uid}-reply-count`}
                className={`${textareaClass} w-full max-w-[80ch]`}
                data-testid="outbound-reply-text"
              />
              <p id={`${uid}-reply-count`} className="flex max-w-[80ch] flex-wrap justify-between gap-2 text-supporting text-ink-3">
                <span>{paste.effect_text}</span>
                <span className="tabular-nums" data-testid="outbound-reply-count">
                  {t("bm.reply.count", { n: text.length, max: REPLY_MAX })}
                </span>
              </p>
              <ActionGroup label={paste.label}>
                <Button variant="primary" loading={busy} disabled={!ready} onClick={() => void reply()} data-testid="outbound-confirm">
                  {paste.confirm_label}
                </Button>
              </ActionGroup>
            </div>
          ) : answer === "decline" ? (
            <div className="space-y-3 motion-fade" data-testid="outbound-confirm-decline">
              <fieldset className="min-w-0 border-0 p-0">
                <legend className="mb-2 text-sm font-semibold text-ink-2">{actions.decline.reasons_label_text}</legend>
                <div className="flex flex-wrap gap-2" data-testid="outbound-reasons">
                  {actions.decline.reasons.map((r) => (
                    <label
                      key={r.code}
                      className={`motion-press relative inline-flex min-h-9 cursor-pointer items-center rounded-pill border px-3.5 text-sm font-medium has-focus-visible:outline-2 has-focus-visible:outline-offset-2 has-focus-visible:outline-focus ${reason === r.code ? "border-f-ink text-ink shadow-[inset_0_0_0_1px_var(--color-f-ink)]" : "border-line-ui bg-card text-ink-2 hover:border-ink-3"}`}
                      data-testid={`outbound-reason-${r.code}`}
                    >
                      <input type="radio" name={`${uid}-reason`} value={r.code} checked={reason === r.code} onChange={() => setReason(r.code)} className="absolute inset-0 cursor-pointer opacity-0" />
                      {r.text}
                    </label>
                  ))}
                </div>
              </fieldset>
              <p className="max-w-[72ch] text-sm text-ink-2" data-testid="outbound-decline-effect">
                {actions.decline.effect_text}
              </p>
              <ActionGroup label={actions.decline.label}>
                <Button variant="primary" loading={busy} onClick={() => void decline()} data-testid="outbound-confirm">
                  {actions.decline.confirm_label}
                </Button>
              </ActionGroup>
            </div>
          ) : null}
        </section>
      ) : null}

      {actions?.withdraw ? (
        <div className="border-t border-line pt-3" data-testid="outbound-withdraw">
          {withdrawing ? (
            <div className="space-y-2">
              <p className="max-w-[72ch] text-sm text-ink-2">{actions.withdraw.effect_text}</p>
              <div className="flex flex-wrap items-center gap-3">
                <Button size="sm" loading={busy} onClick={() => void withdraw()} data-testid="outbound-withdraw-confirm">
                  {actions.withdraw.confirm_label}
                </Button>
                <button type="button" className={quietLink} onClick={() => setWithdrawing(false)} disabled={busy}>
                  {t("bm.cancel")}
                </button>
              </div>
            </div>
          ) : (
            <button type="button" className={`${quietLink} px-0 text-ink-3`} onClick={() => setWithdrawing(true)} data-testid="outbound-withdraw-open">
              {actions.withdraw.label}
            </button>
          )}
        </div>
      ) : null}

      {refused ? (
        <p role="alert" className="max-w-[72ch] rounded-tile border border-warn-line bg-warn-bg px-3.5 py-2.5 text-sm text-ink" data-testid="outbound-refused">
          {refused}
        </p>
      ) : null}
      {error ? <ErrorState error={error} /> : null}
    </div>
  );
}

/**
 * The review's term rows: what they asked (the ask's own cell, from the offer picture's asked path, as the send view's left column reads it) → the reply's own cell. The server's
 * "instead of …" is never put in the asked column; a term the picture has no ask for leaves that cell empty. Rows with neither are left out.
 */
export function reviewRows(terms: NonNullable<NonNullable<OutboundView["actions"]>["accept"]["review"]>["terms"], asked: PicturePath | null | undefined): TermRow[] {
  const askedOf = (key: string) => asked?.terms?.find((x) => x.key === key) ?? null;
  return (terms ?? [])
    .map((r) => {
      const a = askedOf(r.key);
      return { key: r.key, label: r.label, asked: a?.cell_text ?? a?.value_text ?? null, proposed: r.cell_text ?? r.value_text };
    })
    .filter((r) => r.asked || r.proposed);
}

// ---------------------------------------------------------------- what came of it

/**
 * What came of the counter the owner sent outside FLOW (`outbound.answer`): the server's title and sentence, then per answer what it adds: for an acceptance who recorded it and from what,
 * where it stands and what follows (the agreement's receipt folded under "Agreement details"); for a counter their reply against our last offer, term by term, and where their reply stands;
 * for a no the reason as reported. The server's links last, its primary one filled. The history is the workspace's own section, not repeated here.
 */
export function EndingStep({ outbound, receipt, decision }: { outbound: OutboundView; receipt?: CommitmentReceiptView | null; decision: string }) {
  const { t } = useI18n();
  const answer = outbound.answer ?? "closed";
  return (
    <div className="space-y-4" data-testid="outbound-ending" data-answer={answer} data-tone={outbound.tone}>
      <div className="space-y-1.5">
        <StepHeading testId="outbound-ending-title">{outbound.title_text}</StepHeading>
        <p className="max-w-[72ch] text-[15px] text-ink-2" data-testid="outbound-ending-text">
          {outbound.text}
        </p>
        {outbound.provenance_text ? (
          <p className="max-w-[72ch] text-sm text-ink-3" data-testid="outbound-ending-provenance">
            {outbound.provenance_text}
          </p>
        ) : null}
        {outbound.reason_text ? (
          <p className="inline-flex rounded-pill bg-panel px-3 py-1 text-sm font-medium text-ink" data-testid="outbound-ending-reason" data-reason={outbound.reason_code ?? ""}>
            {outbound.reason_text}
          </p>
        ) : null}
      </div>
      {answer === "accepted" && outbound.status_text ? (
        <p className="text-[15px] font-semibold text-f-green-ink" data-testid="outbound-ending-status">
          {outbound.status_text}
        </p>
      ) : null}
      {outbound.consequences?.length ? (
        <div data-testid="outbound-ending-consequences">
          {outbound.consequences_title_text ? <h3 className="mb-1.5 text-sm font-bold text-ink">{outbound.consequences_title_text}</h3> : null}
          <ul className="list-disc space-y-1 pl-5 text-sm text-ink">
            {outbound.consequences.map((c, i) => (
              <li key={i}>{c}</li>
            ))}
          </ul>
        </div>
      ) : null}
      {outbound.evidence_quote ? (
        <blockquote className="max-w-[72ch] border-l-2 border-line-strong pl-3 text-[15px] leading-snug text-ink-2" data-testid="outbound-ending-evidence">
          “{outbound.evidence_quote}”
        </blockquote>
      ) : null}
      {outbound.changes?.length ? (
        <TermsRows
          rows={outbound.changes.map((c) => ({ key: c.key, label: c.label, asked: c.ours_text, proposed: c.theirs_text, changed: c.changed }))}
          askedHead={t("ws.ours")}
          proposedHead={t("ws.theirs")}
          testId="outbound-ending-changes"
        />
      ) : null}
      {outbound.reply_quote ? (
        <blockquote className="max-w-[72ch] border-l-2 border-f-purple pl-3 text-[15px] leading-snug text-ink" data-testid="outbound-ending-quote">
          “{outbound.reply_quote}”
        </blockquote>
      ) : null}
      {outbound.reply_state_text ? (
        <p className="text-sm text-ink-2" data-testid="outbound-ending-reply-state">
          {outbound.reply_state_text}
        </p>
      ) : null}
      {outbound.links.length ? (
        <ActionGroup testId="outbound-ending-links">
          {outbound.links.map((l) => (
            <ButtonLink key={l.href} href={l.href} variant={l.primary ? "primary" : "secondary"} data-testid={l.primary ? "outbound-ending-primary" : undefined}>
              {l.label}
            </ButtonLink>
          ))}
        </ActionGroup>
      ) : null}
      {receipt ? (
        <details className="group border-t border-line pt-3" data-testid="outbound-agreement-details">
          <summary className={`${quietLink} cursor-pointer list-none px-0`}>{t("ws.agreementDetails")}</summary>
          <div className="pt-3">
            <CommitmentReceipt receipt={receipt} id={`${decision}-agreement-receipt`.replace(/[^A-Za-z0-9_-]/g, "-")} title={t("receipt.title.agreed")} testId="deal-agreement-receipt" />
          </div>
        </details>
      ) : null}
    </div>
  );
}
