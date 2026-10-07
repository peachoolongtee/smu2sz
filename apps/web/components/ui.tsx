"use client";

import { useState, type ButtonHTMLAttributes, type ReactNode } from "react";
import { requestSignIn } from "@/lib/auth";
import { ApiError } from "@/lib/errors";
import { useI18n } from "@/lib/i18n";
import { CheckIcon, CopyIcon, Spinner } from "./icons";

export type Tone = "neutral" | "ok" | "warn" | "bad" | "info" | "brand";

const toneBadge: Record<Tone, string> = {
  neutral: "bg-subtle text-ink-2 border-line",
  ok: "bg-ok-bg text-ok-fg border-ok-line",
  warn: "bg-warn-bg text-warn-fg border-warn-line",
  bad: "bg-bad-bg text-bad-fg border-bad-line",
  info: "bg-info-bg text-info-fg border-info-line",
  brand: "bg-brand-50 text-brand-700 border-brand-100",
};

const toneBorder: Record<Tone, string> = {
  neutral: "border-line",
  ok: "border-ok-line",
  warn: "border-warn-line",
  bad: "border-bad-line",
  info: "border-info-line",
  brand: "border-brand-100",
};

const toneText: Record<Tone, string> = {
  neutral: "text-ink",
  ok: "text-ok-fg",
  warn: "text-warn-fg",
  bad: "text-bad-fg",
  info: "text-info-fg",
  brand: "text-brand-700",
};

export function Badge({
  tone = "neutral",
  children,
  title,
  className = "",
}: {
  tone?: Tone;
  children: ReactNode;
  title?: string;
  className?: string;
}) {
  return (
    <span
      title={title}
      className={`badge inline-flex items-center gap-1 whitespace-nowrap rounded-full border px-2 py-0.5 text-xs font-medium ${toneBadge[tone]} ${className}`}
    >
      {children}
    </span>
  );
}

