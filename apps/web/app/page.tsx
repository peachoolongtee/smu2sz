"use client";

import { Suspense, useEffect } from "react";
import { HomeDashboard } from "@/components/home/dashboard/home-dashboard";
import { useFixAlert } from "@/components/home/fix-alert";
import { ErrorState, LoadingBlock } from "@/components/ui";
import { HomeV2Page } from "@/components/home/v2/home-v2";
import { getFeatures, getHome } from "@/lib/api";
import { onSignedIn } from "@/lib/auth";
import { bump } from "@/lib/demo-store";
import { useI18n } from "@/lib/i18n";
import { useAsync } from "@/lib/use-async";

/**
 * The owner's home: am I safe, what should I do, who funds the business.
 * One server read (GET /home) written in business words; every figure is the server's. Refetches after any action.
 */
const LAST_VISIT_KEY = "tl-last-visit";

/** The simulated day of the owner's previous visit (a per-browser convenience); null on the first visit or without storage. */
function readLastVisit(): number | null {
  try {
    const raw = window.localStorage.getItem(LAST_VISIT_KEY);
    const n = raw === null ? NaN : Number(raw);
    return Number.isInteger(n) && n >= 0 ? n : null;
  } catch {
    return null;
  }
}

export default function HomePage() {
  const { lang } = useI18n();
  // "Since my last visit": the marker is read when the home is fetched (client side), so no state is needed for it.
  const view = useAsync(() => getHome(lang, typeof window === "undefined" ? null : readLastVisit()), [lang]);
  // Remember this visit once the home has loaded, so the next visit asks "since then".
  useEffect(() => {
    if (!view.data) return;
    try {
      window.localStorage.setItem(LAST_VISIT_KEY, String(view.data.day));
    } catch {
      /* storage unavailable: the home shows the last week */
    }
  }, [view.data]);
  // The agent's answer to "Go ahead" lives on the page: the action block leaves once the fix has run, its answer stays.
  const fixer = useFixAlert();
  // A read refused for want of the owner token refetches once the owner has signed in.
  useEffect(() => onSignedIn(() => bump()), []);
  const h = view.data;
  // Home V2 (the server's FEATURE_HOME_V2): the Home read carries `home_v2` and /health says the switch is on; only then is the page the V2 one. Asked only when the read
  // carries the block, so with the switch off nothing more is read. A switch that cannot be read leaves the dashboard.
  const hasV2 = Boolean(h?.home_v2);
  const features = useAsync(() => (hasV2 ? getFeatures() : Promise.resolve(null)), [hasV2]);
  const v2On = hasV2 && features.data?.home_v2 === true;

  return view.error ? (
    <ErrorState error={view.error} onRetry={view.reload} />
  ) : !h || (hasV2 && features.data === undefined) ? (
    <LoadingBlock rows={3} />
  ) : v2On ? (
    <Suspense fallback={<LoadingBlock rows={3} />}>
      <HomeV2Page h={h} fixer={fixer} loading={view.loading} onRetry={view.reload} />
    </Suspense>
  ) : (
    <HomeDashboard h={h} fixer={fixer} loading={view.loading} onRetry={view.reload} />
  );
}
