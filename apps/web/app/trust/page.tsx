"use client";

import { Suspense } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { DownloadIcon, ShieldCheckIcon } from "@/components/icons";
import { EvidenceView } from "@/components/trust/evidence-view";
import { SecurityView } from "@/components/trust/security-view";
import { ButtonLink, LoadingBlock, PageHeader } from "@/components/ui";
import { SegmentedTabs } from "@/components/ui/segmented-tabs";
import { useI18n } from "@/lib/i18n";

type View = "security" | "evidence";

/**
 * Security and evidence: the destination of an evidence link, not a menu item. The address chooses the view (`?view=evidence|security`), marks one record
 * (`&entry=<seq>` in the evidence, `&event=<id>` in the security audit) and says where the owner came from (`&from=activity|demo`, which becomes the first control, a
 * way back). One page, two views; no hash routing. The views are the engine pages' own, under a section heading, so the page keeps one h1.
 */
function TrustBody() {
  const { t } = useI18n();
  const params = useSearchParams();
  const pathname = usePathname();
  const router = useRouter();
  const entryParam = params.get("entry");
  const eventParam = params.get("event");
  const from = params.get("from");
  // An entry names the evidence and an event names the security audit, unless the address says which view outright.
  const asked = params.get("view");
  const view: View = asked === "evidence" || asked === "security" ? asked : entryParam ? "evidence" : "security";
  const entry = entryParam !== null && /^\d+$/.test(entryParam) ? Number(entryParam) : null;
  const back = from === "activity" ? { href: "/activity", label: t("trust.back.activity") } : from === "demo" ? { href: "/demo", label: t("trust.back.demo") } : null;

  const choose = (v: View) => {
    const q = new URLSearchParams();
    q.set("view", v);
    if (from) q.set("from", from);
    router.replace(`${pathname}?${q}`, { scroll: false });
  };

  return (
    <>
      {back ? (
        <div className="mb-3">
          <ButtonLink href={back.href} variant="ghost" size="sm" data-testid="trust-back">
            {back.label}
          </ButtonLink>
        </div>
      ) : null}
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
        <section data-testid={`trust-${view}`}>{view === "security" ? <SecurityView embedded event={eventParam} /> : <EvidenceView embedded entry={entry} entryAsked={entryParam !== null} />}</section>
      </div>
    </>
  );
}

export default function TrustPage() {
  return (
    <Suspense fallback={<LoadingBlock rows={3} />}>
      <TrustBody />
    </Suspense>
  );
}
