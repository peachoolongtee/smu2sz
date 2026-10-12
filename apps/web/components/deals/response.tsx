"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { obligationSentence } from "@/components/deals/commitments";
import { authorityText, authorityTone } from "@/components/deals/path-columns";
import { ActionBar } from "@/components/business/action-bar";
import { Badge, Button, Callout, Card, ErrorState, Segmented, SlowNotice, StatePill, textLinkClass } from "@/components/ui";
import { counterChanged, negotiate } from "@/lib/api";
import { evaluate as evaluateAndCache } from "@/lib/demo";
import { bump, recordNegotiation } from "@/lib/demo-store";
import { isTimeout } from "@/lib/errors";
import { useNarrow } from "@/lib/use-narrow";
import { useI18n } from "@/lib/i18n";
import { errorText } from "@/lib/error-text";
import type { Mode } from "@/lib/mode";
import type { BuyerProfile, CounterChangedDetail, CounterProposal, Displayed, NegotiationView, PicturePath, VerdictView } from "@/lib/types";
import { Disclosure } from "@/components/business/kit";

type Counter = Displayed<CounterProposal> & { text_when?: string; rationale_when?: string; label_when?: string | null; outbound_blocked?: boolean };

/** The DOM id (and test id) of a counter's card: "deal-option-Option-B". */
export function optionDomId(label: string): string {
  return `deal-option-${label.replace(/\s+/g, "-")}`;
}

/**
 * One counter as a business card: what changes for the buyer (the counter's own wording), what it costs (the plain
 * cost, or the net economic cost with the funding cost and the offset beside it, never "¥0.00" alone), and behind
 * "Details": why it works and the terms the buyer would agree to, as sentences. Formulas stay in the page's
 * calculation disclosure.
 */
function CounterBusinessCard({ c, recommended, today, action }: { c: Counter; recommended: boolean; today: number; action?: React.ReactNode }) {
  const { t, te } = useI18n();
  const e = c.economics ?? null;
  return (
    <li id={optionDomId(c.label)} tabIndex={-1} className="py-4 first:pt-0 last:pb-0" data-testid={optionDomId(c.label)}>
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="text-base font-semibold text-ink">{c.label_when ?? c.label}</h3>
          {recommended ? <Badge tone="brand">{t("biz.deals.option.recommended")}</Badge> : null}
        </div>
        {/* A plain cost sits on the title's line; a net cost needs its two parts and keeps the rows below. */}
        {!e?.is_net ? (
          <p className="flex items-baseline gap-2 text-sm">
            <span className="text-ink-3">{t("biz.deals.estCost")}</span>
            <span className="text-lg font-semibold tabular-nums text-ink" data-testid="deal-option-cost">
              {c.supplier_cost_display}
            </span>
          </p>
        ) : null}
      </div>
      <p className="mt-2 text-sm text-ink" data-testid="deal-option-text">
        {c.text_when ?? c.text}
      </p>
      {e?.is_net ? (
        <dl className="mt-3 text-sm">
          <div className="flex items-baseline justify-between gap-3">
            <dt className="text-ink-2">{t("biz.deals.netCost")}</dt>
            <dd className="text-lg font-semibold tabular-nums text-ink" data-testid="deal-option-cost">
              {/* The server says the net ("≈ ¥0" when the adjustment covers the cost: the verifier floors it on purpose, never a gain). */}
              {e.net_words ?? e.net_display}
            </dd>
          </div>
          <div className="mt-1 flex items-baseline justify-between gap-3 text-supporting text-ink-3">
            <dt>{t("biz.deals.fundingCost")}</dt>
            <dd className="tabular-nums">{e.funding_cost_display}</dd>
          </div>
          <div className="flex items-baseline justify-between gap-3 text-supporting text-ink-3">
            <dt>{t("biz.deals.offset")}</dt>
            <dd className="tabular-nums">−{e.offset_display}</dd>
          </div>
        </dl>
      ) : null}
      {action ? <div className="mt-3">{action}</div> : null}
      <Disclosure testId="deal-option-details" className="mt-3 text-sm" summary={t("biz.deals.optionDetails", { label: c.label })}>
        <p className="mt-2 text-meta font-semibold uppercase tracking-wide text-ink-3">{t("biz.deals.whyWorks")}</p>
        <p className="mt-1 text-ink-2">{c.rationale_when ?? c.rationale}</p>
        <p className="mt-3 text-meta font-semibold uppercase tracking-wide text-ink-3">{t("biz.deals.sourceTerms")}</p>
        <ul className="mt-1 list-disc space-y-1 pl-5 text-ink-2" data-testid="deal-option-terms">
          {c.obligations.map((o) => (
            <li key={o.id}>{obligationSentence(o, t, te, today)}</li>
          ))}
        </ul>
      </Disclosure>
    </li>
  );
}

