import type { Metadata, Viewport } from "next";
import { headers } from "next/headers";
import type { ReactNode } from "react";
import { AppShell } from "@/components/app-shell";
import { PRE_HYDRATION } from "@/lib/pre-hydration";
import "@fontsource-variable/plus-jakarta-sans";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "FLOW", template: "%s · FLOW" },
  description: "FLOW: the AI working-capital agent that reads buyer terms, protects the cash reserve and funds the gap within the owner's signed limits.",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
};

export default async function RootLayout({ children }: { children: ReactNode }) {
  // SEC-12: the pre-hydration script carries this request's CSP nonce (proxy.ts), the only way an inline script may run
  const nonce = (await headers()).get("x-nonce") ?? undefined;
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script nonce={nonce} dangerouslySetInnerHTML={{ __html: PRE_HYDRATION }} />
      </head>
      <body>
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
