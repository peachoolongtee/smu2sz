/**
 * NEXT_DIST_DIR lets the mock and live e2e builds sit side by side (NEXT_PUBLIC_* values are inlined at
 * build time). The default `.next` is unchanged for normal development and deploys.
 */
/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  distDir: process.env.NEXT_DIST_DIR || ".next",
};

export default nextConfig;
