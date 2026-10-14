"use client";

import { ToolTile } from "@/components/business/surface";
import { CheckCircleIcon, DocumentIcon, SparkIcon, WalletIcon } from "@/components/icons";
import { getApprovals } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { useAsync } from "@/lib/use-async";

/**
 * The deal tools at the head of Deals, so none of them is hidden: the approvals (the loud tile while something waits for the owner), the sandbox for
 * testing terms, the purchase check and attaching a deal's documents. The count is the approvals read's own (pending rows); nothing else is computed.
 */
export function DealTools() {
  const { t } = useI18n();
  const { token } = useAuth();
  const list = useAsync(() => (token ? getApprovals().catch(() => []) : Promise.resolve([])), [Boolean(token)]);
  const pending = list.data?.filter((a) => a.status === "PENDING").length ?? 0;
  return (
    <section aria-label={t("deals.tools")} className="grid grid-cols-2 gap-3 lg:grid-cols-[1.5fr_1fr_1fr_1fr]" data-testid="deal-tools">
      <ToolTile
        href="/approvals"
        icon={CheckCircleIcon}
        title={t("nav.approvals")}
        body={pending ? t("deals.tools.approvals.pending", { n: pending }) : t("deals.tools.approvals.none")}
        badge={pending ? t("deals.tools.approvals.badge", { n: pending }) : null}
        tone={pending ? "feature" : "plain"}
        testId="deal-tool-approvals"
      />
      <ToolTile href="/whatif" icon={SparkIcon} title={t("deals.tools.sandbox")} body={t("biz.cash.whatif.sub")} testId="deal-tool-sandbox" />
      <ToolTile href="/capex" icon={WalletIcon} title={t("biz.cash.capex.open")} body={t("biz.cash.capex.sub")} testId="deal-tool-capex" />
      <ToolTile href="/documents" icon={DocumentIcon} title={t("deals.tools.attach")} body={t("deals.tools.attach.body")} testId="deal-tool-attach" />
    </section>
  );
}