export function PageHeader({
  title,
  subtitle,
  actions,
  icon,
}: {
  title: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
  /** A coloured icon tile beside the title (Business pages). */
  icon?: ReactNode;
}) {
  return (
    <header className="page-head mb-5 flex flex-wrap items-start justify-between gap-3">
      {icon ? <div className="shrink-0">{icon}</div> : null}
      <div className="min-w-0 flex-1">
        <h1 className="text-xl font-semibold tracking-tight text-ink">{title}</h1>
        {subtitle ? <p className="mt-1 max-w-3xl text-sm text-ink-2">{subtitle}</p> : null}
      </div>
      {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
    </header>
  );
}

export function Card({
  title,
  subtitle,
  actions,
  children,
  className = "",
  id,
  tone,
}: {
  title?: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
  id?: string;
  tone?: Tone;
}) {
  const border = tone ? toneBorder[tone] : "border-line";
  return (
    <section
      id={id}
      aria-labelledby={title && id ? `${id}-title` : undefined}
      className={`card min-w-0 rounded-(--radius-card) border bg-surface shadow-(--shadow-card) ${border} ${className}`}
    >
      {title ? (
        <div className="card-head flex flex-wrap items-start justify-between gap-2 border-b border-line px-4 py-3">
          <div className="min-w-0">
            <h2 id={id ? `${id}-title` : undefined} className="text-sm font-semibold text-ink">
              {title}
            </h2>
            {subtitle ? <p className="mt-0.5 text-xs text-ink-3">{subtitle}</p> : null}
          </div>
          {actions}
        </div>
      ) : null}
      <div className="card-body p-4">{children}</div>
    </section>
  );
}

export function Stat({
  label,
  value,
  hint,
  tone = "neutral",
  className = "",
}: {
  label: ReactNode;
  value: ReactNode;
  hint?: ReactNode;
  tone?: Tone;
  className?: string;
}) {
  return (
    <div className={`stat min-w-0 rounded-lg border border-line bg-surface px-3.5 py-3 ${className}`}>
      <dt className="text-xs font-medium text-ink-3">{label}</dt>
      <dd className={`mt-1 break-words text-lg font-semibold tabular-nums ${toneText[tone]}`}>{value}</dd>
      {hint ? <p className="mt-0.5 text-xs text-ink-3">{hint}</p> : null}
    </div>
  );
}

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";

const variantClass: Record<ButtonVariant, string> = {
  primary: "btn-primary bg-brand-600 text-white hover:bg-brand-700 border-transparent",
  secondary: "btn-secondary bg-surface text-ink border-line-strong hover:bg-subtle",
  ghost: "btn-ghost bg-transparent text-ink-2 border-transparent hover:bg-subtle",
  danger: "btn-danger bg-bad-fg text-white border-transparent hover:opacity-90",
};

export function Button({
  variant = "secondary",
  size = "md",
  loading = false,
  className = "",
  children,
  disabled,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  size?: "sm" | "md";
  loading?: boolean;
}) {
  return (
    <button
      type="button"
      {...rest}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={`btn inline-flex items-center justify-center gap-1.5 rounded-btn border font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${
        size === "sm" ? "btn-sm min-h-8 px-2.5 text-xs" : "btn-md min-h-10 px-3.5 text-sm"
      } ${variantClass[variant]} ${className}`}
    >
      {loading ? <Spinner /> : null}
      {children}
    </button>
  );
}

export function Skeleton({ className = "" }: { className?: string }) {
  return <div aria-hidden className={`animate-pulse rounded-md bg-subtle ${className}`} />;
}

export function LoadingBlock({ rows = 3, label }: { rows?: number; label?: string }) {
  const { t } = useI18n();
  return (
    <div role="status" aria-live="polite" className="space-y-3">
      <span className="sr-only">{label ?? t("common.loading")}</span>
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} className={i === 0 ? "h-8 w-1/3" : "h-16 w-full"} />
      ))}
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: Error | string; onRetry?: () => void }) {
  const { t } = useI18n();
  const message = typeof error === "string" ? error : error.message;
  // Being signed out is not a failure: the owner's pages ask for the sign-in instead of showing an error code.
  if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
    return (
      <div role="status" className="rounded-lg border border-line bg-surface p-5 text-center shadow-(--shadow-card)" data-testid="signin-needed">
        <p className="font-semibold text-ink">{t("auth.signinToSee")}</p>
        <p className="mx-auto mt-1 max-w-md text-sm text-ink-2">{error.status === 401 ? t("auth.signinToSee.body") : t("auth.signinToSee.forbidden")}</p>
        <Button className="mt-3" variant="primary" onClick={() => requestSignIn("required")}>
          {t("auth.signin")}
        </Button>
      </div>
    );
  }
  return (
    <div role="alert" className="rounded-lg border border-bad-line bg-bad-bg p-4 text-bad-fg">
      <p className="font-semibold">{t("common.error")}</p>
      <p className="mt-1 break-words text-sm">{message}</p>
      {onRetry ? (
        <Button className="mt-3" size="sm" onClick={onRetry}>
          {t("common.retry")}
        </Button>
      ) : null}
    </div>
  );
}

export function EmptyState({
  title,
  body,
  action,
}: {
  title: ReactNode;
  body?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="rounded-lg border border-dashed border-line-strong bg-surface px-6 py-10 text-center">
      <p className="text-sm font-semibold text-ink">{title}</p>
      {body ? <p className="mx-auto mt-1 max-w-md text-sm text-ink-2">{body}</p> : null}
      {action ? <div className="mt-4 flex justify-center">{action}</div> : null}
    </div>
  );
}

export function Callout({ tone = "info", title, children }: { tone?: Tone; title?: ReactNode; children: ReactNode }) {
  return (
    <div className={`rounded-lg border px-3.5 py-3 text-sm ${toneBadge[tone]}`}>
      {title ? <p className="font-semibold">{title}</p> : null}
      <div className={title ? "mt-0.5" : ""}>{children}</div>
    </div>
  );
}

