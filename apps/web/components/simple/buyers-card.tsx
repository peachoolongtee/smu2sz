"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Badge, Button, Card, ErrorState, Hash, type Tone } from "@/components/ui";
import { negotiate, submitOffer } from "@/lib/api";
import { evaluate } from "@/lib/demo";
import { recordNegotiation, recordOffer, selectOffer, useDemo, type DemoState } from "@/lib/demo-store";
import type { DictKey } from "@/lib/dictionary";
import { useI18n } from "@/lib/i18n";
import { INBOX, type InboxMessage } from "@/lib/inbox";

type Stage = "new" | "read" | "checked" | "deal" | "noDeal";

const stageTone: Record<Stage, Tone> = { new: "info", read: "neutral", checked: "warn", deal: "ok", noDeal: "neutral" };
const stageKey: Record<Stage, DictKey> = {
  new: "simple.st.new",
  read: "simple.st.read",
  checked: "simple.st.checked",
  deal: "simple.st.deal",
  noDeal: "simple.st.noDeal",
};

/** Where one inbox message stands in this session: the same offer, verdict and negotiation cache the Buyer offers and Our decision pages use. */
function progress(m: InboxMessage, demo: DemoState) {
  const offer = Object.values(demo.offers).find((o) => o.documents[0]?.doc_id === m.document.doc_id) ?? null;
  const id = offer?.offer.offer_id ?? null;
  const verdict = id ? (demo.verdicts[id] ?? null) : null;
  const negotiation = id ? (demo.negotiations[id] ?? null) : null;
  const stage: Stage = negotiation ? (negotiation.outcome === "DEAL" ? "deal" : "noDeal") : verdict ? "checked" : offer ? "read" : "new";
  return { id, verdict, negotiation, stage };
}

/**
 * The owner overview's buyers: every inbox message grouped by buyer, with one button for the next step. "Check this offer"
 * is POST /offers then POST /offers/{id}/evaluate; "Let the agent negotiate" is POST /negotiate/{id}, which records the
 * commitment (terms hash and nonce) and its operations in the ledger. The results go into the shared demo session, so the
 * full overview, Our decision and the ledger show the same offer, verdict and agreement.
 */
export function SimpleBuyersCard() {
  const { t } = useI18n();
  const [openId, setOpenId] = useState<string | null>(null);
  const buyers = [...new Set(INBOX.map((m) => m.company))];

  return (
    <Card
      id="simple-buyers"
      title={t("simple.buyers.title")}
      subtitle={t("simple.buyers.sub")}
      actions={<Badge tone="neutral">{t("simple.buyers.count", { n: INBOX.length })}</Badge>}
    >
      <div className="space-y-4">
        {buyers.map((company) => (
          <section key={company} aria-label={company}>
            <h3 className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-ink-3">{company}</h3>
            <ul className="divide-y divide-line rounded-lg border border-line">
              {INBOX.filter((m) => m.company === company).map((m) => (
                <MessageRow key={m.id} m={m} open={openId === m.id} onToggle={() => setOpenId(openId === m.id ? null : m.id)} />
              ))}
            </ul>
          </section>
        ))}
      </div>
    </Card>
  );
}

function MessageRow({ m, open, onToggle }: { m: InboxMessage; open: boolean; onToggle: () => void }) {
  const { t, te } = useI18n();
  const demo = useDemo();
  const p = progress(m, demo);
  const preview = m.subject ?? m.document.text;

  return (
    <li data-testid={`simple-msg-${m.id}`} data-stage={p.stage}>
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={open}
        className="flex w-full flex-wrap items-center gap-x-3 gap-y-1 px-3 py-2.5 text-left hover:bg-subtle"
      >
        <span className="min-w-0 flex-1 basis-56">
          <span className="block text-sm font-medium text-ink">
            {m.contact}
            <span className="ml-2 text-xs font-normal text-ink-3">
              {te("inbox.source", m.source)} · {m.time}
              {m.role === "unverified" ? ` · ${t("inbox.role.unverified")}` : ""}
            </span>
          </span>
          <span className="block truncate text-xs text-ink-2">{preview}</span>
        </span>
        <Badge tone={m.role === "unverified" && p.stage !== "new" ? "bad" : stageTone[p.stage]}>{t(stageKey[p.stage])}</Badge>
        <span className="text-xs font-medium text-brand-700">{open ? t("simple.msg.close") : t("simple.msg.open")}</span>
      </button>
      {open ? <MessageDetail m={m} /> : null}
    </li>
  );
}

