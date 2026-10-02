"use client";

import { Badge, Card, ErrorState, Hash, KeyValueList, LoadingBlock, PageHeader, Stat, TableWrap, tableCls, tdCls, thCls } from "@/components/ui";
import { TierBadge } from "@/components/badges";
import { InTransit, lotsInTransit } from "@/components/in-transit";
import { getMandate, getState } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { MandateView, Tier } from "@/lib/types";
import { useAsync } from "@/lib/use-async";

const TIERS: Tier[] = ["TIER_1", "TIER_2", "TIER_3"];

export default function MandatePage() {
  const { t, te } = useI18n();
  const mandate = useAsync(getMandate, []);
  const state = useAsync(getState, []);

  return (
    <>
      <PageHeader title={t("mandate.title")} subtitle={t("mandate.subtitle")} />

      {mandate.error ? (
        <ErrorState error={mandate.error} onRetry={mandate.reload} />
      ) : !mandate.data ? (
        <LoadingBlock rows={4} />
      ) : (
        <MandateBody view={mandate.data} />
      )}

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        {TIERS.map((tier) => (
          <Card
            key={tier}
            id={`tier-${tier}`}
            title={
              <span className="flex items-center gap-2">
                <TierBadge tier={tier} />
                {te("tier.title", tier)}
              </span>
            }
            tone={tier === "TIER_1" ? "ok" : tier === "TIER_2" ? "warn" : "bad"}
            className={tier === "TIER_3" ? "lg:col-span-2" : ""}
          >
            <p className="text-sm text-ink-2">{te("tier.desc", tier)}</p>
            <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-ink">
              {te("tier.examples", tier)
                .split(" | ")
                .map((ex) => (
                  <li key={ex}>{ex}</li>
                ))}
            </ul>
          </Card>
        ))}
      </div>

      <Card id="snapshot" title={t("mandate.snapshot")} subtitle={t("mandate.snapshot.sub")} className="mt-6">
        {state.error ? (
          <ErrorState error={state.error} onRetry={state.reload} />
        ) : !state.data ? (
          <LoadingBlock rows={2} />
        ) : (
          <div className="space-y-4">
            <dl className="grid grid-cols-2 gap-3 lg:grid-cols-4">
              <Stat
                label={t("mandate.cash")}
                value={state.data.state.cash_display}
                hint={
                  lotsInTransit(state.data.state).length ? (
                    <span data-testid="mandate-transit">
                      {t("transit.title")}: <InTransit lots={lotsInTransit(state.data.state)} />
                    </span>
                  ) : undefined
                }
              />
              <Stat label={t("mandate.ebitda")} value={state.data.state.monthly_ebitda_display} />
              <Stat
                label={t("mandate.debt")}
                value={state.data.state.debts[0]?.principal_display ?? t("common.none")}
                hint={state.data.state.debts[0]?.label}
              />
              <Stat
                label={t("mandate.receivable")}
                value={state.data.state.receivables[0]?.face_display ?? t("common.none")}
                hint={
                  state.data.state.receivables[0]
                    ? state.data.state.receivables[0].base_terms_days !== undefined
                      ? t("mandate.receivable.adjusted", {
                          days: state.data.state.receivables[0].terms_days,
                          base: state.data.state.receivables[0].base_terms_days,
                        })
                      : t("mandate.receivable.hint", { days: state.data.state.receivables[0].terms_days })
                    : undefined
                }
              />
            </dl>
            <TableWrap label={t("mandate.flows")}>
              <table className={tableCls}>
                <caption className="sr-only">{t("mandate.flows")}</caption>
                <thead>
                  <tr>
                    <th scope="col" className={thCls}>{t("common.day")}</th>
                    <th scope="col" className={thCls}>{t("common.label")}</th>
                    <th scope="col" className={`${thCls} text-right`}>{t("common.amount")}</th>
                  </tr>
                </thead>
                <tbody>
                  {state.data.state.flows.map((f) => (
                    <tr key={f.id}>
                      <td className={`${tdCls} tabular-nums`}>{f.day}</td>
                      <td className={tdCls}>{f.label}</td>
                      <td className={`${tdCls} text-right tabular-nums`}>{f.amount_display}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </TableWrap>
          </div>
        )}
      </Card>
    </>
  );
}

function MandateBody({ view }: { view: MandateView }) {
  const { t, te } = useI18n();
  const m = view.mandate;
  const sigTone = view.signature.status === "VALID" ? "ok" : "bad";
  const validTone = view.validity.status === "ACTIVE" ? "ok" : "bad";
  return (
    <div className="space-y-6">
      <div className="grid gap-4 md:grid-cols-3">
        <Card id="version" title={t("mandate.version")}>
          <p className="text-2xl font-semibold tabular-nums">v{m.version}</p>
          <p className="mt-1 text-xs text-ink-3">{t("mandate.org", { org: m.org_id })}</p>
          <p className="mt-2 text-xs text-ink-2">{t("mandate.versionNote")}</p>
        </Card>
        <Card id="signature" title={t("mandate.signature")}>
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone={sigTone}>{te("sigstatus", view.signature.status)}</Badge>
            <span className="text-xs text-ink-3">{view.signature.algorithm}</span>
          </div>
          <div className="mt-2 space-y-1 text-xs text-ink-2">
            <p>{view.signature.key_fingerprint}</p>
            <p className="flex items-center gap-1">
              {t("mandate.sig")}: <Hash value={m.signature_hex} />
            </p>
          </div>
        </Card>
        <Card id="expiry" title={t("mandate.expiry")}>
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone={validTone}>{te("validity", view.validity.status)}</Badge>
            {m.revoked ? <Badge tone="bad">{t("mandate.revoked")}</Badge> : <Badge>{t("mandate.notRevoked")}</Badge>}
          </div>
          <p className="mt-2 text-sm tabular-nums">
            {t("mandate.expiresOn", { day: view.validity.expires_day })}
          </p>
          <p className="text-xs text-ink-3">
            {t("mandate.daysLeft", { n: view.validity.days_remaining, today: view.validity.current_day })}
          </p>
        </Card>
      </div>

      <Card id="limits" title={t("mandate.limits")} subtitle={t("mandate.limits.sub")}>
        <dl className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-4">
          <Stat label={t("mandate.minCash")} value={m.min_cash_display} hint={t("mandate.minCash.hint")} />
          <Stat
            label={t("mandate.cap")}
            value={m.max_aggregate_forward_concession_display}
            hint={t("mandate.cap.hint", { days: m.forward_concession_horizon_days })}
          />
          <Stat label={t("mandate.discount")} value={m.max_immediate_discount_display ?? t("common.none")} hint={t("mandate.discount.hint")} />
          <Stat label={t("mandate.dscr")} value={`≥ ${m.min_dscr_display}`} hint={t("mandate.dscr.hint")} />
          <Stat label={t("mandate.leverage")} value={`≤ ${m.max_leverage_display}`} hint={t("mandate.leverage.hint")} />
          <Stat label={t("mandate.apr")} value={`≤ ${m.max_apr_display}`} hint={t("mandate.apr.hint")} />
          <Stat label={t("mandate.tier2")} value={m.tier2_single_commitment_display} hint={t("mandate.tier2.hint")} />
          <Stat label={t("mandate.horizon")} value={t("common.days", { n: m.horizon_days })} hint={t("mandate.horizon.hint")} />
        </dl>
        <div className="mt-4 border-t border-line pt-4">
          <KeyValueList
            items={[
              { k: t("mandate.cleanDown"), v: m.require_clean_down ? t("common.yes") : t("common.no") },
              { k: t("mandate.borrowing"), v: m.allow_new_borrowing ? t("common.yes") : t("common.no") },
              {
                k: t("mandate.perBuyer"),
                v: Object.keys(m.per_buyer_caps_fen).length ? JSON.stringify(m.per_buyer_caps_fen) : t("mandate.perBuyer.none"),
              },
              { k: t("mandate.ownerOnly"), v: t("mandate.ownerOnly.v") },
            ]}
          />
        </div>
      </Card>
    </div>
  );
}
