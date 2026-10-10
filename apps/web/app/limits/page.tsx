"use client";

import Link from "next/link";
import { ShieldCheckIcon } from "@/components/icons";
import { Badge, Card, ErrorState, Hash, LoadingBlock, PageHeader, Stat } from "@/components/ui";
import { getMandate } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { useAsync } from "@/lib/use-async";
import { Disclosure } from "@/components/business/kit";

/** Limits: what the agent may do alone, in sentences; the signed mandate's fields and signature under details. */
export default function LimitsPage() {
  const { t, te } = useI18n();
  const mandate = useAsync(getMandate, []);
  const v = mandate.data;
  const m = v?.mandate;

  return (
    <>
      <PageHeader section="home" icon={ShieldCheckIcon} title={t("nav.limits")} subtitle={t("biz.limits.subtitle")} />
      {mandate.error ? (
        <ErrorState error={mandate.error} onRetry={mandate.reload} />
      ) : !v || !m ? (
        <LoadingBlock rows={3} />
      ) : (
        <div className="space-y-6">
          <Card id="limits-rules" title={t("biz.limits.rules")} subtitle={t("biz.limits.rules.sub", { v: m.version })} actions={<Badge tone={v.validity.status === "ACTIVE" ? "ok" : "bad"}>{te("validity", v.validity.status)}</Badge>}>
            <ul className="list-disc space-y-1.5 pl-5 text-sm text-ink">
              <li>{t("biz.limits.floor", { floor: m.min_cash_display })}</li>
              <li>{t("biz.limits.apr", { cap: m.max_apr_display })}</li>
              <li>{t("biz.limits.concessions", { cap: m.max_aggregate_forward_concession_display, days: m.forward_concession_horizon_days })}</li>
              <li>{t("biz.limits.covenants", { dscr: m.min_dscr_display, lev: m.max_leverage_display })}</li>
              <li>{t("biz.limits.tier2", { amount: m.tier2_single_commitment_display })}</li>
              <li>{m.allow_new_borrowing ? t("biz.limits.borrowingYes") : t("biz.limits.borrowingNo")}</li>
              <li>{t("biz.limits.tier3")}</li>
              <li>{t("biz.limits.expires", { day: v.validity.expires_day, n: v.validity.days_remaining })}</li>
            </ul>
          </Card>
          <dl className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <Stat label={t("biz.safeLevel")} value={m.min_cash_display} />
            <Stat label={t("biz.limits.aprLabel")} value={m.max_apr_display} />
            <Stat label={t("mandate.cap")} value={m.max_aggregate_forward_concession_display} />
            <Stat label={t("biz.limits.tier2Label")} value={m.tier2_single_commitment_display} />
          </dl>
          <Disclosure card summary={t("biz.auditDetails")}>
            <div className="space-y-2 text-sm text-ink-2">
              <p>
                {t("mandate.signature")}: <Badge tone={v.signature.status === "VALID" ? "ok" : "bad"}>{te("sigstatus", v.signature.status)}</Badge> <span className="text-xs">{v.signature.algorithm} · {v.signature.key_fingerprint}</span>
              </p>
              <p className="flex items-center gap-1">
                {t("mandate.sig")}: <Hash value={m.signature_hex} />
              </p>
              <p>{t("mandate.org", { org: m.org_id })}</p>
              <p>
                <Link href="/mandate" className="font-medium text-brand-700 underline underline-offset-2">
                  {t("biz.limits.full")}
                </Link>
              </p>
            </div>
          </Disclosure>
        </div>
      )}
    </>
  );
}
