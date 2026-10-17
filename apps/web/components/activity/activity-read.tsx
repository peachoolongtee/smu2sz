"use client";

import Link from "next/link";
import { useState } from "react";
import { Disclosure } from "@/components/business/kit";
import { CustomerName } from "@/components/customer-link";
import { Badge, Hash } from "@/components/ui";
import { SegmentedTabs } from "@/components/ui/segmented-tabs";
import { StatusPill } from "@/components/ui/status-pill";
import { WorklistSearch } from "@/components/ui/worklist-rows";
import { useI18n } from "@/lib/i18n";
import { selectionHref } from "@/lib/selection";
import type { ActivityRecord, ActivityRow, ActivityView } from "@/lib/types";

const linkCls = "motion-press hit inline-flex min-h-8 items-center rounded-pill px-1 text-sm font-medium text-brand-700 underline underline-offset-2 hover:bg-brand-50 touch:min-h-11";

/** The record behind a row, as the evidence fold holds it: the entry and its hashes and audit sentence, or the security event's own record. */
function RecordBody({ record }: { record: ActivityRecord }) {
  const { t } = useI18n();
  if ("seq" in record) {
    return (
      <dl className="grid grid-cols-[max-content_minmax(0,1fr)] items-center gap-x-3 gap-y-1 text-sm text-ink-2" data-testid="activity-record-body">
        <dt>{t("activity.record.kind")}</dt>
        <dd>{t("trust.entry.named", { n: record.seq, kind: record.kind_text })}</dd>
        <dt>{t("ledger.hash")}</dt>
        <dd>
          <Hash value={record.entry_hash} />
        </dd>
        <dt>{t("ledger.prevHash")}</dt>
        <dd>
          <Hash value={record.prev_hash} />
        </dd>
        <dt>{t("activity.record.sentence")}</dt>
        <dd className="break-words">{record.message}</dd>
        {record.reference_text ? (
          <>
            <dt>{t("activity.record.bank")}</dt>
            <dd className="break-words" data-testid="activity-record-bank">
              {record.reference_text}
            </dd>
          </>
        ) : null}
      </dl>
    );
  }
  return (
    <dl className="grid grid-cols-[max-content_minmax(0,1fr)] gap-x-3 gap-y-1 text-sm text-ink-2" data-testid="activity-record-body">
      <dt>{t("activity.record.kind")}</dt>
      <dd>{record.kind_text}</dd>
      <dt>{t("activity.record.action")}</dt>
      <dd>{record.action_text}</dd>
      <dt>{t("activity.record.detail")}</dt>
      <dd className="break-words">{record.detail}</dd>
    </dl>
  );
}

/** The evidence fold of a row: named by the server's label, holding the record and the way to the full record in the trust views. */
function EvidenceFold({ row }: { row: ActivityRow }) {
  const { t } = useI18n();
  return (
    <Disclosure testId="activity-evidence" className="mt-2" summary={row.evidence_label}>
      <RecordBody record={row.record} />
      <p className="mt-2">
        <Link href={row.evidence_href} className={linkCls} data-testid="activity-evidence-link">
          {t("activity.evidence.open")}
        </Link>
      </p>
    </Disclosure>
  );
}

function Labelled({ label, text, testId }: { label: string; text: string; testId: string }) {
  return (
    <p className="mt-1 break-words text-sm text-ink-2" data-testid={testId}>
      <span className="font-medium text-ink-3">{label}:</span> {text}
    </p>
  );
}

