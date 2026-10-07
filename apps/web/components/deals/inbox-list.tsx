"use client";

import Link from "next/link";
import { CheckIcon } from "@/components/icons";
import { Badge, Card, ErrorState, LoadingBlock, type Tone } from "@/components/ui";
import { useI18n } from "@/lib/i18n";
import { INBOX, type InboxMessage, type InboxSource } from "@/lib/inbox";
import type { Mode } from "@/lib/mode";
import { whenText } from "@/lib/when";

const sourceTone: Record<InboxSource, Tone> = { wechat: "ok", email: "info", portal: "neutral" };

/** One buyer's messages, newest first; the first is the thread's row. */
interface Thread {
  counterpartyId: string;
  company: string;
  messages: InboxMessage[];
}

function threads(messages: InboxMessage[]): Thread[] {
  const out: Thread[] = [];
  for (const m of messages) {
    const th = out.find((x) => x.counterpartyId === m.counterparty_id);
    if (th) th.messages.push(m);
    else out.push({ counterpartyId: m.counterparty_id, company: m.company, messages: [m] });
  }
  return out;
}

/**
 * The inbox, one thread per buyer (owner decision, wayfinder #28). Business mode shows only known contacts and says
 * in one line that a suspicious message was blocked, linking to Activity's refused section; Demo mode shows every
 * message, the unknown sender flagged, and keeps the "simulated" explanation. Clicking a message reads it (the page
 * does that); `statusFor` gives the words for a message already evaluated. The registry (`known`, the counterparty ids
 * on the books) decides who is a known contact, so Business mode shows no message until the books have loaded (a
 * loading block, or the error when the books failed to load): it never shows a sender it has not checked.
 */
