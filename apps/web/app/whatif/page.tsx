"use client";

import { useState } from "react";
import { WhatIfControlsCard } from "@/components/whatif-controls";
import {
  WhatIfCashCard,
  WhatIfCountersCard,
  WhatIfCovenantsCard,
  WhatIfMeterCard,
  WhatIfPlanCard,
  WhatIfTestedCard,
  WhatIfVerdictCard,
} from "@/components/whatif-results";
import { Badge, Callout, ErrorState, LoadingBlock, PageHeader } from "@/components/ui";
import { useI18n } from "@/lib/i18n";
import type { WhatIfParams } from "@/lib/types";
import { useWhatIf } from "./use-whatif";

/** The buyer's actual offer (EX01): the page opens on it so the first thing shown is the real problem. */
const START: WhatIfParams = { terms_days: 60, discount_bp: 120, rebate_bp: 100, price_adjustment_bp: 0, settle_face_fen: null };

export default function WhatIfPage() {
  const { t } = useI18n();
  const [params, setParams] = useState<WhatIfParams>(START);
  const { result, error, loading, reload } = useWhatIf(params);
  const near = result?.mock_nearest;

  return (
    <>
      <PageHeader
        title={t("whatif.title")}
        subtitle={t("whatif.subtitle")}
        actions={<Badge tone="info">{t("whatif.hypothetical")}</Badge>}
      />

      {!result ? (
        error ? (
          <ErrorState error={error} onRetry={reload} />
        ) : (
          <LoadingBlock rows={4} />
        )
      ) : (
        <div className="grid gap-6 lg:grid-cols-[minmax(0,22rem)_minmax(0,1fr)]">
          <div className="lg:sticky lg:top-4 lg:self-start">
            <WhatIfControlsCard controls={result.controls} params={params} onChange={setParams} />
          </div>

          <div className={`min-w-0 space-y-6 transition-opacity ${loading ? "opacity-75" : ""}`} aria-busy={loading}>
            {error ? <ErrorState error={error} onRetry={reload} /> : null}
            {near ? (
              <Callout tone="warn">
                {t("whatif.mockNearest", {
                  terms: near.params.terms_days,
                  discount: result.controls.rate_labels[String(near.params.discount_bp)] ?? "",
                  rebate: result.controls.rate_labels[String(near.params.rebate_bp)] ?? "",
                })}
              </Callout>
            ) : null}
            <WhatIfVerdictCard r={result} loading={loading} />
            <WhatIfCashCard r={result} />
            <div className="grid gap-6 xl:grid-cols-2">
              <WhatIfMeterCard r={result} />
              <div className="space-y-6">
                <WhatIfCovenantsCard r={result} />
                <WhatIfPlanCard r={result} />
              </div>
            </div>
            <WhatIfCountersCard r={result} />
            <WhatIfTestedCard r={result} />
          </div>
        </div>
      )}
    </>
  );
}
