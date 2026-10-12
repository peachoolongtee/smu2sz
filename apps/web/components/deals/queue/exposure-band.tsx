"use client";

import { Disclosure } from "@/components/business/kit";
import { toggleClass } from "@/components/ui";
import { useI18n } from "@/lib/i18n";
import type { ExposureView } from "@/lib/types";
import { eyebrowCls } from "./queue-list";

/**
 * "Your exposure to {buyer}": three short facts under the path columns, for the picked path. The concentration is the same for every path; the late-payment test
 * and the room for another payment follow the pick (the read carries every path, so switching needs no new request). Every sentence is the server's
 * (`band`); a tile with no sentence is not drawn, and the whole band is absent when the read has none. Context, never a verdict: no tile changes what FLOW recommends.
 */
export function ExposureBand({ exposure, pick }: { exposure: ExposureView; pick: string }) {
  const { t } = useI18n();
  const buyer = exposure.concentration.buyer_name;
  const lead = exposure.band.by_path[pick];
  const caps = exposure.capacity[pick];
  const windows = caps?.available ? caps.after.windows : [];
  const tiles = [
    { key: "concentration", label: t("dq.band.concentration"), text: exposure.band.concentration, tone: exposure.flag.material ? "warn" : "neutral", note: null as string | null },
    { key: "late", label: t("dq.band.late", { n: exposure.stress.delay_days }), text: lead?.stress ?? null, tone: "neutral", note: exposure.payments_note ?? exposure.payments.sentence },
    { key: "capacity", label: t("dq.band.capacity"), text: lead?.capacity ?? null, tone: "neutral", note: null },
  ].filter((x) => x.text);
  if (!tiles.length) return null;
  return (
    <section aria-labelledby="dq-band-title" className="motion-reveal space-y-2 border-t border-line pt-3" data-testid="exposure-band">
      <h3 id="dq-band-title" className={`${eyebrowCls} text-ink-3`}>
        {t("dq.band.title", { buyer })}
      </h3>
      <dl className="grid gap-3">
        {tiles.map((x) => (
          <div key={x.key} className={`min-w-0 border-l-[3px] pl-3 ${x.tone === "warn" ? "border-warn-solid" : "border-line-strong"}`} data-testid={`exposure-${x.key}`}>
            <dt className="text-[0.8125rem] font-semibold text-ink-3">{x.label}</dt>
            <dd className="mt-0.5 text-sm text-ink">
              {x.text}
              {x.note ? <span className="mt-1 block text-[0.8125rem] text-ink-3">{x.note}</span> : null}
            </dd>
          </div>
        ))}
      </dl>
      {windows.length ? (
        <Disclosure testId="exposure-capacity" className="text-sm" summary={t("dq.band.detail")}>
          <ul className="space-y-2 pt-1">
            {windows.map((w, i) => (
              <li key={`${w.dimension}-${i}`} className="min-w-0 text-sm text-ink">
                <span className="font-semibold">{w.label}</span>
                {w.facility_name ? <span className="text-ink-3">{` · ${w.facility_name}`}</span> : null}
                <span className="block text-ink-2">{w.after_text ? t("dq.band.todayAfter", { today: w.today_text ?? "—", after: w.after_text }) : (w.today_text ?? "")}</span>
                {w.recovers_when ? <span className="block text-[0.8125rem] text-ink-3">{t("dq.band.recovers", { when: w.recovers_when })}</span> : null}
                {w.recovery_assumed_text ? <span className="block text-[0.8125rem] text-ink-3">{w.recovery_assumed_text}</span> : null}
              </li>
            ))}
          </ul>
        </Disclosure>
      ) : null}
    </section>
  );
}

/** The paid-late toggle above the chart: one dashed grey line for the picked path. It never changes the pick; its sentence is the read's assumption ("a test, not a forecast"). */
export function StressToggle({ exposure, on, onChange }: { exposure: ExposureView; on: boolean; onChange: (on: boolean) => void }) {
  const { t } = useI18n();
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1" data-testid="stress-toggle-row">
      <button type="button" aria-pressed={on} onClick={() => onChange(!on)} className={toggleClass(on)} data-testid="stress-toggle">
        {t("dq.stress.toggle", { buyer: exposure.concentration.buyer_name, n: exposure.stress.delay_days })}
      </button>
      <span className="text-[0.8125rem] text-ink-3">{t("dq.stress.note")}</span>
    </div>
  );
}
