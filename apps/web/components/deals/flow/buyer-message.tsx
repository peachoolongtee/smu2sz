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

const card = "rounded-[20px] border border-line bg-card p-5 sm:p-6";

/**
 * The counter's figures inside the letter, set apart on screen only (amounts, rates, calendar dates, in either language): the clipboard gets the server's `text` unchanged.
 * This marks spans of the server's text; it writes nothing.
 */
const FIGURE = /¥[\d,]+(?:\.\d+)?|\d+(?:\.\d+)?%|\d{1,2} (?:January|February|March|April|May|June|July|August|September|October|November|December) \d{4}|\d{4}年\d{1,2}月\d{1,2}日/g;
function Letter({ text }: { text: string }) {
  const parts: ReactNode[] = [];
  let last = 0;
  for (const m of text.matchAll(FIGURE)) {
    const at = m.index ?? 0;
    if (at > last) parts.push(<Fragment key={`t${at}`}>{text.slice(last, at)}</Fragment>);
    parts.push(
      <mark key={`m${at}`} className="rounded-[4px] bg-f-amber/45 px-0.5 font-semibold text-ink">
        {m[0]}
      </mark>,
    );
    last = at + m[0].length;
  }
  if (last < text.length) parts.push(<Fragment key="end">{text.slice(last)}</Fragment>);
  return <>{parts}</>;
}

