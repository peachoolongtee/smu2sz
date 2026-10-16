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
export const RefreshIcon = (p: P) => (
  <svg {...base(p)}>
    <path d="M13 8a5 5 0 1 1-1.46-3.54M13 2.5v2.5h-2.5" />
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
/** An arc that turns; where motion is reduced (a frozen arc says nothing) it is an ellipsis instead (see globals.css). */
export const Spinner = (p: P) => (
  <>
    <svg {...base(p)} className={`spinner animate-spin ${p.className ?? ""}`}>
      <path d="M8 2a6 6 0 1 0 6 6" />
    </svg>
    <span aria-hidden className="spinner-dots font-semibold leading-none">
      …
    </span>
  </>
);
export const ArrowDownIcon = (p: P) => (
  <svg {...base(p)}>
    <path d="M8 2.5v10M4 8.5l4 4 4-4" />
  </svg>
);
export const AlertIcon = (p: P) => (
  <svg {...base(p)}>
    <path d="M8 3v6M8 12.2v.1" />
  </svg>
);
export const ClockIcon = (p: P) => (
  <svg {...base(p)}>
    <circle cx="8" cy="8" r="5.5" />
    <path d="M8 5v3.2l2 1.3" />
  </svg>
);
export const ChatIcon = (p: P) => (
  <svg {...base(p)}>
    <path d="M2.5 3.5h11a1 1 0 0 1 1 1v6a1 1 0 0 1-1 1H7l-3 2.5v-2.5H2.5a1 1 0 0 1-1-1v-6a1 1 0 0 1 1-1z" />
  </svg>
);
export const DashedRingIcon = (p: P) => (
  <svg {...base(p)}>
    <circle cx="8" cy="8" r="5.5" strokeDasharray="2.2 2.2" />
  </svg>
);
export const RingIcon = (p: P) => (
  <svg {...base(p)}>
    <circle cx="8" cy="8" r="5.5" />
  </svg>
);
export const RingDotIcon = (p: P) => (
  <svg {...base(p)}>
    <circle cx="8" cy="8" r="5.5" />
    <circle cx="8" cy="8" r="1.6" fill="currentColor" stroke="none" />
  </svg>
);
export const CheckCircleIcon = (p: P) => (
  <svg {...base(p)}>
    <circle cx="8" cy="8" r="5.5" />
    <path d="M5.4 8.2l1.8 1.8 3.4-3.6" />
  </svg>
);
export const HourglassIcon = (p: P) => (
  <svg {...base(p)}>
    <path d="M4.5 2.5h7M4.5 13.5h7M5 2.5c0 3 3 3.5 3 5.5s-3 2.5-3 5.5M11 2.5c0 3-3 3.5-3 5.5s3 2.5 3 5.5" />
  </svg>
);
export const DocumentIcon = (p: P) => (
  <svg {...base(p)}>
    <path d="M4 2h5.5L12.5 5v9H4z" />
    <path d="M9.5 2v3h3M6 8.5h4.5M6 11h4.5" />
  </svg>
);
export const TwoRingsIcon = (p: P) => (
  <svg {...base(p)}>
    <circle cx="6" cy="8" r="3.6" />
    <circle cx="10" cy="8" r="3.6" />
  </svg>
);
export const ListIcon = (p: P) => (
  <svg {...base(p)}>
    <path d="M5.5 4.5h8M5.5 8h8M5.5 11.5h8M2.5 4.5h.01M2.5 8h.01M2.5 11.5h.01" />
  </svg>
);
export const CalendarIcon = (p: P) => (
  <svg {...base(p)}>
    <rect x="2.5" y="3.5" width="11" height="10" rx="1.5" />
    <path d="M2.5 6.5h11M5.5 2v3M10.5 2v3" />
  </svg>
);
export const ChevronRightIcon = (p: P) => (
  <svg {...base(p)}>
    <path d="M6 3.5L10.5 8 6 12.5" />
  </svg>
);

/* Business navigation icons (24-unit grid). */
const base24 = (p: P) => ({
  width: 20,
  height: 20,
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.8,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
  "aria-hidden": true,
  focusable: false,
  ...p,
});

export const HomeIcon = (p: P) => (
  <svg {...base24(p)}>
    <path d="M3.5 10.5 12 4l8.5 6.5" />
    <path d="M5.5 9v10.5h13V9" />
    <path d="M10 19.5v-5h4v5" />
  </svg>
);
export const DealsIcon = (p: P) => (
  <svg {...base24(p)}>
    <path d="M4 5.5h11a1.5 1.5 0 0 1 1.5 1.5v6A1.5 1.5 0 0 1 15 14.5H9l-4 3.5v-3.5H4A1.5 1.5 0 0 1 2.5 13V7A1.5 1.5 0 0 1 4 5.5Z" />
    <path d="M19.5 9.5h.5A1.5 1.5 0 0 1 21.5 11v5a1.5 1.5 0 0 1-1.5 1.5h-.5V20l-3-2.5H12" />
  </svg>
);
export const WalletIcon = (p: P) => (
  <svg {...base24(p)}>
    <path d="M4 7.5V17a2 2 0 0 0 2 2h13.5V9.5H6a2 2 0 0 1-2-2Zm0 0A2 2 0 0 1 6 5.5h11.5v4" />
    <circle cx="16" cy="14.25" r="1.1" fill="currentColor" stroke="none" />
  </svg>
);
export const InboxInIcon = (p: P) => (
  <svg {...base24(p)}>
    <path d="M12 3.5v9M8.5 9 12 12.5 15.5 9" />
    <path d="M3.5 13.5h4.25l1.5 2.5h5.5l1.5-2.5h4.25V19a1.5 1.5 0 0 1-1.5 1.5H5A1.5 1.5 0 0 1 3.5 19v-5.5Z" />
  </svg>
);
export const ActivityIcon = (p: P) => (
  <svg {...base24(p)}>
    <path d="M3.5 12h4l2.5-6.5 4 13 2.5-6.5h4" />
  </svg>
);
export const ShieldCheckIcon = (p: P) => (
  <svg {...base24(p)}>
    <path d="M12 3.5 5 6v5.5c0 4.2 2.8 7.2 7 9 4.2-1.8 7-4.8 7-9V6l-7-2.5Z" />
    <path d="m9 12 2.2 2.2L15.2 10" />
  </svg>
);
export const SparkIcon = (p: P) => (
  <svg {...base24(p)}>
    <path d="M12 3.5v4M12 16.5v4M3.5 12h4M16.5 12h4M6 6l2.6 2.6M15.4 15.4 18 18M18 6l-2.6 2.6M8.6 15.4 6 18" />
  </svg>
);

// ---- pages A1 (part 1): who acted on an Activity entry (16 px, like the base set)
export const UserIcon = (p: P) => (
  <svg {...base(p)}>
    <circle cx="8" cy="5.5" r="2.5" />
    <path d="M3 13.5c.6-2.6 2.6-4 5-4s4.4 1.4 5 4" />
  </svg>
);
export const BankIcon = (p: P) => (
  <svg {...base(p)}>
    <path d="M2 6.5 8 3l6 3.5M3.5 7.5v4M6.5 7.5v4M9.5 7.5v4M12.5 7.5v4M2.5 13h11" />
  </svg>
);
export const StoreIcon = (p: P) => (
  <svg {...base(p)}>
    <path d="M2.5 6.5 3.5 3h9l1 3.5M3 6.5h10M3.5 6.5v7h9v-7M6.5 13.5v-3h3v3" />
  </svg>
);
