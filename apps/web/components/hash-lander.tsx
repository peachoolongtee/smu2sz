"use client";

import { usePathname, useSearchParams } from "next/navigation";
import { Suspense, useEffect } from "react";

/** How long a page may take to draw the section an address names (its reads load after the route renders). */
const WAIT_MS = 12_000;

/**
 * An address with a section (`/cash#cash-readings`, `/#home-v2-action`; the links under an Ask FLOW answer) lands on that section once the
 * page has drawn it: the element is waited for, a closed fold (`<details>`) that is or holds it is opened, and it is scrolled to the top of
 * the view and given the focus (without a second scroll), so the owner sees the thing the link named. Runs on every route change and on a
 * hash change within a page. Reduced motion: the jump is instant (the browser's `scroll-behavior` is not smooth under it).
 */
function Lander() {
  const pathname = usePathname();
  const search = useSearchParams().toString();
  useEffect(() => {
    let timer = 0;
    let stop = false;
    function land() {
      window.clearTimeout(timer);
      const raw = window.location.hash.slice(1);
      if (!raw) return;
      let id = raw;
      try {
        id = decodeURIComponent(raw);
      } catch {
        /* a malformed hash is looked for as it is */
      }
      const started = Date.now();
      const tick = () => {
        if (stop) return;
        const el = document.getElementById(id);
        if (!el) {
          if (Date.now() - started < WAIT_MS) timer = window.setTimeout(tick, 120);
          return;
        }
        const fold = el instanceof HTMLDetailsElement ? el : el.closest("details");
        if (fold && !fold.open) fold.open = true;
        // `[data-landed]` keeps it clear of the sticky header (globals.css).
        el.setAttribute("data-landed", "true");
        el.scrollIntoView({ block: "start" });
        if (!el.hasAttribute("tabindex") && !/^(A|BUTTON|INPUT|SELECT|TEXTAREA|DETAILS|SUMMARY)$/.test(el.tagName)) el.setAttribute("tabindex", "-1");
        el.focus({ preventScroll: true });
      };
      tick();
    }
    land();
    window.addEventListener("hashchange", land);
    return () => {
      stop = true;
      window.clearTimeout(timer);
      window.removeEventListener("hashchange", land);
    };
  }, [pathname, search]);
  return null;
}

export function HashLander() {
  return (
    <Suspense fallback={null}>
      <Lander />
    </Suspense>
  );
}
