"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { customerHref, type CustomerContext } from "@/lib/customer-href";
import { originOf } from "@/lib/selection";

const linkClass = "rounded-control underline decoration-line-ui decoration-1 underline-offset-4 hover:text-brand-700 hover:decoration-brand-600";

/** What a customer name's link carries besides the customer: the row's own decision, path and invoice (never the page's selected row's). */
export type OwnContext = Pick<CustomerContext, "decision" | "path" | "invoice">;

/**
 * Every customer name in Deals, Receivables and Activity is this: a link to /customers/{id} whose href carries that row's own context (`decision`, `path`, `invoice`:
 * pass the row's, or nothing) and the origin page (`from`, read from the route), never what the address holds for another row (audit UX07, UX34). The name is the
 * server's string. `className` is added to the link (a row's own weight and size).
 */
export function CustomerName({ id, children, className = "", testId, decision, path, invoice }: { id: string | null | undefined; children: ReactNode; className?: string; testId?: string } & OwnContext) {
  const pathname = usePathname();
  if (!id) return <span className={className}>{children}</span>;
  return (
    <Link href={customerHref(id, { decision, path, invoice, from: originOf(pathname) })} className={`${linkClass} ${className}`} data-testid={testId}>
      {children}
    </Link>
  );
}

/**
 * A dictionary sentence that names the customer ("Agreement with {buyer}") with the name as the link: the sentence is written around a marker
 * and split there, so the words stay the dictionary's in both languages and only the name becomes a link. Without an id it is the plain sentence.
 */
export function CustomerSentence({ id, name, sentence, className, testId, decision, path, invoice }: { id: string | null | undefined; name: string; sentence: (buyer: string) => string; className?: string; testId?: string } & OwnContext) {
  const mark = "\u0001";
  const parts = id ? sentence(mark).split(mark) : [];
  if (!id || parts.length !== 2) return <>{sentence(name)}</>;
  return (
    <>
      {parts[0]}
      <CustomerName id={id} className={className} testId={testId} decision={decision} path={path} invoice={invoice}>
        {name}
      </CustomerName>
      {parts[1]}
    </>
  );
}
