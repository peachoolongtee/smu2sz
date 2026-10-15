"use client";

import { Suspense, useEffect } from "react";
import { useFixAlert } from "@/components/home/fix-alert";
import { ErrorState, LoadingBlock } from "@/components/ui";
import { HomeV2Page } from "@/components/home/v2/home-v2";
import { SetupWelcome } from "@/components/setup/welcome";
import { getHome } from "@/lib/api";
import { onSignedIn } from "@/lib/auth";
import { bump } from "@/lib/demo-store";
import { useI18n } from "@/lib/i18n";
import { useSetupStatus } from "@/lib/setup-draft";
import { useAsync } from "@/lib/use-async";

/**
 * The owner's home (Home V2): the company's status, what to do and what it costs, the cash forecast, and the worklist of what waits for the owner.
 * One server read (GET /home) written in business words, with the worklist and customers beside it; every figure is the server's. Refetches after any action.
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
  // A new business with no books yet (ADR-0013): Home cannot answer "Am I safe?", so it offers the setup instead.
  const { status: setup } = useSetupStatus();
  const h = view.data;
  if (setup?.books === "blank") return <SetupWelcome />;
  if (view.error) return <ErrorState error={view.error} onRetry={view.reload} />;
  if (!h) return <LoadingBlock rows={3} />;
  return (
    <Suspense fallback={<LoadingBlock rows={3} />}>
      <HomeV2Page h={h} fixer={fixer} loading={view.loading} onRetry={view.reload} />
    </Suspense>
  );
}
