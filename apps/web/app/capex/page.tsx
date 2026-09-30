"use client";

import Link from "next/link";
import { useState } from "react";
import { CheckIcon, XIcon } from "@/components/icons";
import { TierBadge } from "@/components/badges";
import { ViolationCard } from "@/components/verdict-parts";
import {
  Badge,
  Button,
  Callout,
  Card,
  EmptyState,
  ErrorState,
  KeyValueList,
  PageHeader,
  Stat,
  TableWrap,
  tableCls,
  tdCls,
  thCls,
} from "@/components/ui";
import { downloadFile } from "@/lib/api";
import { runBorrowerFile, runCapex } from "@/lib/demo";
import { useDemo } from "@/lib/demo-store";
import { useI18n } from "@/lib/i18n";

export default function CapexPage() {
  const { t } = useI18n();
  const demo = useDemo();
  const [busy, setBusy] = useState<"capex" | "file" | string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const capex = demo.capex;
  const file = demo.borrowerFile;

  async function run(kind: "capex" | "file") {
    setBusy(kind);
    setError(null);
    try {
      await (kind === "capex" ? runCapex() : runBorrowerFile());
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
    <>
      <PageHeader title={t("capex.title")} subtitle={t("capex.subtitle")} />
      {error ? <ErrorState error={error} /> : null}

      {!capex ? (
        <EmptyState
          title={t("capex.empty.title")}
          body={t("capex.empty.body")}
          action={
            <Button variant="primary" loading={busy === "capex"} onClick={() => void run("capex")}>
              {t("capex.evaluate")}
            </Button>
          }
        />
      ) : (
        <div className="space-y-6">
          <dl className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <Stat label={t("capex.npv")} value={capex.npv_display} hint={capex.request.label} tone="ok" />
            <Stat label={t("capex.payback")} value={t("capex.paybackValue", { n: capex.payback_month })} />
            <Stat label={t("capex.leverage")} value={`${capex.leverage_financed.text}×`} hint={t("capex.leverage.limit", { limit: capex.leverage_limit_display })} />
            <Stat
              label={t("capex.leverageExt")}
              value={`${capex.leverage_with_extension.text}×`}
              hint={t("capex.leverageExt.hint")}
            />
          </dl>

          <Card id="structures" title={t("capex.structures")} subtitle={t("capex.structures.sub", { limit: capex.dscr_limit_display })}>
            <TableWrap label={t("capex.structures")}>
              <table className={`${tableCls} min-w-[50rem]`}>
                <caption className="sr-only">{t("capex.structures")}</caption>
                <thead>
                  <tr>
                    <th scope="col" className={`${thCls} sticky left-0 z-10`}>{t("capex.structure")}</th>
                    <th scope="col" className={`${thCls} text-right`}>{t("capex.monthly")}</th>
                    <th scope="col" className={`${thCls} text-right`}>{t("capex.interest")}</th>
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
                      <tr key={s.id} className={selected ? "bg-ok-bg/60" : ""} data-testid={`structure-${s.id}`}>
                        <th scope="row" className={`${tdCls} sticky left-0 z-10 min-w-36 text-left font-medium ${selected ? "bg-ok-bg" : "bg-surface"}`}>
                          {s.label}
                          {selected ? (
                            <Badge tone="ok" className="mt-1 flex w-fit">
                              <CheckIcon />
                              {t("capex.selected")}
                            </Badge>
                          ) : null}
                        </th>
                        <td className={`${tdCls} whitespace-nowrap text-right font-medium tabular-nums`}>
                          {s.monthly_payment_display ?? t("common.none")}
                        </td>
                        <td className={`${tdCls} whitespace-nowrap text-right tabular-nums`}>{s.total_interest_display ?? t("common.none")}</td>
                        {[1, 2, 3, 4, 5, 6].map((m) => {
                          const cell = s.dscr_by_month.find((d) => d.month === m);
                          return (
                            <td key={m} className={`${tdCls} text-right tabular-nums`}>
                              {cell ? (
                                <span
                                  className={`inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-xs font-semibold ${
                                    cell.passes ? "bg-ok-bg text-ok-fg" : "bg-bad-bg text-bad-fg"
                                  }`}
                                  title={cell.passes ? t("capex.passes") : t("capex.fails")}
                                >
                                  {cell.passes ? <CheckIcon width={12} height={12} /> : <XIcon width={12} height={12} />}
                                  {cell.dscr.text}&times;
                                </span>
                              ) : (
                                <span className="text-ink-3">{t("common.none")}</span>
                              )}
                            </td>
                          );
                        })}
                        <td className={`${tdCls} min-w-48`}>
                          <Badge tone={s.feasible ? "ok" : "bad"}>{s.feasible ? t("capex.feasible") : t("capex.infeasible")}</Badge>
                          <p className="mt-1 text-xs text-ink-2">{s.note}</p>
                          {s.extra_cost_vs_selected_display ? (
                            <p className="mt-1 text-xs font-medium text-warn-fg">
                              {t("capex.dearer", { amount: s.extra_cost_vs_selected_display })}
                            </p>
                          ) : null}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </TableWrap>
          </Card>

          <section aria-labelledby="capex-fail-title">
            <h2 id="capex-fail-title" className="mb-2 text-sm font-semibold">
              {t("capex.why")}
            </h2>
            <ul className="grid gap-4 xl:grid-cols-2">
              {capex.structures
                .filter((s) => s.violations.length)
                .flatMap((s) => s.violations.map((v) => <ViolationCard key={`${s.id}-${v.code}`} v={v} />))}
            </ul>
          </section>

          <Card id="tier" title={t("capex.tier")} tone="warn" actions={<TierBadge tier={capex.required_tier} />}>
            <p className="text-sm text-ink-2">{t("capex.tier.body")}</p>
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <Button variant="primary" loading={busy === "file"} disabled={Boolean(file)} onClick={() => void run("file")}>
                {file ? t("capex.file.done") : t("capex.file.generate")}
              </Button>
              {file ? (
                <Link href="/approvals" className="text-sm font-medium text-brand-700 underline underline-offset-2">
                  {t("capex.file.approvals")}
                </Link>
              ) : null}
            </div>
          </Card>

          {file ? (
            <Card
              id="file"
              title={t("capex.file.title")}
              subtitle={file.style}
              actions={<Badge tone="warn">{t("capex.file.status")}</Badge>}
            >
              <div className="grid gap-4 md:grid-cols-2">
                {file.sections.map((sec) => (
                  <div key={sec.title} className="rounded-lg border border-line p-3">
                    <h3 className="mb-2 text-sm font-semibold">{sec.title}</h3>
                    <KeyValueList items={sec.rows.map((r) => ({ k: r.label, v: r.value }))} />
                  </div>
                ))}
              </div>
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
                    {file.pdf_note ? <span className="text-xs text-ink-3">{file.pdf_note}</span> : null}
                  </>
                ) : (
                  <p className="text-xs text-ink-3">{t("capex.file.mockDownload")}</p>
                )}
              </div>
              {file.approval_id ? <p className="mt-2 text-xs text-ink-2">{t("capex.file.approval", { id: file.approval_id })}</p> : null}
              <div className="mt-3">
                <Callout tone="info">{file.lender_note ?? t("capex.file.note")}</Callout>
              </div>
            </Card>
          ) : null}
        </div>
      )}
    </>
  );
}
