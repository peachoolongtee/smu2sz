import type { SVGProps } from "react";

/** The info mark: a ring with an "i". Decorative; its button carries the name. */
export function InfoIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" aria-hidden {...props}>
      <circle cx="8" cy="8" r="6.25" />
      <path d="M8 7.25v3.5" />
      <circle cx="8" cy="4.9" r="0.5" fill="currentColor" />
    </svg>
  );
}
