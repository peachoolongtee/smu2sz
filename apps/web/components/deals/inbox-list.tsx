"use client";

import { CheckIcon } from "@/components/icons";
import { Badge, Card, type Tone } from "@/components/ui";
import { useI18n } from "@/lib/i18n";
import { INBOX, type InboxMessage, type InboxSource } from "@/lib/inbox";
import { whenText } from "@/lib/when";

const sourceTone: Record<InboxSource, Tone> = { wechat: "ok", email: "info", portal: "neutral" };

/**
 * The simulated inbox, ported from `test/ui-ux`: one row per message with where it came from, the company, the contact
 * and the time. WeChat, email and the buyer portal are not connected, so the rows are copies and the card says so.
 * Clicking a row reads it (the page does that); the registry (`known`, the counterparty ids on the books) decides who is a
 * known contact, so FastCapital shows "Not in your contacts".
 */
export function InboxList({
  currentDocId,
  readDocIds,
  known,
  busy,
  today,
  onOpen,
}: {
  currentDocId: string | null;
  readDocIds: (string | undefined)[];
  known: Set<string> | null;
  /** The id of the message being read, or null. */
  busy: string | null;
  today: number;
  onOpen: (m: InboxMessage) => void;
}) {
  const { t, te } = useI18n();
  return (
    <Card id="inbox-list" title={t("biz.deals.simulatedInbox")} subtitle={t("inbox.list.sub")}>
      <ul className="-m-4 divide-y divide-line" aria-label={t("biz.deals.simulatedInbox")} data-testid="inbox-list">
        {INBOX.map((m) => {
          const current = m.document.doc_id === currentDocId;
          const read = readDocIds.includes(m.document.doc_id);
          const unknown = known ? !known.has(m.counterparty_id) : false;
          return (
            <li key={m.id}>
              <button
                type="button"
                onClick={() => onOpen(m)}
                disabled={busy !== null}
                aria-current={current ? "true" : undefined}
                data-testid={`inbox-msg-${m.id}`}
                className={`flex min-h-11 w-full flex-wrap items-start gap-x-3 gap-y-1 px-4 py-3 text-left transition-colors hover:bg-subtle focus-visible:outline-2 focus-visible:-outline-offset-2 disabled:cursor-wait ${
                  current ? "bg-brand-50 shadow-[inset_3px_0_0_var(--color-brand-600)]" : ""
                }`}
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
                    {unknown ? <Badge tone="bad">{t("inbox.unknownSender")}</Badge> : null}
                  </span>
                  {m.subject ? <span className="mt-0.5 block text-sm text-ink">{m.subject}</span> : null}
                  <span className="mt-0.5 block truncate text-sm text-ink-2">{m.document.text.replace(/\s+/g, " ")}</span>
                </span>
                <span className="flex shrink-0 flex-col items-end gap-1 text-xs text-ink-3">
                  <span>{t("inbox.at", { when: whenText(m.document.received_day, today, t), time: m.time })}</span>
                  {busy === m.id ? (
                    <span className="font-medium text-brand-700">{t("inbox.reading")}</span>
                  ) : current ? (
                    <span className="font-medium text-brand-700">{t("inbox.showing")}</span>
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
            </li>
          );
        })}
      </ul>
    </Card>
  );
}
