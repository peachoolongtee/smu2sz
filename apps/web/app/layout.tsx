import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";
import { AppShell } from "@/components/app-shell";
import { PRE_HYDRATION } from "@/lib/pre-hydration";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "FLOW 流", template: "%s · FLOW 流" },
  description: "FLOW 流: the AI working-capital agent that reads buyer terms, protects the cash reserve and funds the gap within the owner's signed limits.",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: PRE_HYDRATION }} />
        {/* Endowus's type: Lato for reading, a serif for headlines (DESIGN.md). Offline, the system stack in globals.css stands in. */}
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        {/* The root layout wraps every route, so this loads on every page (the rule targets the Pages Router's per-page heads). */}
        {/* eslint-disable-next-line @next/next/no-page-custom-font */}
        <link
          rel="stylesheet"
          href="https://fonts.googleapis.com/css2?family=Lato:wght@400;700;900&family=Libre+Caslon+Text:wght@400;700&display=swap"
        />
      </head>
      <body>
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
