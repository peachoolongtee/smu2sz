"use client";

import "@/app/flow-look.css";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useId, useMemo, useRef, useState, type DragEvent, type KeyboardEvent } from "react";
import { CheckIcon } from "@/components/icons";
import { DocumentReview } from "@/components/document-review";
import { contractsOff, DocStatusBadge, whenWords } from "@/components/documents";
import { Button, Callout, Card, ErrorState, inputClass, LoadingBlock, PageHeader, TableWrap, tableCls, tdCls, thCls } from "@/components/ui";
import { getDocuments, getState, submitDocument } from "@/lib/api";
import { bump } from "@/lib/demo-store";
import { useI18n } from "@/lib/i18n";
import type { Counterparty, DocumentKind, SubmitDocumentRequest } from "@/lib/types";
import { useAsync } from "@/lib/use-async";

const MAX_BYTES = 5 * 1024 * 1024;
const READABLE = /\.(pdf|docx|txt|md)$/i;

/**
 * Contract ingestion (brief 03): upload a signed contract or lender agreement, review the agent's
 * reading beside the text, and confirm or reject it. The selected document is in the address (?id=DOC-…), so the home cards
 * link straight to it. Everything goes through lib/api.ts; the reading, the amounts and the comparison are the server's.
 */
export default function DocumentsPage() {
  return (
    <div className="flow-f min-w-0">
      <Suspense fallback={<LoadingBlock rows={3} />}>
        <Documents />
      </Suspense>
    </div>
  );
}

