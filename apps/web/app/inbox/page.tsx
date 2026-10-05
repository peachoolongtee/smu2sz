"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useId, useState } from "react";
import { AnnotatedText } from "@/components/annotated-text";
import { DealSteps } from "@/components/deal-steps";
import { NextStep } from "@/components/next-step";
import { OfferItemCard } from "@/components/offer-parts";
import { ArrowRightIcon, CheckIcon } from "@/components/icons";
import { Badge, Button, Callout, Card, EmptyState, ErrorState, LoadingBlock, PageHeader, Segmented, type Tone } from "@/components/ui";
import { ANNOTATION_STYLE, type AnnotationKind } from "@/lib/annotation-style";
import { getState, submitOffer } from "@/lib/api";
import { evaluate as evaluateAndCache } from "@/lib/demo";
import { recordOffer, selectOffer, useDemo } from "@/lib/demo-store";
import { useI18n } from "@/lib/i18n";
import { INBOX, SOURCE_CHANNEL, inboxMessageForDoc, type InboxMessage, type InboxSource } from "@/lib/inbox";
import { annotationsFor, offerItems, type OfferItem } from "@/lib/offer-items";
import { useAsync } from "@/lib/use-async";
import { useCurrentOffer } from "@/lib/use-current";

const SOURCES: InboxSource[] = ["wechat", "email", "portal"];
const sourceTone: Record<InboxSource, Tone> = { wechat: "ok", email: "info", portal: "neutral" };

interface Pasted {
  text: string;
  source: InboxSource;
  sender: string;
}

