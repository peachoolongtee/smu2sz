"use client";

import { useEffect, useState } from "react";
import { DownloadIcon, ShieldCheckIcon } from "@/components/icons";
import { EvidenceView } from "@/components/trust/evidence-view";
import { SecurityView } from "@/components/trust/security-view";
import { PageHeader } from "@/components/ui";
import { SegmentedTabs } from "@/components/ui/segmented-tabs";
import { useI18n } from "@/lib/i18n";

type View = "security" | "evidence";

/**
 * Security & evidence, opened from the account menu: what FLOW refused and why (the security audit) and the record chain as a file anyone can check
 * (the evidence). One page, two views; `#evidence` opens the second. The views are the engine pages' own, under a section heading.
 */
export default function TrustPage() {
  const { t } = useI18n();
  const [view, setView] = useState<View>("security");
  // The address is read once the page is on screen (the server cannot see a hash): `#evidence` opens the second view.
  useEffect(() => {
    if (window.location.hash !== "#evidence") return;
    const frame = window.requestAnimationFrame(() => setView("evidence"));
    return () => window.cancelAnimationFrame(frame);
  }, []);
  const choose = (v: View) => {
    setView(v);
    try {
      window.history.replaceState(null, "", v === "evidence" ? "#evidence" : window.location.pathname);
    } catch {
      /* the address keeps its hash */
    }
  };
  return (
    <>
      <PageHeader section="home" icon={ShieldCheckIcon} title={t("nav.trust")} subtitle={t("trust.subtitle")} />
      <div className="space-y-6">
        <SegmentedTabs
          label={t("trust.view")}
          value={view}
          onChange={choose}
          testId="trust-view"
          tabs={[
            { value: "security" as View, label: t("trust.view.security"), icon: ShieldCheckIcon, testId: "trust-view-security" },
            { value: "evidence" as View, label: t("trust.view.evidence"), icon: DownloadIcon, testId: "trust-view-evidence" },
          ]}
        />
        <section className="card-flat" data-testid={`trust-${view}`}>
          {view === "security" ? <SecurityView embedded /> : <EvidenceView embedded />}
        </section>
      </div>
    </>
  );
}