function BusinessRow({ row }: { row: ActivityRow }) {
  const { t } = useI18n();
  // A deal's row always reaches the deal: the server's own link when it leads to Deals, else the deal opened in place from its record id.
  const dealHref = row.decision_id?.startsWith("deal:") && !row.href?.startsWith("/deals") ? selectionHref("/deals", { customer: row.customer_id, decision: row.decision_id, invoice: null, from: "activity" }) : null;
  return (
    <li className="grid gap-x-5 gap-y-1 py-4 sm:grid-cols-[7rem_minmax(0,1fr)]" data-testid="activity-row" data-kind={row.kind} data-category={row.category}>
      <p className="text-supporting font-medium text-ink-3 first-letter:uppercase" data-testid="activity-when">
        {row.when}
      </p>
      <div className="min-w-0">
        <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-1">
          <h3 className="min-w-0 flex-1 basis-64 text-balance text-base font-bold text-ink" data-testid="activity-event">
            {row.title_text}
          </h3>
          {row.href && row.href_label ? (
            <Link href={row.href} className={linkCls} data-testid="activity-open-decision">
              {row.href_label}
            </Link>
          ) : null}
          {dealHref ? (
            <Link href={dealHref} className={linkCls} data-testid="activity-open-deal">
              {t("deals.history.open")}
            </Link>
          ) : null}
          {/* An agreed or ended deal opens in Deals (`href`); the decision record stays one link away. */}
          {row.record_href ? (
            <Link href={row.record_href} className={linkCls} data-testid="activity-open-record">
              {t("deals.record")}
            </Link>
          ) : null}
        </div>
        {row.detail_text ? (
          <p className="mt-0.5 break-words text-sm text-ink-2" data-testid="activity-detail">
            {row.detail_text}
          </p>
        ) : null}
        {row.why_text ? <Labelled label={t("biz.activity.why")} text={row.why_text} testId="activity-why" /> : null}
        {row.remaining_text ? <Labelled label={t("biz.activity.remains")} text={row.remaining_text} testId="activity-remains" /> : null}
        <p className="mt-1 text-supporting text-ink-3" data-testid="activity-meta">
          {[
            row.status_word ? { id: "activity-status", text: row.status_word } : null,
            { id: "activity-actor", text: row.actor_text },
            row.customer_name ? { id: "activity-customer", text: row.customer_name, customerId: row.customer_id } : null,
          ]
            .filter((x): x is { id: string; text: string; customerId?: string | null } => x !== null)
            .map((x, i) => (
              <span key={x.id}>
                {i > 0 ? <span aria-hidden> · </span> : null}
                {x.customerId ? (
                  <CustomerName id={x.customerId} testId={x.id}>
                    {x.text}
                  </CustomerName>
                ) : (
                  <span data-testid={x.id}>{x.text}</span>
                )}
              </span>
            ))}
        </p>
        <EvidenceFold row={row} />
      </div>
    </li>
  );
}

/**
 * Activity on GET /activity: the stable title with the state as the pill and subheading, a search and the category tabs, then the business record first (what changed, why it
 * matters, what remains, the way to the decision, the evidence under a fold), then Security (the harmless failed sign-ins in one line, their rows under a fold, and each real
 * alert as its own item). The search and the category only hide rows the read carries; with All and an empty search every row of the read is on the page.
 */
