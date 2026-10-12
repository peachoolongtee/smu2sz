/**
 * The segmented control's behaviour without its markup (components/ui/segmented-tabs.tsx draws it): which tab an arrow key moves to, the ARIA
 * attributes each tab carries and the badge's tone. Plain functions, so a unit test reads them without a browser (scripts/w12-design-system.test.mjs).
 */

export type BadgeTone = "neutral" | "alert";

export interface TabState {
  /** A tab that cannot be chosen (nothing behind it): skipped by the arrow keys, never focused. */
  disabled?: boolean;
}

/**
 * The tab an arrow key lands on, or null when the key is not a tab key. Left and Up go back, Right and Down forward, both wrapping; Home and End go to the
 * first and last. Disabled tabs are skipped; when every other tab is disabled the focus stays where it is.
 */
export function nextTabIndex(key: string, from: number, tabs: readonly TabState[]): number | null {
  const n = tabs.length;
  if (n === 0) return null;
  const ok = (i: number) => !tabs[i]?.disabled;
  if (key === "Home") return [...tabs.keys()].find(ok) ?? null;
  if (key === "End") return [...tabs.keys()].reverse().find(ok) ?? null;
  const by = key === "ArrowRight" || key === "ArrowDown" ? 1 : key === "ArrowLeft" || key === "ArrowUp" ? -1 : 0;
  if (!by) return null;
  for (let step = 1; step <= n; step++) {
    const i = (((from + by * step) % n) + n) % n;
    if (ok(i)) return i;
  }
  return null;
}

/** The one tab in the page's tab order (roving tabindex): the selected tab, or, with nothing selected or the selected one disabled, the first that can be chosen. */
export function tabStop(selected: number, tabs: readonly TabState[]): number {
  if (selected >= 0 && !tabs[selected]?.disabled) return selected;
  const first = tabs.findIndex((t) => !t.disabled);
  return first < 0 ? 0 : first;
}

export interface TabAttrs {
  role: "tab";
  "aria-selected": boolean;
  "aria-controls"?: string;
  id?: string;
  tabIndex: 0 | -1;
  disabled: boolean;
}

/** The attributes of tab `i` (the tablist's `aria-label` is the caller's). */
export function tabAttrs(i: number, selected: number, tabs: readonly (TabState & { id?: string; controls?: string })[]): TabAttrs {
  const t = tabs[i];
  return {
    role: "tab",
    "aria-selected": i === selected,
    ...(t.controls ? { "aria-controls": t.controls } : {}),
    ...(t.id ? { id: t.id } : {}),
    tabIndex: i === tabStop(selected, tabs) ? 0 : -1,
    disabled: Boolean(t.disabled),
  };
}

/**
 * A badge is shown when it has something to say: a number (zero included: "0" is an answer) or a word; null, undefined and the empty string draw nothing.
 * Red (`alert`) is only for a count that needs the owner; every other count is neutral.
 */
export function badgeShown(badge: string | number | null | undefined): boolean {
  return badge !== null && badge !== undefined && badge !== "";
}

export const BADGE_CLASS: Record<BadgeTone, string> = {
  neutral: "bg-line-strong text-ink",
  alert: "bg-bad-solid text-white",
};
