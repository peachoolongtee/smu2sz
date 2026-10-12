"use client";

import { useRef } from "react";
import { HUE, hueOf, Swatch } from "@/components/deals/path-hue";
import { StatePill, toggleClass, type Tone } from "@/components/ui";
import { useI18n } from "@/lib/i18n";
import type { CounterEconomics, PathAuthority, PicturePath } from "@/lib/types";

const toneOfTag = (tone: PicturePath["tag_tone"]): Tone => (tone === "mute" ? "neutral" : tone);

/** The three classes of who decides, one tone each (the verifier chose the class; this is the fixed map of class to tone). */
const AUTHORITY_TONE: Record<PathAuthority, Tone> = { flow_may: "ok", needs_owner: "warn", over_limit: "bad" };

/** The tone of the "who decides" line: the server's class when it sent one, else (an older server) what the path already said about itself. */
export function authorityTone(p: PicturePath): Tone {
  if (p.authority) return AUTHORITY_TONE[p.authority];
  return p.needs_owner ? "warn" : p.sendable ? "ok" : "neutral";
}

/** The server's words for who decides, else the earlier `decides_text`. */
export const authorityText = (p: PicturePath): string => p.authority_text ?? p.decides_text;

/**
 * One column per path, in the server's order, as a radio group: the line's key (the same swatch as the tiles) and the path's name and tag, its cost on
 * one basis with the parts of a net cost beneath it, its three terms (what it is, then what it replaces, muted), where its cash is lowest, who decides
 * (in the server's class and tone) and the button that puts the path on the chart. Pointing at or focusing a column lights its line on the chart.
 * Every word and figure is the server's; the colour is never the only channel (the name, the tag and the words say the same).
 *
 * An older server sends `cost_display` / `cost_note` and no total, basis or components: a reply whose counter carries a net economic cost then shows
 * that net with its two parts (`economics`, the verifier's), so a zero net never stands alone.
 */
