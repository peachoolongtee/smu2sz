"use client";

import { useRef } from "react";
import { HUE, hueOf } from "@/components/deals/path-hue";
import { StatePill, type Tone } from "@/components/ui";
import { useI18n } from "@/lib/i18n";
import type { PictureMoment, PicturePath } from "@/lib/types";

const toneOf = (tone: PicturePath["tag_tone"]): Tone => (tone === "mute" ? "neutral" : tone);

/**
 * One column per path, in the server's order, as a radio group: a short colour mark matching the path's line, its name and tag, its cost, its three
 * terms (what it is, then what it replaces, muted), the cash that day on the selected moment (with the server's note in the bad tone when it is under the
 * minimum), who decides, and the button that puts the path on the chart. Every word and figure is the server's; the colour is never the only channel (the
 * name, the tag and the button's words say the same).
 */
export function PathColumns({ paths, pick, onPick, moment }: { paths: PicturePath[]; pick: string; onPick: (key: string) => void; moment: PictureMoment | null }) {
  const { t } = useI18n();
  const group = useRef<HTMLDivElement>(null);
  const move = (from: number, by: number) => {
    const next = (from + by + paths.length) % paths.length;
    onPick(paths[next].key);
    group.current?.querySelectorAll<HTMLButtonElement>("[role=radio]")[next]?.focus();
  };
  return (
    <div ref={group} role="radiogroup" aria-label={t("biz.deals.paths.group")} className="flex flex-wrap items-stretch gap-3.5" data-testid="path-columns">
      {paths.map((p, i) => {
        const on = p.key === pick;
        const hue = HUE[hueOf(p)];
        const cash = moment?.values.find((v) => v.key === p.key) ?? null;
        return (
          <div
            key={p.key}
            data-testid={`path-col-${i}`}
            data-selected={on ? "true" : "false"}
            className={`motion-reveal flex min-w-0 flex-[1_1_15rem] flex-col gap-3 rounded-card border-2 bg-surface p-4 transition-[border-color,box-shadow] duration-(--dur) ease-out ${on ? `${hue.border} ${hue.shadow}` : "border-line"}`}
          >
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h3 className="inline-flex items-center gap-2 text-base font-extrabold text-ink">
                <span aria-hidden className={`h-1 w-[18px] rounded-sm ${hue.bg}`} />
                {p.label}
              </h3>
              <StatePill tone={toneOf(p.tag_tone)}>{p.tag_text}</StatePill>
            </div>
            <div>
              <p className="text-xs text-ink-3">{t("biz.deals.paths.cost")}</p>
              <p className={`text-2xl font-extrabold tracking-[-0.02em] tabular-nums ${p.kind === "asked" && !p.sendable ? "text-bad-fg" : "text-ink"}`} data-testid={`path-col-cost-${i}`}>
                {p.cost_display}
              </p>
              <p className="text-sm text-ink-2">{p.cost_note}</p>
            </div>
            <dl className="space-y-2 text-sm">
              {p.terms.map((term) => (
                <div key={term.key}>
                  <dt className="text-xs text-ink-3">{term.label}</dt>
                  <dd className="font-bold text-ink">
                    {term.value_text}
                    {term.instead_of_text ? <span className="ml-1.5 font-semibold text-ink-3">{term.instead_of_text}</span> : null}
                  </dd>
                </div>
              ))}
            </dl>
            {moment ? (
              <div className="rounded-tile bg-subtle px-3 py-2.5" data-testid={`path-col-cash-${i}`} data-below={cash?.below_floor ? "true" : "false"}>
                <p className="text-xs text-ink-3">{t("biz.deals.paths.cash", { when: moment.label })}</p>
                <p className={`text-lg font-extrabold tabular-nums ${cash?.below_floor ? "text-bad-fg" : "text-ink"}`}>{cash?.closing_display ?? "—"}</p>
                {cash?.below_floor && cash.note ? <p className="text-xs font-bold text-bad-fg">{cash.note}</p> : null}
              </div>
            ) : null}
            <div className="mt-auto space-y-2 border-t border-line pt-3">
              <p className={`text-sm leading-snug ${p.needs_owner ? "font-bold text-warn-fg" : p.sendable ? "font-bold text-ok-fg" : "text-ink-2"}`}>{p.decides_text}</p>
              <button
                type="button"
                role="radio"
                aria-checked={on}
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
                className={`motion-press inline-flex min-h-10 touch:min-h-11 w-full items-center justify-center rounded-control border px-4 text-sm font-bold text-ink ${on ? `${hue.border} bg-subtle` : "border-line-ui bg-surface hover:bg-subtle"}`}
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