/**
 * What the buyer answered once a counter was sent. DEAL: the agreement now on the books, its terms as sentences. NO_DEAL:
 * each counter and the buyer's refusal, then what happens next: whether the funding for the gap still ran on the books
 * (the server's operation statuses) with the way to Cash & funding. The buyer's own words, which can carry the engine's
 * day numbers, wait behind "What the buyer wrote". The counters are the verifier's; this card only reports the answer.
 */
function NegotiationOutcome({ negotiation }: { negotiation: NegotiationView }) {
  const { t } = useI18n();
  const deal = negotiation.outcome === "DEAL";
  const accepted = negotiation.rounds.find((r) => r.buyer_response === "ACCEPT");
  const ran = negotiation.operations.filter((o) => o.status === "EXECUTED");
  const words = negotiation.rounds.filter((r) => r.buyer_text);
  return (
    <Card flat id="counters" title={t("biz.deals.answerTitle")}>
      {deal ? (
        <>
          <p className="text-base font-semibold text-ink" data-testid="deal-negotiation">
            {t("biz.deals.dealDone", { counter: accepted?.counter_label_when ?? accepted?.counter_label ?? "" })}
          </p>
          {/* The agreed terms are said once, in the Agreements card; this is the way to it. */}
          <p className="mt-2">
            <a href="#commitments" className={textLinkClass}>
              {t("biz.deals.seeAgreement")}
            </a>
          </p>
        </>
      ) : (
        <>
          <p className="text-base font-semibold text-ink" data-testid="deal-negotiation">
            {t("biz.deals.noDeal")}
          </p>
          <ol className="mt-3 space-y-1.5" data-testid="deal-rounds">
            {negotiation.rounds.map((r) => (
              <li key={r.round} className="flex flex-wrap items-center gap-2 text-sm">
                <span className="font-medium text-ink">{t("biz.deals.round", { n: r.round })}</span>
                {r.counter_label ? <span className="text-ink-2">{r.counter_label_when ?? r.counter_label}</span> : null}
                <Badge tone={r.buyer_response === "ACCEPT" ? "ok" : "neutral"}>{r.buyer_response === "ACCEPT" ? t("biz.deals.accepted") : t("biz.deals.refused")}</Badge>
              </li>
            ))}
          </ol>
          {ran.length ? (
            <div className="mt-3 rounded-tile border border-ok-line bg-ok-bg px-3 py-2 text-sm" data-testid="deal-gap-funded">
              <p className="font-medium text-ok-fg">{t("biz.deals.gapFunded")}</p>
              <Link href="/cash" className={`mt-1 ${textLinkClass}`}>
                {t("biz.deals.seeCash")}
              </Link>
            </div>
          ) : (
            <p className="mt-3 text-sm text-ink-2" data-testid="deal-nothing-changed">
              {t("biz.deals.nothingChanged")}
            </p>
          )}
        </>
      )}
      {words.length ? (
        <Disclosure testId="deal-buyer-words" className="mt-3 text-sm" summary={t("biz.deals.buyerWrote")}>
          <ul className="mt-1.5 space-y-1.5 text-ink-2">
            {words.map((r) => (
              <li key={r.round} className="break-words">
                {r.buyer_text}
              </li>
            ))}
          </ul>
        </Disclosure>
      ) : null}
    </Card>
  );
}

/**
 * One counter's send control. Above the button, in 14 px ink, what sending does: "This will" and the server's lines (the agreement it
 * records, the funding it draws or requests, the estimated cost), or the server's one `send_scope` sentence when it sent no lines. The first
 * press asks once, as Home's Run does; the second sends exactly what is shown. The outbound guard's hold says the wording was held back.
 * The question also asks how the demo's simulated buyer leans (feat/upgrading): open to a counter, or holding firm, which refuses it.
 */