export default function InboxPage() {
  const { t, te } = useI18n();
  const router = useRouter();
  const current = useCurrentOffer();
  const demo = useDemo();
  const [active, setActive] = useState<string | null>(null);
  // "evaluate", "paste", or the id of the inbox message being read.
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function run(key: string, work: () => Promise<void>) {
    setBusy(key);
    setError(null);
    try {
      await work();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }

  /** Opening a message reads it. One already read is just shown again, so clicking around costs nothing. */
  function open(m: InboxMessage) {
    const known = Object.values(demo.offers).find((o) => o.documents[0]?.doc_id === m.document.doc_id);
    if (known) return selectOffer(known.offer.offer_id);
    void run(m.id, async () =>
      recordOffer(
        await submitOffer(m.fixtureId ? { fixture_id: m.fixtureId } : { counterparty_id: m.counterparty_id, documents: [m.document] }),
        m.fixtureId,
      ),
    );
  }

  function readPasted(p: Pasted) {
    void run("paste", async () =>
      recordOffer(
        await submitOffer({
          counterparty_id: p.sender,
          documents: [{ doc_id: "PASTED-msg", channel: SOURCE_CHANNEL[p.source], sender_id: p.sender, received_day: 0, text: p.text }],
        }),
      ),
    );
  }

  function evaluate(offerId: string) {
    void run("evaluate", async () => {
      await evaluateAndCache(offerId);
      router.push("/verdict");
    });
  }

  const offer = current.offer;
  const items: OfferItem[] = offer ? offerItems(offer.offer) : [];
  const obligations = items.filter((i) => i.group === "obligation");
  const flags = items.filter((i) => i.group !== "obligation");
  const legendKinds = [...new Set(items.map((i) => i.kind))] as AnnotationKind[];

  return (
    <>
      <PageHeader title={t("inbox.title")} subtitle={t("inbox.subtitle")} />
      <DealSteps />

      <InboxList
        currentDocId={offer?.documents[0]?.doc_id ?? null}
        readDocIds={Object.values(demo.offers).map((o) => o.documents[0]?.doc_id)}
        busy={busy}
        onOpen={open}
      />
      <PasteMessage busy={busy === "paste"} onRead={readPasted} />
      {error ? (
        <div className="mb-6">
          <ErrorState error={error} />
        </div>
      ) : null}

      {current.error ? (
        <ErrorState error={current.error} onRetry={current.reload} />
      ) : current.loading ? (
        <LoadingBlock rows={3} />
      ) : !offer ? (
        <EmptyState title={t("inbox.empty.title")} body={t("inbox.empty.body")} />
      ) : (
        <>
        <NextStep
          label={t("next.label")}
          action={
            <>
              <Button variant="primary" loading={busy === "evaluate"} onClick={() => evaluate(offer.offer.offer_id)}>
                {t("inbox.evaluate")}
                <ArrowRightIcon />
              </Button>
              <Link href="/trajectory" className="text-sm font-medium text-brand-700 underline underline-offset-2">
                {t("inbox.seeTrajectory")}
              </Link>
            </>
          }
        >
          {t("next.inbox")}
        </NextStep>
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1.35fr)_minmax(0,1fr)]">
          <div className="min-w-0 space-y-4">
            {offer.documents.map((doc) => {
              const meta = inboxMessageForDoc(doc.doc_id);
              return (
                <Card
                  key={doc.doc_id}
                  id={`doc-${doc.doc_id}`}
                  title={meta ? t("inbox.from", { company: meta.company, contact: meta.contact }) : t("inbox.received", { sender: doc.sender_id })}
                  subtitle={[
                    meta ? te("inbox.source", meta.source) : te("channel", doc.channel),
                    meta ? t("inbox.at", { day: doc.received_day, time: meta.time }) : t("common.dayN", { n: doc.received_day }),
                    doc.filename,
                  ]
                    .filter(Boolean)
                    .join(" · ")}
                  actions={<Badge tone={offer.offer.status === "COMPILED" ? "ok" : "warn"}>{te("compilestatus", offer.offer.status)}</Badge>}
                >
                  {meta?.subject ? <p className="mb-2 text-sm font-semibold">{meta.subject}</p> : null}
                  <AnnotatedText
                    ariaLabel={t("inbox.annotated")}
                    text={doc.text}
                    annotations={annotationsFor(items, doc.doc_id, (i) =>
                      i.group === "obligation" ? te("obligation", i.kind) : te("flag", i.kind),
                    )}
                    activeId={active}
                    onActivate={setActive}
                  />
                  <ul className="mt-3 flex flex-wrap gap-1.5" aria-label={t("inbox.legend")}>
                    {legendKinds.map((k) => (
                      <li
                        key={k}
                        className={`rounded-md border px-1.5 py-0.5 text-xs font-medium ${ANNOTATION_STYLE[k].chip}`}
                      >
                        {items.find((i) => i.kind === k)?.group === "obligation" ? te("obligation", k) : te("flag", k)}
                      </li>
                    ))}
                  </ul>
                  <p className="mt-3 text-xs text-ink-3">
                    {t("inbox.compiler", { compiler: offer.offer.compiler, version: offer.offer.prompt_version })}
                  </p>
                </Card>
              );
            })}
          </div>

          <div className="min-w-0 space-y-4">
            <Card id="obligations" title={t("inbox.obligations", { n: obligations.length })} subtitle={t("inbox.obligations.sub")}>
              {obligations.length ? (
                <ul className="space-y-3">
                  {obligations.map((i) => (
                    <OfferItemCard key={i.id} item={i} active={active === i.id} onActivate={setActive} />
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-ink-2">{t("inbox.noObligations")}</p>
              )}
              {offer.offer.abstentions.length ? (
                <div className="mt-3">
                  <Callout tone="warn" title={t("inbox.abstained")}>
                    <ul className="list-disc pl-5">
                      {offer.offer.abstentions.map((a) => (
                        <li key={a.field}>
                          {a.field}: {a.reason}
                        </li>
                      ))}
                    </ul>
                  </Callout>
                </div>
              ) : null}
            </Card>
            <Card id="flags" title={t("inbox.flags", { n: flags.length })} subtitle={t("inbox.flags.sub")} tone={flags.length ? "bad" : undefined}>
              {flags.length ? (
                <ul className="space-y-3">
                  {flags.map((i) => (
                    <OfferItemCard key={i.id} item={i} active={active === i.id} onActivate={setActive} />
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-ink-2">{t("inbox.noFlags")}</p>
              )}
            </Card>
          </div>
        </div>
        </>
      )}
    </>
  );
}

/** The simulated inbox: one row per message, with where it came from and who sent it. Clicking a row reads it. */
function InboxList({
  currentDocId,
  readDocIds,
  busy,
  onOpen,
}: {
  currentDocId: string | null;
  readDocIds: (string | undefined)[];
  busy: string | null;
  onOpen: (m: InboxMessage) => void;
}) {
  const { t, te } = useI18n();
  // The registry decides who is a known contact; FastCapital is not in it.
  const state = useAsync(getState, []);
  const known = state.data ? new Set(state.data.state.counterparties.map((c) => c.id)) : null;
  return (
    <Card id="inbox-list" title={t("inbox.list")} subtitle={t("inbox.list.sub")} actions={<Badge tone="info">{t("inbox.simulated")}</Badge>} className="mb-3">
      <ul className="-m-4 divide-y divide-line" aria-label={t("inbox.list")}>
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
                className={`flex w-full flex-wrap items-start gap-x-3 gap-y-1 px-4 py-3 text-left transition-colors hover:bg-subtle disabled:cursor-wait ${
                  current ? "bg-brand-50 shadow-[inset_3px_0_0_var(--color-brand-600)]" : ""
                }`}
              >
                <Badge tone={sourceTone[m.source]} className="mt-0.5 w-16 justify-center">
                  {te("inbox.source", m.source)}
                </Badge>
                <span className="min-w-0 flex-1 basis-56">
                  <span className="flex flex-wrap items-center gap-x-2 gap-y-0.5">
                    <span className={`text-sm text-ink ${read ? "font-medium" : "font-semibold"}`}>{m.company}</span>
                    <span className="text-xs text-ink-3">
                      {m.contact} · {te("inbox.role", m.role)}
                    </span>
                    {unknown ? <Badge tone="bad">{t("inbox.unknownSender")}</Badge> : null}
                  </span>
                  {m.subject ? <span className="mt-0.5 block text-sm text-ink">{m.subject}</span> : null}
                  <span className="mt-0.5 block truncate text-sm text-ink-2">{m.document.text.replace(/\s+/g, " ")}</span>
                </span>
                <span className="flex shrink-0 flex-col items-end gap-1 text-xs text-ink-3">
                  <span>{t("inbox.at", { day: m.document.received_day, time: m.time })}</span>
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

/** A message that did not come through the inbox: pasted by the owner, saying where it came from and who sent it. */
function PasteMessage({ busy, onRead }: { busy: boolean; onRead: (p: Pasted) => void }) {
  const { t, te } = useI18n();
  const [text, setText] = useState("");
  const [source, setSource] = useState<InboxSource>("wechat");
  const [sender, setSender] = useState("BUYER-1");
  const textId = useId();
  const senderId = useId();
  return (
    <details className="mb-6 rounded-(--radius-card) border border-line bg-surface px-4 py-3" data-testid="inbox-paste">
      <summary className="cursor-pointer text-sm font-medium text-brand-700">{t("inbox.paste")}</summary>
      <div className="mt-3 space-y-3">
        <div className="flex flex-wrap items-end gap-4">
          <Segmented
            label={t("inbox.paste.source")}
            name="paste-source"
            value={source}
            onChange={setSource}
            options={SOURCES.map((s) => ({ value: s, label: te("inbox.source", s) }))}
          />
          <div>
            <label htmlFor={senderId} className="mb-1 block text-xs font-medium text-ink-2">
              {t("inbox.paste.sender")}
            </label>
            <select
              id={senderId}
              value={sender}
              onChange={(e) => setSender(e.target.value)}
              className="min-h-9 rounded-md border border-line-strong bg-surface px-2 text-sm"
            >
              <option value="BUYER-1">Foshan Home Retail Co.</option>
              <option value="BUYER-2">Dongguan Office Supplies Ltd.</option>
            </select>
          </div>
        </div>
        <div>
          <label htmlFor={textId} className="mb-1 block text-xs font-medium text-ink-2">
            {t("inbox.message")}
          </label>
          <textarea
            id={textId}
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={3}
            className="w-full rounded-md border border-line-strong bg-surface px-3 py-2 text-sm leading-relaxed"
          />
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="primary" loading={busy} disabled={!text.trim()} onClick={() => onRead({ text, source, sender })}>
            {t("inbox.compile")}
          </Button>
          <span className="text-xs text-ink-3">{t("inbox.compile.hint")}</span>
        </div>
      </div>
    </details>
  );
}
