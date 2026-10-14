"use client";

import { useEffect, useState } from "react";
import { AnnotatedText, type Annotation } from "@/components/annotated-text";
import { OutcomeBadge } from "@/components/badges";
import { SpanQuote } from "@/components/offer-parts";
import { Button, Callout, Card, EmptyState, ErrorState, LoadingBlock, PageHeader, Stat } from "@/components/ui";
import { StatusPill } from "@/components/ui/status-pill";
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

/**
 * The security audit: the hostile message with each flagged span, what it achieved (nothing booked, moved or disclosed), the reply sent, the circuit breaker and every
 * event, each in the server's words (`kind_text`, `action_text`, `day_when`) with the engine's id kept as the record's own mark. `event` (an event id in the address)
 * marks one event: scrolled to, drawn with a visible mark and `aria-current`, focused. On the engine's own page it has the page header; `embedded` (the /trust page)
 * gives it a section heading instead, so the page keeps one h1.
 */
export function SecurityView({ embedded = false, event = null }: { embedded?: boolean; event?: string | null }) {
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
  const eventFound = event !== null && !!data?.events.some((e) => e.id === event);
  // The address names one event: bring it into view and give it focus, once the events are there.
  useEffect(() => {
    if (event === null || !eventFound) return;
    const el = document.getElementById(`event-${event}`);
    if (!el) return;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    el.scrollIntoView({ block: "center", behavior: reduced ? "auto" : "smooth" });
    el.focus({ preventScroll: true });
  }, [event, eventFound]);

  // The audit may omit the documents (live API). Fall back to the offers this session compiled, matched by the spans' doc_id.
  const spanDocId = data?.events.flatMap((e) => e.spans)[0]?.doc_id;
  const doc =
    data?.documents.find((d) => d.doc_id === spanDocId) ??
    Object.values(demo.offers)
      .flatMap((o) => o.documents)
      .find((d) => d.doc_id === spanDocId) ??
    data?.documents[0];
  const counterparties = [...new Set(data?.events.map((e) => e.counterparty_id).filter((c): c is string => Boolean(c)))];
  const kindWord = (e: { kind: SecurityEventKind; kind_text?: string }) => e.kind_text ?? te("secevent", e.kind);
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
          label: kindWord(e),
        })),
    ) ?? [];

  return (
    <>
      {embedded ? (
        <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <h2 className="font-display text-xl font-extrabold tracking-[-0.01em] text-ink">{t("sec.title")}</h2>
            <p className="mt-0.5 max-w-3xl text-supporting text-ink-3">{t("sec.subtitle")}</p>
          </div>
          <Button loading={busy} onClick={() => void run()} data-testid="trust-security-run">
            {t("sec.run")}
          </Button>
        </div>
      ) : (
        <PageHeader
          title={t("sec.title")}
          subtitle={t("sec.subtitle")}
          actions={
            <Button variant="primary" loading={busy} onClick={() => void run()}>
              {t("sec.run")}
            </Button>
          }
        />
      )}
      {error ? (
        <div className="mb-4">
          <ErrorState error={error} />
        </div>
      ) : null}

      {audit.error ? (
        <ErrorState error={audit.error} onRetry={audit.reload} />
      ) : !data ? (
        <LoadingBlock rows={4} />
      ) : data.events.length === 0 ? (
        <>
          {event !== null ? (
            <p role="status" className="mb-3 text-sm text-ink-2" data-testid="trust-event-missing">
              {t("trust.event.missing")}
            </p>
          ) : null}
          <EmptyState
          title={t("sec.empty.title")}
          body={t("sec.empty.body")}
          action={
            <Button variant="secondary" loading={busy} onClick={() => void run()}>
              {t("sec.run")}
            </Button>
          }
        />
        </>
      ) : (
        <div className="space-y-6">
          {doc ? (
                      <Card id="sec-message" title={t("sec.message", { sender: doc.sender_id })} subtitle={t("sec.message.sub")} tone="bad" actions={<OutcomeBadge outcome="REJECT" />}>
              <AnnotatedText text={doc.text} annotations={annotations} activeId={active} onActivate={setActive} ariaLabel={t("sec.message", { sender: doc.sender_id })} />
            </Card>
          ) : null}

          <section aria-labelledby="sec-scoreboard">
            <h2 id="sec-scoreboard" className="mb-2 font-display text-base font-extrabold text-ink">
              {t("sec.scoreboard")}
            </h2>
            <dl className="grid grid-cols-2 gap-3 lg:grid-cols-4">
              <Stat label={t("sec.facilities")} value={data.summary.facilities_added} tone="ok" />
              <Stat label={t("sec.commitments")} value={data.summary.commitments_booked} tone="ok" />
              <Stat label={t("sec.money")} value={data.summary.money_moved_display} tone="ok" />
              <Stat
                label={t("sec.disclosed")}
                tone="ok"
                value={
                  data.summary.disclosed_fields.length ? (
                    <ul className="list-none space-y-0.5 text-sm font-semibold" data-testid="sec-disclosed-list">
                      {data.summary.disclosed_fields.map((f) => (
                        <li key={f}>{f}</li>
                      ))}
                    </ul>
                  ) : (
                    t("common.none")
                  )
                }
              />
            </dl>
          </section>

          {data.summary.reply_text ? (
            <Card id="sec-reply" title={t("sec.reply")} subtitle={t("sec.reply.sub")}>
              <blockquote className="rounded-tile border border-line bg-subtle px-3 py-2 text-sm">{data.summary.reply_text}</blockquote>
            </Card>
          ) : null}

          <Card id="sec-circuit" title={t("sec.circuit")} subtitle={t("sec.circuit.note")}>
            <div className="flex flex-wrap items-center gap-3">
              {counterparties.map((id) => (
                <Button key={id} variant="secondary" loading={circuit.busy === id} disabled={circuit.busy !== null} onClick={() => void resetBreaker(id)} data-testid={`circuit-reset-${id}`}>
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
            {event !== null && !eventFound ? (
              <p role="status" className="mb-3 text-sm text-ink-2" data-testid="trust-event-missing">
                {t("trust.event.missing")}
              </p>
            ) : null}
            <ul className="space-y-3">
              {data.events.map((e) => {
                const marked = e.id === event;
                return (
                  <li
                    key={e.id}
                    id={`event-${e.id}`}
                    tabIndex={-1}
                    aria-current={marked ? "true" : undefined}
                    className={`rounded-tile border p-3 outline-none focus-visible:ring-2 focus-visible:ring-brand-600 ${marked ? "border-brand-600 bg-brand-50 ring-2 ring-brand-600" : active === e.id ? "border-ink ring-2 ring-ink/15" : "border-bad-line"}`}
                    onMouseEnter={() => setActive(e.id)}
                    onMouseLeave={() => setActive(null)}
                    data-testid={`event-${e.id}`}
                    data-marked={marked ? "true" : undefined}
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-sm font-semibold text-ink" data-testid="event-kind">
                        {e.title_text ?? kindWord(e)}
                      </span>
                      <StatusPill tone="green" className="max-w-full !whitespace-normal">
                        {e.action_text ?? e.action_taken}
                      </StatusPill>
                      {marked ? <StatusPill tone="lavender">{t("trust.marked")}</StatusPill> : null}
                    </div>
                    <p className="mt-1 flex flex-wrap items-baseline gap-x-3 gap-y-0.5 text-meta text-ink-3">
                      <span className="break-all font-mono">{e.id}</span>
                      {e.day_when ? <span>{e.day_when}</span> : null}
                      {e.trace_id ? <span className="break-all font-mono">{e.trace_id}</span> : null}
                    </p>
                    <p className="mt-2 break-words text-sm">{e.detail}</p>
                    {e.spans.map((s) => (
                      <SpanQuote key={`${s.doc_id}:${s.start}`} text={s.text} />
                    ))}
                  </li>
                );
              })}
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
