import type { Metadata } from "next";
import { Landing } from "@/components/landing/landing";

export const metadata: Metadata = { title: "Welcome" };

/** The landing page: the way in for someone who has FLOW ("Access FLOW") and for someone new ("Get started with FLOW!", the setup). */
export default function WelcomePage() {
  return <Landing />;
}
