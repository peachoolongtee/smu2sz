"use client";

import { Fragment, useEffect, useId, useState, type ReactNode } from "react";
import { Button, ErrorState, LoadingBlock, Segmented } from "@/components/ui";
import { ActionGroup } from "@/components/ui/action-group";
import { ShieldCheckIcon } from "@/components/icons";
import { getBuyerMessage, markOffered, messageRefusal } from "@/lib/api";
import { counterChanged } from "@/lib/decision";
import { bump } from "@/lib/demo-store";
import { errorText } from "@/lib/error-text";
import { useI18n } from "@/lib/i18n";
import type { BuyerMessageView, CounterChangedDetail, OfferedResult, PicturePath } from "@/lib/types";
import { useAsync } from "@/lib/use-async";

type Lang = "en" | "zh";

/** The id the send review's "Go to the message to the buyer" brings into view. */
export const buyerMessageId = (offerId: string, counterId: string) => `buyer-message-${offerId}-${counterId}`.replace(/[^A-Za-z0-9_-]/g, "-");

/**
 * The counter's figures inside the letter, set apart on screen only (amounts, rates, calendar dates, in either language): the clipboard gets the server's `text` unchanged.
 * This marks spans of the server's text; it writes nothing.
 */
const FIGURE = /¥[\d,]+(?:\.\d+)?|\d+(?:\.\d+)?%|\d{1,2} (?:January|February|March|April|May|June|July|August|September|October|November|December) \d{4}|\d{4}年\d{1,2}月\d{1,2}日/g;
const TRAILING = /[,.;:，。；：]+$/;
function Letter({ text }: { text: string }) {
  const parts: ReactNode[] = [];
  let last = 0;
  for (const m of text.matchAll(FIGURE)) {
    const at = m.index ?? 0;
    // The figure alone: a comma or full stop that follows it stays in the text, outside the highlight.
    const figure = m[0].replace(TRAILING, "");
    if (!figure) continue;
    if (at > last) parts.push(<Fragment key={`t${at}`}>{text.slice(last, at)}</Fragment>);
    parts.push(
      <mark key={`m${at}`} className="rounded-[4px] bg-f-amber/45 px-0.5 font-semibold text-ink" data-testid="buyer-message-figure">
        {figure}
      </mark>,
    );
    last = at + figure.length;
  }
  if (last < text.length) parts.push(<Fragment key="end">{text.slice(last)}</Fragment>);
  return <>{parts}</>;
}

/**
 * The composer of one reply the owner sends themself (ADR-0011 addendum, round three): FLOW transmits nothing, and the message is the main element.
 *   Left (about 30%): what goes out, verified: each term, what they asked → what FLOW proposes (the ask's own cells from the picture's asked path, the reply's from the message read's
 *     `review`), the cost (green within the owner's limits), the day it is open until, and whose authority it goes out under (`authority_text`, else `review.decides_text`).
 *   Right (about 70%): the composer toolbar (the recipient, the buyer's language, how it goes out: `channel`), the letter at full width, the notice and how the request arrived, then the
 *     grouped actions: Copy (the filled one until it has been copied; a copy that fails says so and advances nothing), then Mark as sent, with what marking it does underneath.
 * The buyer's language changes the message only: every word around it is the page's (`?lang=<buyer>&ui_lang=<page>`). Marking it sent records that and nothing else, bound to the verdict,
 * the books and the exact message shown (it waits for a copy of the message on screen, never the other language's, and sends the hash of what was copied); a refusal (409) records nothing and says the server's `message_when`. MESSAGE_CHANGED reads the message again; COUNTER_CHANGED is the send
 * review's own refusal (`onCounterChanged`: its "Check again"). When FLOW prepares no message its reason is shown in the letter's place. Below lg the two columns stack.
 */
