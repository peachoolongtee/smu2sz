"use client";

import type { ReactNode } from "react";
import { inputClass } from "@/components/ui";

/**
 * The setup's form pieces (ADR-0013). Every value is the text the owner typed; the server parses and checks it. A field the server
 * named in an issue is marked invalid (`issue` is the server's sentence, read out under the field).
 */

const invalidCls = "border-bad-solid ring-1 ring-bad-solid";

export function Field({ label, hint, issue, children, className = "" }: { label: ReactNode; hint?: ReactNode; issue?: string; children: ReactNode; className?: string }) {
  return (
    <label className={`flex min-w-0 flex-col gap-1.5 text-sm font-semibold text-ink ${className}`}>
      {label}
      {children}
      {issue ? <span className="text-meta font-medium text-bad">{issue}</span> : hint ? <span className="text-meta font-normal text-ink-3">{hint}</span> : null}
    </label>
  );
}

type InputProps = {
  value: string | number | null | undefined;
  onChange: (v: string) => void;
  invalid?: boolean;
  placeholder?: string;
  label?: string;
  className?: string;
  type?: "text" | "date" | "number" | "password";
  /** The field's narrowest width inside a table row: names "lg", amounts and dates "md" (default), day counts "sm". */
  size?: "sm" | "md" | "lg";
  inputMode?: "decimal" | "numeric" | "text";
  testId?: string;
};

const MIN_W = { sm: "min-w-20", md: "min-w-32", lg: "min-w-48" } as const;

export function TextInput({ value, onChange, invalid, placeholder, label, className = "", type = "text", inputMode, testId, size = "md" }: InputProps) {
  return (
    <input
      type={type}
      value={value ?? ""}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      aria-label={label}
      aria-invalid={invalid || undefined}
      inputMode={inputMode}
      data-testid={testId}
      className={`${inputClass} w-full ${MIN_W[size]} font-normal ${invalid ? invalidCls : ""} ${className}`}
    />
  );
}

export const MoneyInput = (p: InputProps) => <TextInput inputMode="decimal" {...p} />;
export const DateInput = (p: InputProps) => <TextInput type="date" {...p} />;

/** A whole number of days or months; blank is null. */
export function IntInput({ value, onChange, ...rest }: Omit<InputProps, "onChange" | "value"> & { value: number | null | undefined; onChange: (v: number | null) => void }) {
  return (
    <TextInput
      inputMode="numeric"
      size="sm"
      value={value ?? ""}
      onChange={(v) => {
        const n = v.trim() === "" ? null : Number(v.replace(/[^0-9]/g, ""));
        onChange(n === null || Number.isNaN(n) ? null : n);
      }}
      {...rest}
    />
  );
}

export function Select<T extends string>({ value, onChange, options, label, invalid, testId }: { value: T; onChange: (v: T) => void; options: { value: T; label: string }[]; label?: string; invalid?: boolean; testId?: string }) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value as T)}
      aria-label={label}
      aria-invalid={invalid || undefined}
      data-testid={testId}
      className={`${inputClass} w-full min-w-40 pr-8 font-normal ${invalid ? invalidCls : ""}`}
    >
      {options.map((o) => (
        <option key={o.value} value={o.value}>
          {o.label}
        </option>
      ))}
    </select>
  );
}

/** A small "Remove" button for a table row or a card. */
export function RemoveButton({ onClick, label }: { onClick: () => void; label: string }) {
  return (
    <button type="button" onClick={onClick} aria-label={label} title={label} className="motion-press hit grid size-9 place-items-center rounded-pill text-ink-3 hover:bg-subtle hover:text-bad">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden>
        <path d="M18 6 6 18M6 6l12 12" />
      </svg>
    </button>
  );
}

/** The add-a-row link under a table ("+ Add a source"). */
export function AddButton({ onClick, children, testId }: { onClick: () => void; children: ReactNode; testId?: string }) {
  return (
    <button type="button" onClick={onClick} data-testid={testId} className="motion-press inline-flex min-h-10 items-center rounded-control border border-brand-600 px-4 text-sm font-semibold text-brand-700 hover:bg-brand-50">
      {children}
    </button>
  );
}

/** Issues keyed by the server's field path, for one step. */
export type Issues = Record<string, string>;
