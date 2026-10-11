"use client";

import { ReadWhen } from "@/components/business/freshness";
import { useI18n } from "@/lib/i18n";
import type { HomeStatus, HomeView } from "@/lib/types";

/** The status word's pill: a light tint of the status with its own dot (the dot and the word say it, the tint only helps). Status colour is for status and nothing else. */
const PILL: Record<HomeStatus, { box: string; dot: string }> = {
  SAFE: { box: "border-ok-line bg-ok-bg text-ok-fg", dot: "bg-ok-solid text-ok-solid" },
  WATCH: { box: "border-warn-line bg-warn-bg text-warn-fg", dot: "bg-warn-solid text-warn-solid" },
  ACTION_NEEDED: { box: "border-bad-line bg-bad-bg text-bad-fg", dot: "bg-bad-solid text-bad-solid" },
  CRITICAL: { box: "border-bad-line bg-bad-bg text-bad-fg", dot: "bg-bad-solid text-bad-solid" },
};

/** What is on its way, one server headline per lot ("¥255k funding arriving in 3 days"); an older recording gets the total. */
function InTransit({ transit }: { transit: NonNullable<HomeView["cash"]["in_transit"]> }) {
  const { t } = useI18n();
  return (
    <div className="text-sm text-ink-2">
      <p>
        <span>{t("biz.arriving")} </span>
        <strong className="font-bold tabular-nums text-ink" data-testid="home-arriving">
          {transit.total_display}
        </strong>
      </p>
      <p className="mt-0.5" data-testid="home-in-transit">
        {transit.lots.every((l) => l.headline) ? transit.lots.map((l) => <span key={`${l.facility_name}-${l.arrival_day}-${l.amount_display}`} className="block">{l.headline}</span>) : t("biz.inTransit", { amount: transit.total_display })}
      </p>
    </div>
  );
}

/**
 * The Home headline, straight on the page with no card: the status pill, the one `h1` (the server's sentence as it is, never parsed or
 * part-coloured), the note behind it, what is still arriving, and, when nothing is unsafe, the worst point as one quiet line. The cash picture
 * (components/home/cash-picture.tsx) says the rest: today's cash, the reserve, the first breach, the lowest point and what moves the line.
 * Every sentence and figure is the server's.
 */
export function StatusBlock({ h }: { h: HomeView }) {
  const { te } = useI18n();
  const pill = PILL[h.status] ?? PILL.WATCH;
  const pulses = h.status === "ACTION_NEEDED" || h.status === "CRITICAL";
  const unsafe = h.cash.first_breach_day !== null;
  return (
    <header aria-labelledby="home-status-title" className="motion-reveal flex flex-col items-start gap-2.5 short:gap-2" data-testid="home-status" data-status={h.status}>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <span className={`inline-flex items-center gap-2 rounded-pill border px-3 py-1 text-xs font-extrabold uppercase tracking-[0.06em] ${pill.box}`} data-testid="home-status-word">
          {/* The dot repeats the pill's status as a mark; it pulses once when the status asks for the owner (never on a calm one). */}
          <span aria-hidden className={`relative size-1.5 shrink-0 rounded-pill ${pill.dot} ${pulses ? "motion-pulse" : ""}`} />
          {h.status_text ?? te("homestatus", h.status)}
        </span>
        {/* How fresh the conclusion is: the server's own "when" for the read the figures come from. */}
        <ReadWhen when={h.cash.last_read_when} testId="home-read-when" />
      </div>
      <h1 id="home-status-title" className="max-w-4xl text-balance font-display text-[1.75rem] font-extrabold leading-[1.12] tracking-[-0.025em] text-ink sm:text-4xl lg:text-[2.5rem] short:lg:text-4xl" data-testid="home-headline">
        {h.headline}
      </h1>
      <p className="max-w-3xl text-pretty text-base text-ink-2 sm:text-[1.0625rem] sm:leading-normal" data-testid="home-note">
        {h.note}
      </p>
      {h.cash.in_transit ? <InTransit transit={h.cash.in_transit} /> : null}
      {!unsafe && h.worst ? (
        <p className="max-w-3xl text-sm text-ink-3" data-testid="home-worst">
          {h.worst}
        </p>
      ) : null}
    </header>
  );
}
