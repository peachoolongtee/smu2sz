"use client";

import Link from "next/link";
import { type ReactNode, useState } from "react";
import { TierBadge } from "@/components/badges";
import { BorrowerFileSections } from "@/components/business/borrower-file";
import { CheckIcon, ChevronRightIcon, XIcon } from "@/components/icons";
import { Button, ErrorState, TableWrap, tableCls, tdCls, thCls } from "@/components/ui";
import { StatusPill } from "@/components/ui/status-pill";
import { ViolationCard } from "@/components/verdict-parts";
import { downloadFile } from "@/lib/api";
import { runBorrowerFile, runCapex, runCapexApply } from "@/lib/demo";
import { useDemo } from "@/lib/demo-store";
import type { DictKey } from "@/lib/dictionary";
import { useI18n } from "@/lib/i18n";
import { whenText } from "@/lib/when";

/** A part of the quick check: a hairline above, a heading, an optional quiet line, then the content (the check sits inside one fold, so its parts are not cards of their own). */
function Part({ id, title, sub, aside, children }: { id?: string; title: string; sub?: string; aside?: ReactNode; children: ReactNode }) {
  return (
    <section id={id} className="border-t border-line pt-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <h3 className="font-display text-[15px] font-bold leading-tight text-ink">{title}</h3>
          {sub ? <p className="mt-1 text-supporting text-ink-3">{sub}</p> : null}
        </div>
        {aside}
      </div>
      <div className="mt-3">{children}</div>
    </section>
  );
}

function Mini({ label, value, hint, bad, good }: { label: string; value: string; hint?: string; bad?: boolean; good?: boolean }) {
  return (
    <div className="rounded-[14px] bg-subtle px-3 py-2">
      <dt className="text-supporting text-ink-3">{label}</dt>
      <dd className={`font-display text-lg font-bold tabular-nums ${bad ? "text-bad-fg" : good ? "text-ok-fg" : "text-ink"}`}>{value}</dd>
      {hint ? <dd className="text-supporting text-ink-3">{hint}</dd> : null}
    </div>
  );
}

/**
 * The capex screen without a contract (POST /capex/evaluate on the demo's ¥600k machine): is it worth doing, which financing structure holds every covenant month by month, the
 * application and the borrower file. Every figure is the server's. `quiet` makes its first control a secondary one, for when the buy side's own work leads the page.
 */
