"use client";

import { useId, useRef, useState } from "react";
import { Button, inputClass } from "@/components/ui";
import { newKey, recordReceipt } from "@/lib/api";
import { errorText } from "@/lib/error-text";
import { useI18n } from "@/lib/i18n";
import { yuanTextToFen } from "@/lib/money-input";
import type { ReceivableRow, ReceiptWords } from "@/lib/types";

/** Whether the owner can record a payment on this invoice: it is in the books, open or financed, with something still owed. */
export function canRecordPayment(row: ReceivableRow): boolean {
  return (row.status === "OPEN" || row.status === "FINANCED") && typeof row.outstanding_fen === "number" && row.outstanding_fen > 0;
}

/**
 * "Record a payment" on an open invoice (feature inventory gap 1): a secondary button that opens a small form under it. The amount is the whole
 * outstanding (the server's own figure and fen, sent as they are) or part of it (typed in yuan, read as whole fen by `yuanTextToFen`, never added
 * up); the date is today on the books' clock (the server dates it); a bank reference is optional. Each press of Record sends the existing
 * RECEIVE_PAYMENT operation as the owner with a new idempotency key. A booked payment closes the form and hands the server's words to the page
 * (`onRecorded`), which reloads the books; a refusal and any error are shown beside the button, in the server's words where it wrote them.
 */
export function RecordPayment({ row, onRecorded, scope = "" }: { row: ReceivableRow; onRecorded: (words: ReceiptWords) => void; scope?: string }) {
  const { t, lang } = useI18n();
  const id = useId();
  const [open, setOpen] = useState(false);
  const [mode, setMode] = useState<"full" | "part">("full");
  const [amount, setAmount] = useState("");
  const [reference, setReference] = useState("");
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<{ headline: string | null; lines: string[] } | null>(null);
  const amountRef = useRef<HTMLInputElement>(null);
  const rid = row.receivable_id;
  const tid = (name: string) => `recv3-pay-${scope}${name}`;

  const close = () => {
    setOpen(false);
    setProblem(null);
  };

  const submit = async () => {
    const fen = mode === "full" ? row.outstanding_fen : yuanTextToFen(amount);
    if (!fen) {
      setProblem({ headline: null, lines: [t("recv3.pay.amount.invalid")] });
      amountRef.current?.focus();
      return;
    }
    setBusy(true);
    setProblem(null);
    try {
      const res = await recordReceipt({ receivable_id: rid, amount_fen: fen, bank_reference: reference.trim() || null, key: newKey() }, lang);
      const words = res.receipt;
      const status = res.result.status;
      if (status === "EXECUTED" || status === "DUPLICATE") {
        setOpen(false);
        setAmount("");
        setReference("");
        setMode("full");
        // The server's words; without them (a failure writing them) the executor's own sentence, which is the server's too.
        onRecorded(words ?? { status, tone: status === "EXECUTED" ? "ok" : "info", headline_text: res.result.message, lines: [], reconciliation_text: null });
      } else {
        setProblem({ headline: words?.headline_text ?? null, lines: words?.lines.length ? words.lines : words ? [] : [res.result.message] });
      }
    } catch (e) {
      setProblem({ headline: null, lines: [errorText(e, t)] });
    } finally {
      setBusy(false);
    }
  };

  if (!canRecordPayment(row)) return null;

  return (
    <>
      <span className="contents" data-testid={tid("action")}>
        <Button
          size="md"
          className="min-h-11"
          aria-expanded={open}
          aria-controls={`${id}-form`}
          onClick={() => (open ? close() : setOpen(true))}
          data-testid={tid("open")}
        >
          {t("recv3.pay.button")}
        </Button>
      </span>
      {open ? (
        <form
          id={`${id}-form`}
          aria-labelledby={`${id}-title`}
          className="basis-full space-y-3 rounded-tile border border-line bg-subtle p-3.5 sm:p-4"
          data-testid={tid("form")}
          data-receivable={rid}
          onSubmit={(e) => {
            e.preventDefault();
            void submit();
          }}
        >
          <div>
            <p id={`${id}-title`} className="font-semibold text-ink">
              {t("recv3.pay.title", { buyer: row.buyer_name ?? "" })}
            </p>
            <p className="mt-0.5 text-sm text-ink-3">{t("recv3.pay.note")}</p>
          </div>
          <fieldset className="space-y-2">
            <legend className="sr-only">{t("recv3.pay.amount")}</legend>
            <label className="flex min-h-11 cursor-pointer items-center gap-2.5 text-sm text-ink">
              <input type="radio" name={`${id}-mode`} checked={mode === "full"} onChange={() => setMode("full")} className="size-4 accent-brand-600" data-testid={tid("full")} />
              <span>{t("recv3.pay.full", { amount: row.outstanding_display ?? "" })}</span>
            </label>
            <label className="flex min-h-11 cursor-pointer items-center gap-2.5 text-sm text-ink">
              <input
                type="radio"
                name={`${id}-mode`}
                checked={mode === "part"}
                onChange={() => {
                  setMode("part");
                  setTimeout(() => amountRef.current?.focus(), 0);
                }}
                className="size-4 accent-brand-600"
                data-testid={tid("part")}
              />
              <span>{t("recv3.pay.part")}</span>
            </label>
            {mode === "part" ? (
              <label className="block pl-6.5 text-sm">
                <span className="block font-medium text-ink-2">{t("recv3.pay.amount")}</span>
                <input
                  ref={amountRef}
                  inputMode="decimal"
                  autoComplete="off"
                  value={amount}
                  onChange={(e) => setAmount(e.target.value)}
                  placeholder={t("recv3.pay.amount.hint")}
                  aria-describedby={`${id}-amount-hint`}
                  className={`${inputClass} mt-1 w-full max-w-xs tabular-nums`}
                  data-testid={tid("amount")}
                />
                <span id={`${id}-amount-hint`} className="mt-1 block text-meta text-ink-3">
                  {t("recv3.pay.amount.hint")}
                </span>
              </label>
            ) : null}
          </fieldset>
          <p className="text-sm text-ink-2" data-testid={tid("date")}>
            {t("recv3.pay.date")}
          </p>
          <label className="block text-sm">
            <span className="block font-medium text-ink-2">{t("recv3.pay.ref")}</span>
            <input
              value={reference}
              maxLength={64}
              autoComplete="off"
              onChange={(e) => setReference(e.target.value)}
              aria-describedby={`${id}-ref-hint`}
              className={`${inputClass} mt-1 w-full max-w-xs`}
              data-testid={tid("ref")}
            />
            <span id={`${id}-ref-hint`} className="mt-1 block text-meta text-ink-3">
              {t("recv3.pay.ref.hint")}
            </span>
          </label>
          <div className="flex flex-wrap items-start gap-2">
            <Button type="submit" variant="primary" className="min-h-11" loading={busy} data-testid={tid("submit")}>
              {busy ? t("recv3.pay.sending") : t("recv3.pay.submit")}
            </Button>
            <Button variant="ghost" className="min-h-11" onClick={close} disabled={busy} data-testid={tid("cancel")}>
              {t("recv3.pay.cancel")}
            </Button>
            {problem ? (
              <div role="alert" className="min-w-0 flex-1 basis-56 rounded-tile border border-bad-line bg-bad-bg px-3 py-2 text-sm text-bad-fg" data-testid={tid("error")}>
                {problem.headline ? <p className="font-semibold">{problem.headline}</p> : null}
                {problem.lines.map((line) => (
                  <p key={line}>{line}</p>
                ))}
              </div>
            ) : null}
          </div>
        </form>
      ) : null}
    </>
  );
}

