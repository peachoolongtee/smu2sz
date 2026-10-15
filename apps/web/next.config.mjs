/**
 * NEXT_DIST_DIR lets the mock and live e2e builds sit side by side (NEXT_PUBLIC_* values are inlined at
 * build time). The default `.next` is unchanged for normal development and deploys.
 */
/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  distDir: process.env.NEXT_DIST_DIR || ".next",
  // Security register SEC-12: the owner console is never framed (approve and accept buttons), never sniffed, and sends no referrer.
  // A full Content-Security-Policy (script-src with the pre-hydration script's hash, connect-src the API origin) is the next step;
  // it needs a browser run before it ships.
  async headers() {
    return [{
      source: "/:path*",
      headers: [
        { key: "X-Frame-Options", value: "DENY" },
        { key: "Content-Security-Policy", value: "frame-ancestors 'none'; object-src 'none'; base-uri 'none'" },
        { key: "X-Content-Type-Options", value: "nosniff" },
        { key: "Referrer-Policy", value: "no-referrer" },
      ],
    }];
  },
};

export default nextConfig;
