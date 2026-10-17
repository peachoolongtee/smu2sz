"use client";

import Link from "next/link";
import { ArrowRightIcon } from "@/components/icons";
import { setPanelOpen } from "@/lib/chat";
import { useI18n } from "@/lib/i18n";
import type { NlAnswerCard, NlCardAction, NlCardFigure } from "@/lib/types";

const TILE: Record<NlCardFigure["tone"], string> = {
  danger: "bg-[color-mix(in_srgb,var(--color-f-risk)_8%,var(--color-card))] text-f-risk",
  ok: "bg-[color-mix(in_srgb,var(--color-f-green)_40%,var(--color-card))] text-f-green-ink",
  neutral: "bg-panel text-f-ink",
};

/** The key figures: up to three tiles, each the server's value over its short label; the tone colours the value and is said in words to a screen reader by the label itself. */
function Tiles({ figures }: { figures: NlCardFigure[] }) {
  const { t } = useI18n();
  if (!figures.length) return null;
  return (
    <ul aria-label={t("ask.figuresLabel")} className="grid grid-cols-2 gap-2 min-[420px]:grid-cols-3" data-testid="card-figures">
      {figures.map((f, i) => (
        <li key={`${f.label}-${i}`} className={`min-w-0 rounded-[14px] px-3 py-2.5 ${TILE[f.tone] ?? TILE.neutral}`} data-testid="card-figure" data-tone={f.tone}>
          <p className="break-words font-display text-[17px] font-bold leading-tight tracking-[-0.01em] tabular-nums">{f.value}</p>
          <p className="mt-0.5 text-supporting text-ink-2">{f.label}</p>
        </li>
      ))}
    </ul>
  );
}

/**
 * A link to a section of the page already open changes only the hash, which a client navigation does not announce: once the address is the
 * link's, say so, so the section lands (components/hash-lander.tsx opens and scrolls to it). Gives up after two seconds.
 */
function announceWhenAt(href: string): void {
  const want = new URL(href, window.location.href);
  if (!want.hash) return;
  let tries = 0;
  const tick = () => {
    const here = window.location;
    if (here.pathname === want.pathname && here.search === want.search && here.hash === want.hash) window.dispatchEvent(new Event("hashchange"));
    else if (tries++ < 40) window.setTimeout(tick, 50);
  };
  window.setTimeout(tick, 0);
}

/**
 * The links under an answer, as chips: each opens the page that shows what it names (the server's label and href). A link only: it never
 * approves, sends or runs anything. Opening one closes the side panel so the page is seen.
 */
export function ActionChips({ actions }: { actions: NlCardAction[] }) {
  const { t } = useI18n();
  const links = actions.filter((a) => a.kind === "link" && a.href.startsWith("/") && !a.href.startsWith("//"));
  if (!links.length) return null;
  return (
    <nav aria-label={t("ask.actions")} data-testid="card-actions">
      <ul className="flex flex-wrap gap-2">
        {links.map((a) => (
          <li key={a.href} className="min-w-0 max-w-full">
            <Link
              href={a.href}
              onClick={() => {
                setPanelOpen(false);
                announceWhenAt(a.href);
              }}
              className="motion-press inline-flex min-h-9 max-w-full items-center gap-1.5 rounded-pill border border-[color-mix(in_srgb,var(--color-f-purple)_45%,var(--color-f-line))] bg-card px-3.5 text-meta font-semibold text-f-purple-ink hover:bg-f-purple-soft touch:min-h-11"
              data-testid="card-action"
              data-href={a.href}
            >
              <span className="min-w-0 truncate">{a.label}</span>
              <ArrowRightIcon width={13} height={13} className="shrink-0" />
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}

/** "How FLOW worked this out": closed until opened; the day, the books and the assumptions the answer used, and every figure it read. */
function How({ card }: { card: NlAnswerCard }) {
  const { t } = useI18n();
  const all = card.all_figures?.length ? card.all_figures : card.figures;
  if (!card.basis && !all.length) return null;
  return (
    <details className="group text-supporting" data-testid="card-how">
      <summary className="inline-flex min-h-8 cursor-pointer list-none items-center gap-1.5 rounded-pill pr-2 font-medium text-ink-3 hover:text-ink touch:min-h-11 [&::-webkit-details-marker]:hidden">
        <svg aria-hidden viewBox="0 0 16 16" width={12} height={12} className="transition-transform duration-(--dur-fast) group-open:rotate-90" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round">
          <path d="M6 4l4 4-4 4" />
        </svg>
        {t("ask.how")}
      </summary>
      <div className="mt-1.5 space-y-2 rounded-[14px] bg-panel px-3 py-2.5 text-ink-2">
        {card.basis ? (
          <p data-testid="card-basis">
            <span className="font-semibold text-ink">{t("ask.basis")}: </span>
            {card.basis}
          </p>
        ) : null}
        {all.length ? (
          <dl className="grid grid-cols-[minmax(0,1fr)_auto] gap-x-4 gap-y-1" aria-label={t("ask.figures")} data-testid="card-all-figures">
            {all.map((f, i) => (
              <div key={`${f.label}-${i}`} className="contents">
                <dt className="min-w-0">{f.label}</dt>
                <dd className={`text-right font-semibold tabular-nums ${f.tone === "danger" ? "text-f-risk" : "text-ink"}`}>{f.value}</dd>
              </div>
            ))}
          </dl>
        ) : null}
      </div>
    </details>
  );
}

/**
 * An answer with structure (the server's card): the lead in bold (the yes/no or the figure), the key figures, the rest of the reply, the links,
 * then "How FLOW worked this out". `data-testid="chat-reply"` holds the reply's words (the lead and the rest), as the plain reply did.
 */
export function AnswerCard({ card, reply }: { card: NlAnswerCard; reply: string }) {
  const lead = card.lead.trim();
  return (
    <div className="space-y-3" data-testid="chat-card">
      {lead ? (
        <div className="space-y-3" data-testid="chat-reply">
          <p className="whitespace-pre-wrap break-words text-[15px] font-semibold leading-snug text-ink" data-testid="card-lead">
            {lead}
          </p>
          <Tiles figures={card.figures} />
          {card.body ? (
            <p className="whitespace-pre-wrap break-words text-sm leading-relaxed text-ink-2" data-testid="card-body">
              {card.body}
            </p>
          ) : null}
        </div>
      ) : (
        <>
          <p className="whitespace-pre-wrap break-words text-sm leading-relaxed text-ink" data-testid="chat-reply">
            {reply}
          </p>
          <Tiles figures={card.figures} />
        </>
      )}
      <ActionChips actions={card.actions} />
      <How card={card} />
    </div>
  );
}
