"use client";

import { ToolTile } from "@/components/business/surface";
import { DocumentIcon } from "@/components/icons";
import { useI18n } from "@/lib/i18n";

/** The one tool at the head of Deals: attaching a deal's documents (the page is otherwise only the deals). */
export function DealTools() {
  const { t } = useI18n();
  return (
    <section aria-label={t("deals.tools")} className="mx-auto w-full md:w-1/2" data-testid="deal-tools" data-tour="deals-attach">
      <ToolTile className="min-h-40 items-center justify-center text-center sm:min-h-56" href="/documents" icon={DocumentIcon} title={t("deals.tools.attach")} body={t("deals.tools.attach.body")} testId="deal-tool-attach" />
    </section>
  );
}
