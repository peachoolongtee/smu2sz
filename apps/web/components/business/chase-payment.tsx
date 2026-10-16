"use client";

import { useEffect, useRef, useState } from "react";
import { Button, ButtonLink, ErrorState, LoadingBlock } from "@/components/ui";
import { getChase } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { useAsync } from "@/lib/use-async";

/**
 * "Chase payment" on an overdue or at-risk invoice: a secondary control that opens a native modal dialog (focus trapped, Esc to
 * close, focus back on the control) with the server's handoff for that invoice. The facts are the server's labelled rows, the
 * request is the server's text, and the one primary action is "Copy request" (the browser copies the text and writes nothing).
 * Nothing is sent from here: the owner pastes the request into their own mail or chat. "Open the buyer thread" shows when the
 * server says a deal thread exists.
 */
export function ChasePayment({
  receivableId,
  buyer,
  list = false,
  top = false,
  className = "",
  label,
  variant = "secondary",
  size = "sm",
  scope: scopeName,
}: {
  receivableId: string;
  buyer: string;
  /** The phone list's control: the page holds the table and the list at once (one hidden by the breakpoint), so their test ids and dialog ids differ. */
  list?: boolean;
  /** The button beside the top action sentence above the summary: its own test ids and dialog ids again. */
  top?: boolean;
  className?: string;
  /** The button's words when the server names the action ("Prepare reminder"); default "Chase payment". The dialog is the same handoff. */
  label?: string;
  variant?: "primary" | "secondary";
  size?: "sm" | "md";
  /** Test-id and dialog-id scope when the control sits in a place of its own (the selected invoice). */
  scope?: string;
}) {
  const { t } = useI18n();
  const ref = useRef<HTMLDialogElement>(null);
  const [open, setOpen] = useState(false);
  const scope = scopeName ?? (top ? "top-" : list ? "list-" : "");
  const words = label ?? t("biz.chase.button");
  const title = `chase-${scope}title-${receivableId}`;

  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) d.showModal();
    if (!open && d.open) d.close();
  }, [open]);

  return (
    <>
      <Button
        size={size}
        variant={variant}
        className={className}
        aria-haspopup="dialog"
        aria-label={`${words}: ${buyer}`}
        onClick={() => setOpen(true)}
        data-testid={`chase-${scope}open-${receivableId}`}
      >
        {words}
      </Button>
      <dialog
        ref={ref}
        aria-labelledby={title}
        data-testid={`chase-${scope}dialog-${receivableId}`}
        onClose={() => setOpen(false)}
        onClick={(e) => {
          if (e.target === e.currentTarget) setOpen(false);
        }}
        className="fixed inset-0 m-auto h-fit w-[min(36rem,calc(100vw-2rem))] max-h-[calc(100dvh-2rem)] overflow-y-auto rounded-card border border-line bg-surface p-5 text-ink shadow-pop backdrop:bg-ink/40"
      >
        {open ? <ChaseBody receivableId={receivableId} buyer={buyer} titleId={title} onClose={() => setOpen(false)} /> : null}
      </dialog>
    </>
  );
}

function ChaseBody({ receivableId, buyer, titleId, onClose }: { receivableId: string; buyer: string; titleId: string; onClose: () => void }) {
  const { t, lang } = useI18n();
  const chase = useAsync(() => getChase(receivableId, lang), [receivableId, lang]);
  const [copy, setCopy] = useState<"idle" | "copied" | "failed">("idle");
  const d = chase.data;

  const copyRequest = async () => {
    if (!d) return;
    try {
      await navigator.clipboard.writeText(d.request_text);
      setCopy("copied");
    } catch {
      setCopy("failed");
    }
  };

  return (
    <div className="space-y-4">
      <div>
        <h2 id={titleId} className="text-base font-semibold">
          {t("biz.chase.title")}: {buyer}
        </h2>
        <p className="mt-1 text-sm text-ink-2">{t("biz.chase.sub")}</p>
      </div>
      {chase.error ? (
        <ErrorState error={chase.error} onRetry={chase.reload} />
      ) : !d ? (
        <LoadingBlock rows={2} />
      ) : (
        <>
          <dl className="grid grid-cols-1 gap-x-4 gap-y-0.5 text-sm sm:grid-cols-[minmax(0,max-content)_minmax(0,1fr)] sm:gap-y-1.5" data-testid="chase-facts">
            {d.facts.map((f, i) => (
              <div key={f.id} className="contents" data-testid={`chase-fact-${f.id}`}>
                <dt className={`text-ink-3 ${i > 0 ? "mt-1.5 sm:mt-0" : ""}`}>{f.label}</dt>
                <dd className="min-w-0 break-words font-medium tabular-nums text-ink">{f.value}</dd>
              </div>
            ))}
          </dl>
          <div>
            <h3 className="text-sm font-semibold">{t("biz.chase.request")}</h3>
            <p className="mt-1 whitespace-pre-wrap break-words rounded-tile border border-line bg-subtle px-3 py-2 text-sm leading-relaxed text-ink" data-testid="chase-request">
              {d.request_text}
            </p>
          </div>
        </>
      )}
      <div className="flex flex-wrap items-center gap-2">
        {d ? (
          <Button variant="primary" className="min-h-11" onClick={() => void copyRequest()} data-testid="chase-copy">
            {t("biz.chase.copy")}
          </Button>
        ) : null}
        {d?.thread_href ? (
          <ButtonLink href={d.thread_href} className="min-h-11" data-testid="chase-thread">
            {t("biz.chase.thread")}
          </ButtonLink>
        ) : null}
        <Button variant="ghost" className="min-h-11" onClick={onClose} data-testid="chase-close">
          {t("biz.chase.close")}
        </Button>
        <span role="status" aria-live="polite" className="text-sm text-ink-2" data-testid="chase-copy-status">
          {copy === "copied" ? t("biz.chase.copied") : copy === "failed" ? t("biz.chase.copyfailed") : ""}
        </span>
      </div>
    </div>
  );
}