/** The server's words for the payment just recorded, above the invoices: what it did, line by line, and how the reconciliation reads it. */
export function RecordedPayment({ words, onDismiss }: { words: ReceiptWords; onDismiss: () => void }) {
  const { t } = useI18n();
  const tone = words.tone === "ok" ? "border-ok-line bg-ok-bg" : words.tone === "bad" ? "border-bad-line bg-bad-bg" : "border-info-line bg-info-bg";
  return (
    <div role="status" className={`rounded-tile border px-3.5 py-3 text-sm ${tone}`} data-testid="recv3-pay-result" data-status={words.status}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 space-y-1">
          {words.headline_text ? (
            <p className="font-semibold text-ink" data-testid="recv3-pay-headline">
              {words.headline_text}
            </p>
          ) : null}
          {words.lines.map((line, i) => (
            <p key={i} className="text-ink-2" data-testid="recv3-pay-line">
              {line}
            </p>
          ))}
          {words.reconciliation_text ? (
            <p className="text-ink-2" data-testid="recv3-pay-recon">
              <span className="font-semibold text-ink">{t("recv3.pay.recon")}</span>{" "}
              {words.reconciliation_text}
            </p>
          ) : null}
        </div>
        <Button variant="ghost" size="sm" onClick={onDismiss} data-testid="recv3-pay-dismiss">
          {t("recv3.pay.done")}
        </Button>
      </div>
    </div>
  );
}
