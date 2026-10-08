"use client";

import Link from "next/link";
import { ClockIcon } from "@/components/icons";
import { Avatar, Row } from "@/components/business/kit";
import { buttonClass, Card, textLinkClass } from "@/components/ui";
import { useI18n } from "@/lib/i18n";
import type { DecisionSummary } from "@/lib/types";

/** The path of a decision's record page. The id carries colons, so it is encoded. */
export const decisionHref = (id: string): string => `/decisions/${encodeURIComponent(id)}`;

/**
 * What is left after a cure that did not restore the reserve (F17): the server's sentence and the supported routes it names, as links.
 * The page never invents a cure and never waives the reserve; this block only says it still needs the owner's decision and where to look.
 * With no approval waiting it is the page's one primary: its first route (the server lists them in order) is the filled button.
 */
export function RemainingTaskBlock({ text, links, decisionId, primary = false }: { text: string; links: { label: string; href: string }[]; decisionId?: string | null; primary?: boolean }) {
  const { t } = useI18n();
  return (
    <Card id="home-remaining" tone="warn" title={t("biz.remaining.title")} actions={decisionId ? <Link href={decisionHref(decisionId)} className={textLinkClass}>{t("biz.remaining.record")}</Link> : undefined}>
      <p className="text-sm text-ink" data-testid="home-remaining-text">
        {text}
      </p>
      {links.length ? (
        <ul className="mt-3 flex flex-wrap gap-2" data-testid="home-remaining-links" aria-label={t("biz.remaining.links")}>
          {links.map((l, i) => (
            <li key={l.href}>
              <Link href={l.href} className={buttonClass(primary && i === 0 ? "primary" : "secondary", "md", "max-w-full whitespace-normal text-center")}>
                {l.label}
              </Link>
            </li>
          ))}
        </ul>
      ) : null}
    </Card>
  );
}

/** Up to three decisions that are not finished, each with what it is waiting for and who: the record's own words, linking to the record. */
export function WaitingOnBlock({ decisions }: { decisions: DecisionSummary[] }) {
  const { t } = useI18n();
  return (
    <Card id="home-waiting-on" title={t("biz.waitingOn")} subtitle={t("biz.waitingOn.sub")}>
      <ul className="motion-rise -my-1 divide-y divide-line" data-testid="home-waiting-on-list">
        {decisions.map((d) => (
          <li key={d.id}>
            <Row
              testId={`home-open-${d.id}`}
              titleTestId="home-open-headline"
              href={decisionHref(d.id)}
              avatar={
                <Avatar tone={d.waiting_for.party === "owner" ? "warn" : "neutral"}>
                  <ClockIcon />
                </Avatar>
              }
              title={d.headline}
              sub={
                <>
                  <span className="font-medium text-ink-2" data-testid="home-open-state">
                    {d.state_text}
                  </span>
                  {" · "}
                  <span data-testid="home-open-waiting">{d.waiting_for.text}</span>
                </>
              }
              right={d.amount_display ?? undefined}
            />
          </li>
        ))}
      </ul>
    </Card>
  );
}
