"use client";

import { useEffect, useId, useState } from "react";
import { Button, ErrorState, LoadingBlock, Segmented } from "@/components/ui";
import { ActionGroup } from "@/components/ui/action-group";
import { getBuyerMessage, markOffered, messageRefusal } from "@/lib/api";
import { counterChanged } from "@/lib/decision";
import { bump } from "@/lib/demo-store";
import { errorText } from "@/lib/error-text";
import { useI18n } from "@/lib/i18n";
import type { BuyerMessageView, CounterChangedDetail, OfferedResult } from "@/lib/types";
import { useAsync } from "@/lib/use-async";

type Lang = "en" | "zh";

/** The id the send review's "Go to the message to the buyer" brings into view. */
export const buyerMessageId = (offerId: string, counterId: string) => `buyer-message-${offerId}-${counterId}`.replace(/[^A-Za-z0-9_-]/g, "-");

/**
 * The message to the buyer for one reply (ADR-0011 addendum): FLOW transmits nothing. The server prepares the message for this counter, guarded like every outbound text; the owner copies it,
 * sends it themself, and marks it sent. The toggle is the BUYER's language (the message is written in it), not the page's: the message and its hash come from the read in the buyer's
 * language, every other word (the notice, how the request arrived, the day it is open until, why there is none, the buttons) from the read in the page's. When FLOW prepares none the
 * server's reason is shown and nothing can be copied or marked.
 *
 * "I've sent it to the buyer" records that and nothing else (no agreement, no money), bound to the verdict, the books and the exact message shown; a refusal (409) records nothing and says
 * the server's `message_when`. MESSAGE_CHANGED reads the message again; COUNTER_CHANGED is the send review's own refusal (`onCounterChanged`: its "Check again").
 */
export function BuyerMessage({
  offerId,
  counterId,
  onMarked,
  onCounterChanged,
  onBusy,
}: {
  offerId: string;
  counterId: string;
  /** Told with the server's answer once the mark is recorded (the deal now waits for the buyer). */
  onMarked: (r: OfferedResult) => void;
  onCounterChanged: (d: CounterChangedDetail) => void;
  onBusy?: (busy: boolean) => void;
}) {
  const { t, lang } = useI18n();
  const uid = useId();
  const [buyerLang, setBuyerLang] = useState<Lang>(lang);
  const words = useAsync(() => getBuyerMessage(offerId, counterId, lang), [offerId, counterId, lang]);
  const other = useAsync(() => (buyerLang === lang ? Promise.resolve(null) : getBuyerMessage(offerId, counterId, buyerLang)), [offerId, counterId, buyerLang, lang]);
  const page: BuyerMessageView | undefined = words.data;
  const msg: BuyerMessageView | undefined = buyerLang === lang ? page : (other.data ?? undefined);
  const [copy, setCopy] = useState<"idle" | "copied" | "failed">("idle");
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
    setCopy("idle");
  };

  const copyMessage = async () => {
    if (!msg?.text) return;
    try {
      await navigator.clipboard.writeText(msg.text);
      setCopy("copied");
    } catch {
      setCopy("failed");
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
          setCopy("idle");
          words.reload();
          other.reload();
        }
      } else setError(errorText(e, t));
    } finally {
      setMarking(false);
    }
  };

  const failed = words.error ?? other.error;
  return (
    <section
      id={buyerMessageId(offerId, counterId)}
      tabIndex={-1}
      aria-labelledby={`${uid}-title`}
      className="min-w-0 space-y-3 rounded-tile border border-line bg-subtle px-4 py-4 outline-none"
      data-testid="buyer-message"
      data-counter={counterId}
    >
      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
        <h4 id={`${uid}-title`} className="font-display text-base font-extrabold leading-snug text-ink">
          {t("bm.title")}
        </h4>
        <div className="flex flex-wrap items-center gap-2" data-testid="buyer-message-lang">
          <span aria-hidden className="text-supporting font-medium text-ink-2">
            {t("bm.lang")}
          </span>
          <Segmented<Lang>
            label={t("bm.lang")}
            name={`${uid}-lang`}
            value={buyerLang}
            onChange={pickLang}
            options={[
              { value: "en", label: t("bm.lang.en") },
              { value: "zh", label: t("bm.lang.zh") },
            ]}
          />
        </div>
      </div>
      {failed && !page ? (
        <ErrorState error={errorText(failed, t)} onRetry={() => (words.error ? words.reload() : other.reload())} />
      ) : !page || !msg ? (
        <LoadingBlock rows={3} label={t("bm.reading")} />
      ) : (
        <>
          <p className="max-w-[68ch] text-sm text-ink-2" data-testid="buyer-message-notice">
            {page.notice_text}
          </p>
          <p className="max-w-[68ch] text-supporting text-ink-3" data-testid="buyer-message-provenance" data-via={page.provenance.via ?? ""}>
            {page.provenance.text}
          </p>
          {msg.text ? (
            <>
              <p
                lang={buyerLang === "zh" ? "zh-CN" : "en"}
                className="m-0 max-w-[72ch] whitespace-pre-wrap break-words rounded-tile border border-line bg-surface px-3.5 py-3 text-[15px] leading-relaxed text-ink"
                data-testid="buyer-message-text"
                data-lang={buyerLang}
              >
                {msg.text}
              </p>
              <p className="text-sm" data-testid="buyer-message-until">
                <span className="mr-2 text-supporting font-bold text-ink-3">{t("bm.validUntil")}</span>
                <span className="text-ink">{page.valid_until_date}</span>
              </p>
              <ActionGroup testId="buyer-message-actions" label={t("bm.title")}>
                <Button onClick={() => void copyMessage()} data-testid="buyer-message-copy">
                  {page.copy_label}
                </Button>
                <Button loading={marking} disabled={!msg.message_hash} onClick={() => void markSent()} data-testid="buyer-message-mark-sent">
                  {page.mark_sent_label}
                </Button>
                <span role="status" aria-live="polite" className="text-sm text-ink-2" data-testid="buyer-message-copy-status">
                  {copy === "copied" ? t("biz.chase.copied") : copy === "failed" ? t("bm.copyfailed") : ""}
                </span>
              </ActionGroup>
            </>
          ) : page.blocked ? (
            <p className="max-w-[68ch] text-[15px] leading-snug text-ink" role="status" data-testid="buyer-message-blocked" data-code={page.blocked.code}>
              {page.blocked.text}
            </p>
          ) : null}
          {refused ? (
            <p role="alert" className="max-w-[68ch] rounded-tile border border-warn-line bg-warn-bg px-3.5 py-2.5 text-sm text-ink" data-testid="buyer-message-refused">
              {refused}
            </p>
          ) : null}
          {error ? <ErrorState error={error} /> : null}
        </>
      )}
    </section>
  );
}
