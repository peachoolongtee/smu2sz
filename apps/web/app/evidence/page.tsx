"use client";

import { DownloadIcon } from "@/components/icons";
import { Button, Callout, Card, EmptyState, ErrorState, Hash, KeyValueList, LoadingBlock, PageHeader } from "@/components/ui";
import { getEvidence } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { useAsync } from "@/lib/use-async";

interface EvidenceLine {
  seq?: number;
  kind?: string;
  status?: string;
  entry_hash?: string | null;
  /** Live evidence brackets the operations with a `run` header and a `chain` trailer (with head_hash). */
  record?: string;
  head_hash?: string | null;
}

function parse(jsonl: string): { lines: string[]; head: EvidenceLine | null; last: EvidenceLine | null; headHash: string | null } {
  const lines = jsonl.split("\n").filter((l) => l.trim().length > 0);
  const safe = (l: string | undefined): EvidenceLine | null => {
    if (!l) return null;
    try {
      return JSON.parse(l) as EvidenceLine;
    } catch {
      return null;
    }
  };
  const records = lines.map(safe);
  // Operation entries only: skip the live `run` header and `chain` trailer when present.
  const ops = records.filter((r): r is EvidenceLine => r !== null && r.record !== "run" && r.record !== "chain");
  const trailer = records.find((r) => r?.record === "chain") ?? null;
  return { lines, head: ops[0] ?? null, last: ops[ops.length - 1] ?? null, headHash: trailer?.head_hash ?? ops[ops.length - 1]?.entry_hash ?? null };
}

export default function EvidencePage() {
  const { t } = useI18n();
  const ev = useAsync(getEvidence, []);

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
      <PageHeader title={t("evid.title")} subtitle={t("evid.subtitle")} />
      {ev.error ? (
        <ErrorState error={ev.error} onRetry={ev.reload} />
      ) : ev.data === undefined ? (
        <LoadingBlock rows={3} />
      ) : ev.data.trim() === "" ? (
        <EmptyState title={t("evid.empty.title")} body={t("evid.empty.body")} />
      ) : (
        <EvidenceBody text={ev.data} onDownload={() => download(ev.data ?? "")} />
      )}
    </>
  );
}

function EvidenceBody({ text, onDownload }: { text: string; onDownload: () => void }) {
  const { t } = useI18n();
  const { lines, head, last, headHash } = parse(text);
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
            { k: t("evid.first"), v: head ? [head.seq !== undefined ? `#${head.seq}` : null, head.kind].filter(Boolean).join(" ") : t("common.none") },
            { k: t("evid.last"), v: last ? [last.seq !== undefined ? `#${last.seq}` : null, last.kind].filter(Boolean).join(" ") : t("common.none") },
            { k: t("evid.head"), v: <Hash value={headHash} /> },
            { k: t("evid.file"), v: <span className="font-mono text-meta">termsledger-evidence.jsonl</span> },
          ]}
        />
        <div className="mt-3">
          <Callout tone="info">{t("evid.how")}</Callout>
        </div>
      </Card>

      <Card id="evidence-preview" title={t("evid.preview")} subtitle={t("evid.preview.sub")}>
        <pre
          tabIndex={0}
          aria-label={t("evid.preview")}
          className="max-h-96 overflow-auto rounded-tile border border-line bg-subtle p-3 font-mono text-meta leading-relaxed"
        >
          {lines.join("\n")}
        </pre>
      </Card>
    </div>
  );
}
