"use client";

import { useState } from "react";
import { Badge, Button, Callout, textareaClass } from "@/components/ui";
import { getSetupDocuments, readSetupDocument } from "@/lib/api";
import { errorText } from "@/lib/error-text";
import { useI18n } from "@/lib/i18n";
import type { SetupDocument } from "@/lib/types";
import { useAsync } from "@/lib/use-async";

async function toBase64(file: File): Promise<string> {
  const bytes = new Uint8Array(await file.arrayBuffer());
  let binary = "";
  for (let i = 0; i < bytes.length; i += 0x8000) binary += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  return btoa(binary);
}

/**
 * "Fill from a document": the confirmed contracts (or lender agreements) already in Documents, and a way to upload one during setup.
 * The server reads it and returns the row it suggests for the start date; the page fills the row and the owner checks it.
 */
export function DocPicker({ kind, startDate, onUse, onClose }: { kind: SetupDocument["kind"]; startDate: string; onUse: (d: SetupDocument) => void; onClose: () => void }) {
  const { t, lang } = useI18n();
  const docs = useAsync(() => getSetupDocuments(startDate, lang), [startDate, lang]);
  const [file, setFile] = useState<File | null>(null);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const list = (docs.data ?? []).filter((d) => d.kind === kind && d.row);

  async function read() {
    setBusy(true);
    setError(null);
    try {
      const doc = file
        ? await readSetupDocument({ kind, filename: file.name, content_base64: await toBase64(file), title: file.name, start_date: startDate }, lang)
        : await readSetupDocument({ kind, text, start_date: startDate }, lang);
      onUse(doc);
    } catch (e) {
      setError(errorText(e, t));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4 rounded-card border border-brand-600 bg-brand-50/40 p-4" data-testid={`setup-docs-${kind}`}>
      <div className="flex items-center justify-between gap-2">
        <p className="text-sm font-bold text-ink">{t("setup.docs.title")}</p>
        <Button size="sm" variant="ghost" onClick={onClose}>
          {t("setup.docs.close")}
        </Button>
      </div>
      {docs.data && list.length === 0 ? <p className="text-sm text-ink-2">{t("setup.docs.none")}</p> : null}
      <ul className="space-y-2">
        {list.map((d) => (
          <li key={d.document_id} className="flex flex-wrap items-center gap-3 rounded-tile border border-line bg-surface p-3">
            <div className="min-w-0 flex-1">
              <p className="text-sm font-semibold text-ink">{d.title}</p>
              <p className="text-meta text-ink-3">{[...(d.facts ?? []), d.progress?.text].filter(Boolean).join(" · ")}</p>
            </div>
            <Badge tone={d.from_setup ? "neutral" : "ok"}>{d.from_setup ? t("setup.docs.fromSetup") : t("setup.docs.confirmed")}</Badge>
            <Button size="sm" variant="primary" onClick={() => onUse(d)} data-testid="setup-doc-use">
              {t("setup.docs.use")}
            </Button>
          </li>
        ))}
      </ul>
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="flex flex-col gap-1.5 text-sm font-semibold text-ink">
          {t("setup.docs.upload")}
          <input
            type="file"
            accept=".pdf,.docx,.txt,.md,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            className="text-sm font-normal text-ink-2 file:mr-3 file:rounded-control file:border file:border-line-ui file:bg-surface file:px-3 file:py-1.5 file:text-sm file:font-semibold file:text-ink"
          />
        </label>
        <label className="flex flex-col gap-1.5 text-sm font-semibold text-ink">
          {t("setup.docs.paste")}
          <textarea value={text} onChange={(e) => setText(e.target.value)} rows={3} className={`${textareaClass} font-normal`} />
        </label>
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <Button variant="secondary" onClick={read} loading={busy} disabled={!file && !text.trim()}>
          {busy ? t("setup.docs.reading") : t("setup.docs.read")}
        </Button>
        <p className="text-meta text-ink-3">{t("setup.docs.note")}</p>
      </div>
      {error ? <Callout tone="bad">{error}</Callout> : null}
    </div>
  );
}