/** Radio-group segmented control. Native radios give arrow-key navigation for free. */
export function Segmented<T extends string>({
  label,
  name,
  value,
  onChange,
  options,
}: {
  label: string;
  name: string;
  value: T;
  onChange: (v: T) => void;
  options: { value: T; label: ReactNode }[];
}) {
  return (
    <fieldset className="min-w-0">
      <legend className="sr-only">{label}</legend>
      <div className="seg inline-flex rounded-md border border-line-strong bg-subtle p-0.5">
        {options.map((o) => (
          <label
            key={o.value}
            className="seg-opt relative cursor-pointer whitespace-nowrap rounded px-3 py-1.5 text-xs font-medium text-ink-2 has-checked:bg-surface has-checked:text-ink has-checked:shadow-sm has-focus-visible:outline-2 has-focus-visible:outline-brand-600"
          >
            <input
              type="radio"
              name={name}
              value={o.value}
              checked={value === o.value}
              onChange={() => onChange(o.value)}
              className="absolute inset-0 cursor-pointer opacity-0"
            />
            {o.label}
          </label>
        ))}
      </div>
    </fieldset>
  );
}

/** Horizontally scrollable table region that remains keyboard-scrollable. */
export function TableWrap({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div
      role="region"
      aria-label={label}
      tabIndex={0}
      className="overflow-x-auto rounded-lg border border-line bg-surface"
    >
      {children}
    </div>
  );
}

export const tableCls = "w-full border-collapse text-left text-sm [&_tbody_tr:last-child_td]:border-b-0 [&_tbody_tr:last-child_th]:border-b-0";
export const thCls = "whitespace-nowrap border-b border-line bg-subtle px-3 py-2 text-xs font-semibold text-ink-2";
export const tdCls = "border-b border-line px-3 py-2 align-top";

/** Shortened hash with the full value on hover and a copy button. */
export function Hash({ value, className = "" }: { value: string | null; className?: string }) {
  const { t } = useI18n();
  const [copied, setCopied] = useState(false);
  if (!value) return <span className="text-ink-3">{t("common.none")}</span>;
  const short = value.length > 20 ? `${value.slice(0, 10)}…${value.slice(-6)}` : value;
  return (
    <span className={`inline-flex items-center gap-1 font-mono text-xs ${className}`}>
      <span title={value}>{short}</span>
      <button
        type="button"
        aria-label={t("common.copy")}
        className="rounded p-1 text-ink-3 hover:bg-subtle hover:text-ink"
        onClick={() => {
          void navigator.clipboard?.writeText(value).then(() => {
            setCopied(true);
            setTimeout(() => setCopied(false), 1200);
          });
        }}
      >
        {copied ? <CheckIcon /> : <CopyIcon />}
      </button>
    </span>
  );
}

export function Formula({ children }: { children: ReactNode }) {
  return (
    <code className="block break-words rounded-md border border-line bg-subtle px-2.5 py-1.5 font-mono text-xs leading-relaxed text-ink">
      {children}
    </code>
  );
}

export function KeyValueList({ items }: { items: { k: ReactNode; v: ReactNode }[] }) {
  return (
    <dl className="grid grid-cols-1 gap-x-4 gap-y-0.5 text-sm sm:grid-cols-[minmax(0,max-content)_minmax(0,1fr)] sm:gap-y-1.5">
      {items.map((it, i) => (
        <div key={i} className="contents">
          {/* Stacked on a phone (the label above its value), side by side from the small breakpoint up. */}
          <dt className={`text-ink-3 ${i > 0 ? "mt-1.5 sm:mt-0" : ""}`}>{it.k}</dt>
          <dd className="min-w-0 break-words font-medium tabular-nums text-ink">{it.v}</dd>
        </div>
      ))}
    </dl>
  );
}
