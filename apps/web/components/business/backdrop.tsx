/**
 * The Business pages' background: quiet shapes behind the cards so the canvas is not a flat grey. A faint dot grid that
 * fades out towards the edges, three large soft colour glows that drift very slowly, thin concentric rings in the top
 * right corner and a light wave across the bottom. Fixed, behind everything, ignored by pointers and screen readers; the
 * drift stops under reduced motion (the global rule in globals.css).
 */
export function Backdrop() {
  return (
    <div aria-hidden className="biz-backdrop pointer-events-none fixed inset-0 -z-10 overflow-hidden">
      <div className="biz-dots absolute inset-0" />
      <div className="biz-blob biz-blob-a" />
      <div className="biz-blob biz-blob-b" />
      <div className="biz-blob biz-blob-c" />
      <svg className="absolute -right-40 -top-40 h-[34rem] w-[34rem] text-brand-600/[0.09]" viewBox="0 0 400 400" fill="none">
        {[60, 100, 140, 180].map((r) => (
          <circle key={r} cx="200" cy="200" r={r} stroke="currentColor" strokeWidth="1.25" />
        ))}
      </svg>
      <svg className="absolute -left-24 bottom-0 h-56 w-[120%] text-violet-500/[0.08]" viewBox="0 0 1200 200" preserveAspectRatio="none" fill="none">
        <path d="M0 140 C 200 60, 400 200, 600 120 S 1000 40, 1200 110" stroke="currentColor" strokeWidth="2" />
        <path d="M0 170 C 220 100, 420 220, 640 150 S 1020 80, 1200 140" stroke="currentColor" strokeWidth="1.25" />
      </svg>
      <svg className="absolute -left-16 top-1/3 h-40 w-40 text-teal-500/[0.12]" viewBox="0 0 100 100" fill="none">
        <rect x="18" y="18" width="64" height="64" rx="18" stroke="currentColor" strokeWidth="1.5" transform="rotate(18 50 50)" />
      </svg>
    </div>
  );
}
