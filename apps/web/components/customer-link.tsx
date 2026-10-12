"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, type ReactNode } from "react";
import { customerHref, readContext } from "@/lib/customer-href";

/** A customer's name as the link to their overview, carrying the context the current URL holds (`decision`, `path`, `invoice`). */
const linkClass = "rounded-control underline decoration-line-ui decoration-1 underline-offset-4 hover:text-brand-700 hover:decoration-brand-600";

function Linked({ id, children, className, testId }: { id: string; children: ReactNode; className: string; testId?: string }) {
  const href = customerHref(id, readContext(useSearchParams()));
  return (
    <Link href={href} className={className} data-testid={testId}>
      {children}
    </Link>
  );
}

/**
 * Every customer name in Deals, Receivables, Cash and Activity is this: a link to /customers/{id} whose href is `customerHref(id, ctx)`, `ctx` read
 * from the URL the owner is on, so the overview's back link puts them where they were. The name is the server's string. While the URL is being
 * read (and in the static page) the plain name stands, so nothing shifts. `className` is added to the link (a row's own weight and size).
 */
export function CustomerName({ id, children, className = "", testId }: { id: string | null | undefined; children: ReactNode; className?: string; testId?: string }) {
  if (!id) return <span className={className}>{children}</span>;
  return (
    <Suspense fallback={<span className={className}>{children}</span>}>
      <Linked id={id} className={`${linkClass} ${className}`} testId={testId}>
        {children}
      </Linked>
    </Suspense>
  );
}

/**
 * A dictionary sentence that names the customer ("Agreement with {buyer}") with the name as the link: the sentence is written around a marker
 * and split there, so the words stay the dictionary's in both languages and only the name becomes a link. Without an id it is the plain sentence.
 */
export function CustomerSentence({ id, name, sentence, className, testId }: { id: string | null | undefined; name: string; sentence: (buyer: string) => string; className?: string; testId?: string }) {
  const mark = "\u0001";
  const parts = id ? sentence(mark).split(mark) : [];
  if (!id || parts.length !== 2) return <>{sentence(name)}</>;
  return (
    <>
      {parts[0]}
      <CustomerName id={id} className={className} testId={testId}>
        {name}
      </CustomerName>
      {parts[1]}
    </>
  );
}
