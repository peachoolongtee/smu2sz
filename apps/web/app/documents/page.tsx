"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useId, useMemo, useRef, useState, type DragEvent } from "react";
import { DocumentReview } from "@/components/document-review";
import { contractsOff, DocStatusBadge } from "@/components/documents";
import { Button, Callout, Card, EmptyState, ErrorState, inputClass, LoadingBlock, PageHeader, TableWrap, tableCls, tdCls, thCls } from "@/components/ui";
import { getContractFixtures, getDocuments, getState, submitDocument } from "@/lib/api";
import { API_MODE } from "@/lib/config";
import { bump } from "@/lib/demo-store";
import { useI18n } from "@/lib/i18n";
import type { Counterparty, DocumentKind, DocumentSummary, SubmitDocumentRequest } from "@/lib/types";
import { useAsync } from "@/lib/use-async";

const MAX_BYTES = 5 * 1024 * 1024;
/** A demo document dragged from the list onto the drop zone carries its fixture id and chosen format under this type. */
const FIXTURE_MIME = "application/x-flow-fixture";
const READABLE = /\.(pdf|docx|txt|md)$/i;

type Format = "md" | "docx" | "pdf";

/**
 * Contract ingestion (brief 03): read a demo document or upload a signed contract or lender agreement, review the agent's
 * reading beside the text, and confirm or reject it. The selected document is in the address (?id=DOC-…), so the home cards
 * link straight to it. Everything goes through lib/api.ts; the reading, the amounts and the comparison are the server's.
 */
export default function DocumentsPage() {
  return (
    <Suspense fallback={<LoadingBlock rows={3} />}>
      <Documents />
    </Suspense>
  );
}

