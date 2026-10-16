"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button, Callout, ErrorState, LoadingBlock } from "@/components/ui";
import { demoReset, getDemoStory, openBooks, previewSetup } from "@/lib/api";
import { changeBooks } from "@/lib/books-guard";
import { API_MODE } from "@/lib/config";
import { bump, resetSession } from "@/lib/demo-store";
import { errorText } from "@/lib/error-text";
import { useI18n } from "@/lib/i18n";
import { clearDraft } from "@/lib/setup-draft";
import type { SetupDraft, SetupPreview, SetupStatus } from "@/lib/types";
import { rememberAccount } from "@/lib/account-flag";
import { useAsync } from "@/lib/use-async";
import { TextInput } from "./fields";
import { StepHeading } from "./steps";

/**
 * Step 6: the server checks the whole draft and answers with what to fix, what to look at, the summary and a first forecast
 * (POST /setup/preview, which writes nothing). Signing re-types the owner's sign-in; the server signs the limits and opens the books.
 */
export function StepReview({ draft, status, goTo }: { draft: SetupDraft; status: SetupStatus | undefined; goTo: (n: number) => void }) {
  const { t, lang } = useI18n();
  const router = useRouter();
  // Keyed on the draft itself: on a reload the saved draft arrives after the first render, and the check must be of that draft.
  const preview = useAsync(() => previewSetup(draft, lang), [lang, JSON.stringify(draft)]);
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const p = preview.data;

  async function open() {
    setBusy(true);
    setError(null);
    try {
      await openBooks(draft, password, lang);
      // An account: the landing page now offers "Access FLOW" on this browser.
      rememberAccount();
      clearDraft();
      resetSession();
      bump();
      router.push("/");
    } catch (e) {
      setError(errorText(e, t));
      setBusy(false);
    }
  }

  // Opening replaces only blank books. When other books are open the owner can start again from blank ones here, through the same guard as every reset: the dialog lists
  // what the books on the server lose (from a fresh read) and its confirm is the one thing that replaces them. The draft in this browser is kept.
  const [resetting, setResetting] = useState(false);
  const [blankDone, setBlankDone] = useState(false);
  async function toBlank() {
    setResetting(true);
    setError(null);
    try {
      const story = await getDemoStory(lang, null);
      await changeBooks(
        story.books,
        async (guard) => {
          await demoReset("blank", guard);
          // A new session on the new books: every read (the setup's status included) is taken again.
          resetSession();
          setBlankDone(true);
        },
        {
          always: true,
          labels: { title: t("setup.blank.title"), confirm: t("setup.blank.confirm"), cancel: t("demo.load.cancel"), keeps: story.books.reset_keeps_text },
          gives: { heading: t("demo.alt.get"), text: t("demo.card.blank.help") },
        },
      );
    } catch (e) {
      setError(errorText(e, t));
    } finally {
      setResetting(false);
    }
  }
  const canReset = API_MODE === "live" && status !== undefined && status.books !== "blank";

  return (
    <div className="space-y-6">
      <StepHeading title={t("setup.s6.title")} sub={t("setup.s6.sub")} />
      {preview.error ? <ErrorState error={preview.error} onRetry={preview.reload} /> : !p ? <LoadingBlock rows={3} /> : <Review p={p} goTo={goTo} reload={preview.reload} />}
      {status && status.books !== "blank" ? (
        <Callout tone="warn">{status.books === "own" && status.opened ? t("setup.replace.own", { text: status.opened.text }) : t("setup.replace.demo")}</Callout>
      ) : null}
      {status && !status.can_open && status.can_open_text ? <Callout tone="warn">{status.can_open_text}</Callout> : null}
      {canReset ? (
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2" data-testid="setup-blank">
          <Button loading={resetting} onClick={() => void toBlank()} data-testid="setup-blank-reset">
            {t("setup.blank.button")}
          </Button>
          <p className="min-w-0 flex-[1_1_18rem] text-sm text-ink-3">{t("setup.blank.hint")}</p>
        </div>
      ) : blankDone && status?.books === "blank" ? (
        <p role="status" className="text-sm font-medium text-ok-fg" data-testid="setup-blank-done">
          {t("setup.blank.done")}
        </p>
      ) : null}
      <section className="flex flex-wrap items-end gap-4 rounded-card border-2 border-brand-600 bg-brand-50 p-5" data-testid="setup-sign">
        <div className="min-w-0 flex-[999_1_320px] space-y-1">
          <h3 className="text-base font-bold text-ink">{t("setup.s6.sign.title")}</h3>
          <p className="text-sm text-ink-2">{t("setup.s6.sign.body")}</p>
        </div>
        <label className="flex flex-[1_1_220px] flex-col gap-1.5 text-sm font-semibold text-ink">
          {t("setup.s6.password")}
          <TextInput type="password" value={password} onChange={setPassword} testId="setup-password" />
        </label>
        <Button variant="primary" onClick={open} loading={busy} disabled={!p?.ok || !password || (status ? !status.can_open : false)} data-testid="setup-open">
          {t("setup.s6.open")}
        </Button>
      </section>
      {error ? <Callout tone="bad">{error}</Callout> : null}
    </div>
  );
}

