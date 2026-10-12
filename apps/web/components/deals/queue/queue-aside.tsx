"use client";

import Link from "next/link";
import { useI18n } from "@/lib/i18n";
import type { ExposureView } from "@/lib/types";
import { eyebrowCls } from "./queue-list";

/**
 * Why this customer matters: three facts only (a year's contribution when the server has an estimate, what they owe now, their share of what you are owed),
 * the way to the customer's profile, the sentence that this is context and not a promise, the late-payment question (a link into Cash with the test loaded)
 * and the note that both links keep the selection. The figures are the exposure read's strings; the contribution row is absent until the read carries it.
 */
export function QueueAside({ exposure, customerHref, stressHref, pathLabel }: { exposure: ExposureView; customerHref: string; stressHref: string; pathLabel: string }) {
  const { t } = useI18n();
  const buyer = exposure.concentration.buyer_name;
  // The aside's words are the read's `customer_context`; a server that has not sent it gives the concentration's own figures.
  const cc = exposure.customer_context ?? null;
  const owes = cc?.owes_display ?? exposure.concentration.ar_buyer_display;
  const share = cc?.share_text ?? exposure.concentration.ar_share_display;
  return (
    <aside aria-labelledby="dq-aside-title" className="flex min-w-0 flex-col gap-3 lg:border-l lg:border-line lg:pl-6" data-testid="queue-aside">
      <h3 id="dq-aside-title" className={`${eyebrowCls} text-ink-3`}>
        {t("dq.aside.title", { buyer })}
      </h3>
      <dl className="grid grid-cols-[auto_minmax(0,1fr)] items-baseline gap-x-4 gap-y-2.5 text-sm">
        {cc?.contribution_display ? (
          <>
            <dt className="text-ink-3">{t("dq.aside.contribution")}</dt>
            <dd className="m-0" data-testid="aside-contribution">
              <span className="font-display text-base font-extrabold tabular-nums text-ink">{cc.contribution_display}</span>
              {cc.contribution_note ? <span className="block text-[0.8125rem] font-semibold text-warn-fg" data-testid="aside-contribution-note">{cc.contribution_note}</span> : null}
            </dd>
          </>
        ) : null}
        <dt className="text-ink-3">{t("dq.aside.owes")}</dt>
        <dd className="m-0 font-display text-base font-extrabold tabular-nums text-ink" data-testid="aside-owes">
          {owes}
        </dd>
        <dt className="text-ink-3">{t("dq.aside.share")}</dt>
        <dd className={`m-0 font-display text-base font-extrabold tabular-nums ${exposure.flag.material ? "text-warn-fg" : "text-ink"}`} data-testid="aside-share">
          {share}
        </dd>
      </dl>
      <Link href={customerHref} className="text-sm font-bold text-brand-700 hover:underline focus-visible:underline" data-testid="aside-profile">
        {t("dq.aside.profile")} ›
      </Link>
      <p className="border-t border-line pt-2.5 text-[0.8125rem] leading-relaxed text-ink-2">{t("dq.aside.context", { buyer })}</p>
      <Link href={stressHref} className="text-[0.8125rem] font-bold text-brand-700 hover:underline focus-visible:underline" data-testid="aside-stress">
        {t("dq.aside.late", { buyer, n: exposure.stress.delay_days })} ›
      </Link>
      <p className="text-[0.8125rem] leading-relaxed text-ink-3">{t("dq.aside.keeps", { label: pathLabel })}</p>
    </aside>
  );
}
