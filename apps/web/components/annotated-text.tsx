"use client";

import { ANNOTATION_STYLE, type AnnotationKind } from "@/lib/annotation-style";

export interface Annotation {
  id: string;
  kind: AnnotationKind;
  start: number;
  end: number;
  /** 1-based number shown next to the span and in the side list. */
  n: number;
  label: string;
}

interface Segment {
  from: number;
  to: number;
  covering: Annotation[];
}

function segmentise(length: number, annotations: Annotation[]): Segment[] {
  const cuts = new Set<number>([0, length]);
  for (const a of annotations) {
    cuts.add(Math.max(0, Math.min(length, a.start)));
    cuts.add(Math.max(0, Math.min(length, a.end)));
  }
  const points = [...cuts].sort((x, y) => x - y);
  const out: Segment[] = [];
  for (let i = 0; i < points.length - 1; i++) {
    const from = points[i];
    const to = points[i + 1];
    out.push({ from, to, covering: annotations.filter((a) => a.start <= from && a.end >= to) });
  }
  return out;
}

/**
 * Renders a source document with its spans highlighted inline. Overlapping spans are supported: the
 * narrowest span styles a segment, and a number badge marks where each span starts. Hovering or focusing
 * a mark activates it so the side list can highlight the same item.
 */
export function AnnotatedText({
  text,
  annotations,
  activeId,
  onActivate,
  ariaLabel,
}: {
  text: string;
  annotations: Annotation[];
  activeId: string | null;
  onActivate: (id: string | null) => void;
  ariaLabel: string;
}) {
  const segments = segmentise(text.length, annotations);
  return (
    <div
      role="group"
      aria-label={ariaLabel}
      className="whitespace-pre-wrap break-words rounded-tile border border-line bg-surface p-4 text-base leading-8 text-ink"
    >
      {segments.map((seg) => {
        const chunk = text.slice(seg.from, seg.to);
        if (!seg.covering.length) return <span key={seg.from}>{chunk}</span>;
        const primary = [...seg.covering].sort((a, b) => a.end - a.start - (b.end - b.start))[0];
        const active = seg.covering.some((a) => a.id === activeId);
        const style = ANNOTATION_STYLE[primary.kind];
        const startsHere = seg.covering.filter((a) => a.start === seg.from);
        return (
          <mark
            key={seg.from}
            tabIndex={0}
            data-annotation={seg.covering.map((a) => a.id).join(" ")}
            title={seg.covering.map((a) => `${a.n}. ${a.label}`).join(" / ")}
            aria-description={seg.covering.map((a) => `${a.n}. ${a.label}`).join(" / ")}
            onMouseEnter={() => onActivate(primary.id)}
            onMouseLeave={() => onActivate(null)}
            onFocus={() => onActivate(primary.id)}
            onBlur={() => onActivate(null)}
            className={`rounded-sm px-0.5 text-ink decoration-2 underline-offset-4 ${
              active ? style.markActive : style.mark
            }`}
          >
            {startsHere.map((a) => (
              <sup
                key={a.id}
                className="mr-0.5 inline-block rounded-pill bg-ink px-1.5 align-top text-xs font-bold leading-4 text-white"
              >
                {a.n}
              </sup>
            ))}
            {chunk}
          </mark>
        );
      })}
    </div>
  );
}
