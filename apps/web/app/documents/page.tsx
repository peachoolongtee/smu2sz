"use client";

import "@/app/flow-look.css";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useId, useMemo, useRef, useState, type DragEvent, type KeyboardEvent, type RefObject } from "react";
import { CheckIcon } from "@/components/icons";
import { DocumentReview } from "@/components/document-review";
import { contractsOff, DocStatusBadge, whenWords } from "@/components/documents";
import { Button, Callout, Card, ErrorState, inputClass, LoadingBlock, PageHeader, TableWrap, tableCls, tdCls, textLinkClass, thCls } from "@/components/ui";
import { addCustomer, existingCustomerId, getDocuments, getState, newKey, submitDocument } from "@/lib/api";
import { bump } from "@/lib/demo-store";
import { ApiError } from "@/lib/errors";
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
          <UploadForm parties={parties} onRead={read} onPartiesChanged={state.reload} />
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
        <svg aria-hidden width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={`shrink-0 text-ink-3 transition-transform duration-(--dur-fast) ${open ? "rotate-180" : ""}`}>
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
 * The owner's own file, as a drop zone: say what it is and who it is with, then drop the file or choose it with Upload and read. The file may come first
 * (owner's report, 17 Oct): a file given before the company is kept here, named ("Ready to read: …"), and the company field opens with its question; the file
 * is read as soon as a company is chosen or added, and nothing is sent before (the server reads documents only for companies on the books). Remove discards it.
 */
function UploadForm({ parties, onRead, onPartiesChanged }: { parties: Counterparty[]; onRead: (req: SubmitDocumentRequest) => Promise<void>; onPartiesChanged: () => void }) {
  const { t } = useI18n();
  const kindId = useId();
  const partyId = useId();
  const fileId = useId();
  const input = useRef<HTMLInputElement>(null);
  const partyInput = useRef<HTMLInputElement>(null);
  const removeButton = useRef<HTMLButtonElement>(null);
  const [kind, setKind] = useState<DocumentKind>("BUYER_CONTRACT");
  const [typed, setTyped] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [over, setOver] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // The file given before the company: kept here, never sent, until a company is chosen (then it is read at once) or the owner removes it.
  const [waiting, setWaiting] = useState<File | null>(null);
  // A customer added here is chosen at once, before the companies on the books are read again.
  const [added, setAdded] = useState<Counterparty[]>([]);
  // The add panel is open with this name in it ("" for an empty one); null: closed.
  const [adding, setAdding] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const role = kind === "BUYER_CONTRACT" ? "BUYER" : "LENDER";
  const known = [...parties, ...added.filter((a) => !parties.some((p) => p.id === a.id))];
  const options = known.filter((c) => c.role === role && c.known);
  // The company is chosen from the list, or typed by name: an exact name, else the one company whose name contains what was typed. Nothing that is not on the books can be chosen.
  const needle = typed.trim().toLowerCase();
  const matches = needle ? options.filter((c) => c.name.toLowerCase() === needle) : [];
  const near = needle && matches.length === 0 ? options.filter((c) => c.name.toLowerCase().includes(needle)) : [];
  const found = matches[0] ?? (near.length === 1 ? near[0] : undefined);
  const chosen = found?.id ?? "";
  // A contract with a buyer: a new customer can always be added here (lender agreements only choose a lender on the books).
  const canAdd = role === "BUYER";
  // The name typed is not on the books: the add offer names it.
  const offerTyped = canAdd && Boolean(needle) && !found && near.length === 0;
  const askWho = waiting !== null && !chosen;

  // The server's sentence for the customer added stays a few seconds, quietly.
  useEffect(() => {
    if (!notice) return;
    const id = window.setTimeout(() => setNotice(null), 6000);
    return () => window.clearTimeout(id);
  }, [notice]);

  // The server answers once, when the reading is done, so the bar is the work in hand: it climbs toward the end while the file is sent and read, and fills when the answer arrives.
  const [progress, setProgress] = useState(0);
  useEffect(() => {
    if (busy === null) return;
    const id = window.setInterval(() => setProgress((p) => p + (92 - p) * 0.08), 120);
    return () => window.clearInterval(id);
  }, [busy]);

  // The list of companies, opened by the field (see CompanyField). `ask` is set when a file waits for its company.
  const [listOpen, setListOpen] = useState(false);
  const quietFocus = useRef(false);
  const focusField = (open: boolean) => {
    quietFocus.current = !open;
    partyInput.current?.focus();
    quietFocus.current = false;
    setListOpen(open);
  };

  /** The file is read for company `id`; without one it waits here and the company field asks who it is with. */
  async function upload(f: File | null, id = chosen) {
    if (!f) return;
    if (f.size > MAX_BYTES) {
      setError(t("docs.tooBig"));
      return;
    }
    if (!id) {
      setWaiting(f);
      setError(null);
      focusField(true);
      return;
    }
    setWaiting(null);
    setProgress(6);
    setBusy(f.name);
    setError(null);
    try {
      await onRead({ kind, counterparty_id: id, filename: f.name, content_base64: await toBase64(f) });
      setProgress(100);
    } finally {
      setBusy(null);
    }
  }

  /** A company picked from the list (or typed and confirmed): it is the one in the field, and a file waiting for it is read now. */
  function commit(c: Counterparty) {
    setTyped(c.name);
    setListOpen(false);
    setNotice(null);
    setAdding(null);
    setError(null);
    if (waiting && !busy) void upload(waiting, c.id);
  }

  /** The customer added is chosen; `said` null: it was on the books already (a 409), and the owner is told so by its name there. */
  function choose(c: Counterparty, said: string | null) {
    const there = known.find((p) => p.id === c.id);
    const picked = there ?? c;
    if (!there) setAdded((list) => [...list, c]);
    setTyped(picked.name);
    setAdding(null);
    setError(null);
    setNotice(said ?? t("docs.newCustomer.exists", { name: picked.name }));
    onPartiesChanged();
    focusField(false);
    if (waiting && !busy) void upload(waiting, picked.id);
  }

  function openAdd() {
    setListOpen(false);
    setAdding(found ? "" : typed.trim());
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
  const hintId = `${partyId}-hint`;
  const askId = `${partyId}-ask`;
  const askText = role === "BUYER" ? t("docs.counterparty.ask") : t("docs.counterparty.askLender");
  const describedBy = [needle && !found && adding === null ? hintId : null, askWho ? askId : null].filter(Boolean).join(" ") || undefined;
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
          <CompanyField
            id={partyId}
            inputRef={partyInput}
            quietFocus={quietFocus}
            value={typed}
            onType={(v) => {
              setTyped(v);
              setNotice(null);
              setAdding(null);
            }}
            options={options}
            found={found}
            canAdd={canAdd}
            addLabel={offerTyped ? t("docs.newCustomer.offer", { name: typed.trim() }) : t("docs.newCustomer.any")}
            open={listOpen}
            onOpen={setListOpen}
            onPick={commit}
            onAdd={openAdd}
            onLeave={(to) => {
              // The exact name typed while a file waits is the company chosen: the file is read when the owner leaves the field (not on the way to Remove).
              if (waiting && matches[0] && to !== removeButton.current) commit(matches[0]);
            }}
            ask={askWho ? askText : null}
            invalid={Boolean(needle && !found)}
            describedBy={describedBy}
            className={field}
          />
          {adding !== null && canAdd ? (
            <NewCustomerPanel
              key={adding}
              typed={adding}
              onAdded={choose}
              onCancel={() => {
                setAdding(null);
                focusField(false);
              }}
            />
          ) : (
            <>
              {askWho ? (
                <p id={askId} role="status" className="mt-1 text-meta font-bold text-ink" data-testid="doc-ask-who">
                  {askText}
                </p>
              ) : null}
              {needle && !found && !offerTyped ? (
                <p id={hintId} className="mt-1 text-meta text-bad-fg">
                  {near.length > 1 ? t("docs.counterparty.many") : t("docs.counterparty.none")}
                </p>
              ) : notice ? (
                <p role="status" className="mt-1 text-meta text-ink-3" data-testid="doc-new-customer-done">
                  {notice}
                </p>
              ) : null}
              {canAdd ? (
                <p id={offerTyped ? hintId : undefined} className="mt-0.5 text-meta">
                  {offerTyped ? <span className="sr-only">{t("docs.counterparty.none")} </span> : null}
                  <button type="button" onClick={openAdd} className={`${textLinkClass} -ml-2`} data-testid="doc-new-customer">
                    <span aria-hidden>+ </span>
                    {offerTyped ? t("docs.newCustomer.offer", { name: typed.trim() }) : t("docs.newCustomer.any")}
                  </button>
                </p>
              ) : null}
            </>
          )}
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
        <p className="mt-3 max-w-full break-words text-base font-bold text-ink" data-testid={waiting && !busy && !over ? "doc-waiting" : undefined}>
          {busy ? t("docs.drop.reading", { name: busy }) : over ? t("docs.drop.active") : waiting ? t("docs.waiting.ready", { name: waiting.name }) : t("docs.drop.title")}
        </p>
        <p className="mt-1 max-w-md text-meta text-ink-3">{t("docs.drop.sub")}</p>
        {busy !== null ? (
          <div className="mt-4 w-full max-w-sm" data-testid="doc-progress">
            <div role="progressbar" aria-label={t("docs.drop.reading", { name: busy })} aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(progress)} className="h-2 overflow-hidden rounded-full bg-line-strong">
              <div className="h-full rounded-full bg-brand-600 transition-[width] duration-(--dur) ease-out motion-reduce:transition-none" style={{ width: `${progress}%` }} />
            </div>
            <p className="mt-1 text-meta tabular-nums text-ink-3">{Math.round(progress)}%</p>
          </div>
        ) : (
          <div className="mt-4 flex flex-wrap items-center justify-center gap-2">
            <Button
              variant="primary"
              size="sm"
              onClick={() => {
                setError(null);
                // A file already waits: Upload and read reads it for the company chosen, or asks again who it is with.
                if (waiting) return chosen ? void upload(waiting) : focusField(true);
                input.current?.click();
              }}
              data-testid="doc-upload"
            >
              {t("docs.upload")}
            </Button>
            {waiting ? (
              <Button
                ref={removeButton}
                size="sm"
                aria-label={t("docs.waiting.removeLabel", { name: waiting.name })}
                onClick={() => {
                  setWaiting(null);
                  setListOpen(false);
                }}
                data-testid="doc-waiting-remove"
              >
                {t("docs.waiting.remove")}
              </Button>
            ) : null}
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

type Choice = { kind: "company"; c: Counterparty } | { kind: "add" };

/**
 * "Who it is with": a combobox in the page's look (the field and a list of the books' companies of the right role). The list opens when the field is focused,
 * clicked or ArrowDown is pressed, so every company shows without typing; typing filters it. Arrow keys move, Enter or a click picks, Escape and Tab close, a
 * press outside closes. For a contract with a buyer, the last choice adds a new customer. `ask` is the question shown on top of the list while a file waits.
 */
function CompanyField({
  id,
  inputRef,
  quietFocus,
  value,
  onType,
  options,
  found,
  canAdd,
  addLabel,
  open,
  onOpen,
  onPick,
  onAdd,
  onLeave,
  ask,
  invalid,
  describedBy,
  className,
}: {
  id: string;
  inputRef: RefObject<HTMLInputElement | null>;
  quietFocus: RefObject<boolean>;
  value: string;
  onType: (v: string) => void;
  options: Counterparty[];
  found: Counterparty | undefined;
  canAdd: boolean;
  addLabel: string;
  open: boolean;
  onOpen: (open: boolean) => void;
  onPick: (c: Counterparty) => void;
  onAdd: () => void;
  /** The focus left the field (for `to`, null when it left the page). */
  onLeave: (to: EventTarget | null) => void;
  ask: string | null;
  invalid: boolean;
  describedBy: string | undefined;
  className: string;
}) {
  const { t } = useI18n();
  const root = useRef<HTMLDivElement>(null);
  const [active, setActive] = useState(-1);
  const listId = `${id}-list`;
  const optId = (i: number) => `${id}-opt-${i}`;
  const needle = value.trim().toLowerCase();
  // The whole list while nothing is typed or the name typed is the company chosen; else the companies whose name has what was typed.
  const shown = !needle || (found && found.name.toLowerCase() === needle) ? options : options.filter((c) => c.name.toLowerCase().includes(needle));
  const choices: Choice[] = [...shown.map((c) => ({ kind: "company" as const, c })), ...(canAdd ? [{ kind: "add" as const }] : [])];
  const expanded = open && choices.length > 0;

  useEffect(() => {
    if (!open) return;
    const away = (e: PointerEvent) => {
      if (!root.current?.contains(e.target as Node)) onOpen(false);
    };
    document.addEventListener("pointerdown", away);
    return () => document.removeEventListener("pointerdown", away);
  }, [open, onOpen]);

  // The active choice stays in sight in a long list.
  useEffect(() => {
    if (expanded && active >= 0) document.getElementById(`${id}-opt-${active}`)?.scrollIntoView({ block: "nearest" });
  }, [expanded, active, id]);

  const show = (at?: number) => {
    const current = found ? shown.findIndex((c) => c.id === found.id) : -1;
    setActive(at ?? current);
    onOpen(true);
  };
  const pick = (choice: Choice) => {
    setActive(-1);
    if (choice.kind === "add") onAdd();
    else onPick(choice.c);
  };

  function onKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    const n = choices.length;
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      if (!n) return;
      if (!expanded) return show(e.key === "ArrowDown" ? Math.max(0, found ? shown.findIndex((c) => c.id === found.id) : 0) : n - 1);
      setActive((i) => (e.key === "ArrowDown" ? (i + 1) % n : i <= 0 ? n - 1 : i - 1));
    } else if (e.key === "Enter") {
      if (expanded && active >= 0 && active < n) {
        e.preventDefault();
        pick(choices[active]);
      } else if (found) {
        e.preventDefault();
        onPick(found);
      }
    } else if (e.key === "Escape") {
      if (expanded) {
        e.preventDefault();
        onOpen(false);
      }
    } else if (e.key === "Tab") {
      onOpen(false);
    }
  }

  return (
    <div ref={root} className="relative">
      <input
        ref={inputRef}
        id={id}
        role="combobox"
        aria-autocomplete="list"
        aria-expanded={expanded}
        aria-controls={expanded ? listId : undefined}
        aria-activedescendant={expanded && active >= 0 ? optId(active) : undefined}
        value={value}
        onChange={(e) => {
          onType(e.target.value);
          setActive(-1);
          onOpen(true);
        }}
        onFocus={() => {
          if (!quietFocus.current && !found) show();
        }}
        onClick={() => {
          if (!expanded) show();
        }}
        onBlur={(e) => onLeave(e.relatedTarget)}
        onKeyDown={onKeyDown}
        autoComplete="off"
        spellCheck={false}
        placeholder={t("docs.counterparty.placeholder")}
        aria-invalid={invalid || undefined}
        aria-describedby={describedBy}
        className={`${className} pr-9 ${expanded ? "border-ink" : ""}`}
        data-testid="doc-counterparty"
      />
      <svg aria-hidden width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={`pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-ink-3 transition-transform duration-(--dur-fast) ${expanded ? "rotate-180" : ""}`}>
        <path d="M6 9l6 6 6-6" />
      </svg>
      {expanded ? (
        // A press inside the list keeps the focus in the field, so the field's own state (and a screen reader's place) is not lost on the way to the click.
        <div onMouseDown={(e) => e.preventDefault()} className="absolute left-0 right-0 top-full z-20 mt-1.5 overflow-hidden rounded-card border border-line bg-surface shadow-pop" data-testid="doc-counterparty-popup">
          {ask ? (
            <p aria-hidden className="border-b border-line px-3 py-2 text-meta font-bold text-ink">
              {ask}
            </p>
          ) : null}
          <ul id={listId} role="listbox" aria-label={t("docs.counterparty.list")} className="max-h-72 overflow-y-auto p-1.5" data-testid="doc-counterparty-list">
            {choices.map((choice, i) => {
              const selected = choice.kind === "company" && choice.c.id === found?.id;
              return (
                <li
                  key={choice.kind === "add" ? "+add" : choice.c.id}
                  id={optId(i)}
                  role="option"
                  aria-selected={selected}
                  onPointerEnter={() => setActive(i)}
                  onClick={() => pick(choice)}
                  className={`flex min-h-10 cursor-pointer items-center gap-3 rounded-tile px-3 py-2 text-sm touch:min-h-11 ${i === active ? "bg-subtle" : ""} ${choice.kind === "add" ? "font-bold text-brand-700" : "text-ink"}`}
                  data-testid={choice.kind === "add" ? "doc-counterparty-add" : undefined}
                >
                  {choice.kind === "add" ? (
                    <>
                      <span aria-hidden>+</span>
                      <span className="min-w-0 flex-1 break-words">{addLabel}</span>
                    </>
                  ) : (
                    <>
                      <span className="min-w-0 flex-1 break-words">{choice.c.name}</span>
                      {selected ? <CheckIcon aria-hidden className="shrink-0 text-ink" /> : null}
                    </>
                  )}
                </li>
              );
            })}
          </ul>
        </div>
      ) : null}
    </div>
  );
}

/** A failed request's sentence for the owner: the server's own message when it sent one in words, else the app's. */
function saidOf(e: unknown, fallback: string): string {
  if (e instanceof ApiError) {
    const m = (e.detail as { message?: unknown } | undefined)?.message;
    if (typeof m === "string" && m.trim()) return m;
  }
  return fallback;
}

/**
 * A buyer who is not on the books yet, added from "Who it is with" (its list's last choice or the link under it): the name as typed (or empty), a short name if the owner wants one,
 * Add customer or Cancel. The customer added (or the one already on the books with that name) is chosen in the field.
 */
function NewCustomerPanel({ typed, onAdded, onCancel }: { typed: string; onAdded: (c: Counterparty, said: string | null) => void; onCancel: () => void }) {
  const { t, lang } = useI18n();
  const titleId = useId();
  const nameId = useId();
  const shortId = useId();
  const errorId = useId();
  const nameInput = useRef<HTMLInputElement>(null);
  const [name, setName] = useState(typed);
  const [short, setShort] = useState("");
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  // One key for this customer: a retry after a failed call adds it once.
  const [key] = useState(newKey);

  useEffect(() => {
    nameInput.current?.focus();
  }, []);

  async function add() {
    if (busy) return;
    const clean = name.trim();
    if (!clean) {
      setProblem(t("docs.newCustomer.nameNeeded"));
      nameInput.current?.focus();
      return;
    }
    setBusy(true);
    setProblem(null);
    try {
      const res = await addCustomer({ name: clean, short_name: short.trim() || null, idempotency_key: key }, lang);
      onAdded({ id: res.customer.id, name: res.customer.name, role: "BUYER", known: true }, res.event_text);
    } catch (e) {
      const existing = existingCustomerId(e);
      if (existing) {
        // Already on the books: that customer is the one chosen, and the owner is told so.
        onAdded({ id: existing, name: clean, role: "BUYER", known: true }, null);
      } else {
        setProblem(saidOf(e, t("docs.newCustomer.failed")));
      }
    } finally {
      setBusy(false);
    }
  }

  const field = `${inputClass} ${FOCUS} w-full touch:min-h-11`;
  return (
    <form
      aria-labelledby={titleId}
      onSubmit={(e) => {
        e.preventDefault();
        void add();
      }}
      onKeyDown={(e) => {
        if (e.key === "Escape") {
          e.preventDefault();
          onCancel();
        }
      }}
      className="motion-reveal mt-2 rounded-card border border-line bg-subtle/60 p-3"
      data-testid="doc-new-customer-panel"
    >
      <p id={titleId} className="text-meta font-bold text-ink">
        {t("docs.newCustomer.title")}
      </p>
      <label htmlFor={nameId} className="mt-2 mb-1 block text-meta font-bold text-ink-2">
        {t("docs.newCustomer.name")}
      </label>
      <input
        ref={nameInput}
        id={nameId}
        value={name}
        onChange={(e) => {
          setName(e.target.value);
          setProblem(null);
        }}
        autoComplete="off"
        maxLength={120}
        aria-invalid={problem ? true : undefined}
        aria-describedby={problem ? errorId : undefined}
        className={field}
        data-testid="doc-new-customer-name"
      />
      <label htmlFor={shortId} className="mt-2 mb-1 block text-meta font-bold text-ink-2">
        {t("docs.newCustomer.short")}
      </label>
      <input id={shortId} value={short} onChange={(e) => setShort(e.target.value)} autoComplete="off" maxLength={40} className={field} data-testid="doc-new-customer-short" />
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <Button type="submit" variant="primary" size="sm" loading={busy} data-testid="doc-new-customer-add">
          {t("docs.newCustomer.add")}
        </Button>
        <Button size="sm" disabled={busy} onClick={onCancel} data-testid="doc-new-customer-cancel">
          {t("docs.newCustomer.cancel")}
        </Button>
        {problem ? (
          <p id={errorId} role="alert" className="min-w-0 basis-full text-meta text-bad-fg sm:basis-auto" data-testid="doc-new-customer-error">
            {problem}
          </p>
        ) : null}
      </div>
    </form>
  );
}
