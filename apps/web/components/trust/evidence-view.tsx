"use client";

import { useEffect } from "react";
import { OpStatusBadge } from "@/components/badges";
import { Disclosure } from "@/components/business/kit";
import { DownloadIcon } from "@/components/icons";
import { Button, Callout, Card, EmptyState, ErrorState, Hash, KeyValueList, LoadingBlock, PageHeader } from "@/components/ui";
import { StatusPill } from "@/components/ui/status-pill";
import { getEvidence, getLedger } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { OperationView } from "@/lib/types";
import { useAsync } from "@/lib/use-async";

/** The file's lines, kept whole for the download and the raw preview; the entries themselves are read from the ledger, which has their words. */
function parse(jsonl: string): { lines: string[]; headHash: string | null } {
  const lines = jsonl.split("\n").filter((l) => l.trim().length > 0);
  const safe = (l: string): { record?: string; head_hash?: string | null; entry_hash?: string | null } | null => {
    try {
      return JSON.parse(l);
    } catch {
      return null;
    }
  };
  const records = lines.map(safe);
  const ops = records.filter((r) => r !== null && r.record !== "run" && r.record !== "chain");
  const trailer = records.find((r) => r?.record === "chain") ?? null;
  return { lines, headHash: trailer?.head_hash ?? ops[ops.length - 1]?.entry_hash ?? null };
}

/**
 * The evidence: the record chain as a file anyone can check, and its entries one by one in the ledger's own words (`kind_text`, the business sentence), never the
 * engine's kind codes. The raw file stays the download and a preview under a fold. `entry` (a sequence number in the address) marks one entry: it is scrolled to,
 * drawn with a visible mark and `aria-current`, and takes focus. `embedded` (the /trust page) swaps the page header for a section heading, so the page keeps one h1.
 */