function SendControl({ c, lines, primary, filled = primary, sending, busy, onSend }: { c: Counter; lines: string[] | null; primary: boolean; /** Brand-filled (the page's one primary); the test ids follow `primary`. */ filled?: boolean; sending: boolean; busy: boolean; onSend: (profile: BuyerProfile) => void }) {
  const { t } = useI18n();
  const [confirming, setConfirming] = useState(false);
  const [profile, setProfile] = useState<BuyerProfile>("cooperative");
  // The outbound guard held this counter's wording back: it cannot be sent as it stands.
  const held = Boolean(c.outbound_blocked);
  const scopeId = `scope-${optionDomId(c.label)}`;
  const name = c.label_when ?? c.label;
  const suffix = primary ? "" : `-${c.label.replace(/\s+/g, "-")}`;
  return (
    <div className="space-y-3">
      {!held ? (
        lines?.length ? (
          <div id={scopeId} data-testid="deal-send-scope">
            <p className="text-sm font-semibold text-ink">{t("biz.deals.send.thisWill")}</p>
            <ul className="mt-1 list-disc space-y-0.5 pl-4 text-sm text-ink sm:pl-5" data-testid="deal-send-scope-lines">
              {lines.map((l) => (
                <li key={l}>{l}</li>
              ))}
            </ul>
          </div>
        ) : (
          <p id={scopeId} className="max-w-prose text-sm text-ink" data-testid="deal-send-scope">
            {c.send_scope || t("biz.deals.send.simulated")}
          </p>
        )
      ) : null}
      {confirming && !held ? (
        <div className="rounded-tile border border-brand-100 bg-brand-50 p-4" role="group" aria-labelledby={`send-confirm-${c.id}`} data-testid={`deal-send-confirm-box${suffix}`}>
          <p id={`send-confirm-${c.id}`} className="font-semibold text-ink">
            {t("biz.deals.send.confirmTitle", { label: name })}
          </p>
          <p className="mt-0.5 text-sm text-ink-2">{t("biz.deals.send.confirmBody")}</p>
          <div className="mt-3 flex flex-wrap items-center gap-3">
            <span className="text-supporting font-medium text-ink-2">{t("biz.deals.send.profile")}</span>
            <Segmented<BuyerProfile>
              label={t("biz.deals.send.profile")}
              name={`deal-buyer-profile-${c.id}`}
              value={profile}
              onChange={setProfile}
              options={[
                { value: "cooperative", label: t("biz.deals.send.cooperative") },
                { value: "hard_line", label: t("biz.deals.send.hardLine") },
              ]}
            />
          </div>
          {profile === "hard_line" ? (
            <p className="mt-2 text-sm text-ink-2" data-testid={`deal-send-refusal${suffix}`}>
              {t("biz.deals.send.ifRefuseOne")}
            </p>
          ) : null}
          <div className="mt-3 flex flex-wrap gap-2">
            <Button variant="primary" loading={sending} disabled={busy} onClick={() => { onSend(profile); setConfirming(false); }} data-testid={`deal-send-confirm${suffix}`}>
              {sending ? t("biz.deals.sending") : t("biz.deals.send.confirmGo", { label: name })}
            </Button>
            <Button variant="secondary" disabled={busy} onClick={() => setConfirming(false)} data-testid={`deal-send-cancel${suffix}`}>
              {t("biz.confirm.cancel")}
            </Button>
          </div>
        </div>
      ) : (
        <div className="flex flex-wrap items-center gap-3">
          <Button
            variant={filled ? "primary" : "secondary"}
            loading={sending}
            disabled={held || busy}
            aria-describedby={scopeId}
            onClick={() => setConfirming(true)}
            data-testid={primary ? "deal-send" : `deal-send-${c.label.replace(/\s+/g, "-")}`}
          >
            {sending ? t("biz.deals.sending") : t("biz.deals.sendOption", { label: name })}
          </Button>
          {held ? (
            <span className="text-supporting font-medium text-warn-fg" role="status" data-testid="deal-send-blocked">
              {t("biz.deals.send.blocked")}
            </span>
          ) : null}
        </div>
      )}
    </div>
  );
}

