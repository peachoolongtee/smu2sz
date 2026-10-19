import { AlertIcon } from "@/components/icons";
import { useI18n } from "@/lib/i18n";
import { senderUnverified, UNVERIFIED_SENDER_KEY, type SenderProvenance } from "./unverified-sender-model";

/**
 * "Unverified sender: this message came without the buyer's key" (SEC-19), shown where the owner can accept a request or approve an operation on it when the server says
 * nobody signed it (`sender_unverified`). Nothing when no view says so. The mark is `aria-hidden`: the words are the label.
 */
export function UnverifiedSender({ views, testId = "unverified-sender", className = "" }: { views: (SenderProvenance | null | undefined)[]; testId?: string; className?: string }) {
  const { t } = useI18n();
  if (!senderUnverified(...views)) return null;
  return (
    <p role="note" className={`flex max-w-[72ch] items-center gap-1.5 text-sm font-bold text-f-amber-ink ${className}`} data-testid={testId}>
      <AlertIcon width={16} height={16} className="shrink-0" aria-hidden />
      {t(UNVERIFIED_SENDER_KEY)}
    </p>
  );
}
