"use client";

import Link from "next/link";
import { ButtonLink } from "@/components/ui";
import { useI18n } from "@/lib/i18n";
import { useSetupDraft } from "@/lib/setup-draft";

/**
 * The start of the setup (ADR-0013): what a new owner sees on Home before any books exist, and on /setup before the first step. Three
 * ways in: type it in (the six steps), a spreadsheet template (not built yet, and says so), or contracts first (step 3's reader).
 */
export function SetupWelcome() {
  const { t } = useI18n();
  const { touched } = useSetupDraft();
  return (
    <div className="space-y-6" data-testid="setup-welcome">
      <div className="space-y-2">
        <h1 className="type-headline text-balance text-ink">{t("setup.welcome.title")}</h1>
        <p className="max-w-[64ch] text-pretty text-base text-ink-2">{t("setup.welcome.body")}</p>
      </div>
      <div className="grid gap-4 md:grid-cols-3">
        <div className="flex flex-col gap-2 rounded-card border-2 border-brand-600 bg-brand-50 p-5">
          <span className="text-meta font-bold uppercase tracking-wide text-brand-700">{t("setup.welcome.type.tag")}</span>
          <strong className="text-base text-ink">{t("setup.welcome.type.title")}</strong>
          <p className="text-sm text-ink-2">{t("setup.welcome.type.body")}</p>
          <ButtonLink href="/setup?step=1" variant="primary" className="mt-auto" data-testid="setup-start">
            {touched ? t("setup.welcome.type.continue") : t("setup.welcome.type.cta")}
          </ButtonLink>
        </div>
        <div className="flex flex-col gap-2 rounded-card border border-line bg-surface p-5">
          <span className="text-meta font-bold uppercase tracking-wide text-ink-3">{t("setup.welcome.sheet.tag")}</span>
          <strong className="text-base text-ink">{t("setup.welcome.sheet.title")}</strong>
          <p className="text-sm text-ink-2">{t("setup.welcome.sheet.body")}</p>
          <span aria-disabled className="mt-auto inline-flex min-h-10 items-center justify-center rounded-control border border-dashed border-line-strong px-4 text-sm font-semibold text-ink-3">
            {t("setup.welcome.sheet.cta")}
          </span>
        </div>
        <div className="flex flex-col gap-2 rounded-card border border-line bg-surface p-5">
          <span className="text-meta font-bold uppercase tracking-wide text-ink-3">{t("setup.welcome.docs.tag")}</span>
          <strong className="text-base text-ink">{t("setup.welcome.docs.title")}</strong>
          <p className="text-sm text-ink-2">{t("setup.welcome.docs.body")}</p>
          <ButtonLink href="/setup?step=3&pick=1" className="mt-auto" data-testid="setup-contracts-first">
            {t("setup.welcome.docs.cta")}
          </ButtonLink>
        </div>
      </div>
      <div className="rounded-card border-2 border-dashed border-line-strong p-5 text-ink-3">
        <p className="text-sm font-semibold">{t("setup.welcome.placeholder.title")}</p>
        <p className="text-meta">{t("setup.welcome.placeholder.body")}</p>
      </div>
      <p className="text-meta text-ink-3">
        <Link href="/demo" className="underline underline-offset-2">
          {t("setup.welcome.demo")}
        </Link>
      </p>
    </div>
  );
}
