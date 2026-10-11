"use client";

import Link from "next/link";
import { useState, type ComponentProps, type ReactNode } from "react";
import { requestSignIn } from "@/lib/auth";
import { ApiError, isTimeout } from "@/lib/errors";
import { useI18n } from "@/lib/i18n";
import { errorText } from "@/lib/error-text";
import { usePathname } from "next/navigation";
import { shellFor, useMode } from "@/lib/mode";
import { CheckIcon, CopyIcon, Spinner } from "./icons";
import { PageIcon, type Section, type SectionIcon } from "./section";

export type Tone = "neutral" | "ok" | "warn" | "bad" | "info" | "brand";

const toneBadge: Record<Tone, string> = {
  neutral: "bg-subtle text-ink-2 border-line",
  ok: "bg-ok-bg text-ok-fg border-ok-line",
  warn: "bg-warn-bg text-warn-fg border-warn-line",
  bad: "bg-bad-bg text-bad-fg border-bad-line",
  info: "bg-info-bg text-info-fg border-info-line",
  brand: "bg-brand-50 text-brand-700 border-brand-100",
};

/** A callout's surface: the tone's tint and line; its title takes the tone's fg and its body stays in ink-2. */
const toneSurface: Record<Tone, string> = {
  neutral: "bg-subtle border-line",
  ok: "bg-ok-bg border-ok-line",
  warn: "bg-warn-bg border-warn-line",
  bad: "bg-bad-bg border-bad-line",
  info: "bg-info-bg border-info-line",
  brand: "bg-brand-50 border-brand-100",
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

/** The solid mark beside a status word: a 6 px dot that must be seen on its own tint (3:1). Colour never speaks alone: the word is always there. */
const toneDot: Partial<Record<Tone, string>> = { ok: "bg-ok-solid", warn: "bg-warn-solid", bad: "bg-bad-solid", info: "bg-info-solid" };

/** A tinted status pill (bg, line, fg) with its solid dot; neutral and brand badges (a tier, a count, "Recommended") carry no status and no dot. */
export function Badge({
  tone = "neutral",
  children,
  title,
  className = "",
  dot = true,
  wrap = false,
}: {
  tone?: Tone;
  children: ReactNode;
  title?: string;
  className?: string;
  /** False where the label has its own mark (a glyph). */
  dot?: boolean;
  /** A label that is a whole sentence from the server may wrap (and never wider than its row) instead of running off a phone. */
  wrap?: boolean;
}) {
  const mark = dot ? toneDot[tone] : undefined;
  return (
    <span
      title={title}
      className={`inline-flex items-center gap-1 rounded-pill border px-2.5 py-0.5 text-xs font-medium ${wrap ? "max-w-full" : "whitespace-nowrap"} ${toneBadge[tone]} ${className}`}
    >
      {mark ? <span aria-hidden className={`size-1.5 shrink-0 rounded-full ${mark}`} /> : null}
      {children}
    </span>
  );
}

/** The mark that goes with a state's words, one per tone, so a state is never colour alone. */
const toneGlyph: Record<Tone, string> = { ok: "✓", warn: "▲", bad: "■", info: "◆", brand: "◆", neutral: "○" };

/**
 * A state as the server names it: the words, a glyph for the tone (never colour alone) and the tone the SERVER chose (`state_tone` /
 * `result_tone`; the browser never colours a state itself). 12 px, the same pill as `Badge`, with a mark of its own instead of the dot.
 */
export function StatePill({ tone, children, testId, wrap = true }: { tone: Tone; children: ReactNode; testId?: string; wrap?: boolean }) {
  return (
    <span data-testid={testId} data-tone={tone}>
      <Badge tone={tone} dot={false} wrap={wrap}>
        <span aria-hidden className="text-xs leading-none">
          {toneGlyph[tone]}
        </span>
        {children}
      </Badge>
    </span>
  );
}

/** A small tag that carries no status (a channel, a kind, a count): a Badge without the dot. Same pill, same tones. */
export function Chip({ tone = "neutral", children, title, className = "", wrap }: { tone?: Tone; children: ReactNode; title?: string; className?: string; wrap?: boolean }) {
  return (
    <Badge tone={tone} title={title} dot={false} className={className} wrap={wrap}>
      {children}
    </Badge>
  );
}

/**
 * A page's title. With `section` (the Business pages and Approvals) the title takes its section's round icon chip, in the
 * Business shell only: the Demo shell keeps the flat look.
 */
export function PageHeader({
  title,
  subtitle,
  actions,
  section,
  icon,
}: {
  title: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
  section?: Section;
  /** The chip's glyph when the page is not the section's own (Approvals and Limits sit under Home). */
  icon?: SectionIcon;
}) {
  const mode = useMode();
  const pathname = usePathname();
  const chip = section && shellFor(pathname, mode) === "business";
  return (
    <header className="motion-reveal mb-5 flex flex-wrap items-start justify-between gap-3">
      <div className="flex min-w-0 items-start gap-3">
        {chip ? <PageIcon section={section} icon={icon} /> : null}
        <div className="min-w-0">
          <h1 className={`text-balance font-display text-2xl font-normal tracking-tight text-ink sm:text-[1.75rem] ${chip ? "leading-10" : ""}`}>{title}</h1>
          {subtitle ? <p className="mt-1 max-w-3xl text-pretty text-sm text-ink-2">{subtitle}</p> : null}
        </div>
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
      className={`motion-reveal min-w-0 rounded-card border bg-surface shadow-card ${border} ${className}`}
    >
      {title ? (
        <div className="flex flex-wrap items-start justify-between gap-2 px-5 pt-4">
          <div className="min-w-0">
            <h2 id={id ? `${id}-title` : undefined} className="text-balance text-base font-bold text-ink">
              {title}
            </h2>
            {subtitle ? <p className="mt-0.5 text-pretty text-xs text-ink-3">{subtitle}</p> : null}
          </div>
          {actions}
        </div>
      ) : null}
      <div className={title ? "px-5 pb-5 pt-3" : "p-5"}>{children}</div>
    </section>
  );
}

/** A figure on the deep block takes its status's bright tone (the plain tone is for a white surface); a neutral figure is white. */
const toneOnDeep: Record<Tone, string> = {
  neutral: "text-on-deep",
  ok: "text-ok-bright",
  warn: "text-warn-bright",
  bad: "text-bad-bright",
  info: "text-info-bright",
  brand: "text-on-deep",
};

/**
 * The one fact tile: an uppercase eyebrow (what it is), the figure (`tabular-nums`, 20 px, 24 px with `size="lg"`), a quiet caption
 * (when, of what, against what) and, only when the server sent one, a delta chip. Two surfaces: `surface` (white, hairline) and
 * `deep` (translucent white on the navy Home hero). The figure takes a status colour only when `tone` names a status; a delta
 * chip is neutral unless the server names its tone (the browser never subtracts). `testId` goes on the figure, so a spec can read
 * it; the tile is a `<div>` and belongs in a `<dl>`. `hint` is the older name of `caption`.
 */
export function Stat({
  label,
  value,
  caption,
  hint,
  tone = "neutral",
  delta,
  deltaTone = "neutral",
  surface = "surface",
  size = "md",
  tint = false,
  testId,
  captionTestId,
  rootTestId,
  row = false,
  press,
  className = "",
}: {
  label: ReactNode;
  value: ReactNode;
  caption?: ReactNode;
  hint?: ReactNode;
  tone?: Tone;
  /** The server's `delta_display` ("+3.5%"); its tone is a status only when the server names one. */
  delta?: ReactNode;
  deltaTone?: Tone;
  surface?: "surface" | "deep";
  size?: "md" | "lg";
  /** A status-tinted tile (the owner must decide; within limits): the tone's tint and line instead of the hairline. */
  tint?: boolean;
  testId?: string;
  captionTestId?: string;
  /** On the tile itself, for a spec that reads the label, figure and caption together. */
  rootTestId?: string;
  /** Below the small breakpoint the tile is one row (the label, then the figure at the right, the caption under both) so a phone reads several facts in a few lines; from `sm` it is the tile. */
  row?: boolean;
  /** A tile that leads somewhere on this page (a filter): one quiet text button, stretched over the whole tile like a link tile's link. */
  press?: { label: string; onPress: () => void; testId?: string };
  className?: string;
}) {
  const deep = surface === "deep";
  const note = caption ?? hint;
  const box = deep ? "bg-on-deep/10" : tint && tone !== "neutral" ? `border ${toneSurface[tone]}` : "border border-line bg-surface";
  return (
    <div className={`min-w-0 rounded-tile px-4 py-3 ${press ? "motion-lift relative hover:bg-subtle" : ""} ${row ? "max-sm:flex max-sm:flex-wrap max-sm:items-baseline max-sm:justify-between max-sm:gap-x-3 max-sm:py-1.5" : ""} ${box} ${className}`} data-testid={rootTestId}>
      <dt className={`text-xs font-semibold uppercase tracking-wide ${deep ? "text-on-deep-muted" : "text-ink-3"}`}>{label}</dt>
      <dd className={`mt-1 flex flex-wrap items-baseline gap-x-2 gap-y-1 font-semibold tabular-nums ${row ? "max-sm:mt-0 max-sm:justify-end max-sm:text-right" : ""} ${size === "lg" ? "text-xl sm:text-2xl" : "text-lg sm:text-xl"}`}>
        <span className={`min-w-0 break-words ${deep ? toneOnDeep[tone] : toneText[tone]}`} data-testid={testId}>
          {value}
        </span>
        {delta ? (
          <span className={`inline-flex items-center whitespace-nowrap rounded-pill border px-2 py-0.5 text-xs font-medium ${deep ? "border-on-deep/20 bg-on-deep/10 text-on-deep" : toneBadge[deltaTone]}`}>{delta}</span>
        ) : null}
      </dd>
      {note ? (
        <dd className={`mt-0.5 text-xs ${row ? "max-sm:mt-0 max-sm:basis-full" : ""} ${deep ? "text-on-deep-muted" : "text-ink-3"}`} data-testid={captionTestId}>
          {note}
        </dd>
      ) : null}
      {press ? (
        <dd className="mt-0.5 text-xs">
          <button type="button" onClick={press.onPress} className="rounded-pill font-medium text-brand-700 underline underline-offset-2 after:absolute after:inset-0 after:rounded-tile" data-testid={press.testId}>
            {press.label}
          </button>
        </dd>
      ) : null}
    </div>
  );
}

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";
type ButtonSize = "sm" | "md";

const variantClass: Record<ButtonVariant, string> = {
  primary: "bg-brand-600 text-white hover:bg-brand-700 border-transparent",
  secondary: "bg-surface text-ink border-line-ui hover:bg-subtle",
  ghost: "bg-transparent text-ink-2 border-transparent hover:bg-subtle hover:text-ink",
  danger: "bg-bad-solid text-white border-transparent hover:brightness-90",
};

/**
 * The one button shape: a pill, 40 px tall (32 px compact; 44 px wherever a finger is the pointer, the `touch:` variant), 16 px of padding, medium weight. Primary is the brand fill (one per
 * page); secondary a line-ui outline; ghost text only; danger is the destructive fill. `Button` and `ButtonLink` both wear it,
 * so a link that looks like a button is the same button.
 */
export function buttonClass(variant: ButtonVariant = "secondary", size: ButtonSize = "md", className = ""): string {
  return `motion-press inline-flex items-center justify-center gap-1.5 whitespace-nowrap rounded-control border font-semibold disabled:cursor-not-allowed disabled:opacity-50 ${
    size === "sm" ? "min-h-8 px-3 text-xs touch:min-h-11" : "min-h-10 px-4 text-sm touch:min-h-11"
  } ${variantClass[variant]} ${className}`;
}

export function Button({
  variant = "secondary",
  size = "md",
  loading = false,
  className = "",
  children,
  disabled,
  ...rest
}: ComponentProps<"button"> & {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
}) {
  return (
    <button type="button" {...rest} disabled={disabled || loading} aria-busy={loading || undefined} className={buttonClass(variant, size, className)}>
      {loading ? <Spinner /> : null}
      {children}
    </button>
  );
}

/** A pill that toggles (a preset, a scene): the selected one takes the brand tint and a brand boundary, the rest are secondary buttons. */
export function toggleClass(active: boolean, size: ButtonSize = "md", className = ""): string {
  return `motion-press inline-flex items-center justify-center gap-1.5 whitespace-nowrap rounded-control border font-semibold disabled:cursor-not-allowed disabled:opacity-50 ${
    size === "sm" ? "min-h-8 px-3 text-xs touch:min-h-11" : "min-h-10 px-4 text-sm touch:min-h-11"
  } ${active ? "border-brand-600 bg-brand-50 text-brand-700" : "border-line-ui bg-surface text-ink hover:bg-subtle"} ${className}`;
}

/** A quiet text link in a card's header or a sentence (the "open" links): brand-700 on white is 7.7:1. */
export const textLinkClass = "motion-press hit inline-flex min-h-8 items-center rounded-pill px-2 text-xs font-medium text-brand-700 underline underline-offset-2 hover:bg-brand-50";

/** A link in a button's shape (a navigation that is the page's next step). */
export function ButtonLink({ variant = "secondary", size = "md", className = "", ...rest }: ComponentProps<typeof Link> & { variant?: ButtonVariant; size?: ButtonSize }) {
  return <Link {...rest} className={buttonClass(variant, size, className)} />;
}

/** Text fields: a pill, 40 px tall, a line-ui boundary (3:1). A multi-line field takes `textareaClass`. */
export const inputClass = "min-h-10 rounded-control border border-line-ui bg-surface px-4 text-sm text-ink placeholder:text-ink-3";
export const textareaClass = "rounded-card border border-line-ui bg-surface px-4 py-2.5 text-sm leading-relaxed text-ink placeholder:text-ink-3";

export function Skeleton({ className = "" }: { className?: string }) {
  return <div aria-hidden className={`animate-pulse rounded-tile bg-subtle ${className}`} />;
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

/**
 * "This is taking longer than usual…": a request that ran out of time is not a refusal and not a verdict. A read is simply read again;
 * for a write that may already have landed the caller's Retry reads the current state first (`note` then says it did). Never red: nothing
 * is known to have failed.
 */
export function SlowNotice({ message, onRetry, note }: { message: string; onRetry?: () => void; note?: string | null }) {
  const { t } = useI18n();
  return (
    <div role="status" className="motion-reveal rounded-card border border-warn-line bg-warn-bg p-4 text-warn-fg" data-testid="slow-notice">
      <p className="font-semibold">{message}</p>
      {note ? (
        <p className="mt-1 text-sm" data-testid="slow-checked">
          {note}
        </p>
      ) : null}
      {onRetry ? (
        <Button className="mt-3" size="sm" onClick={onRetry} data-testid="slow-retry">
          {t("common.retry")}
        </Button>
      ) : null}
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: Error | string; onRetry?: () => void }) {
  const { t } = useI18n();
  const message = typeof error === "string" ? error : errorText(error, t);
  if (isTimeout(error)) return <SlowNotice message={message} onRetry={onRetry} />;
  // Being signed out is not a failure: the owner's pages ask for the sign-in in words instead of showing an error code.
  if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
    return (
      <div role="status" className="motion-reveal rounded-card border border-line bg-surface p-5 text-center shadow-card" data-testid="signin-needed">
        <p className="font-semibold text-ink">{t("auth.signinToSee")}</p>
        <p className="mx-auto mt-1 max-w-md text-sm text-ink-2">{error.status === 401 ? t("auth.signinToSee.body") : t("auth.signinToSee.forbidden")}</p>
        <Button className="mt-3" variant="primary" onClick={() => requestSignIn("required")}>
          {t("auth.signin")}
        </Button>
      </div>
    );
  }
  return (
    <div role="alert" className="motion-reveal rounded-card border border-bad-line bg-bad-bg p-4">
      <p className="font-semibold text-bad-fg">{t("common.error")}</p>
      <p className="mt-1 break-words text-sm text-ink-2">{message}</p>
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
    <div className="motion-reveal rounded-card border border-dashed border-line-strong bg-surface px-6 py-10 text-center">
      <p className="text-balance text-sm font-semibold text-ink">{title}</p>
      {body ? <p className="mx-auto mt-1 max-w-md text-pretty text-sm text-ink-2">{body}</p> : null}
      {action ? <div className="mt-4 flex justify-center">{action}</div> : null}
    </div>
  );
}

export function Callout({ tone = "info", title, children }: { tone?: Tone; title?: ReactNode; children: ReactNode }) {
  return (
    <div className={`rounded-tile border px-3.5 py-3 text-sm ${toneSurface[tone]}`}>
      {title ? <p className={`font-semibold ${toneText[tone]}`}>{title}</p> : null}
      <div className={`text-ink-2 ${title ? "mt-0.5" : ""}`}>{children}</div>
    </div>
  );
}

/**
 * The pill track of a segmented control, with its sliding pill thumb. The thumb is one option wide (the options share the width
 * equally) and moves by transform to the selected option; with nothing selected it hides.
 */
function SegmentedTrack({ count, index, role, label, children }: { count: number; index: number; role?: "group"; label?: string; children: ReactNode }) {
  return (
    <div
      role={role}
      aria-label={label}
      className="relative inline-grid auto-cols-fr grid-flow-col rounded-pill border border-line-ui bg-subtle p-0.5"
      style={{ ["--n" as string]: count }}
    >
      <span
        aria-hidden
        className={`motion-slide pointer-events-none absolute inset-y-0.5 left-0.5 w-[calc((100%-0.25rem)/var(--n))] rounded-pill bg-surface shadow-card ${index < 0 ? "opacity-0" : ""}`}
        style={{ transform: `translateX(${Math.max(index, 0) * 100}%)` }}
      />
      {children}
    </div>
  );
}

const segmentedOption = "hit relative z-10 grid min-h-8 cursor-pointer place-items-center whitespace-nowrap rounded-pill px-3.5 text-xs font-medium transition-colors";

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
      <SegmentedTrack count={options.length} index={options.findIndex((o) => o.value === value)}>
        {options.map((o) => (
          <label
            key={o.value}
            className={`${segmentedOption} has-focus-visible:outline-2 has-focus-visible:outline-offset-2 has-focus-visible:outline-focus ${value === o.value ? "text-ink" : "text-ink-2 hover:text-ink"}`}
          >
            <input
              type="radio"
              name={name}
              value={o.value}
              checked={value === o.value}
              onChange={() => onChange(o.value)}
              className="absolute inset-0 z-10 cursor-pointer opacity-0"
            />
            {o.label}
          </label>
        ))}
      </SegmentedTrack>
    </fieldset>
  );
}

