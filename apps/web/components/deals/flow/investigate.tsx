"use client";

import { Disclosure } from "@/components/business/kit";
import { ErrorState, LoadingBlock } from "@/components/ui";
import { OpenSection } from "@/components/ui/open-section";
import { StateWord } from "@/components/ui/state-word";
import { getEnvelope } from "@/lib/api";
import { STRATEGY_MVP } from "@/lib/config";
import { useI18n } from "@/lib/i18n";
import type { EnvelopePackageView, EnvelopeView } from "@/lib/types";
import { useAsync } from "@/lib/use-async";
import { AUTH_TONE } from "./flow-parts";

/** The authority class of a package of the envelope, from the verifier's own outcome and tier (the server's enums; the words are the dictionary's). */
export function packageClass(p: Pick<EnvelopePackageView, "outcome" | "tier">): "flow_may" | "needs_owner" | "over_limit" {
  if (p.outcome === "ACCEPT" || p.tier === "TIER_1") return "flow_may";
  return p.outcome === "NEEDS_OWNER_APPROVAL" || p.tier === "TIER_2" ? "needs_owner" : "over_limit";
}

const SHOWN_FIRST = 3;

/**
 * What the owner can live with for this buyer, by who may act on it (FLOW may send it, you approve first, over a limit you signed): the envelope's packages in the server's
 * one-line words, the first three of each class and the rest behind "more". Read only when the investigation is open and only with the strategy flag; a server without the
 * route (or with the feature off) mounts nothing.
 */
export function EnvelopePackages({ buyerId }: { buyerId: string }) {
  const { t, lang } = useI18n();
  const read = useAsync<EnvelopeView | null>(async () => (STRATEGY_MVP ? await getEnvelope(buyerId, lang, false) : null), [buyerId, lang]);
  const e = read.data;
  if (!STRATEGY_MVP) return null;
  if (read.error) return <ErrorState error={t("biz.strategy.envelope.error")} onRetry={read.reload} />;
  if (read.loading && !e) return <LoadingBlock rows={3} label={t("biz.strategy.envelope.loading")} />;
  if (!e || e.refused || !e.packages.length) return null;
  const classes = (["flow_may", "needs_owner", "over_limit"] as const).map((c) => ({ c, items: e.packages.filter((p) => packageClass(p) === c) })).filter((x) => x.items.length);
  return (
    <OpenSection title={t("deals.envelope.title")} subtitle={t("deals.envelope.sub", { buyer: e.buyer_name })} testId="deal-envelope-packages" id="deal-envelope-section">
      <div className="space-y-4">
        {classes.map(({ c, items }) => (
          <div key={c} data-testid={`envelope-class-${c}`}>
            <p className="mb-1 text-supporting font-bold text-ink-2">
              <StateWord tone={AUTH_TONE[c]}>{t(`deals.class.${c}` as const)}</StateWord>
            </p>
            <ul className="divide-y divide-line">
              {items.slice(0, SHOWN_FIRST).map((p, i) => (
                <PackageLine key={i} p={p} />
              ))}
            </ul>
            {items.length > SHOWN_FIRST ? (
              <Disclosure testId={`envelope-more-${c}`} summary={t("deals.envelope.more", { n: items.length - SHOWN_FIRST })}>
                <ul className="divide-y divide-line">
                  {items.slice(SHOWN_FIRST).map((p, i) => (
                    <PackageLine key={i} p={p} />
                  ))}
                </ul>
              </Disclosure>
            ) : null}
          </div>
        ))}
        {e.unlisted_counters.map((s, i) => (
          <p key={i} className="text-supporting text-ink-2">
            {s}
          </p>
        ))}
      </div>
    </OpenSection>
  );
}

function PackageLine({ p }: { p: EnvelopePackageView }) {
  return (
    <li className="py-2 text-sm text-ink" data-testid="envelope-package">
      {p.summary}
      {p.flags.length ? <span className="text-ink-2">{` · ${p.flags.join(", ")}`}</span> : null}
    </li>
  );
}
