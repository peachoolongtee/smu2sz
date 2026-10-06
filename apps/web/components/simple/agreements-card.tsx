"use client";

import { useState } from "react";
import { commitmentFor } from "@/components/approval-card";
import { obligationSentence } from "@/components/home/agreements-card";
import { SectionLink } from "@/components/home/today-card";
import { Badge, Button, Card, ErrorState, Hash, LoadingBlock, type Tone } from "@/components/ui";
import { ApiError, decideApproval, getApprovals, getLedger, getState } from "@/lib/api";
import { bump, useDemo } from "@/lib/demo-store";
import type { DictKey } from "@/lib/dictionary";
import { useI18n } from "@/lib/i18n";
import { isWriteConflictDetail } from "@/lib/live/retry";
import type { ApprovalDecision, ApprovalView, Commitment, CommitmentStatus, Displayed } from "@/lib/types";
import { useAsync } from "@/lib/use-async";

type Column = "pending" | "confirmed" | "rejected";

interface Item {
  key: string;
  column: Column;
  buyer: string | null;
  title: string;
  terms: string[];
  hash: string | null;
  badge: { tone: Tone; label: string };
  cost: string | null;
  /** A pending approval the owner can decide from here. */
  approval: ApprovalView | null;
}

const COLUMN_OF: Record<CommitmentStatus, Column> = {
  PROPOSED: "pending",
  ACCEPTED: "confirmed",
  ACTIVE: "confirmed",
  FULFILLED: "confirmed",
  EXPIRED: "rejected",
  REVOKED: "rejected",
};

const commitmentTone: Record<Column, Tone> = { pending: "warn", confirmed: "ok", rejected: "bad" };
const COLUMNS: { id: Column; title: DictKey; empty: DictKey }[] = [
  { id: "pending", title: "simple.deals.pending", empty: "simple.deals.empty.pending" },
  { id: "confirmed", title: "simple.deals.confirmed", empty: "simple.deals.empty.confirmed" },
  { id: "rejected", title: "simple.deals.rejected", empty: "simple.deals.empty.rejected" },
];

/**
 * The owner overview's agreements in three columns. Reads GET /ledger (commitments, each with its terms hash), GET /state
 * (buyer names) and GET /approvals/queue; adds this session's negotiations that ended without a deal and offers the agent
 * declined. Approve and Turn down are POST /approvals/{id}, the same call as the Approvals page, so both overviews and the
 * ledger move together.
 */
