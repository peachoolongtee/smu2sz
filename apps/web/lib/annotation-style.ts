import type { ObligationType } from "./types";

/**
 * Colour AND line style per annotation kind, so the meaning never depends on colour alone:
 * obligations use solid underlines, flags use dashed/dotted ones, and every span carries a number.
 */
export type AnnotationKind = ObligationType | "DATA_REQUEST" | "AUTHORITY_CLAIM" | "FUNDING_CLAIM";

interface Style {
  mark: string;
  markActive: string;
  chip: string;
}

export const ANNOTATION_STYLE: Record<AnnotationKind, Style> = {
  IMMEDIATE_DISCOUNT: {
    mark: "bg-sky-100 decoration-sky-600 underline decoration-solid",
    markActive: "bg-sky-200 ring-2 ring-sky-600",
    chip: "border-sky-300 bg-sky-50 text-sky-900",
  },
  TERMS_EXTENSION: {
    mark: "bg-amber-100 decoration-amber-600 underline decoration-solid",
    markActive: "bg-amber-200 ring-2 ring-amber-600",
    chip: "border-amber-300 bg-amber-50 text-amber-900",
  },
  CONTINGENT_REBATE: {
    mark: "bg-violet-100 decoration-violet-600 underline decoration-solid",
    markActive: "bg-violet-200 ring-2 ring-violet-600",
    chip: "border-violet-300 bg-violet-50 text-violet-900",
  },
  VOLUME_COMMITMENT: {
    mark: "bg-teal-100 decoration-teal-600 underline decoration-solid",
    markActive: "bg-teal-200 ring-2 ring-teal-600",
    chip: "border-teal-300 bg-teal-50 text-teal-900",
  },
  OPERATIONAL_CONCESSION: {
    mark: "bg-lime-100 decoration-lime-700 underline decoration-solid",
    markActive: "bg-lime-200 ring-2 ring-lime-700",
    chip: "border-lime-300 bg-lime-50 text-lime-900",
  },
  PRICE_ADJUSTMENT: {
    mark: "bg-cyan-100 decoration-cyan-600 underline decoration-solid",
    markActive: "bg-cyan-200 ring-2 ring-cyan-600",
    chip: "border-cyan-300 bg-cyan-50 text-cyan-900",
  },
  CLAIMED_PRIOR_CONCESSION: {
    mark: "bg-red-100 decoration-red-600 underline decoration-dashed",
    markActive: "bg-red-200 ring-2 ring-red-600",
    chip: "border-red-300 bg-red-50 text-red-900",
  },
  DATA_REQUEST: {
    mark: "bg-pink-100 decoration-pink-600 underline decoration-dotted",
    markActive: "bg-pink-200 ring-2 ring-pink-600",
    chip: "border-pink-300 bg-pink-50 text-pink-900",
  },
  AUTHORITY_CLAIM: {
    mark: "bg-orange-100 decoration-orange-600 underline decoration-wavy",
    markActive: "bg-orange-200 ring-2 ring-orange-600",
    chip: "border-orange-300 bg-orange-50 text-orange-900",
  },
  FUNDING_CLAIM: {
    mark: "bg-fuchsia-100 decoration-fuchsia-600 underline decoration-dashed",
    markActive: "bg-fuchsia-200 ring-2 ring-fuchsia-600",
    chip: "border-fuchsia-300 bg-fuchsia-50 text-fuchsia-900",
  },
};
