"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useId, useState } from "react";
import { DocumentReview } from "@/components/document-review";
import { contractsOff, DocStatusBadge } from "@/components/documents";
import { Button, Callout, Card, EmptyState, ErrorState, LoadingBlock, PageHeader, TableWrap, tableCls, tdCls, thCls } from "@/components/ui";
import { getContractFixtures, getDocuments, getState, submitDocument } from "@/lib/api";
import { API_MODE } from "@/lib/config";
import { bump } from "@/lib/demo-store";
import { useI18n } from "@/lib/i18n";
import type { Counterparty, DocumentKind, DocumentSummary, SubmitDocumentRequest } from "@/lib/types";
import { useAsync } from "@/lib/use-async";

const MAX_BYTES = 5 * 1024 * 1024;
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
  const selected = useSearchParams().get("id");
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
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  if (contractsOff(list.error)) {
    return (
      <>
        <PageHeader title={t("docs.title")} subtitle={t("docs.subtitle")} />
        <Callout tone="info">{t("home.deals.off")}</Callout>
      </>
    );
  }

  return (
    <>
      <PageHeader title={t("docs.title")} subtitle={t("docs.subtitle")} />
      <div className="space-y-6">
        <Card id="docs-read" title={t("docs.read")} subtitle={t("docs.read.sub")}>
          <div className="grid gap-6 lg:grid-cols-2">
            <DemoDocuments existing={docs} nameOf={nameOf} onRead={read} onOpen={open} />
            <UploadForm parties={parties} onRead={read} />
          </div>
          {error ? (
            <div className="mt-4">
              <ErrorState error={error} />
            </div>
          ) : null}
        </Card>

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

        {selected ? <DocumentReview key={selected} id={selected} /> : <EmptyState title={t("docs.select")} />}
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
              <li key={f.id} className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-line px-3 py-2" data-testid={`fixture-${f.id}`}>
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

/** The owner's own file: what it is, who it is with (a known buyer or lender on the registry), and the file itself. */
function UploadForm({ parties, onRead }: { parties: Counterparty[]; onRead: (req: SubmitDocumentRequest) => Promise<void> }) {
  const { t, te } = useI18n();
  const kindId = useId();
  const partyId = useId();
  const fileId = useId();
  const [kind, setKind] = useState<DocumentKind>("BUYER_CONTRACT");
  const [party, setParty] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const role = kind === "BUYER_CONTRACT" ? "BUYER" : "LENDER";
  const options = parties.filter((c) => c.role === role && c.known);
  const chosen = options.some((c) => c.id === party) ? party : (options[0]?.id ?? "");

  async function upload() {
    if (!file || !chosen) return;
    if (file.size > MAX_BYTES) {
      setError(t("docs.tooBig"));
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await onRead({ kind, counterparty_id: chosen, filename: file.name, content_base64: await toBase64(file) });
    } finally {
      setBusy(false);
    }
  }

  const field = "min-h-9 w-full rounded-md border border-line-strong bg-surface px-2.5 text-sm";
  return (
    <section className="min-w-0">
      <h3 className="text-sm font-semibold text-ink">{t("docs.own")}</h3>
      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        <div>
          <label htmlFor={kindId} className="mb-1 block text-xs font-medium text-ink-2">
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
          <label htmlFor={partyId} className="mb-1 block text-xs font-medium text-ink-2">
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
        <div className="sm:col-span-2">
          <label htmlFor={fileId} className="mb-1 block text-xs font-medium text-ink-2">
            {t("docs.file")}
          </label>
          <input
            id={fileId}
            type="file"
            accept=".pdf,.docx,.txt,.md,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            className="block w-full text-sm text-ink-2 file:mr-3 file:rounded-md file:border file:border-line-strong file:bg-surface file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-ink"
          />
        </div>
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <Button variant="primary" loading={busy} disabled={!file || !chosen} onClick={() => void upload()} data-testid="doc-upload">
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