function Documents() {
  const { t } = useI18n();
  const router = useRouter();
  const params = useSearchParams();
  const selected = params.get("id");
  // A clause link (the deal summary): `at` is the term's span in the text, `clause` its number; the review lights it up.
  const at = params.get("at");
  const clause = params.get("clause");
  const focus = useMemo(() => (at || clause ? { at, clause } : undefined), [at, clause]);
  const list = useAsync(getDocuments, []);
  const state = useAsync(getState, []);
  const [error, setError] = useState<string | null>(null);
  const docs = list.data?.documents ?? [];
  const parties = state.data?.state.counterparties ?? [];
  const nameOf = (id: string) => parties.find((c) => c.id === id)?.name ?? id;

  const open = (id: string) => router.replace(`/documents?id=${encodeURIComponent(id)}`, { scroll: false });

  async function read(req: SubmitDocumentRequest) {
    setError(null);
    try {
      const view = await submitDocument(req);
      bump();
      open(view.id);
      // The deal picture is the answer to the drop: bring it into view once the review has rendered.
      window.setTimeout(() => document.getElementById("deal-picture-title")?.scrollIntoView({ behavior: "smooth", block: "start" }), 600);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  if (contractsOff(list.error)) {
    return (
      <>
        <PageHeader section="deals" title={t("docs.title")} subtitle={t("docs.subtitle")} />
        <Callout tone="info">{t("home.deals.off")}</Callout>
      </>
    );
  }

  return (
    <>
      <PageHeader section="deals" title={t("docs.title")} subtitle={t("docs.subtitle")} />
      <div className="space-y-8">
        <Card id="docs-read" title={t("docs.read")} subtitle={t("docs.read.sub")}>
          <div className="grid gap-6 lg:grid-cols-[minmax(0,1.25fr)_minmax(0,1fr)]">
            <UploadForm parties={parties} onRead={read} />
            <DemoDocuments existing={docs} nameOf={nameOf} onRead={read} onOpen={open} />
          </div>
          {error ? (
            <div className="mt-4">
              <ErrorState error={error} />
            </div>
          ) : null}
        </Card>

        {selected ? <DocumentReview key={selected} id={selected} focus={focus} /> : <EmptyState title={t("docs.select")} />}

        <Card id="docs-list" title={t("docs.list")}>
          {list.error ? (
            <ErrorState error={list.error} onRetry={list.reload} />
          ) : !list.data ? (
            <LoadingBlock rows={2} />
          ) : docs.length === 0 ? (
            <p className="text-sm text-ink-3" data-testid="docs-empty">
              {t("docs.list.empty")}
            </p>
          ) : (
            <TableWrap label={t("docs.list")}>
              <table className={tableCls}>
                <thead>
                  <tr>
                    <th className={thCls}>{t("docs.col.document")}</th>
                    <th className={thCls}>{t("docs.col.with")}</th>
                    <th className={thCls}>{t("docs.col.read")}</th>
                    <th className={thCls}>{t("docs.col.status")}</th>
                  </tr>
                </thead>
                <tbody>
                  {docs.map((d) => (
                    <tr key={d.id} className={d.id === selected ? "bg-brand-50" : undefined} data-testid={`doc-row-${d.id}`} data-status={d.status}>
                      <td className={tdCls}>
                        <button type="button" onClick={() => open(d.id)} className="text-left font-medium text-brand-700 underline underline-offset-2">
                          {d.title}
                        </button>
                        <span className="block break-words text-xs text-ink-3">
                          {d.id} · {d.summary}
                        </span>
                      </td>
                      <td className={tdCls}>{d.counterparty_name}</td>
                      <td className={`${tdCls} whitespace-nowrap`}>{t("common.dayN", { n: d.uploaded_day })}</td>
                      <td className={tdCls}>
                        <DocStatusBadge doc={d} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </TableWrap>
          )}
        </Card>
      </div>
    </>
  );
}

/** The synthetic demo documents (GET /fixtures/contracts): read one in any of its formats, or open the reading already made. */
function DemoDocuments({
  existing,
  nameOf,
  onRead,
  onOpen,
}: {
  existing: DocumentSummary[];
  nameOf: (id: string) => string;
  onRead: (req: SubmitDocumentRequest) => Promise<void>;
  onOpen: (id: string) => void;
}) {
  const { t, te } = useI18n();
  const fixtures = useAsync(getContractFixtures, []);
  const [formats, setFormats] = useState<Record<string, Format>>({});
  const [busy, setBusy] = useState<string | null>(null);
  return (
    <section className="min-w-0">
      <h3 className="text-sm font-semibold text-ink">{t("docs.demo")}</h3>
      <p className="mt-0.5 text-xs text-ink-3">{t("docs.demo.hint")}</p>
      {fixtures.error ? (
        <div className="mt-3">
          <ErrorState error={fixtures.error} onRetry={fixtures.reload} />
        </div>
      ) : !fixtures.data ? (
        <div className="mt-3">
          <LoadingBlock rows={2} />
        </div>
      ) : (
        <ul className="mt-3 space-y-2">
          {fixtures.data.map((f) => {
            const made = existing.filter((d) => d.source === `fixture:${f.id}` && d.status !== "REJECTED");
            const last = made.length ? made[made.length - 1] : null;
            const format = formats[f.id] ?? "md";
            return (
              <li
                key={f.id}
                draggable
                onDragStart={(e) => {
                  e.dataTransfer.setData(FIXTURE_MIME, JSON.stringify({ fixture_id: f.id, format }));
                  e.dataTransfer.effectAllowed = "copy";
                }}
                className="flex cursor-grab flex-wrap items-center justify-between gap-2 rounded-tile border border-line bg-surface px-3 py-2.5 hover:border-brand-100 hover:shadow-lift active:cursor-grabbing"
                data-testid={`fixture-${f.id}`}
              >
                <div className="min-w-0">
                  <p className="text-sm font-medium text-ink">{f.title}</p>
                  <p className="text-xs text-ink-3">
                    {te("dockind", f.kind)} · {nameOf(f.counterparty_id)}
                  </p>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  {last ? (
                    <Button size="sm" onClick={() => onOpen(last.id)} data-testid={`fixture-open-${f.id}`}>
                      {t("docs.openIt")}
                    </Button>
                  ) : null}
                  <label className="sr-only" htmlFor={`fmt-${f.id}`}>
                    {t("docs.format")}
                  </label>
                  <select
                    id={`fmt-${f.id}`}
                    value={format}
                    onChange={(e) => setFormats((s) => ({ ...s, [f.id]: e.target.value as Format }))}
                    className="min-h-8 rounded-md border border-line-strong bg-surface px-2 text-xs"
                  >
                    {f.formats.map((x) => (
                      <option key={x} value={x}>
                        {te("docformat", x)}
                      </option>
                    ))}
                  </select>
                  {/* Reading a document again is a new reading for the owner to review; the one already confirmed stays. */}
                  <Button
                    size="sm"
                    variant={last ? "secondary" : "primary"}
                    loading={busy === f.id}
                    disabled={busy !== null}
                    data-testid={`fixture-read-${f.id}`}
                    onClick={async () => {
                      setBusy(f.id);
                      await onRead({ fixture_id: f.id, format });
                      setBusy(null);
                    }}
                  >
                    {last ? t("docs.readAgain") : t("docs.readIt")}
                  </Button>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}

async function toBase64(file: File): Promise<string> {
  const bytes = new Uint8Array(await file.arrayBuffer());
  let binary = "";
  for (let i = 0; i < bytes.length; i += 0x8000) binary += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  return btoa(binary);
}

/**
 * The owner's own file, as a drop zone: say what it is and who it is with, then drop the file (it is read at once) or choose it and press
 * Upload and read. A demo document dragged from the list beside it is read the same way.
 */
function UploadForm({ parties, onRead }: { parties: Counterparty[]; onRead: (req: SubmitDocumentRequest) => Promise<void> }) {
  const { t, te } = useI18n();
  const kindId = useId();
  const partyId = useId();
  const fileId = useId();
  const input = useRef<HTMLInputElement>(null);
  const [kind, setKind] = useState<DocumentKind>("BUYER_CONTRACT");
  const [party, setParty] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [over, setOver] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const role = kind === "BUYER_CONTRACT" ? "BUYER" : "LENDER";
  const options = parties.filter((c) => c.role === role && c.known);
  const chosen = options.some((c) => c.id === party) ? party : (options[0]?.id ?? "");

  async function upload(f: File | null = file) {
    if (!f || !chosen) return;
    if (f.size > MAX_BYTES) {
      setError(t("docs.tooBig"));
      return;
    }
    setBusy(f.name);
    setError(null);
    try {
      await onRead({ kind, counterparty_id: chosen, filename: f.name, content_base64: await toBase64(f) });
    } finally {
      setBusy(null);
    }
  }

  async function onDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setOver(false);
    if (busy) return;
    const fixture = e.dataTransfer.getData(FIXTURE_MIME);
    if (fixture) {
      setBusy(t("docs.demo"));
      setError(null);
      try {
        await onRead(JSON.parse(fixture) as SubmitDocumentRequest);
      } finally {
        setBusy(null);
      }
      return;
    }
    const dropped = e.dataTransfer.files?.[0];
    if (!dropped) return;
    if (!READABLE.test(dropped.name)) {
      setError(t("docs.drop.unsupported"));
      return;
    }
    setFile(dropped);
    await upload(dropped);
  }

  const field = `${inputClass} w-full`;
  return (
    <section className="min-w-0">
      <h3 className="text-sm font-bold text-ink">{t("docs.own")}</h3>
      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        <div>
          <label htmlFor={kindId} className="mb-1 block text-xs font-bold text-ink-2">
            {t("docs.kind")}
          </label>
          <select id={kindId} value={kind} onChange={(e) => setKind(e.target.value as DocumentKind)} className={field}>
            {(["BUYER_CONTRACT", "LENDER_AGREEMENT"] as const).map((k) => (
              <option key={k} value={k}>
                {te("dockind", k)}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor={partyId} className="mb-1 block text-xs font-bold text-ink-2">
            {t("docs.counterparty")}
          </label>
          <select id={partyId} value={chosen} onChange={(e) => setParty(e.target.value)} className={field}>
            {options.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </div>
      </div>
      <div
        onDragOver={(e) => {
          e.preventDefault();
          e.dataTransfer.dropEffect = "copy";
          if (!over) setOver(true);
        }}
        onDragLeave={() => setOver(false)}
        onDrop={(e) => void onDrop(e)}
        className={`mt-3 flex flex-col items-center justify-center rounded-card border-2 border-dashed px-5 py-8 text-center transition-colors ${
          over ? "border-brand-600 bg-brand-50" : "border-line-strong bg-subtle/60"
        }`}
        data-testid="doc-dropzone"
        data-over={over || undefined}
      >
        <span aria-hidden className={`grid size-12 place-items-center rounded-full ${over ? "bg-brand-600 text-white" : "bg-brand-50 text-brand-600"}`}>
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 16V4M7 9l5-5 5 5" />
            <path d="M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3" />
          </svg>
        </span>
        <p className="mt-3 text-base font-bold text-ink">{busy ? t("docs.drop.reading", { name: busy }) : over ? t("docs.drop.active") : t("docs.drop.title")}</p>
        <p className="mt-1 max-w-md text-xs text-ink-3">{t("docs.drop.sub")}</p>
        <div className="mt-4 flex flex-wrap items-center justify-center gap-2">
          <Button size="sm" onClick={() => input.current?.click()} disabled={busy !== null}>
            {t("docs.drop.choose")}
          </Button>
          {file && !busy ? <span className="max-w-56 truncate text-xs font-bold text-ink-2">{file.name}</span> : null}
        </div>
        <label htmlFor={fileId} className="mt-3 block text-[11px] text-ink-3">
          {t("docs.file")}
        </label>
        <input
          ref={input}
          id={fileId}
          type="file"
          accept=".pdf,.docx,.txt,.md,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          className="sr-only"
        />
        <p className="mt-1 text-[11px] text-ink-3">{t("docs.drop.demoHint")}</p>
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <Button variant="primary" loading={busy !== null && busy !== t("docs.demo")} disabled={!file || !chosen} onClick={() => void upload()} data-testid="doc-upload">
          {t("docs.upload")}
        </Button>
        {API_MODE === "mock" ? <span className="text-xs text-ink-3">{t("docs.mockUpload")}</span> : null}
      </div>
      {error ? (
        <div className="mt-3">
          <ErrorState error={error} />
        </div>
      ) : null}
    </section>
  );
}
