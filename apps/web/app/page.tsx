"use client";

import { useEffect, useState } from "react";
import { AgreementsCard } from "@/components/home/agreements-card";
import { Glossary } from "@/components/home/glossary";
import { NeedsCard } from "@/components/home/needs-card";
import { DoneCard, RiskCard, WaitingCard } from "@/components/home/lists";
import { PositionCard } from "@/components/home/position-card";
import { TodayCard } from "@/components/home/today-card";
import { Badge, PageHeader } from "@/components/ui";
import { getClock } from "@/lib/api";
import { onSignedIn } from "@/lib/auth";
import { bump } from "@/lib/demo-store";
import { useI18n } from "@/lib/i18n";
import type { NlResponse } from "@/lib/types";
import { useAsync } from "@/lib/use-async";

/** The owner's home: what needs them today, in one screen. Every section reads through lib/api.ts and refetches on `bump()`. */
export default function HomePage() {
  const { t } = useI18n();
  // The agent's answer to "go ahead"; it belongs to the day it was given, so moving the clock clears it.
  const [answer, setAnswer] = useState<NlResponse | null>(null);

  // A section that was refused for want of the owner token refetches once the owner has signed in.
  useEffect(() => onSignedIn(() => bump()), []);

  return (
    <>
      <PageHeader title={t("home.title")} subtitle={t("home.subtitle")} actions={<DayBadge />} />
      <div className="space-y-6">
        {/* What needs a decision first, then where the business stands, then the record; the demo clock last. */}
        <NeedsCard answer={answer} onAnswer={setAnswer} />
        <WaitingCard />
        <PositionCard />
        <AgreementsCard />
        <RiskCard />
        <DoneCard />
        <TodayCard onAdvanced={() => setAnswer(null)} />
        <Glossary />
      </div>
    </>
  );
}

/** The simulated day, in the header, so it stays in view while the clock control sits at the bottom. */
function DayBadge() {
  const { t } = useI18n();
  const clock = useAsync(getClock, []);
  return clock.data ? <Badge tone="info" className="px-3 py-1 text-sm">{t("home.dayBadge", { n: clock.data.day })}</Badge> : null;
}
