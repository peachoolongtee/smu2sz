"use client";

import Link from "next/link";
import { useState } from "react";
import { Avatar, BizCard, BizPageHeader, Chip, Disclosure, PageIcon, SectionHead, pillSecondary } from "@/components/business/kit";
import { CartIcon, CheckIcon, ChevronRightIcon, ClockIcon, ShieldCheckIcon, SlidersIcon, XIcon } from "@/components/icons";
import { ViolationCard } from "@/components/verdict-parts";
import { Button, ErrorState, KeyValueList } from "@/components/ui";
import { downloadFile, getApprovals, getState } from "@/lib/api";
import { idsToNames, localNames, plainDays, sentenceCase } from "@/lib/business-words";
import { useAsync } from "@/lib/use-async";
import { runBorrowerFile, runCapex, runCapexApply } from "@/lib/demo";
import { useDemo } from "@/lib/demo-store";
import { useI18n } from "@/lib/i18n";

/**
 * Buy equipment (capex), as the owner asks it: is the machine worth it (one verdict card with the net present value, the
 * payback and the leverage after), how should it be paid for (one row per way to pay, its monthly cover checks one tap
 * away), and what to do next (apply, which waits for the owner's approval; the borrower file). Why a way fails, the
 * assumptions and the file itself wait behind disclosures. Every figure is the server's; evaluating writes nothing.
 */