/** The same pill track made of toggle buttons (`aria-pressed`), for a choice that is a view (a horizon), not a form field. */
export function SegmentedButtons<T extends string | number>({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: T;
  onChange: (v: T) => void;
  options: { value: T; label: ReactNode; testId?: string }[];
}) {
  return (
    <SegmentedTrack role="group" label={label} count={options.length} index={options.findIndex((o) => o.value === value)}>
      {options.map((o) => (
        <button
          key={String(o.value)}
          type="button"
          onClick={() => onChange(o.value)}
          aria-pressed={value === o.value}
          data-testid={o.testId}
          className={`${segmentedOption} ${value === o.value ? "text-ink" : "text-ink-2 hover:text-ink"}`}
        >
          {o.label}
        </button>
      ))}
    </SegmentedTrack>
  );
}

/** Horizontally scrollable table region that remains keyboard-scrollable. */
export function TableWrap({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div
      role="region"
      aria-label={label}
      tabIndex={0}
      className="overflow-x-auto rounded-card border border-line bg-surface"
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
        className="hit rounded-pill p-1 text-ink-3 hover:bg-subtle hover:text-ink"
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
    <code className="block break-words rounded-tile border border-line bg-subtle px-2.5 py-1.5 font-mono text-xs leading-relaxed text-ink">
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