export function ActivityRead({ view }: { view: ActivityView }) {
  const { t } = useI18n();
  const [cat, setCat] = useState("all");
  const [q, setQ] = useState("");
  const active = view.categories.some((c) => c.key === cat) ? cat : "all";
  const needle = q.trim().toLowerCase();
  const shown = view.rows.filter((r) => (active === "all" || r.category === active) && (!needle || r.search_text.toLowerCase().includes(needle)));
  const business = shown.filter((r) => r.kind === "business" || r.kind === "system");
  const benign = shown.filter((r) => r.kind === "benign_auth");
  const alerts = shown.filter((r) => r.kind === "security");
  const showSecurity = benign.length > 0 || alerts.length > 0;
  const s = view.summary;

  return (
    <div id="activity-timeline" className="space-y-6" data-testid="activity-read">
      <div className="space-y-3">
        <div className="max-w-md">
          <WorklistSearch boxed value={q} onChange={setQ} label={t("activity.search")} testId="activity-search" />
        </div>
        {view.categories.length > 1 ? (
          <SegmentedTabs
            label={t("activity.category")}
            value={active}
            onChange={setCat}
            scroll
            testId="activity-filters"
            tabs={view.categories.map((c) => ({ value: c.key, label: c.label, badge: c.count, testId: `activity-filter-${c.key}` }))}
          />
        ) : null}
      </div>

      {view.rows.length === 0 ? (
        <p className="text-sm text-ink-3" data-testid="activity-empty">
          <span className="font-medium text-ink-2">{t("ledger.ops.empty")}.</span> {t("biz.activity.empty.body")}
        </p>
      ) : shown.length === 0 ? (
        <p role="status" className="text-sm text-ink-2" data-testid="activity-filter-none">
          {t("activity.filter.none")}
        </p>
      ) : null}

      {business.length ? (
        <section aria-label={t("activity.changed")} className="card-flat !py-2 sm:!py-2" data-testid="activity-list">
          <ul className="divide-y divide-line">
            {business.map((r) => (
              <BusinessRow key={r.id} row={r} />
            ))}
          </ul>
        </section>
      ) : null}

      {showSecurity ? (
        <section id="activity-refused" aria-labelledby="activity-security-title" data-testid="activity-security" className="card-flat">
          <h2 id="activity-security-title" className="type-section text-ink">
            {t("activity.security")}
          </h2>
          {s.security_alerts_text && alerts.length ? <p className="mt-1 text-sm text-ink-2">{s.security_alerts_text}</p> : null}
          {benign.length ? (
            <div className="mt-3 rounded-card border border-line p-4" data-testid="activity-benign">
              <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                {s.benign_auth_word ? <StatusPill tone="green">{s.benign_auth_word}</StatusPill> : null}
                <p className="min-w-0 flex-1 basis-60 text-sm text-ink">{s.benign_auth_text}</p>
              </div>
              <Disclosure testId="activity-benign-rows" className="mt-2" summary={t("activity.benign.show")}>
                <ul className="divide-y divide-line">
                  {benign.map((r) => (
                    <li key={r.id} className="py-2 text-sm" data-testid="activity-row" data-kind={r.kind}>
                      <p className="break-words text-ink">
                        <span className="text-ink-3 first-letter:uppercase">{r.when}</span> · {r.title_text}
                      </p>
                      <EvidenceFold row={r} />
                    </li>
                  ))}
                </ul>
              </Disclosure>
            </div>
          ) : null}
          {alerts.map((r) => (
            <article key={r.id} className="mt-3 rounded-card border border-warn-line p-4" data-testid="activity-alert" data-kind={r.kind} aria-label={r.title_text}>
              <div className="flex flex-wrap items-start gap-x-3 gap-y-1">
                <StatusPill tone="amber">{r.status_word ?? t("activity.alert")}</StatusPill>
                <h3 className="min-w-0 flex-1 basis-60 text-base font-bold text-ink" data-testid="activity-event">
                  {r.title_text}
                </h3>
              </div>
              <p className="mt-1 text-supporting text-ink-3 first-letter:uppercase">{r.when}</p>
              {r.why_text ? <p className="mt-1 break-words text-sm text-ink-2" data-testid="activity-why">{r.why_text}</p> : null}
              {r.remaining_text ? <p className="mt-0.5 break-words text-sm text-ink-2" data-testid="activity-remains">{r.remaining_text}</p> : null}
              <EvidenceFold row={r} />
            </article>
          ))}
        </section>
      ) : null}

      <p className="text-supporting text-ink-3" data-testid="activity-kept">
        {s.kept_text}
      </p>
    </div>
  );
}

/** The record-chain words, where the page has always shown them: a badge in the header's actions. */
export function ChainBadge({ chain }: { chain: ActivityView["chain"] }) {
  const { t } = useI18n();
  if (!chain.chain_text) return null;
  return (
    <div className="flex items-center gap-2" data-testid="chain-status">
      <Badge tone={chain.chain_valid ? "ok" : "bad"} title={`${chain.chain_scope_text ?? ""} ${t("ledger.entries", { n: chain.chain_length })}`.trim()}>
        {chain.chain_text}
      </Badge>
    </div>
  );
}