function Documents() {
  const { t, lang } = useI18n();
  const router = useRouter();
  const params = useSearchParams();
  const selected = params.get("id");
  // A clause link (the deal summary): `at` is the term's span in the text, `clause` its number; the review lights it up.
  const at = params.get("at");
  const clause = params.get("clause");
  const focus = useMemo(() => (at || clause ? { at, clause } : undefined), [at, clause]);
  // The list is read in the owner's language and again when it changes: the server writes the sentences and the "when" words.
  const list = useAsync(() => getDocuments(lang), [lang]);
  const state = useAsync(getState, []);
  const [error, setError] = useState<Error | null>(null);
  const today = list.data?.day ?? null;
  const docs = list.data?.documents ?? [];
  const parties = state.data?.state.counterparties ?? [];

  const open = (id: string) => router.replace(`/documents?id=${encodeURIComponent(id)}`, { scroll: false });

  async function read(req: SubmitDocumentRequest) {
    setError(null);
    try {
      const view = await submitDocument(req);
      bump();
      open(view.id);
      // The answer to the drop: bring the review into view once it has rendered, its header, the decision and the deal picture in that order.
      window.setTimeout(() => document.getElementById("doc-review")?.scrollIntoView({ behavior: "smooth", block: "start" }), 600);
    } catch (e) {
      setError(e instanceof Error ? e : new Error(String(e)));
    }
  }

  if (contractsOff(list.error)) {
    return (
      <>
        <PageHeader section="docs" title={t("docs.title")} subtitle={t("docs.subtitle")} />
        <Callout tone="info">{t("home.deals.off")}</Callout>
      </>
    );
  }

  return (
    <>
      <PageHeader section="docs" title={t("docs.title")} subtitle={t("docs.subtitle")} />
      {/* A flex column, not a stack: the review's parts are ordered (the decision is a bar at the foot of a phone, under the header on a desktop). */}
      <div className="flex flex-col gap-8">
        <Card id="docs-read" className="order-1">
          <UploadForm parties={parties} onRead={read} />
          {error ? (
            <div className="mt-4">
              <ErrorState error={error} />
            </div>
          ) : null}
        </Card>

        {selected ? (
          <DocumentReview key={selected} id={selected} today={today} focus={focus} />
        ) : null}

        <Card flat id="docs-list" className="order-6" title={t("docs.list")}>
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
                    <tr key={d.id} onClick={() => open(d.id)} className={`cursor-pointer outline-2 -outline-offset-2 outline-transparent transition-[outline-color] hover:outline hover:outline-brand-600 ${d.id === selected ? "bg-brand-50" : ""}`} data-testid={`doc-row-${d.id}`} data-status={d.status}>
                      <td className={tdCls}>
                        <button type="button" onClick={() => open(d.id)} className="text-left font-medium text-brand-700 underline underline-offset-2">
                          {d.title}
                        </button>
                        <span className="block break-words text-meta text-ink-3">{d.summary}</span>
                      </td>
                      <td className={tdCls}>{d.counterparty_name}</td>
                      <td className={`${tdCls} whitespace-nowrap`}>{whenWords(d.uploaded_when, d.uploaded_day, today, t)}</td>
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

async function toBase64(file: File): Promise<string> {
  const bytes = new Uint8Array(await file.arrayBuffer());
  let binary = "";
  for (let i = 0; i < bytes.length; i += 0x8000) binary += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  return btoa(binary);
}

/** A field draws its own focus (a darker border and a soft halo) instead of the page's blue ring. */
const FOCUS = "focus-own focus:border-ink focus:shadow-[0_0_0_3px_color-mix(in_srgb,var(--color-ink)_10%,transparent)]";

const KINDS = ["BUYER_CONTRACT", "LENDER_AGREEMENT"] as const;

/**
 * "What it is": a listbox in the page's look instead of the browser's menu. Each choice has its name and one line on what it means. Arrow keys move,
 * Enter or Space picks, Escape closes, a click outside closes.
 */
function KindSelect({ id, value, onChange, className }: { id: string; value: DocumentKind; onChange: (k: DocumentKind) => void; className: string }) {
  const { t, te } = useI18n();
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const root = useRef<HTMLDivElement>(null);
  const listId = `${id}-list`;
  const current = KINDS.indexOf(value as (typeof KINDS)[number]);

  useEffect(() => {
    if (!open) return;
    const away = (e: PointerEvent) => {
      if (!root.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("pointerdown", away);
    return () => document.removeEventListener("pointerdown", away);
  }, [open]);

  const show = () => {
    setActive(Math.max(current, 0));
    setOpen(true);
  };
  const pick = (k: DocumentKind) => {
    onChange(k);
    setOpen(false);
  };
  function onKeyDown(e: KeyboardEvent<HTMLButtonElement>) {
    if (e.key === "Escape" && open) {
      e.preventDefault();
      setOpen(false);
    } else if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      if (!open) return show();
      setActive((i) => (i + (e.key === "ArrowDown" ? 1 : KINDS.length - 1)) % KINDS.length);
    } else if ((e.key === "Enter" || e.key === " ") && open) {
      e.preventDefault();
      pick(KINDS[active]);
    }
  }

  return (
    <div ref={root} className="relative">
      <button
        id={id}
        type="button"
        role="combobox"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={listId}
        aria-activedescendant={open ? `${id}-opt-${active}` : undefined}
        onClick={() => (open ? setOpen(false) : show())}
        onKeyDown={onKeyDown}
        className={`${className} flex items-center justify-between gap-2 text-left ${open ? "border-ink" : ""}`}
        data-testid="doc-kind"
      >
        <span className="truncate">{te("dockind", value)}</span>
        <svg aria-hidden width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={`shrink-0 text-ink-3 transition-transform duration-150 ${open ? "rotate-180" : ""}`}>
          <path d="M6 9l6 6 6-6" />
        </svg>
      </button>
      {open ? (
        <ul id={listId} role="listbox" aria-label={t("docs.kind")} className="absolute left-0 right-0 top-full z-20 mt-1.5 overflow-hidden rounded-card border border-line bg-surface p-1.5 shadow-pop" data-testid="doc-kind-list">
          {KINDS.map((k, i) => {
            const selected = k === value;
            return (
              <li
                key={k}
                id={`${id}-opt-${i}`}
                role="option"
                aria-selected={selected}
                onPointerEnter={() => setActive(i)}
                onClick={() => pick(k)}
                className={`flex cursor-pointer items-start gap-3 rounded-tile px-3 py-2.5 ${i === active ? "bg-subtle" : ""}`}
              >
                <span className="min-w-0 flex-1">
                  <span className="block text-sm font-bold text-ink">{te("dockind", k)}</span>
                  <span className="mt-0.5 block text-meta text-ink-3">{te("dockind.desc", k)}</span>
                </span>
                {selected ? <CheckIcon aria-hidden className="mt-0.5 shrink-0 text-ink" /> : null}
              </li>
            );
          })}
        </ul>
      ) : null}
    </div>
  );
}

/**
 * The owner's own file, as a drop zone: say what it is and who it is with, then drop the file (it is read at once) or choose it and press
 * Upload and read.
 */
function UploadForm({ parties, onRead }: { parties: Counterparty[]; onRead: (req: SubmitDocumentRequest) => Promise<void> }) {
  const { t } = useI18n();
  const kindId = useId();
  const partyId = useId();
  const fileId = useId();
  const input = useRef<HTMLInputElement>(null);
  const [kind, setKind] = useState<DocumentKind>("BUYER_CONTRACT");
  const [typed, setTyped] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [over, setOver] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const role = kind === "BUYER_CONTRACT" ? "BUYER" : "LENDER";
  const options = parties.filter((c) => c.role === role && c.known);
  // The company is typed by name: an exact name, else the one company whose name contains what was typed. Nothing that is not on the books can be chosen.
  const needle = typed.trim().toLowerCase();
  const matches = needle ? options.filter((c) => c.name.toLowerCase() === needle) : [];
  const near = needle && matches.length === 0 ? options.filter((c) => c.name.toLowerCase().includes(needle)) : [];
  const found = matches[0] ?? (near.length === 1 ? near[0] : undefined);
  const chosen = found?.id ?? "";
  const listId = useId();

  // The server answers once, when the reading is done, so the bar is the work in hand: it climbs toward the end while the file is sent and read, and fills when the answer arrives.
  const [progress, setProgress] = useState(0);
  useEffect(() => {
    if (busy === null) return;
    const id = window.setInterval(() => setProgress((p) => p + (92 - p) * 0.08), 120);
    return () => window.clearInterval(id);
  }, [busy]);

  async function upload(f: File | null) {
    if (!f) return;
    if (!chosen) {
      setError(t("docs.counterparty.pick"));
      return;
    }
    if (f.size > MAX_BYTES) {
      setError(t("docs.tooBig"));
      return;
    }
    setProgress(6);
    setBusy(f.name);
    setError(null);
    try {
      await onRead({ kind, counterparty_id: chosen, filename: f.name, content_base64: await toBase64(f) });
      setProgress(100);
    } finally {
      setBusy(null);
    }
  }

  async function onDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setOver(false);
    if (busy) return;
    const dropped = e.dataTransfer.files?.[0];
    if (!dropped) return;
    if (!READABLE.test(dropped.name)) {
      setError(t("docs.drop.unsupported"));
      return;
    }
    await upload(dropped);
  }

  const field = `${inputClass} ${FOCUS} w-full touch:min-h-11`;
  return (
    <section className="min-w-0">
      <h3 className="text-base font-bold text-ink">{t("docs.own")}</h3>
      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        <div>
          <label htmlFor={kindId} className="mb-1 block text-meta font-bold text-ink-2">
            {t("docs.kind")}
          </label>
          <KindSelect id={kindId} value={kind} onChange={setKind} className={field} />
        </div>
        <div>
          <label htmlFor={partyId} className="mb-1 block text-meta font-bold text-ink-2">
            {t("docs.counterparty")}
          </label>
          <input
            id={partyId}
            list={listId}
            value={typed}
            onChange={(e) => setTyped(e.target.value)}
            autoComplete="off"
            placeholder={t("docs.counterparty.placeholder")}
            aria-invalid={needle && !found ? true : undefined}
            aria-describedby={needle && !found ? `${partyId}-hint` : undefined}
            className={field}
            data-testid="doc-counterparty"
          />
          <datalist id={listId}>
            {options.map((c) => (
              <option key={c.id} value={c.name} />
            ))}
          </datalist>
          {needle && !found ? (
            <p id={`${partyId}-hint`} className="mt-1 text-meta text-bad-fg">
              {near.length > 1 ? t("docs.counterparty.many") : t("docs.counterparty.none")}
            </p>
          ) : null}
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
        <p className="mt-1 max-w-md text-meta text-ink-3">{t("docs.drop.sub")}</p>
        {busy !== null ? (
          <div className="mt-4 w-full max-w-sm" data-testid="doc-progress">
            <div role="progressbar" aria-label={t("docs.drop.reading", { name: busy })} aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(progress)} className="h-2 overflow-hidden rounded-full bg-line-strong">
              <div className="h-full rounded-full bg-brand-600 transition-[width] duration-200 ease-out motion-reduce:transition-none" style={{ width: `${progress}%` }} />
            </div>
            <p className="mt-1 text-meta tabular-nums text-ink-3">{Math.round(progress)}%</p>
          </div>
        ) : (
          <div className="mt-4 flex flex-wrap items-center justify-center gap-2">
            <Button
              variant="primary"
              size="sm"
              onClick={() => {
                if (!chosen) return setError(t("docs.counterparty.pick"));
                setError(null);
                input.current?.click();
              }}
              data-testid="doc-upload"
            >
              {t("docs.upload")}
            </Button>
          </div>
        )}
        <label htmlFor={fileId} className="mt-3 block text-meta text-ink-3">
          {t("docs.file")}
        </label>
        <input
          ref={input}
          id={fileId}
          type="file"
          accept=".pdf,.docx,.txt,.md,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain"
          onChange={(e) => {
            const picked = e.target.files?.[0] ?? null;
            e.target.value = "";
            void upload(picked);
          }}
          className="sr-only"
        />
      </div>
      {error ? (
        <div className="mt-3">
          <ErrorState error={error} />
        </div>
      ) : null}
    </section>
  );
}
