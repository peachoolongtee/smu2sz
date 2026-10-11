"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useId, useState } from "react";
import { AnnotatedText } from "@/components/annotated-text";
import { OfferItemCard } from "@/components/offer-parts";
import { ArrowRightIcon } from "@/components/icons";
import { Badge, Button, Callout, Card, EmptyState, ErrorState, LoadingBlock, PageHeader, Segmented, textareaClass } from "@/components/ui";
import { ANNOTATION_STYLE, type AnnotationKind } from "@/lib/annotation-style";
import { submitOffer } from "@/lib/api";
import { evaluate as evaluateAndCache } from "@/lib/demo";
import { recordOffer } from "@/lib/demo-store";
import { useI18n } from "@/lib/i18n";
import { annotationsFor, offerItems, type OfferItem } from "@/lib/offer-items";
import { SAMPLES, type SampleId } from "@/lib/samples";
import { useCurrentOffer } from "@/lib/use-current";

const SAMPLE_IDS: SampleId[] = ["EX01", "EX01B", "SEC"];

export default function InboxPage() {
  const { t, te } = useI18n();
  const router = useRouter();
  const current = useCurrentOffer();
  const [active, setActive] = useState<string | null>(null);
  const [busy, setBusy] = useState<"compile" | "evaluate" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sample, setSample] = useState<SampleId>("EX01");
  const [text, setText] = useState(SAMPLES.EX01.documents[0].text);
  const textId = useId();

  async function compile(useText: string) {
    setBusy("compile");
    setError(null);
    try {
      const s = SAMPLES[sample];
      // Unedited sample text is the server fixture; edited text is sent as a document for the compiler.
      const edited = useText.trim() !== s.documents[0].text.trim();
      const doc = { ...s.documents[0], text: useText };
      recordOffer(
        await submitOffer(edited ? { counterparty_id: s.counterparty_id, documents: [doc] } : { fixture_id: s.fixtureId }),
        edited ? undefined : s.fixtureId,
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }

  async function evaluate(offerId: string) {
    setBusy("evaluate");
    setError(null);
    try {
      await evaluateAndCache(offerId);
      router.push("/verdict");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }

  const offer = current.offer;
  const items: OfferItem[] = offer ? offerItems(offer.offer) : [];
  const obligations = items.filter((i) => i.group === "obligation");
  const flags = items.filter((i) => i.group !== "obligation");
  const legendKinds = [...new Set(items.map((i) => i.kind))] as AnnotationKind[];

  return (
    <>
      <PageHeader title={t("inbox.title")} subtitle={t("inbox.subtitle")} />

      <Card id="compose" title={t("inbox.compose")} subtitle={t("inbox.compose.sub")} className="mb-6">
        <div className="space-y-3">
          <Segmented
            label={t("inbox.sample")}
            name="sample"
            value={sample}
            onChange={(v) => {
              setSample(v);
              setText(SAMPLES[v].documents[0].text);
            }}
            options={SAMPLE_IDS.map((id) => ({ value: id, label: te("sample", id) }))}
          />
          <div>
            <label htmlFor={textId} className="mb-1 block text-xs font-medium text-ink-2">
              {t("inbox.message")}
            </label>
            <textarea
              id={textId}
              value={text}
              onChange={(e) => setText(e.target.value)}
              rows={3}
              className={`w-full ${textareaClass}`}
            />
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button variant="primary" loading={busy === "compile"} disabled={!text.trim()} onClick={() => void compile(text)}>
              {t("inbox.compile")}
            </Button>
            <span className="text-xs text-ink-3">{t("inbox.compile.hint")}</span>
          </div>
          {error ? <ErrorState error={error} /> : null}
        </div>
      </Card>

      {current.error ? (
        <ErrorState error={current.error} onRetry={current.reload} />
      ) : current.loading ? (
        <LoadingBlock rows={3} />
      ) : !offer ? (
        <EmptyState
          title={t("inbox.empty.title")}
          body={t("inbox.empty.body")}
          action={
            <Button variant="primary" loading={busy === "compile"} onClick={() => void compile(SAMPLES.EX01.documents[0].text)}>
              {t("inbox.empty.cta")}
            </Button>
          }
        />
      ) : (
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1.35fr)_minmax(0,1fr)]">
          <div className="min-w-0 space-y-4">
            {offer.documents.map((doc) => (
              <Card
                key={doc.doc_id}
                id={`doc-${doc.doc_id}`}
                title={t("inbox.received", { sender: doc.sender_id })}
                subtitle={`${te("channel", doc.channel)} · ${t("common.dayN", { n: doc.received_day })}${doc.filename ? ` · ${doc.filename}` : ""}`}
                actions={<Badge tone={offer.offer.status === "COMPILED" ? "ok" : "warn"}>{te("compilestatus", offer.offer.status)}</Badge>}
              >
                <AnnotatedText
                  ariaLabel={t("inbox.annotated")}
                  text={doc.text}
                  annotations={annotationsFor(items, doc.doc_id, (i) =>
                    i.group === "obligation" ? te("obligation", i.kind) : te("flag", i.kind),
                  )}
                  activeId={active}
                  onActivate={setActive}
                />
                <ul className="mt-3 flex flex-wrap gap-1.5" aria-label={t("inbox.legend")}>
                  {legendKinds.map((k) => (
                    <li
                      key={k}
                      className={`rounded-pill border px-2 py-0.5 text-xs font-medium ${ANNOTATION_STYLE[k].chip}`}
                    >
                      {items.find((i) => i.kind === k)?.group === "obligation" ? te("obligation", k) : te("flag", k)}
                    </li>
                  ))}
                </ul>
                <p className="mt-3 text-xs text-ink-3">
                  {t("inbox.compiler", { compiler: offer.offer.compiler, version: offer.offer.prompt_version })}
                </p>
              </Card>
            ))}
            <div className="flex flex-wrap items-center gap-2">
              <Button variant="primary" loading={busy === "evaluate"} onClick={() => void evaluate(offer.offer.offer_id)}>
                {t("inbox.evaluate")}
                <ArrowRightIcon />
              </Button>
              <Link href="/trajectory" className="text-sm font-medium text-brand-700 underline underline-offset-2">
                {t("inbox.seeTrajectory")}
              </Link>
            </div>
          </div>

          <div className="min-w-0 space-y-4">
            <Card
              id="obligations"
              title={t("inbox.obligations", { n: obligations.length })}
              subtitle={t("inbox.obligations.sub")}
              actions={<Badge tone="info">{t("docs.aiLabel")}</Badge>}
            >
              {obligations.length ? (
                <ul className="space-y-3">
                  {obligations.map((i) => (
                    <OfferItemCard key={i.id} item={i} active={active === i.id} onActivate={setActive} />
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-ink-2">{t("inbox.noObligations")}</p>
              )}
              {offer.offer.abstentions.length ? (
                <div className="mt-3">
                  <Callout tone="warn" title={t("inbox.abstained")}>
                    <ul className="list-disc pl-5">
                      {offer.offer.abstentions.map((a) => (
                        <li key={a.field}>
                          {a.field}: {a.reason}
                        </li>
                      ))}
                    </ul>
                  </Callout>
                </div>
              ) : null}
            </Card>
            <Card id="flags" title={t("inbox.flags", { n: flags.length })} subtitle={t("inbox.flags.sub")} tone={flags.length ? "bad" : undefined}>
              {flags.length ? (
                <ul className="space-y-3">
                  {flags.map((i) => (
                    <OfferItemCard key={i.id} item={i} active={active === i.id} onActivate={setActive} />
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-ink-2">{t("inbox.noFlags")}</p>
              )}
            </Card>
          </div>
        </div>
      )}
    </>
  );
}
