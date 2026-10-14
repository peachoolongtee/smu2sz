"use client";

import { ToolTile } from "@/components/business/surface";
import { BankIcon, CheckCircleIcon, DocumentIcon, SparkIcon } from "@/components/icons";
import { getApprovals } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { useAsync } from "@/lib/use-async";

/** The approvals read's pending count (rows waiting for the owner); nothing else is computed. Zero without the owner's token. */
function usePendingApprovals(): number {
  const { token } = useAuth();
  const list = useAsync(() => (token ? getApprovals().catch(() => []) : Promise.resolve([])), [Boolean(token)]);
  return list.data?.filter((a) => a.status === "PENDING").length ?? 0;
}

/** The one tool at the head of Deals: attaching a deal's documents (the page is otherwise only the deals). */
export function DealTools() {
  const { t } = useI18n();
  return (
    <section aria-label={t("deals.tools")} data-testid="deal-tools" data-tour="deals-attach">
      <ToolTile compact href="/documents" icon={DocumentIcon} title={t("deals.tools.attach")} body={t("deals.tools.attach.body")} testId="deal-tool-attach" />
    </section>
  );
}

/**
 * The owner's shortcuts on Home, a low strip under the worklist: the approvals (the loud tile while something waits for the owner), the sandbox for testing terms,
 * loans and purchases (capex) and attaching a deal. One line each, so the strip never takes the page's room; each has its own colour (amber, teal, blue, purple) to tell them apart.
 */
export function HomeTools() {
  const { t } = useI18n();
  const pending = usePendingApprovals();
  return (
    <nav aria-label={t("hv2.foot")} className="grid grid-cols-1 gap-3 sm:grid-cols-2" data-testid="home-tools" data-tour="home-tools">
      <ToolTile
        compact
        href="/approvals"
        icon={CheckCircleIcon}
        title={t("nav.approvals")}
        body={pending ? t("deals.tools.approvals.pending", { n: pending }) : t("home.tools.approvals.none")}
        badge={pending ? t("deals.tools.approvals.badge", { n: pending }) : null}
        tone={pending ? "feature" : "plain"}
        hue="var(--color-warn-solid)"
        testId="hv2-foot-approvals"
      />
      <ToolTile compact hue="var(--color-sec-cash-solid)" href="/whatif" icon={SparkIcon} title={t("deals.tools.sandbox")} body={t("home.tools.sandbox")} testId="hv2-foot-whatif" />
      <ToolTile compact hue="var(--color-sec-home-solid)" href="/capex" icon={BankIcon} title={t("home.tools.capex")} body={t("home.tools.capex.body")} testId="hv2-foot-capex" />
      <ToolTile compact hue="var(--color-sec-deals-solid)" href="/documents" icon={DocumentIcon} title={t("deals.tools.attach")} body={t("home.tools.attach")} testId="hv2-foot-documents" />
    </nav>
  );
}