function Review({ p, goTo, reload }: { p: SetupPreview; goTo: (n: number) => void; reload: () => void }) {
  const { t } = useI18n();
  return (
    <div className="space-y-6">
      {p.errors.length ? (
        <Callout tone="bad" title={t("setup.s6.errors")}>
          <ul className="mt-1 space-y-1.5" data-testid="setup-errors">
            {p.errors.map((e, i) => (
              <li key={i} className="flex flex-wrap items-baseline gap-x-2">
                <span>{e.text}</span>
                {e.step >= 1 && e.step <= 5 ? (
                  <button type="button" onClick={() => goTo(e.step)} className="text-meta font-semibold text-brand-700 underline underline-offset-2">
                    {t("setup.s6.goStep", { n: e.step })}
                  </button>
                ) : null}
              </li>
            ))}
          </ul>
          <Button size="sm" className="mt-3" onClick={reload}>
            {t("setup.s6.reload")}
          </Button>
        </Callout>
      ) : null}
      {p.summary ? (
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-5" data-testid="setup-summary">
          {p.summary.map((s) => (
            <div key={s.step} className="flex flex-col gap-1 rounded-card border border-line bg-surface p-4">
              <span className="text-meta text-ink-3">{s.label}</span>
              <strong className="text-lg tabular-nums text-ink">{s.value}</strong>
              {s.detail ? <span className="text-meta text-ink-2">{s.detail}</span> : null}
              <button type="button" onClick={() => goTo(s.step)} className="mt-auto self-start text-meta font-semibold text-brand-700 underline underline-offset-2">
                {t("setup.s6.edit")}
              </button>
            </div>
          ))}
        </div>
      ) : null}
      <div className="flex flex-wrap items-stretch gap-5">
        {p.first_look ? (
          <section className="min-w-0 flex-[999_1_420px] space-y-3 rounded-card border border-line bg-surface p-5" data-testid="setup-first-look">
            <p className="text-meta font-extrabold uppercase tracking-[0.08em] text-ink-3">{t("setup.s6.firstLook")}</p>
            <p className="type-card-title text-ink">{p.first_look.headline}</p>
            <Forecast look={p.first_look} />
            <p className="text-sm text-ink-2">{p.first_look.detail}</p>
          </section>
        ) : null}
        <section className="min-w-0 flex-[1_1_300px] space-y-3 rounded-card border border-line bg-surface p-5" data-testid="setup-warnings">
          <p className="text-meta font-extrabold uppercase tracking-[0.08em] text-ink-3">
            {t("setup.s6.look")} · {p.warnings.length}
          </p>
          {p.warnings.length === 0 ? (
            <p className="text-sm text-ink-2">{t("setup.s6.nothing")}</p>
          ) : (
            <ul className="space-y-3">
              {p.warnings.map((w, i) => (
                <li key={i} className="border-b border-line pb-3 text-sm text-ink last:border-b-0 last:pb-0">
                  {w.text}
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </div>
  );
}

/** The 90-day line the server projected, with the owner's minimum dashed. Scaling the server's points to the box is all the page does. */
function Forecast({ look }: { look: NonNullable<SetupPreview["first_look"]> }) {
  const { t } = useI18n();
  const W = 600;
  const H = 170;
  const pad = 18;
  const values = [...look.points.map((x) => x.cash_fen), look.min_cash_fen];
  const lo = Math.min(...values, 0);
  const hi = Math.max(...values, 1);
  const last = Math.max(look.points.length - 1, 1);
  const x = (i: number) => (i / last) * W;
  const y = (v: number) => pad + (1 - (v - lo) / (hi - lo || 1)) * (H - 2 * pad);
  const line = look.points.map((pt, i) => `${x(i).toFixed(1)},${y(pt.cash_fen).toFixed(1)}`).join(" ");
  return (
    <svg viewBox={`0 0 ${W} ${H + 18}`} width="100%" role="img" aria-label={`${t("setup.chart.label")}. ${look.headline}`}>
      <line x1="0" x2={W} y1={y(look.min_cash_fen)} y2={y(look.min_cash_fen)} stroke="var(--color-bad-solid, #b42318)" strokeWidth="1.5" strokeDasharray="6 5" />
      <text x={W - 4} y={y(look.min_cash_fen) - 6} fontSize="12" textAnchor="end" fill="currentColor" className="text-ink-2">
        {t("setup.chart.min", { v: look.min_cash_display })}
      </text>
      {lo < 0 ? <line x1="0" x2={W} y1={y(0)} y2={y(0)} stroke="currentColor" strokeOpacity="0.25" /> : null}
      <polyline points={line} fill="none" stroke="var(--color-brand-600, #0368e9)" strokeWidth="2.5" strokeLinejoin="round" />
      <text x="0" y={H + 14} fontSize="11" fill="currentColor" className="text-ink-3">
        {t("setup.chart.today")}
      </text>
      <text x={W} y={H + 14} fontSize="11" textAnchor="end" fill="currentColor" className="text-ink-3">
        {t("setup.chart.end")}
      </text>
    </svg>
  );
}
