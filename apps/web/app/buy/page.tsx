"use client";

import Link from "next/link";
import { useState } from "react";
import { contractsOff } from "@/components/documents";
import { Badge, Button, ButtonLink, Card, EmptyState, ErrorState, inputClass, LoadingBlock, PageHeader } from "@/components/ui";
import { getCapexContractFixtures, getPurchases, submitDocument } from "@/lib/api";
import type { DictKey } from "@/lib/dictionary";
import { useI18n } from "@/lib/i18n";
import type { PurchaseRow, PurchaseStage } from "@/lib/types";
import { useAsync } from "@/lib/use-async";

const STAGE: Record<PurchaseStage, { key: DictKey; tone: "ok" | "warn" | "bad" | "neutral" | "info" }> = {
  REVIEW: { key: "buy.stage.REVIEW", tone: "warn" },
  READY: { key: "buy.stage.READY", tone: "info" },
  AWAITING_APPROVAL: { key: "buy.stage.AWAITING_APPROVAL", tone: "warn" },
  COMMITTED: { key: "buy.stage.COMMITTED", tone: "ok" },
  PAID: { key: "buy.stage.PAID", tone: "neutral" },
  REJECTED: { key: "buy.stage.REJECTED", tone: "neutral" },
};

/** Buying (ADR-0013): every capex contract the owner has given FLOW, where it stands and the one thing to do next. */
export default function BuyPage() {
  const { t, lang } = useI18n();
  const list = useAsync(() => getPurchases(lang), [lang]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [readId, setReadId] = useState<string | null>(null);

  async function readOwn(vendor: string, file: File) {
    setBusy(true);
    setError(null);
    try {
      const doc = await submitDocument({ kind: "CAPEX_CONTRACT", counterparty_id: vendor, filename: file.name, content_base64: await toBase64(file) });
      setReadId(doc.id);
      list.reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function readSample() {
    setBusy(true);
    setError(null);
    try {
      const fixtures = await getCapexContractFixtures();
      if (!fixtures.length) throw new Error(t("buy.noSample"));
      const doc = await submitDocument({ fixture_id: fixtures[0].id });
      setReadId(doc.id);
      list.reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  if (list.error && contractsOff(list.error)) {
    return (
      <>
        <PageHeader title={t("buy.title")} subtitle={t("buy.subtitle")} />
        <EmptyState title={t("buy.off.title")} body={t("buy.off.body")} />
      </>
    );
  }

  return (
    <>
      <PageHeader
        title={t("buy.title")}
        subtitle={t("buy.subtitle")}
        actions={
          <>
            <ButtonLink href="/finance" variant="secondary">{t("buy.toFinance")}</ButtonLink>
            <ButtonLink href="/plans" variant="secondary">{t("buy.toPlans")}</ButtonLink>
          </>
        }
      />
      {list.error ? <ErrorState error={list.error} onRetry={list.reload} /> : null}
      {error ? <ErrorState error={error} /> : null}
      {readId ? (
        <p className="mb-4 text-sm text-ink-2" data-testid="buy-read">
          {t("buy.read.done")}{" "}
          <Link className="font-medium text-brand-700 underline underline-offset-2" href={`/documents?id=${encodeURIComponent(readId)}`}>
            {t("buy.read.review")}
          </Link>
        </p>
      ) : null}
      <UploadCard busy={busy} onRead={(vendor, file) => void readOwn(vendor, file)} />
      {!list.data ? (
        <LoadingBlock rows={3} />
      ) : list.data.purchases.length === 0 ? (
        <EmptyState
          title={t("buy.empty.title")}
          body={t("buy.empty.body")}
          action={
            <Button variant="primary" loading={busy} onClick={() => void readSample()} data-testid="buy-read-sample">
              {t("buy.read.sample")}
            </Button>
          }
        />
      ) : (
        <div className="space-y-4" data-testid="buy-list">
          {list.data.purchases.map((p) => (
            <PurchaseCard key={p.document_id} p={p} />
          ))}
        </div>
      )}
    </>
  );
}

function PurchaseCard({ p }: { p: PurchaseRow }) {
  const { t } = useI18n();
  const stage = STAGE[p.stage];
  return (
    <Card
      flat
      title={p.title}
      subtitle={`${p.vendor_name}${p.price_display ? ` · ${p.price_display}` : ""}`}
      actions={<Badge tone={stage.tone}>{t(stage.key)}</Badge>}
    >
      <div data-testid={`purchase-${p.document_id}`}>
        <p className="text-sm font-medium text-ink" data-testid="purchase-next">{p.next_action}</p>
        {p.payments.length ? (
          <ul className="mt-2 space-y-1 text-meta text-ink-2">
            {p.payments.map((x) => (
              <li key={x.n} className={x.paid ? "text-ink-3 line-through" : ""}>
                {x.amount_display} · {x.when} · {x.label}
              </li>
            ))}
          </ul>
        ) : null}
        <div className="mt-3 flex flex-wrap gap-2">
          {p.stage === "REVIEW" ? (
            <ButtonLink href={`/documents?id=${encodeURIComponent(p.document_id)}`} variant="primary">{t("buy.read.review")}</ButtonLink>
          ) : null}
          {p.stage === "READY" ? (
            <ButtonLink href={`/buy/contract?id=${encodeURIComponent(p.document_id)}`} variant="primary" data-testid="purchase-open">
              {t("buy.open")}
            </ButtonLink>
          ) : null}
          {p.stage === "AWAITING_APPROVAL" ? (
            <ButtonLink href="/approvals" variant="primary">{t("buy.toApprovals")}</ButtonLink>
          ) : null}
          {p.stage === "COMMITTED" || p.stage === "PAID" ? (
            <ButtonLink href={`/buy/contract?id=${encodeURIComponent(p.document_id)}`} variant="secondary">{t("buy.open")}</ButtonLink>
          ) : null}
        </div>
      </div>
    </Card>
  );
}

async function toBase64(file: File): Promise<string> {
  const bytes = new Uint8Array(await file.arrayBuffer());
  let binary = "";
  for (let i = 0; i < bytes.length; i += 0x8000) binary += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  return btoa(binary);
}

/** The owner's own vendor contract: the vendor need not be on the registry yet (committing the purchase adds it). */
function UploadCard({ busy, onRead }: { busy: boolean; onRead: (vendor: string, file: File) => void }) {
  const { t } = useI18n();
  const [vendor, setVendor] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const valid = /^[A-Z0-9][A-Z0-9_-]{1,63}$/.test(vendor) && file !== null;
  return (
    <Card flat id="upload" title={t("buy.upload.title")} className="mb-6">
      <div className="grid gap-3 sm:grid-cols-[1fr_1fr_auto] sm:items-end">
        <label className="grid gap-1 text-meta text-ink-2">
          {t("buy.upload.vendor")}
          <input className={inputClass} value={vendor} onChange={(e) => setVendor(e.target.value.toUpperCase())} data-testid="buy-upload-vendor" />
        </label>
        <label className="grid gap-1 text-meta text-ink-2">
          {t("buy.upload.file")}
          <input type="file" accept=".pdf,.docx,.txt,.md" className="text-sm" onChange={(e) => setFile(e.target.files?.[0] ?? null)} data-testid="buy-upload-file" />
        </label>
        <Button variant="secondary" disabled={!valid} loading={busy} onClick={() => file && onRead(vendor, file)} data-testid="buy-upload-read">
          {t("buy.upload.read")}
        </Button>
      </div>
    </Card>
  );
}
