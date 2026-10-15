"use client";

import { useEffect, useRef } from "react";

/**
 * The page's background: a bundle of thin lines flowing across it (after 21st.dev's "background paths"), each a slow sum of two waves that drifts with time, sweeping gently
 * down from left to right. They are drawn in the page's section hue (`--sec` on the shell) at a low opacity, every fourth one in Home's purple or the chart teal, so the
 * colour says where you are without competing with the cards; a section change glides the hue to the new one.
 *
 * Cheap: a 2D canvas at the screen's pixel density (at most 2), about 30 frames a second, paused while the tab is hidden; under reduced motion it draws once. Decoration only.
 */

type RGB = [number, number, number];

/** The first colour in a CSS value (a hex, or rgb()); a `light-dark(a, b)` value gives its light colour. As 0..255 channels. */
function parse(value: string, fallback: RGB): RGB {
  const hex = value.match(/#([0-9a-f]{6}|[0-9a-f]{3})\b/i)?.[1];
  if (hex) {
    const h = hex.length === 3 ? hex.split("").map((c) => c + c).join("") : hex;
    return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)];
  }
  const rgb = value.match(/rgba?\(\s*([\d.]+)[,\s]+([\d.]+)[,\s]+([\d.]+)/i);
  return rgb ? [Number(rgb[1]), Number(rgb[2]), Number(rgb[3])] : fallback;
}
const ease = (from: RGB, to: RGB, k: number): RGB => [from[0] + (to[0] - from[0]) * k, from[1] + (to[1] - from[1]) * k, from[2] + (to[2] - from[2]) * k];

const LINES = 34;

export function FlowLines({ sectionKey }: { sectionKey: string }) {
  const ref = useRef<HTMLCanvasElement>(null);
  // The colours the lines are heading to (the section's hue, the purple, the teal); the loop eases the drawn ones towards them.
  const target = useRef<RGB[] | null>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const css = getComputedStyle(el);
    target.current = [parse(css.getPropertyValue("--sec"), [146, 82, 220]), parse(css.getPropertyValue("--color-f-purple"), [146, 82, 220]), parse(css.getPropertyValue("--color-chart-teal"), [56, 208, 199])];
  }, [sectionKey]);

  useEffect(() => {
    const canvas = ref.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return;
    let W = 0;
    let H = 0;
    const resize = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      W = window.innerWidth;
      H = window.innerHeight;
      canvas.width = Math.round(W * dpr);
      canvas.height = Math.round(H * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    resize();
    window.addEventListener("resize", resize);

    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let colours: RGB[] | null = null;
    const draw = (time: number) => {
      const goal = target.current;
      if (!goal) return;
      colours = colours ? colours.map((c, i) => ease(c, goal[i], reduce ? 1 : 0.05)) : goal.map((c) => [...c] as RGB);
      ctx.clearRect(0, 0, W, H);
      const t = time / 1000;
      const gap = (H * 0.75) / LINES;
      const step = Math.max(16, W / 90);
      for (let i = 0; i < LINES; i++) {
        const c = i % 4 === 3 ? colours[i % 8 === 3 ? 1 : 2] : colours[0];
        // Fainter at the edges of the bundle, strongest in its middle.
        const mid = 1 - Math.abs(i / (LINES - 1) - 0.5) * 2;
        ctx.strokeStyle = `rgba(${c[0] | 0}, ${c[1] | 0}, ${c[2] | 0}, ${0.1 + mid * 0.22})`;
        ctx.lineWidth = 1 + mid * 0.6;
        ctx.beginPath();
        for (let x = -step; x <= W + step; x += step) {
          const u = x / W;
          const y =
            H * 0.12 +
            i * gap +
            u * H * 0.18 + // the bundle sweeps gently down to the right
            Math.sin(u * 5.2 + t * 0.35 + i * 0.12) * H * 0.05 +
            Math.sin(u * 11.0 - t * 0.22 + i * 0.27) * H * 0.018;
          if (x === -step) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        }
        ctx.stroke();
      }
    };

    if (reduce) {
      // One still drawing, refreshed when the size or the section changes.
      const still = () => draw(4000);
      still();
      const id = window.setInterval(still, 500);
      return () => {
        window.clearInterval(id);
        window.removeEventListener("resize", resize);
      };
    }
    let frame = 0;
    let last = 0;
    const loop = (now: number) => {
      frame = window.requestAnimationFrame(loop);
      if (document.hidden || now - last < 33) return;
      last = now;
      draw(now);
    };
    frame = window.requestAnimationFrame(loop);
    return () => {
      window.cancelAnimationFrame(frame);
      window.removeEventListener("resize", resize);
    };
  }, []);

  return <canvas ref={ref} aria-hidden className="absolute inset-0 size-full" data-testid="flow-lines" />;
}