export function PathColumns({
  paths,
  pick,
  onPick,
  onHover,
  economics,
  windowMonths,
  locked = false,
}: {
  paths: PicturePath[];
  pick: string;
  onPick: (key: string) => void;
  onHover: (key: string | null) => void;
  /** The verifier's economics of the counter behind a reply path, when it has one. */
  economics: (p: PicturePath) => CounterEconomics | null;
  /** The server's valuation window in months (the verdict's `financial_impact.window_months`), for the words of the ongoing figure. */
  windowMonths?: number | null;
  /** A send is in flight: the picks are held, so the reply that is being sent cannot change under it. */
  locked?: boolean;
}) {
  const { t } = useI18n();
  const group = useRef<HTMLDivElement>(null);
  const move = (from: number, by: number) => {
    const next = (from + by + paths.length) % paths.length;
    onPick(paths[next].key);
    group.current?.querySelectorAll<HTMLButtonElement>("[role=radio]")[next]?.focus();
  };
  return (
    <div ref={group} role="radiogroup" aria-label={t("biz.deals.paths.group")} className="flex flex-wrap items-stretch gap-3" data-testid="path-columns">
      {paths.map((p, i) => {
        const on = p.key === pick;
        const hue = HUE[hueOf(p)];
        const eco = p.cost_total_display ? null : economics(p);
        const net = eco?.is_net ? eco : null;
        const total = p.cost_total_display ?? (net ? (net.net_words ?? net.net_display) : p.cost_display);
        const basis = p.cost_basis_text ?? p.cost_note;
        const mixed = Boolean(p.cost_once_display && p.cost_forward_display);
        const parts = p.cost_components?.length ? p.cost_components : net ? [{ label: t("biz.deals.fundingCost"), display: net.funding_cost_display }, { label: t("biz.deals.offset"), display: `−${net.offset_display}` }] : [];
        const tone = authorityTone(p);
        const lowest = p.lowest_short && p.lowest_when ? t("biz.deals.paths.lowestAt", { amount: p.lowest_short, when: p.lowest_when }) : null;
        return (
          <div
            key={p.key}
            data-testid={`path-col-${i}`}
            data-selected={on ? "true" : "false"}
            onPointerEnter={(e) => e.pointerType === "mouse" && onHover(p.key)}
            onPointerLeave={() => onHover(null)}
            // Keyboard focus lights the line too; a tap that happens to focus the button does not (it would leave the other lines dimmed).
            onFocus={(e) => e.target.matches(":focus-visible") && onHover(p.key)}
            onBlur={() => onHover(null)}
            className={`motion-reveal flex min-w-0 flex-[1_1_15rem] flex-col gap-2.5 rounded-card border-2 bg-surface p-3.5 transition-[border-color,box-shadow] duration-(--dur) ease-out ${on ? `${hue.border} shadow-card` : "border-line"}`}
          >
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h3 className="inline-flex items-center gap-2 text-base font-extrabold text-ink">
                <Swatch hue={hueOf(p)} />
                {p.label}
              </h3>
              <StatePill tone={toneOfTag(p.tag_tone)}>{p.tag_text}</StatePill>
            </div>
            <div>
              {mixed ? (
                // Both a one-off and an ongoing cost: each its own figure and words, no single headline (so the two never read as a sum).
                <>
                  <p className="sr-only">{t("biz.deals.paths.cost")}</p>
                  <ul className="space-y-0.5" data-testid={`path-col-parts-${i}`}>
                    <li className={`text-xl font-extrabold tracking-[-0.02em] tabular-nums ${tone === "bad" ? "text-bad-fg" : "text-ink"}`} data-testid={`path-col-forward-${i}`}>
                      {windowMonths ? t("biz.deals.paths.forwardLine", { amount: p.cost_forward_display ?? "", n: windowMonths }) : t("biz.deals.paths.ongoingLine", { amount: p.cost_forward_display ?? "" })}
                    </li>
                    <li className={`text-xl font-extrabold tracking-[-0.02em] tabular-nums ${tone === "bad" ? "text-bad-fg" : "text-ink"}`} data-testid={`path-col-once-${i}`}>
                      {t("biz.deals.paths.onceLine", { amount: p.cost_once_display ?? "" })}
                    </li>
                  </ul>
                </>
              ) : (
                <>
                  <p className={net && !p.cost_total_display ? "text-xs text-ink-3" : "sr-only"}>{net && !p.cost_total_display ? t("biz.deals.netCost") : t("biz.deals.paths.cost")}</p>
                  <p className={`text-2xl font-extrabold tracking-[-0.02em] tabular-nums ${tone === "bad" ? "text-bad-fg" : "text-ink"}`} data-testid={`path-col-cost-${i}`}>
                    {total}
                  </p>
                  <p className="text-sm text-ink-2" data-testid={`path-col-basis-${i}`}>
                    {basis}
                  </p>
                </>
              )}
              {parts.length ? (
                <dl className="mt-2 divide-y divide-line border-y border-line text-xs" data-testid={`path-col-components-${i}`}>
                  {parts.map((c) => (
                    <div key={c.label} className="flex items-baseline justify-between gap-3 py-1">
                      <dt className="text-ink-3">{c.label}</dt>
                      <dd className="font-semibold tabular-nums text-ink-2">{c.display}</dd>
                    </div>
                  ))}
                </dl>
              ) : null}
            </div>
            <dl className="space-y-1.5 text-sm">
              {p.terms.map((term) => (
                <div key={term.key} className="flex flex-wrap items-baseline gap-x-2">
                  <dt className="text-xs text-ink-3">{term.label}</dt>
                  <dd className="font-bold text-ink">
                    {term.value_text}
                    {term.instead_of_text ? <span className="ml-1.5 font-semibold text-ink-3">{term.instead_of_text}</span> : null}
                  </dd>
                </div>
              ))}
            </dl>
            {lowest || p.first_breach_when || p.band_text ? (
              <ul className="space-y-0.5 text-sm text-ink-2" data-testid={`path-col-facts-${i}`}>
                {lowest ? <li data-testid={`path-col-lowest-${i}`}>{lowest}</li> : null}
                {p.first_breach_when ? (
                  <li className="font-bold text-bad-fg" data-testid={`path-col-breach-${i}`}>
                    {t("biz.deals.paths.breach", { when: p.first_breach_when })}
                  </li>
                ) : null}
                {p.band_text ? (
                  <li className="text-xs text-ink-3" data-testid={`path-col-band-${i}`}>
                    {p.band_text}
                  </li>
                ) : null}
              </ul>
            ) : null}
            <div className="mt-auto space-y-2 border-t border-line pt-2.5">
              <p data-testid={`path-col-decides-${i}`} data-authority={p.authority ?? ""}>
                <StatePill tone={tone}>{authorityText(p)}</StatePill>
              </p>
              <button
                type="button"
                role="radio"
                aria-checked={on}
                disabled={locked}
                tabIndex={on ? 0 : -1}
                data-testid={`path-col-pick-${i}`}
                onClick={() => onPick(p.key)}
                onKeyDown={(e) => {
                  if (e.key === "ArrowRight" || e.key === "ArrowDown") {
                    e.preventDefault();
                    move(i, 1);
                  } else if (e.key === "ArrowLeft" || e.key === "ArrowUp") {
                    e.preventDefault();
                    move(i, -1);
                  }
                }}
                className={toggleClass(on, "md", "w-full")}
              >
                {on ? t("biz.deals.paths.showing") : t("biz.deals.paths.show")}
                <span className="sr-only">: {p.label}</span>
              </button>
            </div>
          </div>
        );
      })}
    </div>
  );
}