/**
 * The refusal of a send the books have outgrown (409 COUNTER_CHANGED): nothing was sent. With the current counters the card shows
 * them in place of the old ones; without them (`reevaluate`) the old proposal is withdrawn and "Check again" gets a new one.
 */
function CounterChanged({ detail, onCheck, checking }: { detail: CounterChangedDetail; onCheck: () => void; checking: boolean }) {
  const { t } = useI18n();
  const current = detail.counters.length > 0;
  return (
    <div className="mb-4" role="alert" data-testid="deal-counter-changed" data-reason={detail.reason}>
      <Callout tone="warn" title={t("biz.deals.changed.title")}>
        <p>{current ? t("biz.deals.changed.current") : t("biz.deals.changed.reevaluate")}</p>
        {detail.reevaluate || !current ? (
          <Button className="mt-2" size="sm" variant="secondary" loading={checking} onClick={onCheck} data-testid="deal-check-again">
            {t("biz.deals.checkAgain")}
          </Button>
        ) : null}
      </Callout>
    </div>
  );
}

/**
 * "Recommended response": the first counter as the response to send, the next one behind "Compare another option" with its own send,
 * and what the buyer answered once a counter was sent. Each send names its option, runs the bounded negotiation with the demo's buyer
 * kernel (the label and the server's scope sentence say the reply is simulated), and carries what the owner was shown: the verdict
 * id, the counter id and the verdict's `state_version`. If the books moved the API refuses (409 COUNTER_CHANGED) and nothing is sent.
 * The counters are the verifier's, priced and re-checked on the books; the card only shows them.
 */