function MessageDetail({ m }: { m: InboxMessage }) {
  const { t, te } = useI18n();
  const router = useRouter();
  const demo = useDemo();
  const p = progress(m, demo);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run(work: () => Promise<void>) {
    setBusy(true);
    setError(null);
    try {
      await work();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  /** Reads the message (once) and evaluates it: the inbox page's "open" and "check" in one step. */
  const check = () =>
    run(async () => {
      let id = p.id;
      if (!id) {
        const offer = await submitOffer(m.fixtureId ? { fixture_id: m.fixtureId } : { counterparty_id: m.counterparty_id, documents: [m.document] });
        recordOffer(offer, m.fixtureId);
        id = offer.offer.offer_id;
      } else {
        selectOffer(id);
      }
      await evaluate(id);
    });

  /** The buyer's side is simulated; the overview uses the cooperative buyer, as the guided demo's first scene does. */
  const deal = () =>
    run(async () => {
      if (!p.id) return;
      selectOffer(p.id);
      recordNegotiation(await negotiate(p.id, { buyer_profile: "cooperative" }));
    });

  function openFull() {
    if (p.id) selectOffer(p.id);
    router.push("/verdict");
  }

  const v = p.verdict;
  const n = p.negotiation;
  const commitment = n?.commitment ?? null;

  return (
    <div className="space-y-3 border-t border-line bg-subtle/50 px-3 py-3" data-testid={`simple-detail-${m.id}`}>
      <div>
        <h4 className="text-xs font-semibold uppercase tracking-wide text-ink-3">{t("simple.msg.text")}</h4>
        <p className="mt-1 whitespace-pre-wrap break-words rounded-md border border-line bg-surface px-3 py-2 text-sm text-ink">{m.document.text}</p>
      </div>

      {!v ? (
        <div className="space-y-2">
          <p className="text-xs text-ink-2">{t("simple.msg.check.hint")}</p>
          <Button variant="primary" loading={busy} onClick={() => void check()} data-testid={`simple-check-${m.id}`}>
            {t("simple.msg.check")}
          </Button>
        </div>
      ) : (
        <div className="space-y-3">
          <div data-testid={`simple-thinks-${m.id}`}>
            <h4 className="text-xs font-semibold uppercase tracking-wide text-ink-3">{t("simple.msg.thinks")}</h4>
            <p className="mt-1 text-sm font-medium text-ink">{t(`simple.why.${v.outcome}` as DictKey)}</p>
            {v.violations.length ? (
              <ul className="mt-1 list-disc space-y-0.5 pl-5 text-sm text-ink-2" aria-label={t("simple.why.broken")}>
                {[...new Set(v.violations.map((x) => x.code))].map((code) => (
                  <li key={code}>{te("violation", code)}</li>
                ))}
              </ul>
            ) : null}
          </div>

          {n ? (
            <div
              className={`rounded-md border px-3 py-2 text-sm ${n.outcome === "DEAL" ? "border-ok-line bg-ok-bg text-ok-fg" : "border-line bg-surface text-ink-2"}`}
              role="status"
              data-testid={`simple-result-${m.id}`}
            >
              <p className="font-medium">
                {n.outcome !== "DEAL" ? t("simple.msg.noDeal") : commitment?.status === "PROPOSED" ? t("simple.msg.dealPending") : t("simple.msg.deal")}
              </p>
              {commitment ? (
                <p className="mt-1 flex flex-wrap items-center gap-2 text-xs text-ink-2">
                  {t("simple.msg.fingerprint")}
                  <Hash value={commitment.terms_hash} />
                </p>
              ) : null}
            </div>
          ) : v.counters.length ? (
            <div className="space-y-2">
              <p className="text-xs text-ink-2">{t("simple.msg.counter.hint")}</p>
              <Button variant="primary" loading={busy} onClick={() => void deal()} data-testid={`simple-negotiate-${m.id}`}>
                {t("simple.msg.negotiate")}
              </Button>
            </div>
          ) : (
            <p className="text-xs text-ink-2">{t("simple.msg.nothing")}</p>
          )}
        </div>
      )}

      {error ? <ErrorState error={error} /> : null}

      {p.id ? (
        <p className="text-xs">
          <button type="button" onClick={openFull} className="font-medium text-brand-700 underline underline-offset-2">
            {t("simple.msg.full")}
          </button>
          {commitment ? (
            <>
              {" · "}
              <Link href="/ledger" className="font-medium text-brand-700 underline underline-offset-2">
                {t("simple.deals.log")}
              </Link>
            </>
          ) : null}
        </p>
      ) : null}
    </div>
  );
}
