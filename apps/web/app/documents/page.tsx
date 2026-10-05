"use client";

import { useRouter } from "next/navigation";
import { useId, useState } from "react";
import { OutcomeBadge } from "@/components/badges";
import { CheckIcon, XIcon } from "@/components/icons";
import { Badge, Button, Card, EmptyState, ErrorState, PageHeader, Segmented, type Tone } from "@/components/ui";
import { getClock, getState, submitOffer } from "@/lib/api";
import { evaluate } from "@/lib/demo";
import { recordDocument, recordOffer, selectOffer, useDemo, type OwnerDocKind, type OwnerDocument } from "@/lib/demo-store";
import { useI18n } from "@/lib/i18n";
import { inboxMessageForDoc } from "@/lib/inbox";
import { SAMPLES } from "@/lib/samples";
import type { OfferView, VerdictView } from "@/lib/types";
import { useAsync } from "@/lib/use-async";

const KINDS: OwnerDocKind[] = ["offer", "term_sheet", "invoice", "contract", "other"];

/**
 * Your documents: one place for the owner to hand the agent their paperwork, and a plain read-out of what the agent
 * made of each piece. Buyer offers and messages are read and checked against the limits (the same calls as Buyer
 * offers); other kinds are filed and say so, because the agent does not read them yet.
 */
export default function DocumentsPage() {
  const { t } = useI18n();
  const demo = useDemo();
  const docs = demo.documents ?? [];
  // Messages read elsewhere (the inbox, the demo stepper) belong in the same read-out.
  const linked = new Set(docs.map((d) => d.offerId));
  const otherOffers = Object.values(demo.offers).filter((o) => !linked.has(o.offer.offer_id));

  return (
    <>
      <PageHeader title={t("docs.title")} subtitle={t("docs.subtitle")} />
      <AddDocument />
      <section aria-labelledby="docs-results-title" className="mt-6">
        <h2 id="docs-results-title" className="mb-1 text-sm font-semibold">{t("docs.results")}</h2>
        <p className="mb-3 text-xs text-ink-3">{t("docs.results.sub")}</p>
        {docs.length || otherOffers.length ? (
          <ul className="space-y-4" data-testid="docs-results">
            {docs.map((d) => (
              <DocResult key={d.id} doc={d} />
            ))}
            {otherOffers.map((o) => (
              <OfferResult key={o.offer.offer_id} offer={o} />
            ))}
          </ul>
        ) : (
          <EmptyState title={t("docs.empty.title")} body={t("docs.empty.body")} />
        )}
      </section>
    </>
  );
}