export function QuickCheck({ today, quiet = false }: { today: number; quiet?: boolean }) {
  const { t } = useI18n();
  const demo = useDemo();
  const [busy, setBusy] = useState<"capex" | "file" | "apply" | string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const capex = demo.capex;
  const file = demo.borrowerFile;
  const application = demo.capexApplication;
  // The server selects nothing unless the project is worth doing; an illustration at another term is never selected.
  const worth = capex?.worth_doing !== false;
  const selectedStructure = capex?.structures.find((s) => s.id === capex.selected_id);
  const canPrepareFile = Boolean(selectedStructure && !selectedStructure.hypothetical && selectedStructure.facility_id);

  async function run(kind: "capex" | "file" | "apply") {
    setBusy(kind);
    setError(null);
    try {
      await (kind === "capex" ? runCapex() : kind === "apply" ? runCapexApply() : runBorrowerFile());
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }

  async function download(kind: string, path: string, fileId: string) {
    setBusy(`download-${kind}`);
    setError(null);
    try {
      await downloadFile(path, `${fileId}.${kind}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="space-y-4">
      {error ? <ErrorState error={error} /> : null}

      {!capex ? (
        <div data-tour="capex-start">
          <p className="text-sm text-ink-2">{t("capex.empty.body")}</p>
          <div className="mt-3">
            <Button variant={quiet ? "secondary" : "primary"} loading={busy === "capex"} onClick={() => void run("capex")}>
              {t("capex.evaluate")}
            </Button>
          </div>
        </div>
      ) : (
        <>
          <div className={`rounded-[16px] px-4 py-3 ${worth ? "bg-brand-50" : "bg-warn-bg"}`}>
            <p className="text-pretty text-sm font-medium text-ink" data-testid="capex-recommendation">{capex.recommendation ?? (worth ? null : t("capex.notWorth"))}</p>
            {capex.estimate_note ? <p className="mt-1 text-supporting text-ink-2">{capex.estimate_note}</p> : null}
            {capex.as_of_day !== undefined ? (
              <p className="mt-1 text-supporting text-ink-3" data-testid="capex-as-of">
                {t("capex.asOf", { when: whenText(capex.as_of_day, today, t) })}
              </p>
            ) : null}
          </div>

          <dl className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <Mini label={t("capex.npv")} value={capex.npv_display} hint={capex.request.label} bad={capex.npv_fen < 0} good={capex.npv_fen >= 0} />
            <Mini label={t("capex.payback")} value={capex.payback_month !== null ? t("capex.paybackValue", { n: capex.payback_month }) : t("common.none")} />
            <Mini
              label={t("capex.leverage")}
              value={capex.leverage_financed ? `${capex.leverage_financed.text}×` : t("common.none")}
              hint={t("capex.leverage.limit", { limit: capex.leverage_limit_display })}
            />
            <Mini label={t("capex.leverageExt")} value={capex.leverage_with_extension ? `${capex.leverage_with_extension.text}×` : t("common.none")} hint={t("capex.leverageExt.hint")} />
          </dl>

          <Part id="structures" title={t("capex.structures")} sub={`${t("capex.structures.sub", { limit: capex.dscr_limit_display })} ${t("dscr.readingNote")}`}>
            <TableWrap label={t("capex.structures")}>
              <table className={`${tableCls} min-w-[50rem]`}>
                <caption className="sr-only">{t("capex.structures")}</caption>
                <thead>
                  <tr>
                    <th scope="col" className={`${thCls} sticky left-0 z-10`}>{t("capex.structure")}</th>
                    <th scope="col" className={`${thCls} text-right`}>{t("capex.monthly")}</th>
                    <th scope="col" className={`${thCls} text-right`}>{t("capex.interest")}</th>
                    <th scope="col" className={`${thCls} text-right`} title={t("capex.charges.hint")}>{t("capex.charges")}</th>
                    {[1, 2, 3, 4, 5, 6].map((m) => (
                      <th key={m} scope="col" className={`${thCls} text-right`}>
                        {t("capex.dscrMonth", { n: m })}
                      </th>
                    ))}
                    <th scope="col" className={thCls}>{t("capex.result")}</th>
                  </tr>
                </thead>
                <tbody>
                  {capex.structures.map((s) => {
                    const selected = s.id === capex.selected_id;
                    return (
                      <tr key={s.id} className={selected ? "bg-brand-50" : ""} data-testid={`structure-${s.id}`}>
                        <th scope="row" className={`${tdCls} sticky left-0 z-10 min-w-36 text-left font-medium ${selected ? "bg-brand-50" : "bg-surface"}`}>
                          {s.label}
                          {selected ? (
                            <StatusPill tone="green" className="mt-1 flex w-fit">
                              {t("capex.selected")}
                            </StatusPill>
                          ) : null}
                        </th>
                        <td className={`${tdCls} whitespace-nowrap text-right font-medium tabular-nums`}>{s.monthly_payment_display ?? t("common.none")}</td>
                        <td className={`${tdCls} whitespace-nowrap text-right tabular-nums`}>{s.total_interest_display ?? t("common.none")}</td>
                        <td className={`${tdCls} whitespace-nowrap text-right font-medium tabular-nums`}>{s.charges_total_display ?? t("common.none")}</td>
                        {[1, 2, 3, 4, 5, 6].map((m) => {
                          const cell = s.dscr_by_month.find((d) => d.month === m);
                          return (
                            <td key={m} className={`${tdCls} text-right tabular-nums`}>
                              {cell ? (
                                <span
                                  className={`inline-flex items-center gap-1 rounded-pill px-2 py-0.5 text-supporting font-semibold ${cell.passes ? "bg-ok-bg text-ok-fg" : "bg-bad-bg text-bad-fg"}`}
                                  title={cell.passes ? t("capex.passes") : t("capex.fails")}
                                >
                                  {cell.passes ? <CheckIcon /> : <XIcon />}
                                  {cell.dscr.text}&times;
                                </span>
                              ) : (
                                <span className="text-ink-3">{t("common.none")}</span>
                              )}
                            </td>
                          );
                        })}
                        <td className={`${tdCls} min-w-48`}>
                          {s.hypothetical ? (
                            <StatusPill tone="amber">
                              <span title={t("capex.hypothetical.hint")}>{t("capex.hypothetical")}</span>
                            </StatusPill>
                          ) : (
                            <StatusPill tone={!s.feasible ? "bad" : selected || worth ? "green" : "neutral"}>
                              {!s.feasible ? t("capex.infeasible") : selected || worth ? t("capex.feasible") : t("capex.notRecommended")}
                            </StatusPill>
                          )}
                          <p className="mt-1 text-supporting text-ink-2">{s.note}</p>
                          {s.extra_cost_vs_selected_display ? (
                            <p className="mt-1 text-supporting font-medium text-warn-fg">{t("capex.dearer", { amount: s.extra_cost_vs_selected_display })}</p>
                          ) : null}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </TableWrap>
          </Part>

          {capex.structures.some((s) => s.violations.length) ? (
            <Part title={t("capex.why")}>
              <ul className="grid gap-4 xl:grid-cols-2">
                {capex.structures.filter((s) => s.violations.length).flatMap((s) => s.violations.map((v) => <ViolationCard key={`${s.id}-${v.code}`} v={v} />))}
              </ul>
            </Part>
          ) : null}

          <Part id="tier" title={t("capex.tier")} aside={<TierBadge tier={capex.required_tier} explain />}>
            <p className="text-sm text-ink-2">{t("capex.tier.body")}</p>
            {canPrepareFile ? null : (
              <p className="mt-3 text-sm font-medium text-warn-fg" data-testid="capex-no-file">
                {t("capex.noFile")}
              </p>
            )}
            <p className="mt-3 text-supporting text-ink-3">{t("capex.apply.hint")}</p>
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <Button variant="primary" loading={busy === "apply"} disabled={Boolean(application) || !canPrepareFile || !worth} onClick={() => void run("apply")} data-testid="capex-apply">
                {application ? t("capex.applied") : t("capex.apply")}
              </Button>
              <Button variant="secondary" loading={busy === "file"} disabled={Boolean(file) || !canPrepareFile} onClick={() => void run("file")} data-testid="capex-file">
                {file ? t("capex.file.done") : t("capex.file.generate")}
              </Button>
              {application ? (
                <Link href="/approvals" className="text-sm font-medium text-brand-700 underline underline-offset-2" data-testid="capex-applied">
                  {t("capex.applied.review")}
                </Link>
              ) : null}
            </div>
            {application?.approval_id ? <p className="mt-2 text-supporting text-ink-2">{t("capex.applied.body", { id: application.approval_id })}</p> : null}
          </Part>

          <details id="assumptions" className="group border-t border-line pt-4">
            <summary className="flex cursor-pointer list-none items-center justify-between gap-3 [&::-webkit-details-marker]:hidden">
              <span className="font-display text-[15px] font-bold leading-tight text-ink">{t("biz.capex.basis")}</span>
              <span aria-hidden className="grid size-7 shrink-0 place-items-center rounded-pill bg-subtle text-ink-2 transition-transform duration-(--dur-fast) group-open:rotate-90">
                <ChevronRightIcon width={12} height={12} />
              </span>
            </summary>
            {/* The basis in short: a heading and one line each, every figure the server's; the server's full wording one tap away. */}
            <ul className="mt-3 space-y-3 text-sm" data-testid="capex-basis">
              {(
                [
                  capex.request.hurdle_display && capex.request.payback_limit_months
                    ? ["biz.capex.basis.worth", t("biz.capex.basis.worth.sub", { hurdle: capex.request.hurdle_display, n: capex.request.payback_limit_months })]
                    : null,
                  capex.request.monthly_uplift_display && capex.request.uplift_start_month && capex.request.life_months
                    ? [
                        "biz.capex.basis.estimate",
                        t("biz.capex.basis.estimate.sub", { amount: capex.request.monthly_uplift_display, from: capex.request.uplift_start_month, to: capex.request.life_months }),
                      ]
                    : capex.estimate_note
                      ? ["biz.capex.basis.estimate", capex.estimate_note]
                      : null,
                  ["biz.capex.basis.cheapest", t("biz.capex.basis.cheapest.sub")],
                  ["biz.capex.basis.terms", t("biz.capex.basis.terms.sub")],
                  ["biz.capex.basis.cash", t("biz.capex.basis.cash.sub")],
                  ["biz.capex.basis.debt", t("biz.capex.basis.debt.sub")],
                  ["biz.capex.basis.rates", t("biz.capex.basis.rates.sub")],
                ] as ([DictKey, string] | null)[]
              )
                .filter((x): x is [DictKey, string] => x !== null)
                .map(([key, sub]) => (
                  <li key={key}>
                    <p className="font-semibold text-ink">{t(key)}</p>
                    <p className="mt-0.5 text-ink-3">{sub}</p>
                  </li>
                ))}
            </ul>
            {capex.assumptions?.length ? (
              <details className="mt-3 text-sm">
                <summary className="cursor-pointer text-supporting font-medium text-brand-700">{t("biz.capex.basis.full")}</summary>
                <ul className="mt-2 list-disc space-y-1.5 pl-5 text-supporting text-ink-2" data-testid="capex-assumptions">
                  {capex.assumptions.map((a) => (
                    <li key={a}>{a}</li>
                  ))}
                </ul>
              </details>
            ) : null}
          </details>

          {file ? (
            <Part id="file" title={t("capex.file.title")} sub={file.style} aside={<StatusPill tone="amber">{t("capex.file.status")}</StatusPill>}>
              <p className="mb-3 text-supporting text-ink-2" data-testid="file-as-of">
                {t("capex.file.asOf", { when: whenText(file.generated_day, today, t) })}
              </p>
              <BorrowerFileSections sections={file.sections} />
              <div className="mt-4 flex flex-wrap items-center gap-2" data-testid="borrower-file-downloads">
                {file.downloads ? (
                  <>
                    <span className="text-sm font-medium">{t("capex.file.download")}</span>
                    {(
                      [
                        ["html", file.downloads.html, "capex.file.html"],
                        ["docx", file.downloads.docx, "capex.file.docx"],
                        ["pdf", file.downloads.pdf, "capex.file.pdf"],
                      ] as const
                    ).map(([kind, path, label]) =>
                      path ? (
                        <Button
                          key={kind}
                          variant="secondary"
                          loading={busy === `download-${kind}`}
                          disabled={busy !== null}
                          onClick={() => void download(kind, path, file.file_id)}
                          data-testid={`download-${kind}`}
                        >
                          {t(label)}
                        </Button>
                      ) : null,
                    )}
                    {file.pdf_note ? <span className="text-supporting text-ink-3">{file.pdf_note}</span> : null}
                  </>
                ) : (
                  <p className="text-supporting text-ink-3">{t("capex.file.mockDownload")}</p>
                )}
              </div>
              {file.provenance ? (
                <p className="mt-2 text-supporting text-ink-2" data-testid="file-provenance">
                  {t("capex.file.provenance", {
                    when: whenText(file.provenance.generated_day, today, t),
                    state: file.provenance.state_version,
                    mandate: file.provenance.mandate_version,
                    hash: file.provenance.evidence_hash.slice(0, 12),
                  })}
                </p>
              ) : null}
              <p className="mt-3 rounded-[14px] bg-brand-50 px-3 py-2 text-supporting text-ink">{file.lender_note ?? t("capex.file.note")}</p>
            </Part>
          ) : null}
        </>
      )}
    </div>
  );
}