export function RecommendedResponse({
  v,
  offerId,
  today,
  mode,
  negotiation,
  compareOpen,
  onCompareChange,
  reply,
  bare = false,
  onBusy,
}: {
  v: VerdictView;
  offerId: string;
  today: number;
  mode: Mode;
  negotiation: NegotiationView | null;
  /** The page may hold whether the other options are shown (Option B); without it the card keeps its own state. */
  compareOpen?: boolean;
  onCompareChange?: (open: boolean) => void;
  /** The path picked on the paths picture: the card is then the reply bar for that path (and the counter cards are not shown). */
  reply?: { path: PicturePath; recommended: PicturePath | null; onBack: () => void };
  /** With `reply`: only the send (what it does, the confirm, the refusals and slow notices) in a plain block, for a card that already says the reply. */
  bare?: boolean;
  /** Told whenever a send or a check is in flight, so the page can hold what would unmount it. */
  onBusy?: (busy: boolean) => void;
}) {
  const { t } = useI18n();
  // On a phone the generic line under the title gives way to the answer: the Send button comes up the page.
  const narrow = useNarrow();
  const [localCompare, setLocalCompare] = useState(false);
  const compare = compareOpen ?? localCompare;
  const setCompare = (open: boolean) => (onCompareChange ? onCompareChange(open) : setLocalCompare(open));
  const [sending, setSending] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  // The refusal belongs to the verdict it answered: a new evaluation (same id, other books) starts clean.
  const shownKey = `${v.id}:${v.state_version}`;
  const [refused, setRefused] = useState<{ key: string; detail: CounterChangedDetail } | null>(null);
  const [checking, setChecking] = useState(false);
  // The send ran out of time: it may have landed. Retry reads the deal's record and the books again and sends nothing.
  const [slow, setSlow] = useState(false);
  const [rechecked, setRechecked] = useState(false);
  const inFlight = sending !== null || checking;
  useEffect(() => {
    onBusy?.(inFlight);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- reports the flight, not the callback
  }, [inFlight]);
  const changed = refused && refused.key === shownKey ? refused.detail : null;
  // What the owner is looking at, and what the send will carry: the evaluation's, or the current proposal the API sent back.
  const shown = changed && changed.counters.length ? { verdictId: changed.verdict_id ?? v.id, stateVersion: changed.state_version, counters: changed.counters as Counter[] } : { verdictId: v.id, stateVersion: v.state_version, counters: v.counters as Counter[] };
  const withdrawn = Boolean(changed && !changed.counters.length);
  const counters = withdrawn ? [] : shown.counters;

  async function send(c: Counter, profile: BuyerProfile = "cooperative") {
    setSending(c.id);
    setError(null);
    setSlow(false);
    setRechecked(false);
    try {
      recordNegotiation(await negotiate(offerId, { buyer_profile: profile, verdict_id: shown.verdictId, counter_id: c.id, state_version: shown.stateVersion }));
      setRefused(null);
    } catch (e) {
      const moved = counterChanged(e);
      if (isTimeout(e)) {
        setSlow(true);
        bump();
      } else if (moved) setRefused({ key: shownKey, detail: moved });
      else setError(errorText(e, t));
    } finally {
      setSending(null);
    }
  }

  async function checkAgain() {
    setChecking(true);
    setError(null);
    try {
      await evaluateAndCache(offerId);
      setRefused(null);
    } catch (e) {
      setError(errorText(e, t));
    } finally {
      setChecking(false);
    }
  }

  if (!v.counters.length) {
    return (
      <Card id="counters" title={t("biz.deals.response")}>
        <p className="text-sm text-ink-2" data-testid="deal-no-offer">
          {t("glance.offer.none")}
        </p>
      </Card>
    );
  }
  // The buyer has answered: the outcome replaces the counters, which are no longer choices.
  if (negotiation) return <NegotiationOutcome negotiation={negotiation} />;
  const [first, ...rest] = counters;
  const busy = sending !== null;
  // The server's "This will" lines belong to the priced response (the recommended counter); another counter keeps its one sentence.
  const pricedLines = (c: Counter): string[] | null => (v.workspace?.priced_response?.counter_id === c.id ? (v.workspace.priced_response.send_scope_lines ?? null) : null);
  const controlFor = (c: Counter, primary: boolean) =>
    mode === "business" ? <SendControl c={c} lines={pricedLines(c)} primary={primary} sending={sending === c.id} busy={busy} onSend={(profile) => void send(c, profile)} /> : undefined;

  if (reply) {
    const { path } = reply;
    // The counter behind the path: by its id, or (after a 409 brought current counters) by its name.
    const counter = withdrawn ? undefined : counters.find((c) => c.id === path.key) ?? counters.find((c) => (c.label_when ?? c.label) === path.label);
    const canSend = path.sendable && counter && mode === "business";
    const eyebrow = !path.sendable ? t("biz.deals.reply.cannot") : path.needs_owner ? t("biz.deals.reply.approveFirst", { label: path.label }) : t("biz.deals.reply.eyebrow", { label: path.label });
    // Who decides: the server's class and words (else the earlier sentence), in the class's tone: the same tone as the path's column.
    const tone = authorityTone(path);
    const decides = authorityText(path);
    if (bare) {
      return (
        <div id="counters" className="space-y-3" data-testid="path-reply" data-counters={changed && changed.counters.length ? "current" : "evaluated"} data-path={path.key === "asked" ? "asked" : path.recommended ? "recommended" : "other"}>
          {changed ? <CounterChanged detail={changed} onCheck={() => void checkAgain()} checking={checking} /> : null}
          {canSend ? <SendControl key={counter.id} c={counter} lines={pricedLines(counter)} primary={path.recommended} filled sending={sending === counter.id} busy={busy} onSend={(profile) => void send(counter, profile)} /> : null}
          {slow ? (
            <SlowNotice
              message={t("err.timeout_write")}
              onRetry={() => {
                setSlow(false);
                setRechecked(true);
                bump();
              }}
            />
          ) : rechecked && !error ? (
            <p className="rounded-tile border border-line bg-subtle px-3.5 py-2.5 text-sm text-ink-2" role="status" data-testid="slow-checked">
              {t("biz.slow.checked")}
            </p>
          ) : null}
          {error ? <ErrorState error={error} /> : null}
        </div>
      );
    }
    return (
      <ActionBar id="counters" aria-labelledby="path-reply-title" data-testid="path-reply" data-counters={changed && changed.counters.length ? "current" : "evaluated"} data-path={path.key === "asked" ? "asked" : path.recommended ? "recommended" : "other"}>
        {changed ? (
          <div className="w-full">
            <CounterChanged detail={changed} onCheck={() => void checkAgain()} checking={checking} />
          </div>
        ) : null}
        <div className="min-w-0 flex-[2_1_20rem]">
          <p className={`text-meta font-extrabold uppercase tracking-[0.08em] ${tone === "bad" ? "text-bad-fg" : tone === "warn" ? "text-warn-fg" : tone === "neutral" ? "text-ink-3" : "text-brand-700"}`}>{eyebrow}</p>
          <h2 id="path-reply-title" className="mt-1 text-pretty text-base font-extrabold leading-snug text-ink sm:text-lg" data-testid="path-reply-text">
            {path.sendable ? (path.reply_text ?? decides) : decides}
          </h2>
          {path.sendable ? (
            <p className="mt-1.5" data-testid="path-reply-decides" data-authority={path.authority ?? ""}>
              <StatePill tone={tone}>{decides}</StatePill>
            </p>
          ) : null}
        </div>
        <div className="min-w-0 flex-[1_1_16rem]">
          {canSend ? (
            <SendControl key={counter.id} c={counter} lines={pricedLines(counter)} primary={path.recommended} filled sending={sending === counter.id} busy={busy} onSend={(profile) => void send(counter, profile)} />
          ) : !path.sendable && reply.recommended && reply.recommended.key !== path.key ? (
            <Button variant="secondary" onClick={reply.onBack} data-testid="path-reply-back">
              {t("biz.deals.reply.back", { label: reply.recommended.label })}
            </Button>
          ) : mode === "demo" ? (
            <p className="text-supporting text-ink-3">
              {t("biz.deals.negotiateHint")}{" "}
              <Link href="/verdict#negotiation" className={textLinkClass}>
                {t("biz.deals.negotiateLink")}
              </Link>
            </p>
          ) : null}
        </div>
        {slow ? (
          <div className="w-full">
            <SlowNotice
              message={t("err.timeout_write")}
              onRetry={() => {
                setSlow(false);
                setRechecked(true);
                bump();
              }}
            />
          </div>
        ) : rechecked && !error ? (
          <p className="w-full rounded-tile border border-line bg-subtle px-3.5 py-2.5 text-sm text-ink-2" role="status" data-testid="slow-checked">
            {t("biz.slow.checked")}
          </p>
        ) : null}
        {error ? (
          <div className="w-full">
            <ErrorState error={error} />
          </div>
        ) : null}
      </ActionBar>
    );
  }
  return (
    <Card id="counters" title={t("biz.deals.response")} subtitle={narrow ? undefined : t("biz.deals.counters.sub")}>
      {changed ? <CounterChanged detail={changed} onCheck={() => void checkAgain()} checking={checking} /> : null}
      {first ? (
        <ul className="motion-rise divide-y divide-line">
          <CounterBusinessCard c={first} recommended today={today} action={controlFor(first, true)} />
          {compare ? rest.map((c) => <CounterBusinessCard key={c.id} c={c} recommended={false} today={today} action={controlFor(c, false)} />) : null}
        </ul>
      ) : null}
      {slow ? (
        <div className="mt-3">
          <SlowNotice
            message={t("err.timeout_write")}
            onRetry={() => {
              setSlow(false);
              setRechecked(true);
              bump();
            }}
          />
        </div>
      ) : rechecked && !error ? (
        <p className="mt-3 rounded-tile border border-line bg-subtle px-3.5 py-2.5 text-sm text-ink-2" role="status" data-testid="slow-checked">
          {t("biz.slow.checked")}
        </p>
      ) : null}
      {error ? (
        <div className="mt-3">
          <ErrorState error={error} />
        </div>
      ) : null}
      <div className="mt-3 flex flex-wrap items-center gap-3">
        {rest.length ? (
          <Button variant="secondary" onClick={() => setCompare(!compare)} data-testid="deal-compare">
            {compare ? t("biz.deals.hideCompare") : t("biz.deals.compare", { n: rest.length })}
          </Button>
        ) : null}
        {mode === "demo" ? (
          <p className="text-supporting text-ink-3">
            {t("biz.deals.negotiateHint")}{" "}
            <Link href="/verdict#negotiation" className={textLinkClass}>
              {t("biz.deals.negotiateLink")}
            </Link>
          </p>
        ) : null}
      </div>
    </Card>
  );
}
