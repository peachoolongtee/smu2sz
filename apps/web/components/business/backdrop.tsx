/**
 * The Business pages' background: two large soft discs, one in the Home blue and one in the Cash teal, drifting once, very slowly
 * (40 s, then at rest; no motion under reduced motion). They are tints so faint (globals.css `.biz-disc`) that muted text keeps 4.5:1 on their
 * strongest point; cards are solid and sit on top. Fixed, behind everything, ignored by pointers and screen readers.
 */
export function Backdrop() {
  return (
    <div aria-hidden className="pointer-events-none fixed inset-0 -z-10 overflow-hidden" data-testid="backdrop">
      <div className="biz-disc biz-disc-home" />
      <div className="biz-disc biz-disc-cash" />
    </div>
  );
}
