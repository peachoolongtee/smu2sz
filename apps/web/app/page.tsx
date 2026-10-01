"use client";

import { useEffect, useState } from "react";
import { NeedsCard } from "@/components/home/needs-card";
import { DoneCard, RiskCard, WaitingCard } from "@/components/home/lists";
import { PositionCard } from "@/components/home/position-card";
import { TodayCard } from "@/components/home/today-card";
import { PageHeader } from "@/components/ui";
import { onSignedIn } from "@/lib/auth";
import { bump } from "@/lib/demo-store";
import { useI18n } from "@/lib/i18n";
import type { NlResponse } from "@/lib/types";

/** The owner's home: what needs them today, in one screen. Every section reads through lib/api.ts and refetches on `bump()`. */
export default function HomePage() {
  const { t } = useI18n();
  // The agent's answer to "go ahead"; it belongs to the day it was given, so moving the clock clears it.
  const [answer, setAnswer] = useState<NlResponse | null>(null);

  // A section that was refused for want of the owner token refetches once the owner has signed in.
  useEffect(() => onSignedIn(() => bump()), []);

  return (
    <>
      <PageHeader title={t("home.title")} subtitle={t("home.subtitle")} />
      <div className="space-y-6">
        <TodayCard onAdvanced={() => setAnswer(null)} />
        <NeedsCard answer={answer} onAnswer={setAnswer} />
        <PositionCard />
        <WaitingCard />
        <RiskCard />
        <DoneCard />
      </div>
    </>
  );
}