export function SimpleAgreementsCard() {
  const { t, te } = useI18n();
  const demo = useDemo();
  const view = useAsync(async () => {
    // A refused approvals read (no owner token yet) must not hide what was agreed.
    const [ledger, state, approvals] = await Promise.all([getLedger(), getState(), getApprovals().catch(() => [] as ApprovalView[])]);
    return { ledger, state, approvals };
  }, []);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function decide(id: string, decision: ApprovalDecision) {
    setBusy(`${id}:${decision}`);
    setError(null);
    try {
      await decideApproval(id, decision);
    } catch (e) {
      if (e instanceof ApiError && (e.status === 404 || e.status === 409) && !isWriteConflictDetail(e.detail)) setError(t("simple.deals.err.gone"));
      else setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
      bump();
    }
  }

  const d = view.data;
  let items: Item[] = [];
  if (d) {
    const names = new Map(d.state.state.counterparties.map((cp) => [cp.id, cp.name]));
    const nameOf = (id: string) => names.get(id) ?? id;
    const commitments = d.ledger.commitments;
    const linked = new Map<string, ApprovalView>();
    const loose: ApprovalView[] = [];
    for (const a of d.approvals) {
      const c = commitmentFor(a.operation, commitments);
      if (c) linked.set(c.id, a);
      else loose.push(a);
    }

    const fromCommitment = (c: Displayed<Commitment>): Item => {
      const a = linked.get(c.id) ?? null;
      // A proposed deal whose approval the owner turned down is not waiting any more.
      const column: Column = c.status === "PROPOSED" && a?.status === "REJECTED" ? "rejected" : COLUMN_OF[c.status];
      const waiting = a?.status === "PENDING";
      return {
        key: `c-${c.id}`,
        column,
        buyer: nameOf(c.counterparty_id),
        title: c.id,
        terms: c.obligations.map((o) => obligationSentence(o, t, te)),
        hash: c.terms_hash,
        badge: waiting
          ? { tone: "warn", label: t("simple.deals.needsYou") }
          : a?.status === "REJECTED"
            ? { tone: "bad", label: t("simple.deals.rejectedByYou") }
            : { tone: commitmentTone[column], label: te("deal.status", c.status) },
        cost: c.forward_value_display,
        approval: waiting ? a : null,
      };
    };

    const fromApproval = (a: ApprovalView): Item => ({
      key: `a-${a.id}`,
      column: a.status === "PENDING" ? "pending" : a.status === "APPROVED" ? "confirmed" : "rejected",
      buyer: null,
      title: a.subject,
      terms: [a.amount_display ? `${te("opkind", a.operation_kind)}: ${a.amount_display}` : te("opkind", a.operation_kind)],
      hash: a.operation?.terms_hash ?? null,
      badge:
        a.status === "PENDING"
          ? { tone: "warn", label: t("simple.deals.needsYou") }
          : a.status === "APPROVED"
            ? { tone: "ok", label: t("simple.deals.approved") }
            : { tone: "bad", label: t("simple.deals.rejectedByYou") },
      cost: null,
      approval: a.status === "PENDING" ? a : null,
    });

    // This session's offers that ended without an agreement: nothing is in the ledger for them, so they come from the session.
    const booked = new Set(commitments.map((c) => c.offer_id));
    const fromSession: Item[] = Object.keys(demo.verdicts)
      .filter((id) => !booked.has(id))
      .flatMap((id): Item[] => {
        const n = demo.negotiations[id];
        const v = demo.verdicts[id];
        const offer = demo.offers[id];
        const buyer = offer ? nameOf(offer.offer.counterparty_id) : null;
        if (n?.outcome === "NO_DEAL") {
          return [{ key: `n-${id}`, column: "rejected", buyer, title: id, terms: [n.message], hash: null, badge: { tone: "neutral", label: t("simple.deals.noDeal") }, cost: null, approval: null }];
        }
        if (!n && v.outcome === "REJECT") {
          return [{ key: `v-${id}`, column: "rejected", buyer, title: id, terms: [...new Set(v.violations.map((x) => te("violation", x.code)))], hash: null, badge: { tone: "bad", label: t("simple.deals.declined") }, cost: null, approval: null }];
        }
        return [];
      });

    items = [...[...commitments].reverse().map(fromCommitment), ...loose.map(fromApproval), ...fromSession];
  }

  return (
    <Card id="simple-deals" title={t("simple.deals.title")} subtitle={t("simple.deals.sub")} actions={<SectionLink href="/ledger">{t("simple.deals.log")}</SectionLink>}>
      {view.error ? (
        <ErrorState error={view.error} onRetry={view.reload} />
      ) : !d ? (
        <LoadingBlock rows={2} />
      ) : (
        <>
          {error ? (
            <div className="mb-3">
              <ErrorState error={error} />
            </div>
          ) : null}
          <div className="grid gap-4 lg:grid-cols-3">
            {COLUMNS.map((col) => {
              const list = items.filter((i) => i.column === col.id);
              return (
                <section key={col.id} aria-label={t(col.title)} data-testid={`simple-deals-${col.id}`}>
                  <h3 className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-ink-3">
                    {t(col.title)}
                    <Badge tone={list.length ? commitmentTone[col.id] : "neutral"}>{list.length}</Badge>
                  </h3>
                  {list.length === 0 ? (
                    <p className="rounded-lg border border-dashed border-line px-3 py-3 text-sm text-ink-3">{t(col.empty)}</p>
                  ) : (
                    <ul className="space-y-2">
                      {list.map((i) => (
                        <DealItem key={i.key} item={i} busy={busy} onDecide={(id, dec) => void decide(id, dec)} />
                      ))}
                    </ul>
                  )}
                </section>
              );
            })}
          </div>
        </>
      )}
    </Card>
  );
}

function DealItem({ item, busy, onDecide }: { item: Item; busy: string | null; onDecide: (id: string, d: ApprovalDecision) => void }) {
  const { t } = useI18n();
  const a = item.approval;
  return (
    <li className="rounded-lg border border-line px-3 py-2.5" data-testid={`simple-deal-${item.key}`}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="min-w-0 text-sm font-semibold text-ink">{item.buyer ? t("simple.deals.with", { buyer: item.buyer }) : item.title}</p>
        <Badge tone={item.badge.tone}>{item.badge.label}</Badge>
      </div>
      <ul className="mt-1.5 list-disc space-y-0.5 pl-5 text-sm text-ink-2">
        {item.terms.map((s, i) => (
          <li key={i} className="break-words">
            {s}
          </li>
        ))}
      </ul>
      {item.cost ? (
        <p className="mt-1.5 text-xs text-ink-3">
          {t("simple.deals.cost")}: <span className="font-medium tabular-nums text-ink">{item.cost}</span>
        </p>
      ) : null}
      {item.hash ? (
        <p className="mt-1 flex flex-wrap items-center gap-1 text-xs text-ink-3" data-testid="simple-deal-hash">
          {t("simple.msg.fingerprint")}
          <Hash value={item.hash} />
        </p>
      ) : null}
      {a ? (
        <div className="mt-2 flex flex-wrap gap-2">
          <Button
            variant="primary"
            size="sm"
            loading={busy === `${a.id}:APPROVE`}
            disabled={busy !== null}
            onClick={() => onDecide(a.id, "APPROVE")}
            data-testid={`simple-approve-${a.id}`}
          >
            {t("simple.deals.approve")}
          </Button>
          <Button size="sm" loading={busy === `${a.id}:REJECT`} disabled={busy !== null} onClick={() => onDecide(a.id, "REJECT")} data-testid={`simple-reject-${a.id}`}>
            {t("simple.deals.reject")}
          </Button>
        </div>
      ) : null}
    </li>
  );
}
