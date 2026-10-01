"use client";

import Link from "next/link";
import { useState } from "react";
import { Badge, Button, Card, ErrorState } from "@/components/ui";
import { advanceClock, getClock } from "@/lib/api";
import { bump } from "@/lib/demo-store";
import { useI18n } from "@/lib/i18n";
import { useAsync } from "@/lib/use-async";

const MAX_DAYS = 366;

/** The day, and the demo control that moves the simulated clock. Every section refetches after an advance. */
export function TodayCard({ onAdvanced }: { onAdvanced: () => void }) {
  const { t } = useI18n();
  const clock = useAsync(getClock, []);
  const [days, setDays] = useState("1");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  async function advance(n: number) {
    if (!Number.isInteger(n) || n < 1 || n > MAX_DAYS) {
      setError(t("home.demo.invalid"));
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const r = await advanceClock(n);
      setMessage(r.message);
      onAdvanced();
      bump();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card id="home-today" title={t("home.today")} subtitle={t("home.today.sub")} actions={<Badge tone="info">{t("home.demo.badge")}</Badge>}>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <p className="text-3xl font-semibold tabular-nums text-ink" data-testid="home-day" aria-live="polite">
          {clock.data ? t("common.dayN", { n: clock.data.day }) : "…"}
        </p>
        <form
          className="flex flex-wrap items-end gap-2"
          aria-label={t("home.demo.badge")}
          onSubmit={(e) => {
            e.preventDefault();
            void advance(Number(days));
          }}
        >
          <label className="text-xs font-medium text-ink-3">
            {t("home.demo.days")}
            <input
              type="number"
              inputMode="numeric"
              min={1}
              max={MAX_DAYS}
              step={1}
              value={days}
              onChange={(e) => setDays(e.target.value)}
              className="mt-1 block min-h-10 w-24 rounded-md border border-line-strong bg-surface px-2 text-sm tabular-nums text-ink"
              data-testid="home-days"
            />
          </label>
          <Button type="submit" variant="primary" loading={busy} data-testid="home-advance">
            {t("home.demo.advance")}
          </Button>
          <span className="flex gap-1.5" role="group" aria-label={t("home.demo.badge")}>
            {([1, 7, 30] as const).map((n) => (
              <Button key={n} size="sm" disabled={busy} onClick={() => void advance(n)} data-testid={`home-plus-${n}`}>
                {t(`home.demo.plus${n}` as const)}
              </Button>
            ))}
          </span>
        </form>
      </div>
      <p className="mt-3 text-xs text-ink-3">{t("home.demo.hint")}</p>
      {message ? (
        <p className="mt-2 text-xs text-ink-2" role="status" data-testid="home-moved">
          {t("home.demo.moved", { message })}
        </p>
      ) : null}
      {error ? (
        <div className="mt-3">
          <ErrorState error={error} />
        </div>
      ) : null}
      {clock.error ? (
        <div className="mt-3">
          <ErrorState error={clock.error} onRetry={clock.reload} />
        </div>
      ) : null}
    </Card>
  );
}

export function SectionLink({ href, children }: { href: string; children: string }) {
  return (
    <Link href={href} className="text-xs font-medium text-brand-700 underline underline-offset-2">
      {children}
    </Link>
  );
}
