"use client";

import Link from "next/link";
import { useId, useState, type FormEvent } from "react";
import { ArrowLeftIcon } from "@/components/icons";
import { Button, ButtonLink, Card, SegmentedButtons, inputClass } from "@/components/ui";
import { saveInput } from "@/lib/api";
import { ApiError } from "@/lib/errors";
import { useI18n } from "@/lib/i18n";
import type { InputSheetRow, InputSheetView } from "@/lib/types";

/** Where a fact came from and when the owner entered it, as one quiet line: the server's note, its provenance word, its entered day. */
function Source({ row, id }: { row: InputSheetRow; id: string }) {
  const parts = [row.provenance_text, row.entered_day_text].filter(Boolean);
  return (
    <p id={id} className="text-[13px] leading-relaxed text-ink-2" data-testid={`inputs-source-${row.key}`}>
      {row.note ? <>{row.note} </> : null}
      <span className={`font-bold ${row.provenance_key === "OWNER" ? "text-ink" : "text-warn-fg"}`} data-testid={`inputs-provenance-${row.key}`}>
        {row.note ? "· " : null}
        {parts.join(" · ")}
      </span>
    </p>
  );
}

/** The server's refusal of one field, read where the owner typed it. */
function FieldError({ text, id }: { text: string | undefined; id: string }) {
  if (!text) return null;
  return (
    <p id={id} role="alert" className="text-[13px] font-bold text-bad-fg" data-testid="inputs-error">
      {text}
    </p>
  );
}

function errorText(e: unknown): string {
  if (e instanceof ApiError) {
    const detail = e.detail as { message?: string } | undefined;
    return detail?.message ?? e.message;
  }
  return e instanceof Error ? e.message : String(e);
}

/**
 * The owner's Inputs sheet, in the board's order: annual sales with its source, the gross margin and its basis, the server's check against
 * the books, how the owner classes the customer (context only), the usual delay, and the firm's own rows. Each value is what the server wrote
 * for the form; Save sends only what the owner changed, field by field, as typed (the server parses it), then reads the sheet again so every
 * figure, provenance word and entered day shown is the server's. With the economics fields refused, the server's sentence and no form.
 */
/** What a Save left behind for the sheet read again after it: its status, and the fields that failed with what the owner typed and why. */
export interface SaveCarry {
  status: string | null;
  values: Record<string, string>;
  errors: Record<string, string>;
}