/**
 * The send review of one reply when the owner sends it themself (ADR-0011 addendum, round two): FLOW transmits nothing.
 *   The offer card: what they asked beside what the owner offers (the offer picture's term rows: the ask's own words from the picture's asked path, the reply's from the message read's
 *     `review`), the cost (green within the owner's limits) and who decides it.
 *   The send card (`send_title_text`): the buyer's language (the message changes; every word around it stays in the page's language: `?lang=<buyer>&ui_lang=<page>`), the notice, how the
 *     request arrived (a shield when the sender is verified), the message as a letter, and the two steps: Copy (the filled button until it has been copied), then "I've sent it to the
 *     buyer" (filled once copied), with what marking it does underneath.
 * Marking it sent records that and nothing else, bound to the verdict, the books and the exact message shown; a refusal (409) records nothing and says the server's `message_when`.
 * MESSAGE_CHANGED reads the message again; COUNTER_CHANGED is the send review's own refusal (`onCounterChanged`: its "Check again"). When FLOW prepares no message its reason is shown.
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
  };

  const copyMessage = async () => {
    if (!msg?.text) return;
    try {
      await navigator.clipboard.writeText(msg.text);
      setCopied("copied");
    } catch {
      setCopied("failed");
    }
  };

  const markSent = async () => {
    if (!msg?.message_hash) return;
    setMarking(true);
    setRefused(null);
    setError(null);
    try {
      // What the owner was shown: the verdict, the books' version and the message in the buyer's language.
      const r = await markOffered(offerId, counterId, { verdict_id: msg.verdict_id, state_version: msg.state_version, message_hash: msg.message_hash, lang: buyerLang });
      onMarked(r);
      bump();
    } catch (e) {
      const moved = counterChanged(e);
      const no = messageRefusal(e);
      if (moved) onCounterChanged(moved);
      else if (no) {
        setRefused(no.message_when ?? no.message);
        if (no.code === "MESSAGE_CHANGED") {
          setCopied("idle");
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
    <div className="space-y-4" data-testid="buyer-message-review">
      {review ? (
        <section className={card} aria-labelledby={`${uid}-offer`} data-testid="buyer-message-offer">
          <h4 id={`${uid}-offer`} className="sr-only">
            {t("bm.offer", { label })}
          </h4>
          <div className="grid grid-cols-[minmax(0,1fr)_minmax(0,1fr)] gap-x-6 border-b border-line pb-2 text-supporting font-bold text-ink-3" aria-hidden>
            <span>{t("bm.asked")}</span>
            <span>{t("bm.offer", { label })}</span>
          </div>
          <dl className="m-0 divide-y divide-line" data-testid="buyer-message-terms">
            {rows.map((r) => {
              const a = askedOf(r.key);
              return (
                <div key={r.key} className="py-3" data-testid={`buyer-message-term-${r.key}`}>
                  <dt className="text-supporting font-semibold text-ink-2">{r.label}</dt>
                  <dd className="m-0 mt-1 grid grid-cols-[minmax(0,1fr)_minmax(0,1fr)] gap-x-6 text-[15px]">
                    <span className="text-ink-2" data-testid="buyer-message-term-asked">
                      <span className="sr-only">{t("bm.asked")}: </span>
                      {a?.cell_text ?? a?.value_text ?? r.instead_of_text ?? ""}
                    </span>
                    <span className="font-semibold text-ink" data-testid="buyer-message-term-offer">
                      <span className="sr-only">{t("bm.offer", { label })}: </span>
                      {r.cell_text ?? r.value_text ?? ""}
                    </span>
                  </dd>
                </div>
              );
            })}
          </dl>
          {review.cost_display ? (
            <p className="mt-3 flex flex-wrap items-baseline gap-x-2 border-t border-line pt-3 text-sm" data-testid="buyer-message-cost" data-within={review.needs_owner ? "false" : "true"}>
              <span className="text-supporting font-bold text-ink-3">{t("bm.cost")}</span>
              <span className={`font-bold tabular-nums ${review.needs_owner ? "text-ink" : "text-f-green-ink"}`}>{review.cost_display}</span>
              {review.cost_note ? <span className="text-ink-2">· {review.cost_note}</span> : null}
            </p>
          ) : null}
          {review.decides_text ? (
            <p className="mt-1.5 text-sm text-ink-2" data-testid="buyer-message-decides">
              {review.decides_text}
            </p>
          ) : null}
        </section>
      ) : null}

      <section id={buyerMessageId(offerId, counterId)} tabIndex={-1} aria-labelledby={`${uid}-title`} className={`${card} min-w-0 space-y-4 outline-none`} data-testid="buyer-message" data-counter={counterId}>
        <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
          <h4 id={`${uid}-title`} className="font-display text-base font-extrabold leading-snug text-ink">
            {words.send_title_text ?? t("bm.title")}
          </h4>
          <div className="flex flex-wrap items-center gap-2" data-testid="buyer-message-lang">
            <span aria-hidden className="text-supporting font-medium text-ink-2">
              {t("bm.lang")}
            </span>
            <Segmented<Lang> label={t("bm.lang")} name={`${uid}-lang`} value={buyerLang} onChange={pickLang} options={languages.map((l) => ({ value: l.code, label: l.label }))} />
          </div>
        </div>
        <div className="space-y-1">
          <p className="max-w-[68ch] text-sm text-ink-2" data-testid="buyer-message-notice">
            {words.notice_text}
          </p>
          <p className="flex max-w-[68ch] items-center gap-1.5 text-supporting text-ink-3" data-testid="buyer-message-provenance" data-via={words.provenance.via ?? ""} data-verified={words.provenance.verified ? "true" : "false"}>
            {words.provenance.verified ? <ShieldCheckIcon width={16} height={16} className="shrink-0 text-f-green-ink" /> : null}
            {words.provenance.text}
          </p>
        </div>
        {!msg ? (
          <LoadingBlock rows={4} label={t("bm.reading")} />
        ) : msg.text ? (
          <>
            <figure className="m-0 max-w-[72ch] overflow-hidden rounded-tile border border-line bg-card" data-testid="buyer-message-letter">
              <figcaption className="border-b border-line bg-subtle px-4 py-2 text-supporting font-semibold text-ink-2" data-testid="buyer-message-until">
                {t("bm.letterTo", { buyer: msg.buyer_name, date: words.valid_until_date })}
              </figcaption>
              <p lang={buyerLang === "zh" ? "zh-CN" : "en"} className="whitespace-pre-wrap break-words px-4 py-4 text-[15px] leading-relaxed text-ink" data-testid="buyer-message-text" data-lang={buyerLang}>
                <Letter text={msg.text} />
              </p>
            </figure>
            <ActionGroup testId="buyer-message-actions" label={words.send_title_text ?? t("bm.title")}>
              <Button variant={hasCopied ? "secondary" : "primary"} onClick={() => void copyMessage()} data-testid="buyer-message-copy" data-filled={hasCopied ? "false" : "true"}>
                {words.copy_label}
              </Button>
              <Button variant={hasCopied ? "primary" : "secondary"} loading={marking} disabled={!msg.message_hash} onClick={() => void markSent()} data-testid="buyer-message-mark-sent" data-filled={hasCopied ? "true" : "false"}>
                {words.mark_sent_label}
              </Button>
              <span role="status" aria-live="polite" className="text-sm text-ink-2" data-testid="buyer-message-copy-status">
                {copied === "copied" ? t("biz.chase.copied") : copied === "failed" ? t("bm.copyfailed") : ""}
              </span>
            </ActionGroup>
            <p className="max-w-[68ch] text-sm text-ink-2" data-testid="buyer-message-effect">
              {words.mark_sent_effect_text}
            </p>
          </>
        ) : words.blocked ? (
          <p className="max-w-[68ch] text-[15px] leading-snug text-ink" role="status" data-testid="buyer-message-blocked" data-code={words.blocked.code}>
            {words.blocked.text}
          </p>
        ) : null}
        {refused ? (
          <p role="alert" className="max-w-[68ch] rounded-tile border border-warn-line bg-warn-bg px-3.5 py-2.5 text-sm text-ink" data-testid="buyer-message-refused">
            {refused}
          </p>
        ) : null}
        {error ? <ErrorState error={error} /> : null}
      </section>
    </div>
  );
}