export function BuyerMessage({
  offerId,
  counterId,
  label,
  asked,
  onMarked,
  onCounterChanged,
  onBusy,
}: {
  offerId: string;
  counterId: string;
  /** The reply's name ("Option A"), the picture's. */
  label: string;
  /** The picture's asked path: the ask's own words for each term. */
  asked: PicturePath | null;
  onMarked: (r: OfferedResult) => void;
  onCounterChanged: (d: CounterChangedDetail) => void;
  onBusy?: (busy: boolean) => void;
}) {
  const { t, lang } = useI18n();
  const uid = useId();
  const [buyerLang, setBuyerLang] = useState<Lang>(lang);
  const read = useAsync(() => getBuyerMessage(offerId, counterId, buyerLang, lang), [offerId, counterId, buyerLang, lang]);
  const msg: BuyerMessageView | undefined = read.data && read.data.lang === buyerLang ? read.data : undefined;
  // The words around the message are the page's whatever the buyer's language: the last read's while the next is on its way.
  const [kept, setKept] = useState<BuyerMessageView | undefined>(undefined);
  if (read.data && read.data !== kept) setKept(read.data);
  const words = msg ?? kept;
  const [copied, setCopied] = useState<"idle" | "copied" | "failed">("idle");
  // The message the owner copied (the server's hash of its words, and its language): "I've sent it" records that message, and only after this language's was copied.
  const [copiedMsg, setCopiedMsg] = useState<{ lang: Lang; hash: string } | null>(null);
  const [marking, setMarking] = useState(false);
  const [refused, setRefused] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    onBusy?.(marking);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- reports the flight, not the callback
  }, [marking]);

  // Another language is another message: what was copied is not this one.
  const pickLang = (l: Lang) => {
    setBuyerLang(l);
    setCopied("idle");
    setCopiedMsg(null);
  };

  const copyMessage = async () => {
    if (!msg?.text || !msg.message_hash) return;
    const mine = { lang: buyerLang, hash: msg.message_hash };
    try {
      await navigator.clipboard.writeText(msg.text);
      setCopied("copied");
    } catch {
      setCopied("failed"); // the text is on screen to select and copy by hand
    }
    setCopiedMsg(mine);
  };

  const markSent = async () => {
    if (!msg?.message_hash || copiedMsg?.lang !== buyerLang) return;
    setMarking(true);
    setRefused(null);
    setError(null);
    try {
      // What the owner copied: the verdict, the books' version, the hash of the message copied and the buyer's language on screen (the server refuses the one for the other).
      const r = await markOffered(offerId, counterId, { verdict_id: msg.verdict_id, state_version: msg.state_version, message_hash: copiedMsg.hash, lang: buyerLang });
      onMarked(r);
      bump();
    } catch (e) {
      const moved = counterChanged(e);
      const no = messageRefusal(e);
      if (moved) onCounterChanged(moved);
      else if (no) {
        setRefused(no.message_when ?? no.message);
        if (no.code === "MESSAGE_CHANGED" || no.code === "MESSAGE_LANGUAGE") {
          setCopied("idle");
          setCopiedMsg(null);
          read.reload();
        }
      } else setError(errorText(e, t));
    } finally {
      setMarking(false);
    }
  };

  if (read.error && !words) return <ErrorState error={errorText(read.error, t)} onRetry={read.reload} />;
  if (!words) return <LoadingBlock rows={4} label={t("bm.reading")} />;
  const review = words.review ?? null;
  const askedOf = (key: string) => asked?.terms?.find((x) => x.key === key) ?? null;
  const rows = (review?.terms ?? []).filter((r) => r.value_text || askedOf(r.key)?.value_text || r.instead_of_text);
  const languages = words.languages?.length ? words.languages : [{ code: "en" as const, label: t("bm.lang.en") }, { code: "zh" as const, label: t("bm.lang.zh") }];
  const hasCopied = copied === "copied";
  return (
    <div className="grid gap-x-8 gap-y-6 lg:grid-cols-[minmax(16rem,3fr)_minmax(0,7fr)]" data-testid="buyer-message-review">
      {/* The left column: what goes out, verified: the terms against the ask, the cost, the day it is open until, and whose authority it goes out under. */}
      <section aria-labelledby={`${uid}-offer`} className="min-w-0 space-y-4" data-testid="buyer-message-offer">
        <h4 id={`${uid}-offer`} className="text-supporting font-bold uppercase tracking-wide text-ink-3">
          {t("bm.offer", { label })}
        </h4>
        <dl className="m-0 divide-y divide-line border-y border-line" data-testid="buyer-message-terms">
          {rows.map((r) => {
            const a = askedOf(r.key);
            return (
              <div key={r.key} className="py-2.5" data-testid={`buyer-message-term-${r.key}`}>
                <dt className="text-supporting font-semibold text-ink-3">{r.label}</dt>
                <dd className="m-0 mt-0.5 text-sm">
                  <span className="text-ink-2" data-testid="buyer-message-term-asked">
                    <span className="sr-only">{t("ws.asked")}: </span>
                    {a?.cell_text ?? a?.value_text ?? r.instead_of_text ?? ""}
                  </span>
                  <span aria-hidden className="mx-1.5 text-ink-3">
                    →
                  </span>
                  <span className="font-semibold text-ink" data-testid="buyer-message-term-offer">
                    <span className="sr-only">{t("ws.proposes")}: </span>
                    {r.cell_text ?? r.value_text ?? ""}
                  </span>
                </dd>
              </div>
            );
          })}
        </dl>
        <dl className="m-0 space-y-2 text-sm">
          {review?.cost_text ? (
            <div data-testid="buyer-message-cost" data-within={review.needs_owner ? "false" : "true"}>
              <dt className="sr-only">{t("bm.cost")}</dt>
              <dd className={`m-0 font-semibold ${review.needs_owner ? "text-ink" : "text-f-green-ink"}`}>{review.cost_text}</dd>
            </div>
          ) : review?.cost_display ? (
            <div data-testid="buyer-message-cost" data-within={review.needs_owner ? "false" : "true"}>
              <dt className="text-supporting font-semibold text-ink-3">{t("bm.cost")}</dt>
              <dd className="m-0">
                <span className={`font-bold tabular-nums ${review.needs_owner ? "text-ink" : "text-f-green-ink"}`}>{review.cost_display}</span>
                {review.cost_note ? <span className="text-ink-2"> · {review.cost_note}</span> : null}
              </dd>
            </div>
          ) : null}
          <div data-testid="buyer-message-until">
            <dt className="text-supporting font-semibold text-ink-3">{t("bm.validUntil")}</dt>
            <dd className="m-0 text-ink">{words.valid_until_date}</dd>
          </div>
        </dl>
        {words.authority_text ?? review?.decides_text ? (
          <p className="text-sm text-ink-2" data-testid="buyer-message-decides">
            {words.authority_text ?? review?.decides_text}
          </p>
        ) : null}
      </section>

      {/* The right column: the message itself, at full width under its composer toolbar. */}
      <section id={buyerMessageId(offerId, counterId)} tabIndex={-1} aria-labelledby={`${uid}-title`} className="min-w-0 space-y-4 outline-none" data-testid="buyer-message" data-counter={counterId}>
        <h4 id={`${uid}-title`} className="sr-only">
          {words.send_title_text ?? t("bm.title")}
        </h4>
        <div className="overflow-hidden rounded-tile border border-line bg-card">
          <div className="flex flex-wrap items-center gap-x-4 gap-y-2 border-b border-line bg-panel px-4 py-2.5" data-testid="buyer-message-toolbar">
            <p className="min-w-0 flex-1 text-sm" data-testid="buyer-message-recipient">
              <span className="mr-1.5 text-ink-3">{t("ws.recipient")}</span>
              <span className="font-semibold text-ink">{words.buyer_name}</span>
            </p>
            <div data-testid="buyer-message-lang">
              <Segmented<Lang> label={t("bm.lang")} name={`${uid}-lang`} value={buyerLang} onChange={pickLang} options={languages.map((l) => ({ value: l.code, label: l.label }))} />
            </div>
            {words.channel?.label ? (
              <p className="w-full text-supporting font-semibold text-ink-3 sm:w-auto" data-testid="buyer-message-channel" data-kind={words.channel.kind}>
                {words.channel.label}
              </p>
            ) : null}
          </div>
          {!msg ? (
            <div className="p-4">
              <LoadingBlock rows={4} label={t("bm.reading")} />
            </div>
          ) : msg.text ? (
            <p lang={buyerLang === "zh" ? "zh-CN" : "en"} className="whitespace-pre-wrap break-words px-5 py-5 text-[15px] leading-relaxed text-ink sm:px-6" data-testid="buyer-message-text" data-lang={buyerLang}>
              <Letter text={msg.text} />
            </p>
          ) : words.blocked ? (
            <p className="px-5 py-5 text-[15px] leading-snug text-ink" role="status" data-testid="buyer-message-blocked" data-code={words.blocked.code}>
              {words.blocked.text}
            </p>
          ) : null}
        </div>
        <div className="space-y-1">
          {/* How it goes out, in the server's words: the channel's own sentence when it sends one, else the notice. */}
          <p className="max-w-[72ch] text-sm text-ink-2" data-testid="buyer-message-notice">
            {words.channel?.text ?? words.notice_text}
          </p>
          <p className="flex max-w-[72ch] items-center gap-1.5 text-supporting text-ink-3" data-testid="buyer-message-provenance" data-via={words.provenance.via ?? ""} data-verified={words.provenance.verified ? "true" : "false"}>
            {words.provenance.verified ? <ShieldCheckIcon width={16} height={16} className="shrink-0 text-f-green-ink" /> : null}
            {words.provenance.text}
          </p>
        </div>
        {msg?.text ? (
          <>
            <ActionGroup testId="buyer-message-actions" label={words.send_title_text ?? t("bm.title")}>
              <Button variant={hasCopied ? "secondary" : "primary"} onClick={() => void copyMessage()} data-testid="buyer-message-copy" data-filled={hasCopied ? "false" : "true"}>
                {words.copy_label}
              </Button>
              <Button variant={hasCopied ? "primary" : "secondary"} loading={marking} disabled={!msg.message_hash || copiedMsg?.lang !== buyerLang} onClick={() => void markSent()} data-testid="buyer-message-mark-sent" data-filled={hasCopied ? "true" : "false"}>
                {words.mark_sent_label}
              </Button>
              <span role="status" aria-live="polite" className="text-sm text-ink-2" data-testid="buyer-message-copy-status" data-state={copied}>
                {copied === "copied" ? (words.copied_text ?? t("biz.chase.copied")) : copied === "failed" ? (words.copy_failed_text ?? t("bm.copyfailed")) : ""}
              </span>
            </ActionGroup>
            <p className="max-w-[72ch] text-sm text-ink-2" data-testid="buyer-message-effect">
              {words.mark_sent_effect_text}
            </p>
          </>
        ) : null}
        {refused ? (
          <p role="alert" className="max-w-[72ch] rounded-tile border border-warn-line bg-warn-bg px-3.5 py-2.5 text-sm text-ink" data-testid="buyer-message-refused">
            {refused}
          </p>
        ) : null}
        {error ? <ErrorState error={error} /> : null}
      </section>
    </div>
  );
}