function AddDocument() {
  const { t, te } = useI18n();
  const state = useAsync(getState, []);
  const clock = useAsync(getClock, []);
  const [kind, setKind] = useState<OwnerDocKind>("offer");
  const [from, setFrom] = useState("BUYER-1");
  const [name, setName] = useState("");
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const ids = { file: useId(), from: useId(), name: useId(), text: useId() };
  const parties = state.data?.state.counterparties.filter((c) => c.role !== "OWNER") ?? [];

  async function onFile(file: File | undefined) {
    if (!file) return;
    setError(null);
    // Text only: a PDF or Word file would need a parser this demo does not have, so it asks for the text instead.
    if (!/^text\//.test(file.type) && !/\.(txt|md|eml|csv)$/i.test(file.name)) {
      setError(t("docs.add.notText", { name: file.name }));
      return;
    }
    setName(file.name);
    setText(await file.text());
  }

  async function add() {
    setBusy(true);
    setError(null);
    const day = clock.data?.day ?? 0;
    const docName = name.trim() || t("docs.add.untitled");
    try {
      let offerId: string | null = null;
      if (kind === "offer") {
        const view = await submitOffer({
          counterparty_id: from,
          documents: [{ doc_id: `DOC-${Date.now()}`, channel: "attachment", sender_id: from, received_day: day, text, filename: docName }],
        });
        recordOffer(view);
        offerId = view.offer.offer_id;
        await evaluate(offerId);
      }
      recordDocument({ id: `doc-${Date.now()}`, name: docName, kind, from, text, day, offerId });
      setName("");
      setText("");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  const field = "min-h-9 w-full rounded-md border border-line-strong bg-surface px-2.5 text-sm";
  const lbl = "mb-1 block text-xs font-medium text-ink-2";
  return (
    <Card id="docs-add" title={t("docs.add")} subtitle={t("docs.add.sub")}>
      <div className="space-y-3">
        <Segmented
          label={t("docs.add.kind")}
          name="doc-kind"
          value={kind}
          onChange={setKind}
          options={KINDS.map((k) => ({ value: k, label: te("docs.kind", k) }))}
        />
        <p className="text-xs text-ink-3" data-testid="docs-kind-note">
          {kind === "offer" ? t("docs.add.readsOffer") : t("docs.add.filesOnly")}
        </p>
        <div className="grid gap-3 sm:grid-cols-3">
          <div>
            <label htmlFor={ids.file} className={lbl}>{t("docs.add.file")}</label>
            <input
              id={ids.file}
              type="file"
              accept=".txt,.md,.eml,.csv,text/*"
              onChange={(e) => void onFile(e.target.files?.[0])}
              className="block w-full text-sm file:mr-2 file:rounded-md file:border file:border-line-strong file:bg-surface file:px-2.5 file:py-1.5 file:text-sm"
            />
          </div>
          <div>
            <label htmlFor={ids.name} className={lbl}>{t("docs.add.name")}</label>
            <input id={ids.name} className={field} value={name} onChange={(e) => setName(e.target.value)} data-testid="docs-name" />
          </div>
          <div>
            <label htmlFor={ids.from} className={lbl}>{t("docs.add.from")}</label>
            <select id={ids.from} className={field} value={from} onChange={(e) => setFrom(e.target.value)}>
              {parties.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
              {kind === "offer" ? null : <option value="OTHER">{t("docs.add.someoneElse")}</option>}
            </select>
          </div>
        </div>
        <div>
          <label htmlFor={ids.text} className={lbl}>{t("docs.add.text")}</label>
          <textarea
            id={ids.text}
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={4}
            className="w-full rounded-md border border-line-strong bg-surface px-3 py-2 text-sm leading-relaxed"
            data-testid="docs-text"
          />
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="primary" loading={busy} disabled={!text.trim() || (kind === "offer" && from === "OTHER")} onClick={() => void add()} data-testid="docs-submit">
            {kind === "offer" ? t("docs.add.check") : t("docs.add.fileIt")}
          </Button>
          {kind === "offer" ? (
            <button
              type="button"
              className="text-xs font-medium text-brand-700 underline underline-offset-2"
              onClick={() => {
                setFrom(SAMPLES.EX01.counterparty_id);
                setName(t("docs.add.demoName"));
                setText(SAMPLES.EX01.documents[0].text);
              }}
              data-testid="docs-demo"
            >
              {t("docs.add.demo")}
            </button>
          ) : null}
        </div>
        {error ? <ErrorState error={error} /> : null}
      </div>
    </Card>
  );
}

/** A document the owner added: an offer shows the agent's feedback; any other kind says it is filed and not read. */
function DocResult({ doc }: { doc: OwnerDocument }) {
  const { t, te } = useI18n();
  const demo = useDemo();
  const offer = doc.offerId ? demo.offers[doc.offerId] : undefined;
  if (offer) return <OfferResult offer={offer} title={doc.name} kindLabel={te("docs.kind", doc.kind)} day={doc.day} />;
  return (
    <li>
      <Card
        title={doc.name}
        subtitle={`${te("docs.kind", doc.kind)} · ${t("common.dayN", { n: doc.day })}`}
        actions={<Badge tone="neutral">{t("docs.status.filed")}</Badge>}
      >
        <p className="text-sm text-ink-2">{t("docs.filed.body")}</p>
        <details className="mt-2">
          <summary className="cursor-pointer text-xs font-medium text-brand-700">{t("docs.showText")}</summary>
          <pre className="mt-2 max-h-48 overflow-auto whitespace-pre-wrap rounded-md border border-line bg-subtle p-2 text-xs">{doc.text}</pre>
        </details>
      </Card>
    </li>
  );
}

/** The agent's feedback on an offer, in plain words: the answer, the key points and the way to the full decision. */
function OfferResult({ offer, title, kindLabel, day }: { offer: OfferView; title?: string; kindLabel?: string; day?: number }) {
  const { t, te } = useI18n();
  const router = useRouter();
  const demo = useDemo();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const id = offer.offer.offer_id;
  const verdict: VerdictView | undefined = demo.verdicts[id];
  const doc = offer.documents[0];
  const meta = doc ? inboxMessageForDoc(doc.doc_id) : undefined;
  const heading = title ?? (meta ? `${meta.company} · ${te("inbox.source", meta.source)}` : t("inbox.received", { sender: doc?.sender_id ?? "" }));
  const sub = [kindLabel ?? t("docs.fromInbox"), t("common.dayN", { n: day ?? doc?.received_day ?? 0 })].join(" · ");
  const status: [Tone, string] = verdict ? ["ok", t("docs.status.checked")] : ["warn", t("docs.status.read")];

  async function check() {
    setBusy(true);
    setError(null);
    try {
      await evaluate(id);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <li data-testid={`docs-offer-${id}`}>
      <Card title={heading} subtitle={sub} actions={<Badge tone={status[0]}>{status[1]}</Badge>}>
        {doc ? <p className="mb-3 line-clamp-2 text-sm italic text-ink-2">&ldquo;{doc.text}&rdquo;</p> : null}
        {verdict ? (
          <div className="space-y-3">
            <div className="flex flex-wrap items-center gap-3">
              <OutcomeBadge outcome={verdict.outcome} />
              <p className="min-w-0 flex-1 basis-64 text-sm font-semibold text-ink">{te("verdict.plain", verdict.outcome)}</p>
            </div>
            <div>
              <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-ink-3">{t("docs.feedback")}</p>
              <ul className="space-y-1 text-sm" data-testid="docs-feedback">
                {verdict.violations.length ? (
                  verdict.violations.map((v) => (
                    <li key={`${v.code}-${v.day ?? v.month ?? ""}`} className="flex gap-1.5">
                      <span className="mt-0.5 text-bad-fg">
                        <XIcon width={14} height={14} />
                      </span>
                      {te("violation", v.code)}
                    </li>
                  ))
                ) : (
                  <li className="flex gap-1.5">
                    <span className="mt-0.5 text-ok-fg">
                      <CheckIcon width={14} height={14} />
                    </span>
                    {t("verdict.noViolations")}
                  </li>
                )}
                {verdict.counters.length ? (
                  <li className="text-ink-2">
                    {t("docs.counters", { list: verdict.counters.map((c) => `${c.label} (${t("glance.costsUs", { cost: c.supplier_cost_display })})`).join("; ") })}
                  </li>
                ) : null}
                {verdict.concession_values.length ? (
                  <li className="text-ink-2">{t("glance.givesBuyer", { total: verdict.forward_concession_total_display })}</li>
                ) : null}
              </ul>
            </div>
            <Button
              variant="secondary"
              onClick={() => {
                selectOffer(id);
                router.push("/verdict");
              }}
              data-testid={`docs-open-${id}`}
            >
              {t("docs.open")}
            </Button>
          </div>
        ) : (
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-sm text-ink-2">{t("docs.notChecked")}</p>
            <Button variant="primary" loading={busy} onClick={() => void check()}>
              {t("inbox.evaluate")}
            </Button>
          </div>
        )}
        {error ? (
          <div className="mt-2">
            <ErrorState error={error} />
          </div>
        ) : null}
      </Card>
    </li>
  );
}
