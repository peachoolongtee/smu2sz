/**
 * Concentric discs ripple out from the exact middle of the screen, each a soft brown tint stacked on the last (darkest at the
 * centre, fading outward) with a thin edge. The outermost disc is the canvas colour and covers the screen, then the dialog
 * closes onto the dashboard. `host` is the open modal dialog when there is one (a modal sits above everything else); otherwise the page.
 */
export async function playRipple(host: HTMLElement | null = null): Promise<void> {
  if (typeof window === "undefined" || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  const x = window.innerWidth / 2;
  const y = window.innerHeight / 2;
  const reach = Math.hypot(x, y);
  const parent = host ?? document.body;
  const count = 3;
  const discs: HTMLElement[] = [];
  const anims: Animation[] = [];
  // Largest first, so each smaller disc sits on top and the tints stack toward the centre.
  for (let i = count - 1; i >= 0; i--) {
    const radius = (reach * (i + 1)) / count;
    const outer = i === count - 1;
    const el = document.createElement("div");
    el.setAttribute("aria-hidden", "true");
    Object.assign(el.style, {
      position: "fixed",
      left: `${x - radius}px`,
      top: `${y - radius}px`,
      width: `${radius * 2}px`,
      height: `${radius * 2}px`,
      borderRadius: "50%",
      boxSizing: "border-box",
      background: outer ? "var(--color-canvas)" : "rgba(61, 46, 34, 0.07)",
      border: "1px solid rgba(61, 46, 34, 0.12)",
      pointerEvents: "none",
      zIndex: "9999",
      transform: "scale(0)",
    });
    parent.appendChild(el);
    discs.push(el);
    anims.push(
      el.animate([{ transform: "scale(0)" }, { transform: "scale(1)" }], {
        duration: 600,
        delay: i * 60, // the inner disc leaves first, the outer ones follow it out
        easing: "cubic-bezier(0.22, 1, 0.36, 1)",
        fill: "forwards",
      }),
    );
  }
  try {
    await Promise.all(anims.map((a) => a.finished));
  } catch {
    /* cancelled: carry on to the dashboard */
  }
  // The next screen (or the closed dialog) arrives with the discs still on top; remove them once it is showing.
  setTimeout(() => discs.forEach((d) => d.remove()), host ? 0 : 400);
}