export function InboxList({
  currentDocId,
  readDocIds,
  known,
  busy,
  today,
  mode,
  statusFor,
  onOpen,
  loadError,
  onRetry,
}: {
  currentDocId: string | null;
  readDocIds: (string | undefined)[];
  known: Set<string> | null;
  /** The id of the message being read, or null. */
  busy: string | null;
  today: number;
  mode: Mode;
  /** The recommendation words for a message that was evaluated, else null. */
  statusFor: (docId: string) => string | null;
  onOpen: (m: InboxMessage) => void;
  /** The books (the registry of known contacts) failed to load. */
  loadError?: Error;
  onRetry?: () => void;
}) {
  const { t, te } = useI18n();
  const business = mode === "business";
  const unknown = (m: InboxMessage) => (known ? !known.has(m.counterparty_id) : false);
  const shown = business ? INBOX.filter((m) => !unknown(m)) : INBOX;
  const blocked = business ? INBOX.length - shown.length : 0;
  const all = threads(shown);
  const current = all.find((th) => th.messages.some((m) => m.document.doc_id === currentDocId)) ?? null;
  const others = current ? all.filter((th) => th !== current) : all;

  function row(m: InboxMessage, inThread: boolean) {
    const isCurrent = m.document.doc_id === currentDocId;
    const read = readDocIds.includes(m.document.doc_id);
    const status = read ? statusFor(m.document.doc_id) : null;
    return (
      <button
        key={m.id}
        type="button"
        onClick={() => onOpen(m)}
        disabled={busy !== null}
        aria-current={isCurrent ? "true" : undefined}
        data-testid={`inbox-msg-${m.id}`}
        className={`flex min-h-11 w-full flex-wrap items-start gap-x-3 gap-y-1 px-4 py-3 text-left transition-colors hover:bg-subtle focus-visible:outline-2 focus-visible:-outline-offset-2 disabled:cursor-wait ${
          isCurrent ? "bg-brand-50 shadow-[inset_3px_0_0_var(--color-brand-600)]" : ""
        } ${inThread ? "pl-8" : ""}`}
      >
        <Badge tone={sourceTone[m.source]} className="mt-0.5 w-16 justify-center">
          {te("inbox.source", m.source)}
        </Badge>
        <span className="min-w-0 flex-1 basis-56">
          <span className="flex flex-wrap items-center gap-x-2 gap-y-0.5">
            <span className={`break-words text-sm text-ink ${read ? "font-medium" : "font-semibold"}`}>{m.company}</span>
            <span className="text-xs text-ink-3">
              {m.contact} · {te("inbox.role", m.role)}
            </span>
            {unknown(m) ? <Badge tone="bad">{t("inbox.unknownSender")}</Badge> : null}
          </span>
          {m.subject ? <span className="mt-0.5 block text-sm text-ink">{m.subject}</span> : null}
          {/* The message being read is shown whole; the others keep to one line. */}
          <span className={`mt-0.5 block text-sm text-ink-2 ${isCurrent ? "break-words" : "truncate"}`}>{m.document.text.replace(/\s+/g, " ")}</span>
        </span>
        <span className="flex shrink-0 flex-col items-end gap-1 text-xs text-ink-3">
          <span>{t("inbox.at", { when: whenText(m.document.received_day, today, t), time: m.time })}</span>
          {busy === m.id ? (
            <span className="font-medium text-brand-700">{t("inbox.reading")}</span>
          ) : isCurrent ? (
            <span className="font-medium text-brand-700">{t("inbox.showing")}</span>
          ) : status ? (
            <span className="font-medium text-ink" data-testid="inbox-msg-status">
              {status}
            </span>
          ) : read ? (
            <span className="flex items-center gap-1 text-ok-fg">
              <CheckIcon width={12} height={12} />
              {t("inbox.readDone")}
            </span>
          ) : (
            <span className="font-medium text-brand-700">{t("inbox.tapToRead")}</span>
          )}
        </span>
      </button>
    );
  }

  function thread(th: Thread) {
    const [latest, ...rest] = th.messages;
    return (
      <li key={th.counterpartyId} data-testid={`inbox-thread-${th.counterpartyId}`}>
        {row(latest, false)}
        {rest.length ? (
          <details open={th === current && latest.document.doc_id !== currentDocId}>
            <summary className="cursor-pointer px-4 pb-2 text-xs font-medium text-brand-700">
              {t("biz.deals.moreInThread", { n: rest.length, buyer: th.company })}
            </summary>
            <div className="divide-y divide-line border-t border-line">{rest.map((m) => row(m, true))}</div>
          </details>
        ) : null}
      </li>
    );
  }

  if (business && known === null) {
    return (
      <Card id="inbox-list" title={t("biz.deals.inbox")}>
        <div data-testid={loadError ? "inbox-error" : "inbox-loading"}>
          {loadError ? <ErrorState error={loadError} onRetry={onRetry} /> : <LoadingBlock rows={2} />}
        </div>
      </Card>
    );
  }
  return (
    <Card
      id="inbox-list"
      title={business ? t("biz.deals.inbox") : t("biz.deals.simulatedInbox")}
      subtitle={business ? undefined : t("inbox.list.sub")}
    >
      <ul className=
"-m-4 divide-y divide-line" aria-label={business ? t("biz.deals.inbox") : t("biz.deals.simulatedInbox")} data-testid="inbox-list">
        {current ? thread(current) : null}
        {current && others.length ? (
          <li>
            <details data-testid="inbox-others">
              <summary className="cursor-pointer px-4 py-3 text-sm font-medium text-brand-700">{t("biz.deals.otherMessages", { n: others.reduce((n, th) => n + th.messages.length, 0) })}</summary>
              <ul className="divide-y divide-line border-t border-line">{others.map(thread)}</ul>
            </details>
          </li>
        ) : (
          others.map(thread)
        )}
        {blocked ? (
          <li className="px-4 py-3 text-xs text-ink-3" data-testid="inbox-blocked">
            {t("biz.deals.blocked", { n: blocked })}{" "}
            <Link href="/activity#refused" className="font-medium text-brand-700 underline underline-offset-2">
              {t("biz.deals.blocked.link")}
            </Link>
          </li>
        ) : null}
      </ul>
    </Card>
  );
}
