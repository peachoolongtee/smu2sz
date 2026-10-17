"use client";

import Link from "next/link";
import { CheckIcon } from "@/components/icons";
import { Disclosure } from "@/components/business/kit";
import { Badge, Button, Card, Chip, ErrorState, LoadingBlock, textLinkClass } from "@/components/ui";
import { useI18n } from "@/lib/i18n";
import { INBOX, type InboxMessage } from "@/lib/inbox";
import type { Mode } from "@/lib/mode";
import type { RefusalBlock } from "@/lib/types";
import { whenText } from "@/lib/when";

/** A fold inside the inbox list: its head spans the card, aligned with the rows. */
const foldHead = "hit flex min-h-8 cursor-pointer list-none items-center gap-2 px-2 text-supporting font-medium text-brand-700 [&::-webkit-details-marker]:hidden";

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
 * in one line what the books hold as set aside (the server's count from `GET /ledger`, never the page's own: nothing set aside, no line, and
 * the fixture's example says it is one), linking to Activity's refused section; Demo mode shows every
 * message, the unknown sender flagged, and keeps the "simulated" explanation. Clicking a message reads it (the page
 * does that); `statusFor` gives the words for a message already evaluated. The registry (`known`, the counterparty ids
 * on the books) decides who is a known contact, so Business mode shows no message until the books have loaded (a
 * loading block, or the error when the books failed to load): it never shows a sender it has not checked.
 *
 * Once a deal is selected the list folds to one row, "Inbox (N)" with a "Back to inbox" control (`collapsed`); the full list shows when
 * nothing is selected or on request, and then offers to hide itself again.
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
  collapsed = false,
  onExpand,
  onCollapse,
  refusals,
  onlyCounterparty,
  messages,
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
  /** A deal is selected and the list is folded to one row. */
  collapsed?: boolean;
  onExpand?: () => void;
  /** Shown on the open list while a deal is selected: folds it again. */
  onCollapse?: () => void;
  /** The books' refusal block (`GET /ledger`); null or absent until it has loaded, and then no set-aside line is drawn. */
  refusals?: RefusalBlock | null;
  /** The selected deal's Messages tab: only this buyer's thread. */
  onlyCounterparty?: string | null;
  /** The simulated buyer messages to list: the demo inbox on the demo books, none on the owner's own or blank books. */
  messages?: InboxMessage[];
}) {
  const { t, te } = useI18n();
  const business = mode === "business";
  const unknown = (m: InboxMessage) => (known ? !known.has(m.counterparty_id) : false);
  const inbox = messages ?? INBOX;
  const shown = (business ? inbox.filter((m) => !unknown(m)) : inbox).filter((m) => !onlyCounterparty || m.counterparty_id === onlyCounterparty);
  // Business mode hides the senders the books do not know; the example line is only for a list that actually hides one.
  const hidden = business && !onlyCounterparty ? inbox.length - shown.length : 0;
  const all = threads(shown);
  const current = all.find((th) => th.messages.some((m) => m.document.doc_id === currentDocId)) ?? null;
  const others = current ? all.filter((th) => th !== current) : all;

  // The set-aside line is the books' (the ledger's refusal block): a count when something was set aside, the labelled example when nothing was yet.
  const aside: { text: string; href: string; example: boolean } | null =
    business && refusals
      ? refusals.count > 0 && refusals.set_aside_text
        ? { text: refusals.set_aside_text, href: refusals.href, example: false }
        : hidden > 0 && refusals.example?.is_fixture_example
          ? { text: refusals.example.text, href: refusals.href, example: true }
          : null
      : null;

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
        className={`flex min-h-11 w-full flex-wrap items-start gap-x-3 gap-y-1 px-2 py-3 text-left transition-colors hover:bg-subtle focus-visible:outline-2 focus-visible:-outline-offset-2 disabled:cursor-wait ${
          isCurrent ? "bg-brand-50" : ""
        } ${inThread ? "pl-6" : ""}`}
      >
        <Badge className="mt-0.5 w-16 justify-center">
          {te("inbox.source", m.source)}
        </Badge>
        <span className="min-w-0 flex-1 basis-56">
          <span className="flex flex-wrap items-center gap-x-2 gap-y-0.5">
            <span className={`break-words text-sm text-ink ${read ? "font-medium" : "font-semibold"}`}>{m.company}</span>
            <span className="text-supporting text-ink-3">
              {m.contact} · {te("inbox.role", m.role)}
            </span>
            {unknown(m) ? <Badge tone="bad">{t("inbox.unknownSender")}</Badge> : null}
          </span>
          {m.subject ? <span className="mt-0.5 block text-sm text-ink">{m.subject}</span> : null}
          {/* The message being read is shown whole; the others keep to one line. */}
          <span className={`mt-0.5 block text-sm text-ink-2 ${isCurrent ? "break-words" : "truncate"}`}>{m.document.text.replace(/\s+/g, " ")}</span>
        </span>
        <span className="flex shrink-0 flex-col items-end gap-1 text-supporting text-ink-3">
          <span>{t("inbox.at", { when: whenText(m.document.received_day, today, t), time: m.time })}</span>
          {busy === m.id ? (
            <span className="font-medium text-brand-700">{t("inbox.reading")}</span>
          ) : isCurrent ? (
            <span className="font-medium text-brand-700">{t("inbox.showing")}</span>
          ) : status ? (
            <span data-testid="inbox-msg-status">
              <Chip>{status}</Chip>
            </span>
          ) : read ? (
            <span className="flex items-center gap-1 text-ok-fg">
              <CheckIcon />
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
          <Disclosure flush summaryClass={foldHead} defaultOpen={th === current && latest.document.doc_id !== currentDocId} summary={t("biz.deals.moreInThread", { n: rest.length, buyer: th.company })}>
            <div className="divide-y divide-line border-t border-line">{rest.map((m) => row(m, true))}</div>
          </Disclosure>
        ) : null}
      </li>
    );
  }

  if (collapsed && !(business && known === null)) {
    return (
      <div className="motion-reveal flex flex-wrap items-center justify-between gap-x-3 gap-y-1 border-b border-line pb-2" data-testid="inbox-collapsed">
        <h2 className="text-meta font-extrabold uppercase tracking-[0.08em] text-ink-3">{business ? t("biz.deals.inboxCount", { n: shown.length }) : t("biz.deals.simulatedInboxCount", { n: shown.length })}</h2>
        <Button size="sm" onClick={onExpand} aria-expanded={false} aria-controls="inbox-list" data-testid="inbox-back">
          {t("biz.deals.backToInbox")}
        </Button>
      </div>
    );
  }
  if (business && known === null) {
    return (
      <Card flat id="inbox-list" title={t("biz.deals.inbox")}>
        <div data-testid={loadError ? "inbox-error" : "inbox-loading"}>
          {loadError ? <ErrorState error={loadError} onRetry={onRetry} /> : <LoadingBlock rows={2} />}
        </div>
      </Card>
    );
  }
  return (
    <Card
      flat
      id="inbox-list"
      title={business ? t("biz.deals.inbox") : t("biz.deals.simulatedInbox")}
      subtitle={business ? undefined : t("inbox.list.sub")}
      actions={
        onCollapse ? (
          <Button size="sm" variant="ghost" onClick={onCollapse} aria-expanded data-testid="inbox-hide">
            {t("biz.deals.hideInbox")}
          </Button>
        ) : undefined
      }
    >
      <ul className="motion-rise -mt-1 divide-y divide-line border-b border-line" aria-label={business ? t("biz.deals.inbox") : t("biz.deals.simulatedInbox")} data-testid="inbox-list">
        {current ? thread(current) : null}
        {current && others.length ? (
          <li>
            <Disclosure flush testId="inbox-others" summaryClass={foldHead} summary={t("biz.deals.otherMessages", { n: others.reduce((n, th) => n + th.messages.length, 0) })}>
              <ul className="divide-y divide-line border-t border-line">{others.map(thread)}</ul>
            </Disclosure>
          </li>
        ) : (
          others.map(thread)
        )}
        {aside ? (
          <li className="flex items-start gap-2 px-2 py-3 text-supporting text-ink-2" data-testid="inbox-blocked" data-example={aside.example ? "true" : "false"}>
            <span aria-hidden className="mt-1 size-1.5 shrink-0 rounded-pill bg-bad-solid" />
            <span>
              {aside.text}{" "}
              <Link href={aside.href} className={textLinkClass}>
                {t("biz.deals.blocked.link")}
              </Link>
            </span>
          </li>
        ) : null}
      </ul>
    </Card>
  );
}
