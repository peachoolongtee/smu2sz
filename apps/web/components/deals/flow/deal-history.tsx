"use client";

import type { DictKey } from "@/lib/dictionary";
import { useI18n } from "@/lib/i18n";
import type { DecisionView, OutboundAnswer, OutboundView } from "@/lib/types";

/** The dot of a step or a history line by the server's tone: green agreed, lavender the buyer's turn, ink done, hairline still to come. */
const DOT: Record<string, string> = {
  done: "border-f-ink bg-f-ink",
  ok: "border-f-green-ink bg-f-green",
  waiting: "border-f-purple bg-f-purple-soft ring-2 ring-f-purple-soft",
  neutral: "border-f-muted bg-f-line",
  todo: "border-line-strong bg-surface",
};

const ANSWER_KEY: Record<OutboundAnswer, DictKey> = { accepted: "hist.accepted", countered: "hist.countered", declined: "hist.declined", no_answer: "hist.noAnswer", closed: "hist.closed" };
const OUTCOME_KEY: Partial<Record<OutboundAnswer, DictKey>> = { accepted: "hist.inForce", countered: "hist.newRequest", declined: "hist.noDeal", no_answer: "hist.noDeal", closed: "hist.noDeal" };

interface Step {
  key: string;
  label: string;
  value: string | null;
  /** done | ok | waiting | neutral | todo */
  tone: string;
  current?: boolean;
}

/** The four steps of a deal from its record: the request, the counter sent, the buyer's answer, what came of it. A step the deal has not reached is drawn as still to come. */
export function historySteps(record: DecisionView, t: (k: DictKey) => string): Step[] {
  const history = record.history ?? [];
  const o: OutboundView | null = record.outbound ?? null;
  const asked = history.find((h) => h.kind === "received");
  const steps: Step[] = [{ key: "asked", label: t("hist.asked"), value: asked?.date ?? null, tone: asked ? "done" : "todo" }];
  steps.push(o ? { key: "sent", label: t("hist.sent"), value: o.label_text ?? o.sent.date, tone: "done" } : { key: "sent", label: t("hist.sent"), value: null, tone: "todo", current: Boolean(asked) });
  if (!o) {
    steps.push({ key: "answer", label: t("hist.answer"), value: null, tone: "todo" }, { key: "outcome", label: t("hist.outcome"), value: null, tone: "todo" });
    return steps;
  }
  if (o.answer === null) {
    // The buyer's turn: the deadline is said once, in the identity or the waiting line, not again here.
    steps.push({ key: "answer", label: t("hist.answer"), value: null, tone: "waiting", current: true }, { key: "outcome", label: t("hist.outcome"), value: null, tone: "todo" });
    return steps;
  }
  const answerDay = o.answer === "no_answer" ? o.closes : (o.answered ?? o.closes);
  steps.push({ key: "answer", label: t(ANSWER_KEY[o.answer]), value: answerDay.date, tone: o.tone === "ok" ? "ok" : o.tone === "waiting" ? "waiting" : "neutral" });
  // The outcome: the agreement in force, no deal, a new request; an accepted counter that is not in force (waiting for approval, declined at approval) says the record's own state.
  const inForce = record.state === "AGREED" || record.state === "FULFILLED" || record.state === "MISSED";
  const outcome = o.answer === "accepted" && !inForce ? record.state_text : t(OUTCOME_KEY[o.answer] ?? "hist.outcome");
  steps.push({ key: "outcome", label: t("hist.outcome"), value: outcome, tone: o.answer === "accepted" && inForce ? "ok" : o.answer === "countered" ? "waiting" : "neutral", current: true });
  return steps;
}

/** The deal header's history strip: four steps, a dot, the step's name and its value (a date, the counter sent, when the offer closes). The words are the dictionary's labels and the server's values. */
export function HistoryStrip({ record, scroll = false }: { record: DecisionView; scroll?: boolean }) {
  const { t } = useI18n();
  const steps = historySteps(record, t);
  return (
    <ol aria-label={t("hist.label")} tabIndex={scroll ? 0 : undefined} className={`m-0 mt-4 grid list-none gap-x-3 gap-y-2 p-0 ${scroll ? "auto-cols-[minmax(9rem,1fr)] grid-flow-col overflow-x-auto pb-1" : "grid-cols-2 sm:grid-cols-4"}`} data-testid="deal-history-strip">
      {steps.map((s) => (
        <li key={s.key} className="flex min-w-0 items-start gap-2" data-testid={`history-step-${s.key}`} data-tone={s.tone} aria-current={s.current ? "step" : undefined}>
          <span aria-hidden className={`mt-1 size-3 shrink-0 rounded-pill border-2 ${DOT[s.tone] ?? DOT.todo}`} />
          <span className="min-w-0 text-supporting leading-4">
            <span className={`block font-bold ${s.tone === "todo" ? "text-ink-3" : "text-ink"}`}>{s.label}</span>
            {s.value ? <span className="mt-0.5 block text-ink-2">{s.value}</span> : null}
          </span>
        </li>
      ))}
    </ol>
  );
}
