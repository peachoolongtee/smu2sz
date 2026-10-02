"use client";

import { useState } from "react";
import { AnnotatedText, type Annotation } from "@/components/annotated-text";
import { CodeBadge, OutcomeBadge } from "@/components/badges";
import { SpanQuote } from "@/components/offer-parts";
import { Button, Callout, Card, EmptyState, ErrorState, LoadingBlock, PageHeader, Stat } from "@/components/ui";
import type { AnnotationKind } from "@/lib/annotation-style";
import { getAudit, resetCircuit } from "@/lib/api";
import { runSecurityScene } from "@/lib/demo";
import { bump, useDemo } from "@/lib/demo-store";
import { useI18n } from "@/lib/i18n";
import type { SecurityEventKind } from "@/lib/types";
import { useAsync } from "@/lib/use-async";

const EVENT_KIND: Partial<Record<SecurityEventKind, AnnotationKind>> = {
  UNKNOWN_COUNTERPARTY: "FUNDING_CLAIM",
  UNEVIDENCED_CLAIM: "CLAIMED_PRIOR_CONCESSION",
  DATA_EXTRACTION: "DATA_REQUEST",
  PRIVILEGE_ESCALATION: "AUTHORITY_CLAIM",
  INJECTION: "AUTHORITY_CLAIM",
};

export default function SecurityPage() {
  const { t, te } = useI18n();
  const audit = useAsync(getAudit, []);
  const [active, setActive] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const demo = useDemo();
  const [circuit, setCircuit] = useState<{ busy: string | null; done: string | null }>({ busy: null, done: null });

  async function resetBreaker(counterpartyId: string) {
    setCircuit({ busy: counterpartyId, done: null });
    setError(null);
    try {
      await resetCircuit(counterpartyId);
      bump();
      setCircuit({ busy: null, done: counterpartyId });
    } catch (e) {
      setCircuit({ busy: null, done: null });
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  async function run() {
    setBusy(true);
    setError(null);
    try {
      await runSecurityScene();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  const data = audit.data;
  // The audit may omit the documents (live API). Fall back to the offers this session compiled, matched by the spans' doc_id.
  const spanDocId = data?.events.flatMap((e) => e.spans)[0]?.doc_id;
  const doc =
    data?.documents.find((d) => d.doc_id === spanDocId) ??
    Object.values(demo.offers)
      .flatMap((o) => o.documents)
      .find((d) => d.doc_id === spanDocId) ??
    data?.documents[0];
  const counterparties = [...new Set(data?.events.map((e) => e.counterparty_id).filter((c): c is string => Boolean(c)))];
  const annotations: Annotation[] =
    data?.events.flatMap((e, ei) =>
      e.spans
        .filter((s) => doc && s.doc_id === doc.doc_id)
        .map((s) => ({
          id: e.id,
          kind: EVENT_KIND[e.kind] ?? "DATA_REQUEST",
          start: s.start,
          end: s.end,
          n: ei + 1,
          label: te("secevent", e.kind),
        })),
    ) ?? [];

  return (
    <>
      <PageHeader
        title={t("sec.title")}
        subtitle={t("sec.subtitle")}
        actions={
          <Button variant="primary" loading={busy} onClick={() => void run()}>
            {t("sec.run")}
          </Button>
        }
      />
      {error ? (
        <div className="mb-4">
          <ErrorState error={error} />
        </div>
      ) : null}

      {audit.error ? (
        <ErrorState error={audit.error} onRetry={audit.reload} />
      ) : !data ? (
        <LoadingBlock rows={4} />
      ) : !doc || data.events.length === 0 ? (
        <EmptyState
          title={t("sec.empty.title")}
          body={t("sec.empty.body")}
          action={
            <Button variant="primary" loading={busy} onClick={() => void run()}>
              {t("sec.run")}
            </Button>
          }
        />
      ) : (
        <div className="space-y-6">
          <Card
            id="sec-message"
            title={t("sec.message", { sender: doc.sender_id })}
            subtitle={t("sec.message.sub")}
            tone="bad"
            actions={<OutcomeBadge outcome="REJECT" />}
          >
            <AnnotatedText
              text={doc.text}
              annotations={annotations}
              activeId={active}
              onActivate={setActive}
              ariaLabel={t("sec.message", { sender: doc.sender_id })}
            />
          </Card>

          <section aria-labelledby="sec-scoreboard">
            <h2 id="sec-scoreboard" className="mb-2 text-sm font-semibold">
              {t("sec.scoreboard")}
            </h2>
            <dl className="grid grid-cols-2 gap-3 lg:grid-cols-4">
              <Stat label={t("sec.facilities")} value={data.summary.facilities_added} tone="ok" />
              <Stat label={t("sec.commitments")} value={data.summary.commitments_booked} tone="ok" />
              <Stat label={t("sec.money")} value={data.summary.money_moved_display} tone="ok" />
              <Stat
                label={t("sec.disclosed")}
                value={data.summary.disclosed_fields.length ? data.summary.disclosed_fields.join(", ") : t("common.none")}
                tone="ok"
              />
            </dl>
          </section>

          {data.summary.reply_text ? (
            <Card id="sec-reply" title={t("sec.reply")} subtitle={t("sec.reply.sub")}>
              <blockquote className="rounded-md border-l-4 border-line-strong bg-subtle px-3 py-2 text-sm">{data.summary.reply_text}</blockquote>
            </Card>
          ) : null}

          <Card id="sec-circuit" title={t("sec.circuit")} subtitle={t("sec.circuit.note")}>
            <div className="flex flex-wrap items-center gap-3">
              {counterparties.map((id) => (
                <Button
                  key={id}
                  variant="secondary"
                  loading={circuit.busy === id}
                  disabled={circuit.busy !== null}
                  onClick={() => void resetBreaker(id)}
                  data-testid={`circuit-reset-${id}`}
                >
                  {t("sec.circuit.reset", { id })}
                </Button>
              ))}
              {circuit.done ? (
                <p role="status" className="text-sm text-ok-fg">
                  {t("sec.circuit.done", { id: circuit.done })}
                </p>
              ) : null}
            </div>
          </Card>

          <Card id="sec-events" title={t("sec.events", { n: data.events.length })} subtitle={t("sec.events.sub")}>
            <ul className="space-y-3">
              {data.events.map((e) => (
                <li
                  key={e.id}
                  className={`rounded-lg border p-3 ${active === e.id ? "border-ink ring-2 ring-ink/15" : "border-bad-line"}`}
                  onMouseEnter={() => setActive(e.id)}
                  onMouseLeave={() => setActive(null)}
                  data-testid={`event-${e.id}`}
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <CodeBadge code={e.kind} tone="bad" />
                    <span className="min-w-0 max-w-full break-words rounded-full border border-ok-line bg-ok-bg px-2 py-0.5 text-xs font-medium text-ok-fg">{e.action_taken}</span>
                    <span className="min-w-0 max-w-full break-all text-xs text-ink-3">
                      {e.id} &middot; {t("common.dayN", { n: e.day })}
                      {e.trace_id ? ` · ${e.trace_id}` : ""}
                    </span>
                  </div>
                  <p className="mt-2 break-words text-sm">{e.detail}</p>
                  {e.spans.map((s) => (
                    <SpanQuote key={`${s.doc_id}:${s.start}`} text={s.text} />
                  ))}
                </li>
              ))}
            </ul>
            <div className="mt-4">
              <Callout tone="info">{t("sec.architecture")}</Callout>
            </div>
          </Card>
        </div>
      )}
    </>
  );
}