export default function CapexPage() {
  const { t, lang } = useI18n();
  const demo = useDemo();
  const [busy, setBusy] = useState<"capex" | "file" | "apply" | string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const capex = demo.capex;
  const file = demo.borrowerFile;
  const application = demo.capexApplication;
  // Where the application stands now: the approvals queue is the source (it moves when the owner decides there, on another
  // page), not the answer the apply step got. Refetched on every action (the demo store's version).
  const queue = useAsync(() => (application?.approval_id ? getApprovals().catch(() => []) : Promise.resolve([])), [application?.approval_id, demo.version]);
  const books = useAsync(getState, [demo.version]);
  const decision = application?.approval_id ? (queue.data?.find((a) => a.id === application.approval_id) ?? null) : null;
  const decided = decision?.status ?? (application ? "PENDING" : null);
  const named = (books.data?.state.facilities ?? []).map((f) => ({ id: f.id, name: f.name }));
  const resultText = decision?.presentation?.result_message || decision?.result_message || null;
  // The server selects nothing unless the project is worth doing; an illustration at another term is never selected.
  const worth = capex?.worth_doing !== false;
  const selectedStructure = capex?.structures.find((s) => s.id === capex.selected_id);
  const canPrepareFile = Boolean(selectedStructure && !selectedStructure.hypothetical && selectedStructure.facility_id);
  const failing = capex?.structures.filter((s) => s.violations.length) ?? [];

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
    <>
      <BizPageHeader
        title={t("biz.capex.title")}
        sub={t("biz.capex.sub")}
        icon={
          <PageIcon tone="orange">
            <CartIcon width={22} height={22} />
          </PageIcon>
        }
      />
      {error ? (
        <div className="mb-4">
          <ErrorState error={error} />
        </div>
      ) : null}

      {!capex ? (
        // Before the question is asked: what this page answers, and one button to ask it.
        <div className="rise space-y-4">
          <section className="hero relative overflow-hidden rounded-[1.75rem] p-6 shadow-(--shadow-lift) lg:p-8" data-status="WATCH">
            <span className="grid size-12 place-items-center rounded-full bg-white/12 ring-1 ring-white/15">
              <CartIcon width={22} height={22} />
            </span>
            <h2 className="mt-4 max-w-xl text-2xl font-semibold leading-tight tracking-tight lg:text-[2rem]">{t("biz.capex.ask")}</h2>
            <p className="mt-2 max-w-xl text-white/70">{t("biz.capex.askSub")}</p>
            <Button variant="primary" className="mt-6 !bg-white !text-ink hover:!bg-white/90" loading={busy === "capex"} onClick={() => void run("capex")}>
              {t("capex.evaluate")}
            </Button>
          </section>
          <ul className="grid gap-3 sm:grid-cols-3">
            {(
              [
                [<CheckIcon key="i" width={18} height={18} />, "biz.capex.how1", "ok"],
                [<SlidersIcon key="i" width={18} height={18} />, "biz.capex.how2", "brand"],
                [<ShieldCheckIcon key="i" width={18} height={18} />, "biz.capex.how3", "violet"],
              ] as const
            ).map(([icon, key, tone]) => (
              <li key={key} className="flex items-start gap-3 rounded-(--radius-card) border border-line bg-surface p-4 shadow-(--shadow-card)">
                <Avatar tone={tone}>{icon}</Avatar>
                <p className="text-sm text-ink-2">{t(key)}</p>
              </li>
            ))}
          </ul>
        </div>
      ) : (
        <div className="rise space-y-8">
          {/* The verdict: worth it or not, in one card. */}
          <BizCard className={`overflow-hidden p-0 ${worth ? "" : ""}`}>
            <div className={`px-5 pb-5 pt-5 lg:px-6 ${worth ? "bg-linear-to-br from-ok-bg to-surface" : "bg-linear-to-br from-warn-bg to-surface"}`}>
              <Chip tone={worth ? "ok" : "warn"}>{worth ? t("biz.capex.worth") : t("biz.capex.notWorth")}</Chip>
              <p className="mt-3 max-w-3xl text-lg font-semibold leading-snug tracking-tight text-ink" data-testid="capex-recommendation">
                {capex.recommendation ?? (worth ? null : t("capex.notWorth"))}
              </p>
            </div>
            <dl className="grid grid-cols-2 gap-px border-t border-line bg-line sm:grid-cols-4">
              {(
                [
                  [t("capex.npv"), capex.npv_display, capex.request.label, capex.npv_fen < 0 ? "text-bad-fg" : "text-ok-fg"],
                  [t("capex.payback"), capex.payback_month !== null ? t("capex.paybackValue", { n: capex.payback_month }) : t("common.none"), null, "text-ink"],
                  [t("capex.leverage"), capex.leverage_financed ? `${capex.leverage_financed.text}×` : t("common.none"), t("capex.leverage.limit", { limit: capex.leverage_limit_display }), "text-ink"],
                  [t("capex.leverageExt"), capex.leverage_with_extension ? `${capex.leverage_with_extension.text}×` : t("common.none"), t("capex.leverageExt.hint"), "text-ink"],
                ] as const
              ).map(([k, v, hint, tone]) => (
                <div key={k} className="min-w-0 bg-surface px-5 py-4">
                  <dt className="text-sm text-ink-3">{k}</dt>
                  <dd className={`figure mt-0.5 text-xl font-semibold ${tone}`}>{v}</dd>
                  {hint ? <dd className="text-xs text-ink-3">{hint}</dd> : null}
                </div>
              ))}
            </dl>
            <Disclosure summary={t("biz.capex.basis")} className="border-t border-line px-5">
              <div className="space-y-1 text-sm text-ink-2">
                {capex.estimate_note ? <p>{capex.estimate_note}</p> : null}
                {capex.as_of_day !== undefined ? <p data-testid="capex-as-of">{t("capex.asOf", { day: capex.as_of_day })}</p> : null}
              </div>
            </Disclosure>
          </BizCard>

          {/* Ways to pay: one row each, the monthly payment on the right; the monthly checks behind a tap. */}
          <section aria-labelledby="capex-ways-title">
            <SectionHead id="capex-ways-title" title={t("biz.capex.ways")} sub={t("biz.capex.waysSub", { limit: capex.dscr_limit_display })} />
            <BizCard className="p-1.5">
              <ul>
                {capex.structures.map((s) => {
                  const selected = s.id === capex.selected_id;
                  const verdict = s.hypothetical
                    ? { label: t("capex.hypothetical"), tone: "warn" as const }
                    : !s.feasible
                      ? { label: t("capex.infeasible"), tone: "bad" as const }
                      : selected
                        ? { label: t("capex.selected"), tone: "ok" as const }
                        : { label: worth ? t("capex.feasible") : t("capex.notRecommended"), tone: "neutral" as const };
                  return (
                    <li key={s.id} data-testid={`structure-${s.id}`}>
                      <details className={`rounded-2xl ${selected ? "bg-ok-bg/50" : ""}`}>
                        <summary className="flex min-h-16 items-center gap-3 rounded-2xl px-4 py-3 hover:bg-subtle">
                          <Avatar tone={selected ? "ok" : !s.feasible ? "bad" : "neutral"}>{selected ? <CheckIcon width={16} height={16} /> : !s.feasible ? <XIcon width={14} height={14} /> : <ClockIcon width={18} height={18} />}</Avatar>
                          <span className="min-w-0 flex-1">
                            <span className="block font-semibold text-ink">{localNames(s.label, lang)}</span>
                            <span className="mt-1 flex flex-wrap items-center gap-1.5">
                              <Chip tone={verdict.tone}>{verdict.label}</Chip>
                            </span>
                          </span>
                          <span className="shrink-0 text-right">
                            <span className="figure block font-semibold text-ink">{s.monthly_payment_display ?? "—"}</span>
                            <span className="block text-xs text-ink-3">{t("capex.monthly")}</span>
                          </span>
                          <ChevronRightIcon className="chev shrink-0 text-ink-3" />
                        </summary>
                        <div className="space-y-3 px-4 pb-4 text-sm">
                          <dl className="grid grid-cols-2 gap-3">
                            <div className="rounded-xl bg-surface px-3 py-2 ring-1 ring-line">
                              <dt className="text-xs text-ink-3">{t("capex.interest")}</dt>
                              <dd className="figure font-semibold">{s.total_interest_display ?? t("common.none")}</dd>
                            </div>
                            <div className="rounded-xl bg-surface px-3 py-2 ring-1 ring-line">
                              <dt className="text-xs text-ink-3" title={t("capex.charges.hint")}>
                                {t("capex.charges")}
                              </dt>
                              <dd className="figure font-semibold">{s.charges_total_display ?? t("common.none")}</dd>
                            </div>
                          </dl>
                          {s.dscr_by_month.length ? (
                            <div>
                              <p className="text-xs text-ink-3">{t("biz.capex.cover")}</p>
                              <ul className="mt-1.5 flex flex-wrap gap-1.5">
                                {s.dscr_by_month.slice(0, 6).map((cell) => (
                                  <li
                                    key={cell.month}
                                    className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-semibold ${cell.passes ? "bg-ok-bg text-ok-fg" : "bg-bad-bg text-bad-fg"}`}
                                    title={cell.passes ? t("capex.passes") : t("capex.fails")}
                                  >
                                    {cell.passes ? <CheckIcon width={12} height={12} /> : <XIcon width={12} height={12} />}
                                    {t("biz.capex.month", { n: cell.month })} {cell.dscr.text}&times;
                                  </li>
                                ))}
                              </ul>
                              <p className="mt-1.5 text-xs text-ink-3">{t("dscr.readingNote")}</p>
                            </div>
                          ) : null}
                          {s.note ? <p className="text-ink-2">{localNames(plainDays(s.note, books.data?.day ?? 0, t), lang)}</p> : null}
                          {s.extra_cost_vs_selected_display ? <p className="font-medium text-warn-fg">{t("capex.dearer", { amount: s.extra_cost_vs_selected_display })}</p> : null}
                          {s.hypothetical ? <p className="text-xs text-ink-3">{t("capex.hypothetical.hint")}</p> : null}
                        </div>
                      </details>
                    </li>
                  );
                })}
              </ul>
            </BizCard>
          </section>

          {/* The next step: applying is the owner's act and waits for approval; the borrower file is prepared, never sent. */}
          <BizCard className="p-5 lg:p-6">
            <div className="flex items-start gap-3.5">
              <Avatar tone="violet" size="lg">
                <ShieldCheckIcon width={22} height={22} />
              </Avatar>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-ink-3">{t("biz.capex.nextLabel")}</p>
                <h2 className="text-xl font-semibold tracking-tight text-ink">{t("biz.capex.next")}</h2>
                <p className="mt-1 text-sm text-ink-2">{t("capex.apply.hint")}</p>
                {canPrepareFile ? null : (
                  <p className="mt-2 text-sm font-medium text-warn-fg" data-testid="capex-no-file">
                    {t("capex.noFile")}
                  </p>
                )}
              </div>
            </div>
            <div className="mt-5 flex flex-wrap items-center gap-2">
              <Button variant="primary" loading={busy === "apply"} disabled={Boolean(application) || !canPrepareFile || !worth} onClick={() => void run("apply")} data-testid="capex-apply">
                {!application ? t("capex.apply") : decided === "APPROVED" ? t("biz.capex.appApproved") : decided === "REJECTED" ? t("biz.capex.appDeclined") : t("capex.applied")}
              </Button>
              <Button variant="secondary" loading={busy === "file"} disabled={Boolean(file) || !canPrepareFile} onClick={() => void run("file")} data-testid="capex-file">
                {file ? t("capex.file.done") : t("capex.file.generate")}
              </Button>
              {application && decided === "PENDING" ? (
                <Link href="/approvals" className={pillSecondary} data-testid="capex-applied">
                  {t("capex.applied.review")}
                </Link>
              ) : null}
            </div>
            {/* The application's status, from the approvals queue. */}
            {application ? (
              <div
                className={`mt-4 rounded-2xl px-4 py-3 text-sm ${decided === "APPROVED" ? "bg-ok-bg/70" : decided === "REJECTED" ? "bg-bad-bg/70" : "bg-warn-bg/70"}`}
                role="status"
                data-testid="capex-application-status"
                data-status={decided ?? ""}
              >
                <p className={`font-semibold ${decided === "APPROVED" ? "text-ok-fg" : decided === "REJECTED" ? "text-bad-fg" : "text-warn-fg"}`}>
                  {decided === "APPROVED" ? t("biz.capex.appApproved") : decided === "REJECTED" ? t("biz.capex.appDeclined") : t("biz.capex.appWaiting")}
                </p>
                <p className="mt-0.5 text-ink-2">
                  {decided === "APPROVED"
                    ? t("biz.capex.appApproved.body")
                    : decided === "REJECTED"
                      ? t("biz.capex.appDeclined.body")
                      : application.approval_id
                        ? t("capex.applied.body", { id: application.approval_id })
                        : null}
                </p>
                {resultText && decided !== "PENDING" ? (
                  <p className="mt-1 text-xs text-ink-3">{localNames(sentenceCase(plainDays(idsToNames(resultText, named), books.data?.day ?? 0, t)), lang)}</p>
                ) : null}
              </div>
            ) : null}
            <Disclosure summary={t("capex.tier")} className="mt-3 border-t border-line pt-1">
              <p className="text-sm text-ink-2">{t("capex.tier.body")}</p>
            </Disclosure>
          </BizCard>

          {file ? (
            <BizCard className="p-5 lg:p-6" testId="capex-borrower-file">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <h2 className="text-lg font-semibold tracking-tight text-ink">{t("capex.file.title")}</h2>
                  <p className="text-sm text-ink-3">{file.style}</p>
                </div>
                <Chip tone="warn">{t("capex.file.status")}</Chip>
              </div>
              <div className="mt-4 flex flex-wrap items-center gap-2" data-testid="borrower-file-downloads">
                {file.downloads ? (
                  <>
                    {(
                      [
                        ["html", file.downloads.html, "capex.file.html"],
                        ["docx", file.downloads.docx, "capex.file.docx"],
                        ["pdf", file.downloads.pdf, "capex.file.pdf"],
                      ] as const
                    ).map(([kind, path, label]) =>
                      path ? (
                        <Button key={kind} variant="secondary" loading={busy === `download-${kind}`} disabled={busy !== null} onClick={() => void download(kind, path, file.file_id)} data-testid={`download-${kind}`}>
                          {t("capex.file.download")} · {t(label)}
                        </Button>
                      ) : null,
                    )}
                    {file.pdf_note ? <span className="text-xs text-ink-3">{file.pdf_note}</span> : null}
                  </>
                ) : (
                  <p className="text-sm text-ink-3">{t("capex.file.mockDownload")}</p>
                )}
              </div>
              <Disclosure summary={t("biz.capex.fileContents")} className="mt-3 border-t border-line pt-1">
                <p className="mb-3 text-xs text-ink-3" data-testid="file-as-of">
                  {t("capex.file.asOf", { day: file.generated_day })}
                </p>
                <div className="grid gap-3 md:grid-cols-2">
                  {file.sections.map((sec) => (
                    <div key={sec.title} className="rounded-2xl bg-subtle p-4">
                      <h3 className="mb-2 text-sm font-semibold">{sec.title}</h3>
                      <KeyValueList items={sec.rows.map((r) => ({ k: r.label, v: r.value }))} />
                      {sec.notes?.length ? (
                        <ul className="mt-2 list-disc space-y-1 pl-5 text-xs text-ink-2">
                          {sec.notes.map((n) => (
                            <li key={n}>{n}</li>
                          ))}
                        </ul>
                      ) : null}
                    </div>
                  ))}
                </div>
                {file.provenance ? (
                  <p className="mt-3 text-xs text-ink-3" data-testid="file-provenance">
                    {t("capex.file.provenance", {
                      day: file.provenance.generated_day,
                      state: file.provenance.state_version,
                      mandate: file.provenance.mandate_version,
                      hash: file.provenance.evidence_hash.slice(0, 12),
                    })}
                  </p>
                ) : null}
                <p className="mt-2 text-xs text-ink-3">{file.lender_note ?? t("capex.file.note")}</p>
              </Disclosure>
            </BizCard>
          ) : null}

          <div className="space-y-3">
            {failing.length ? (
              <Disclosure card summary={t("capex.why")} testId="capex-why">
                <ul className="grid gap-4 xl:grid-cols-2">{failing.flatMap((s) => s.violations.map((v) => <ViolationCard key={`${s.id}-${v.code}`} v={v} />))}</ul>
              </Disclosure>
            ) : null}
            {capex.assumptions?.length ? (
              <Disclosure card summary={t("capex.assumptions")}>
                <ul className="list-disc space-y-1.5 pl-5 text-sm text-ink-2" data-testid="capex-assumptions">
                  {capex.assumptions.map((a) => (
                    <li key={a}>{a}</li>
                  ))}
                </ul>
              </Disclosure>
            ) : null}
          </div>
        </div>
      )}
    </>
  );
}
