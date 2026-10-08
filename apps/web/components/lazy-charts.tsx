"use client";

import dynamic from "next/dynamic";
import { LoadingBlock } from "@/components/ui";

/**
 * The recharts-backed views, loaded when a page that draws one is opened (recharts is about a third of the JavaScript of those
 * pages and none of the others). Each stands in with the page's own loading block, at the chart's height so the page does not jump
 * when the chart arrives. Browser-only: a chart measures its box, so there is nothing to render on the server.
 */
const Placeholder = () => (
  <div className="min-h-64 sm:min-h-80">
    <LoadingBlock rows={2} />
  </div>
);

export const CashForecast = dynamic(() => import("@/components/business/cash-forecast").then((m) => m.CashForecast), { ssr: false, loading: Placeholder });
export const CashChart = dynamic(() => import("@/components/charts").then((m) => m.CashChart), { ssr: false, loading: Placeholder });
export const DebtChart = dynamic(() => import("@/components/charts").then((m) => m.DebtChart), { ssr: false, loading: Placeholder });
export const ConcessionMeter = dynamic(() => import("@/components/charts").then((m) => m.ConcessionMeter), { ssr: false, loading: Placeholder });
