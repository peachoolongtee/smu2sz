import type { SVGProps } from "react";

type P = SVGProps<SVGSVGElement>;

const base = (p: P) => ({
  width: 16,
  height: 16,
  viewBox: "0 0 16 16",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.6,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
  "aria-hidden": true,
  focusable: false,
  ...p,
});

export const CheckIcon = (p: P) => (
  <svg {...base(p)}>
    <path d="M3 8.5l3 3 7-7" />
  </svg>
);
export const XIcon = (p: P) => (
  <svg {...base(p)}>
    <path d="M4 4l8 8M12 4l-8 8" />
  </svg>
);
export const MenuIcon = (p: P) => (
  <svg {...base(p)}>
    <path d="M2.5 4.5h11M2.5 8h11M2.5 11.5h11" />
  </svg>
);
export const ArrowRightIcon = (p: P) => (
  <svg {...base(p)}>
    <path d="M3 8h10M9 4l4 4-4 4" />
  </svg>
);
export const ArrowLeftIcon = (p: P) => (
  <svg {...base(p)}>
    <path d="M13 8H3M7 4L3 8l4 4" />
  </svg>
);
export const ResetIcon = (p: P) => (
  <svg {...base(p)}>
    <path d="M3 8a5 5 0 1 0 1.6-3.7M3 3v3h3" />
  </svg>
);
export const DownloadIcon = (p: P) => (
  <svg {...base(p)}>
    <path d="M8 2.5v8M4.5 7.5L8 11l3.5-3.5M3 13.5h10" />
  </svg>
);
export const CopyIcon = (p: P) => (
  <svg {...base(p)}>
    <rect x="5.5" y="5.5" width="8" height="8" rx="1.5" />
    <path d="M10.5 5.5v-2a1 1 0 0 0-1-1h-6a1 1 0 0 0-1 1v6a1 1 0 0 0 1 1h2" />
  </svg>
);
export const ShieldIcon = (p: P) => (
  <svg {...base(p)}>
    <path d="M8 1.8l5 1.8v4c0 3-2.1 5.2-5 6.6-2.9-1.4-5-3.6-5-6.6v-4l5-1.8z" />
  </svg>
);
export const Spinner = (p: P) => (
  <svg {...base(p)} className={`animate-spin ${p.className ?? ""}`}>
    <path d="M8 2a6 6 0 1 0 6 6" />
  </svg>
);
export const ChatIcon = (p: P) => (
  <svg {...base(p)}>
    <path d="M2.5 3.5h11a1 1 0 0 1 1 1v6a1 1 0 0 1-1 1H7l-3 2.5v-2.5H2.5a1 1 0 0 1-1-1v-6a1 1 0 0 1 1-1z" />
  </svg>
);
export const ChevronRightIcon = (p: P) => (
  <svg {...base(p)}>
    <path d="M6 3.5L10.5 8 6 12.5" />
  </svg>
);
