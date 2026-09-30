"use client";

import type { ReactNode } from "react";
import { useI18n } from "@/lib/i18n";
import type { WhatIfControls, WhatIfParams, WhatIfPresetId, WhatIfSlider } from "@/lib/types";
import { Card } from "./ui";

/**
 * The owner's levers. Sliders move integer days, integer bp and a server-listed face stop; every
 * readout is a server-formatted label (controls.rate_labels, controls.face_stops). No money is
 * computed or formatted here (INVARIANT 13).
 */

const PRESET_ORDER: WhatIfPresetId[] = ["actual", "option_a", "option_b", "status_quo"];

export function samePosition(a: WhatIfParams, b: WhatIfParams): boolean {
  return (
    a.terms_days === b.terms_days &&
    a.discount_bp === b.discount_bp &&
    a.rebate_bp === b.rebate_bp &&
    a.price_adjustment_bp === b.price_adjustment_bp &&
    (a.discount_bp === 0 || a.settle_face_fen === b.settle_face_fen)
  );
}

function Slider({
  id,
  label,
  grid,
  value,
  readout,
  hint,
  disabled = false,
  onChange,
}: {
  id: string;
  label: string;
  grid: WhatIfSlider;
  value: number;
  readout: string;
  hint?: ReactNode;
  disabled?: boolean;
  onChange: (v: number) => void;
}) {
  return (
    <div className={disabled ? "opacity-50" : ""}>
      <div className="flex items-baseline justify-between gap-3">
        <label htmlFor={id} className="text-sm font-medium text-ink">
          {label}
        </label>
        <output htmlFor={id} className="text-base font-semibold tabular-nums text-brand-700" data-testid={`${id}-readout`}>
          {readout}
        </output>
      </div>
      <input
        id={id}
        type="range"
        min={grid.min}
        max={grid.max}
        step={grid.step}
        value={value}
        disabled={disabled}
        aria-valuetext={readout}
        onChange={(e) => onChange(Number(e.target.value))}
        className="mt-2 h-2 w-full cursor-pointer accent-brand-600 disabled:cursor-not-allowed"
      />
      {hint ? <p className="mt-1 text-xs text-ink-3">{hint}</p> : null}
    </div>
  );
}

export function WhatIfControlsCard({
  controls,
  params,
  onChange,
}: {
  controls: WhatIfControls;
  params: WhatIfParams;
  onChange: (p: WhatIfParams) => void;
}) {
  const { t } = useI18n();
  const g = controls.grid;
  const rate = (bp: number) => controls.rate_labels[String(bp)] ?? "…";
  const set = (patch: Partial<WhatIfParams>) => onChange({ ...params, ...patch });

  const stops = controls.face_stops;
  const partial = params.settle_face_fen !== null;
  const faceIndex = partial ? stops.findIndex((s) => s.fen === params.settle_face_fen) : stops.length - 1;
  const faceStop = stops[faceIndex >= 0 ? faceIndex : stops.length - 1];
  const middle = stops[Math.floor(stops.length / 2)];

  const termsHint =
    params.terms_days === controls.current_terms_days
      ? `${t("whatif.terms.now", { n: controls.current_terms_days })} · ${t("whatif.terms.same")}`
      : t("whatif.terms.now", { n: controls.current_terms_days });

  return (
    <Card id="whatif-controls" title={t("whatif.controls")} subtitle={t("whatif.controls.sub")}>
      <fieldset>
        <legend className="text-xs font-semibold uppercase tracking-wide text-ink-3">{t("whatif.presets")}</legend>
        <div className="mt-2 grid grid-cols-2 gap-2">
          {PRESET_ORDER.map((id) => {
            const p = controls.presets[id];
            const active = samePosition(params, p);
            return (
              <button
                key={id}
                type="button"
                data-testid={`whatif-preset-${id}`}
                aria-pressed={active}
                onClick={() =>
                  onChange({
                    terms_days: p.terms_days,
                    discount_bp: p.discount_bp,
                    rebate_bp: p.rebate_bp,
                    price_adjustment_bp: p.price_adjustment_bp,
                    settle_face_fen: p.settle_face_fen,
                  })
                }
                className={`min-h-10 rounded-md border px-2.5 py-1.5 text-left text-xs font-medium transition-colors ${
                  id === "actual" ? "col-span-2" : ""
                } ${
                  active
                    ? "border-brand-600 bg-brand-50 text-brand-700"
                    : "border-line-strong bg-surface text-ink hover:bg-subtle"
                }`}
              >
                {t(`whatif.preset.${id}`)}
              </button>
            );
          })}
        </div>
      </fieldset>

      <div className="mt-5 space-y-5">
        <Slider
          id="whatif-terms"
          label={t("whatif.terms")}
          grid={g.terms_days}
          value={params.terms_days}
          readout={t("common.days", { n: params.terms_days })}
          hint={termsHint}
          onChange={(v) => set({ terms_days: v })}
        />
        <Slider
          id="whatif-discount"
          label={t("whatif.discount")}
          grid={g.discount_bp}
          value={params.discount_bp}
          readout={params.discount_bp === 0 ? t("whatif.discount.off") : rate(params.discount_bp)}
          onChange={(v) => set({ discount_bp: v })}
        />
        <div className="rounded-lg border border-line bg-subtle/60 p-3">
          <label className="flex min-h-8 cursor-pointer items-center gap-2 text-sm text-ink-2">
            <input
              type="checkbox"
              checked={partial}
              disabled={params.discount_bp === 0}
              onChange={(e) => set({ settle_face_fen: e.target.checked ? middle.fen : null })}
              className="size-4 accent-brand-600"
            />
            {t("whatif.partial", { id: controls.receivable_id })}
          </label>
          {partial ? (
            <div className="mt-2">
              <Slider
                id="whatif-face"
                label={t("whatif.face")}
                grid={{ min: 0, max: stops.length - 1, step: 1 }}
                value={faceIndex >= 0 ? faceIndex : stops.length - 1}
                readout={faceStop.display}
                disabled={params.discount_bp === 0}
                onChange={(i) => set({ settle_face_fen: stops[i].fen })}
              />
            </div>
          ) : (
            <p className="mt-1 text-xs text-ink-3">{t("whatif.face.whole", { face: controls.receivable_face_display })}</p>
          )}
        </div>
        <Slider
          id="whatif-rebate"
          label={t("whatif.rebate")}
          grid={g.rebate_bp}
          value={params.rebate_bp}
          readout={rate(params.rebate_bp)}
          onChange={(v) => set({ rebate_bp: v })}
        />
        <Slider
          id="whatif-price"
          label={t("whatif.price")}
          grid={g.price_adjustment_bp}
          value={params.price_adjustment_bp}
          readout={rate(params.price_adjustment_bp)}
          onChange={(v) => set({ price_adjustment_bp: v })}
        />
      </div>
    </Card>
  );
}