export function InputsSheet({ view, onSaved, carry = null }: { view: InputSheetView; onSaved: (carry: SaveCarry) => void; carry?: SaveCarry | null }) {
  const { t, lang } = useI18n();
  const uid = useId();
  const rows = view.fields ?? [];
  const firm = view.firm ?? [];
  const all = [...rows, ...firm];
  const initial = Object.fromEntries(all.map((r) => [r.key, r.input_text]));
  const [values, setValues] = useState<Record<string, string>>({ ...initial, ...(carry?.values ?? {}) });
  const [errors, setErrors] = useState<Record<string, string>>(carry?.errors ?? {});
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<string | null>(carry?.status ?? null);
  const back = view.context?.back ?? null;
  const by = Object.fromEntries(all.map((r) => [r.key, r]));
  const set = (key: string, v: string) => setValues((cur) => ({ ...cur, [key]: v }));

  if (view.economics_on === false) {
    return (
      <div className="space-y-4" data-testid="inputs-sheet">
        {back ? <BackLink back={back} /> : null}
        <p className="rounded-card bg-subtle px-4 py-3 text-pretty text-sm text-ink-2" data-testid="inputs-off">
          {view.economics_off_text}
        </p>
      </div>
    );
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    const changed = all.filter((r) => r.editable && (values[r.key] ?? "").trim() !== "" && values[r.key] !== r.input_text);
    setErrors({});
    if (!changed.length) {
      setStatus(t("inputs.nothingChanged"));
      return;
    }
    setBusy(true);
    setStatus(null);
    const failed: Record<string, string> = {};
    for (const r of changed) {
      try {
        await saveInput(r.scope === "firm" ? null : view.buyer_id, { field: r.field, value_text: values[r.key].trim(), provenance: "OWNER_ENTERED" }, lang);
      } catch (err) {
        failed[r.key] = errorText(err);
      }
    }
    setBusy(false);
    setErrors(failed);
    if (Object.keys(failed).length < changed.length) {
      // read again, so every value, provenance word and entered day shown is what the server now holds; a field that failed keeps what
      // the owner typed and the server's reason, and a field that saved starts again from the server's value (never sent twice)
      const kept = Object.fromEntries(Object.keys(failed).map((k) => [k, values[k]]));
      onSaved({ status: t("inputs.saved"), values: kept, errors: failed });
    }
  }

  const input = (r: InputSheetRow, extra = "") => {
    const errId = `${uid}-${r.key}-err`;
    const srcId = `${uid}-${r.key}-src`;
    return (
      <input
        id={`${uid}-${r.key}`}
        type="text"
        inputMode={r.key === "typical_delay" ? "numeric" : "text"}
        value={values[r.key] ?? ""}
        placeholder={r.key === "typical_delay" ? t("inputs.delay.placeholder") : undefined}
        onChange={(e) => set(r.key, e.target.value)}
        disabled={!r.editable || busy}
        aria-invalid={errors[r.key] ? true : undefined}
        aria-describedby={`${srcId}${errors[r.key] ? ` ${errId}` : ""}`}
        className={`${inputClass} min-h-11 w-full font-bold tabular-nums ${extra}`}
        data-testid={`inputs-input-${r.key}`}
      />
    );
  };

  const sales = by.annual_sales;
  const margin = by.gross_margin;
  const basis = by.margin_basis;
  const klass = by.classification;
  const delay = by.typical_delay;
  const picked = klass ? klass.options.find((o) => o.value === values.classification) : undefined;

  return (
    <div className="space-y-4" data-testid="inputs-sheet">
      {back ? <BackLink back={back} /> : null}
      <Card labelledBy={`${uid}-title`}>
        <form onSubmit={submit} noValidate className="space-y-5">
          <div>
            <p className="text-xs font-extrabold uppercase tracking-[0.06em] text-ink-3">
              {view.eyebrow_text ?? t("inputs.eyebrow")}
            </p>
            <h1 id={`${uid}-title`} className="mt-1.5 font-display text-2xl font-extrabold tracking-[-0.02em] text-ink">
              {t("inputs.heading")}
            </h1>
            <p className="mt-1.5 text-pretty text-sm leading-relaxed text-ink-2">{t("inputs.intro")}</p>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            {sales ? (
              <div className="flex min-w-0 flex-col gap-1.5">
                <label htmlFor={`${uid}-${sales.key}`} className="text-[13px] font-bold text-ink">
                  {sales.label}
                </label>
                {input(sales)}
                <Source row={sales} id={`${uid}-${sales.key}-src`} />
                <FieldError text={errors[sales.key]} id={`${uid}-${sales.key}-err`} />
              </div>
            ) : null}
            {margin ? (
              <div className="flex min-w-0 flex-col gap-1.5">
                <label htmlFor={`${uid}-${margin.key}`} className="text-[13px] font-bold text-ink">
                  {margin.label}
                </label>
                <div className="flex gap-2">
                  {input(margin, "min-w-0 flex-1")}
                  {basis && basis.options.length ? (
                    <select
                      aria-label={basis.label}
                      aria-invalid={errors.margin_basis ? true : undefined}
                      aria-describedby={errors.margin_basis ? `${uid}-margin_basis-err` : undefined}
                      value={values.margin_basis ?? basis.input_text}
                      onChange={(e) => set("margin_basis", e.target.value)}
                      disabled={!basis.editable || busy}
                      className={`${inputClass} min-h-11 shrink-0 px-3 font-bold`}
                      data-testid="inputs-basis"
                    >
                      {basis.options.map((o) => (
                        <option key={o.value} value={o.value}>
                          {o.label}
                        </option>
                      ))}
                    </select>
                  ) : null}
                </div>
                <Source row={margin} id={`${uid}-${margin.key}-src`} />
                <FieldError text={errors[margin.key]} id={`${uid}-${margin.key}-err`} />
                <FieldError text={errors.margin_basis} id={`${uid}-margin_basis-err`} />
              </div>
            ) : null}
          </div>

          {view.consistency?.length ? (
            <div className="space-y-1.5 border-l-2 border-line-strong pl-3" data-testid="inputs-consistency">
              {view.consistency.map((c) => (
                <p key={c.key} className="text-pretty text-sm leading-relaxed text-ink-2" data-testid={`inputs-check-${c.key}`}>
                  <span className="font-bold text-ink">{c.lead}</span> {c.text}
                </p>
              ))}
            </div>
          ) : null}

          {klass ? (
            <div className="flex flex-col gap-1.5" data-testid="inputs-classification">
              <span id={`${uid}-class`} className="text-[13px] font-bold text-ink">
                {klass.label}
              </span>
              <div className="self-start" aria-describedby={errors[klass.key] ? `${uid}-${klass.key}-err` : undefined}>
                <SegmentedButtons
                  label={klass.label}
                  value={values.classification ?? ""}
                  onChange={(v) => klass.editable && !busy && set("classification", v)}
                  options={klass.options.map((o) => ({ value: o.value, label: o.label, testId: `inputs-class-${o.value}` }))}
                />
              </div>
              <p className="text-[13px] leading-relaxed text-ink-2" data-testid="inputs-class-note">
                {picked ? picked.note : klass.note}
              </p>
              {picked ? <p className="text-[13px] text-ink-2">{klass.note}</p> : null}
              <p className="text-[13px] font-bold text-ink-2" data-testid="inputs-provenance-classification">
                {[klass.provenance_text, klass.entered_day_text].filter(Boolean).join(" · ")}
              </p>
              <FieldError text={errors[klass.key]} id={`${uid}-${klass.key}-err`} />
            </div>
          ) : null}

          {delay ? (
            <div className="flex flex-col gap-1.5">
              <label htmlFor={`${uid}-${delay.key}`} className="text-[13px] font-bold text-ink">
                {delay.label}
              </label>
              <div className="max-w-60">{input(delay)}</div>
              <Source row={delay} id={`${uid}-${delay.key}-src`} />
              <FieldError text={errors[delay.key]} id={`${uid}-${delay.key}-err`} />
            </div>
          ) : null}

          {firm.length ? (
            <fieldset className="space-y-3 border-t border-line pt-4" data-testid="inputs-firm">
              <legend className="text-xs font-extrabold uppercase tracking-[0.06em] text-ink-3">{t("inputs.firm")}</legend>
              <div className="grid gap-4 sm:grid-cols-2">
                {firm.map((r) => (
                  <div key={r.key} className="flex min-w-0 flex-col gap-1.5">
                    <label htmlFor={`${uid}-${r.key}`} className="text-[13px] font-bold text-ink">
                      {r.label}
                    </label>
                    {input(r)}
                    <Source row={r} id={`${uid}-${r.key}-src`} />
                    <FieldError text={errors[r.key]} id={`${uid}-${r.key}-err`} />
                  </div>
                ))}
              </div>
              {view.vat_note ? (
                <p className="text-[13px] text-ink-2" data-testid="inputs-vat-note">
                  {view.vat_note}
                </p>
              ) : null}
            </fieldset>
          ) : null}

          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line pt-4">
            <p className="min-w-0 flex-[1_1_16rem] text-[13px] leading-relaxed text-ink-2">{view.footer_text}</p>
            <div className="flex gap-2">
              {back ? (
                <ButtonLink href={back.href} data-testid="inputs-cancel">
                  {t("inputs.cancel")}
                </ButtonLink>
              ) : null}
              <Button type="submit" variant="primary" loading={busy} data-testid="inputs-save">
                {busy ? t("inputs.saving") : t("inputs.save")}
              </Button>
            </div>
          </div>
          <p aria-live="polite" className="text-sm font-bold text-ink" data-testid="inputs-status">
            {status}
          </p>
        </form>
      </Card>
    </div>
  );
}

function BackLink({ back }: { back: { label: string; href: string } }) {
  return (
    <Link href={back.href} className="motion-press hit -ml-2 inline-flex min-h-8 items-center gap-1 rounded-pill px-2 text-sm font-bold text-brand-700 underline underline-offset-2 hover:bg-brand-50" data-testid="inputs-back">
      <ArrowLeftIcon width={14} height={14} />
      {back.label}
    </Link>
  );
}