export function EvidenceView({ embedded = false, entry = null, entryAsked = false }: { embedded?: boolean; entry?: number | null; /** The address names an `entry` at all (a number or not): one that is not in the record says so. */ entryAsked?: boolean }) {
  const { t, lang } = useI18n();
  const ev = useAsync(getEvidence, []);
  const ledger = useAsync(() => getLedger(lang), [lang]);

  function download(text: string) {
    const blob = new Blob([text], { type: "application/x-ndjson" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "termsledger-evidence.jsonl";
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  return (
    <>
      {embedded ? (
        <div className="mb-4">
          <h2 className="font-display text-xl font-extrabold tracking-[-0.01em] text-ink">{t("evid.title")}</h2>
          <p className="mt-0.5 max-w-3xl text-supporting text-ink-3">{t("evid.subtitle")}</p>
        </div>
      ) : (
        <PageHeader title={t("evid.title")} subtitle={t("evid.subtitle")} />
      )}
      {ev.error ? (
        <ErrorState error={ev.error} onRetry={ev.reload} />
      ) : ev.data === undefined ? (
        <LoadingBlock rows={3} />
      ) : ev.data.trim() === "" ? (
        <EmptyState title={t("evid.empty.title")} body={t("evid.empty.body")} />
      ) : (
        <EvidenceBody text={ev.data} ops={ledger.data?.operations ?? null} entry={entry} entryAsked={entryAsked} onDownload={() => download(ev.data ?? "")} />
      )}
    </>
  );
}

function EvidenceBody({ text, ops, entry, entryAsked, onDownload }: { text: string; ops: OperationView[] | null; entry: number | null; entryAsked: boolean; onDownload: () => void }) {
  const { t } = useI18n();
  const { lines, headHash } = parse(text);
  const entries = ops ? ops.filter((o) => o.seq !== undefined && o.seq !== null) : [];
  const first = entries[0];
  const last = entries[entries.length - 1];
  const named = (o: OperationView | undefined) => (o ? t("trust.entry.named", { n: o.seq ?? 0, kind: o.kind_text ?? t("trust.entry.other") }) : t("common.none"));
  const found = entry !== null && entries.some((o) => o.seq === entry);

  // The address names one entry: bring it into view and give it focus, once the entries are there.
  useEffect(() => {
    if (entry === null || !found) return;
    const el = document.getElementById(`trust-entry-${entry}`);
    if (!el) return;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    el.scrollIntoView({ block: "center", behavior: reduced ? "auto" : "smooth" });
    el.focus({ preventScroll: true });
  }, [entry, found]);

  return (
    <div className="space-y-6">
      <Card
        id="evidence-summary"
        title={t("evid.summary")}
        actions={
          <Button variant="primary" onClick={onDownload} data-testid="download-evidence">
            <DownloadIcon />
            {t("evid.download")}
          </Button>
        }
      >
        <KeyValueList
          items={[
            { k: t("evid.lines"), v: lines.length },
            { k: t("evid.first"), v: named(first) },
            { k: t("evid.last"), v: named(last) },
            { k: t("evid.head"), v: <Hash value={headHash} /> },
            { k: t("evid.file"), v: <span className="font-mono text-meta">termsledger-evidence.jsonl</span> },
          ]}
        />
        <div className="mt-3">
          <Callout tone="info">{t("evid.how")}</Callout>
        </div>
      </Card>

      <Card id="evidence-entries" title={t("trust.entries", { n: entries.length })} subtitle={t("trust.entries.sub")}>
        {(entryAsked || entry !== null) && ops && !found ? (
          <p role="status" className="mb-3 text-sm text-ink-2" data-testid="trust-entry-missing">
            {t("trust.entry.missing")}
          </p>
        ) : null}
        {ops === null ? (
          <LoadingBlock rows={2} />
        ) : (
          <ol className="divide-y divide-line" data-testid="trust-entries">
            {entries.map((o) => {
              const marked = o.seq === entry;
              return (
                <li
                  key={`${o.seq}-${o.op_id}`}
                  id={`trust-entry-${o.seq}`}
                  tabIndex={-1}
                  aria-current={marked ? "true" : undefined}
                  data-testid={`trust-entry-${o.seq}`}
                  data-marked={marked ? "true" : undefined}
                  className={`scroll-mt-24 rounded-tile py-3 outline-none focus-visible:ring-2 focus-visible:ring-brand-600 ${marked ? "bg-brand-50 px-3 ring-2 ring-brand-600" : ""}`}
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-sm font-semibold text-ink">{t("trust.entry.n", { n: o.seq ?? 0 })}</span>
                    <span className="text-sm text-ink-2" data-testid="trust-entry-kind">
                      {o.kind_text ?? t("trust.entry.other")}
                    </span>
                    <OpStatusBadge status={o.status} />
                    {marked ? <StatusPill tone="lavender">{t("trust.marked")}</StatusPill> : null}
                  </div>
                  {o.event_text || o.message_when ? <p className="mt-1 break-words text-sm text-ink-2">{o.event_text || o.message_when}</p> : null}
                  <dl className="mt-1 grid grid-cols-[max-content_minmax(0,1fr)] items-center gap-x-3 gap-y-0.5 text-meta text-ink-2">
                    <dt>{t("ledger.hash")}</dt>
                    <dd>
                      <Hash value={o.entry_hash} />
                    </dd>
                    <dt>{t("ledger.prevHash")}</dt>
                    <dd>
                      <Hash value={o.prev_hash} />
                    </dd>
                    <dt>{t("audit.executor")}</dt>
                    <dd className="break-words">{o.summary}</dd>
                  </dl>
                </li>
              );
            })}
          </ol>
        )}
      </Card>

      <Disclosure card testId="evidence-raw" summary={t("trust.raw")}>
        <p className="mb-2 text-supporting text-ink-3">{t("evid.preview.sub")}</p>
        <pre tabIndex={0} aria-label={t("evid.preview")} className="max-h-96 overflow-auto rounded-tile border border-line bg-subtle p-3 font-mono text-meta leading-relaxed">
          {lines.join("\n")}
        </pre>
      </Disclosure>
    </div>
  );
}
