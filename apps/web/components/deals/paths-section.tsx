"use client";

import { useCallback, useMemo, useState } from "react";
import { PathColumns } from "@/components/deals/path-columns";
import { PathsPicture } from "@/components/deals/paths-picture";
import { RecommendedResponse } from "@/components/deals/response";
import { Card, LoadingBlock } from "@/components/ui";
import { useI18n } from "@/lib/i18n";
import type { Mode } from "@/lib/mode";
import type { CounterEconomics, NegotiationView, OfferPictureView, PictureMoment, PicturePath, VerdictView } from "@/lib/types";

/** True when the picture carries paths and there is a reply to make (no outcome yet, at least one counter). */
export function pathsUsable(picture: OfferPictureView | null | undefined, negotiation: NegotiationView | null, v: VerdictView): boolean {
  return Boolean(picture && picture.available !== false && picture.paths?.length && !negotiation && v.counters.length > 0);
}

/** What the reply area and the paths share: which path is picked, which moment the cursor is on, and which path is being pointed at. */
export interface PathsState {
  paths: PicturePath[];
  moments: PictureMoment[];
  pick: string;
  onPick: (key: string) => void;
  stop: number;
  onStop: (i: number) => void;
  hoverKey: string | null;
  onHover: (key: string | null) => void;
  picked: PicturePath | null;
  recommended: PicturePath | null;
  /** What the reply bar now shows, said politely after a pick (the bar sits far above the columns); empty until the owner picks. */
  said: string;
}

/**
 * The state of the paths, held by the page so the reply bar (right under the heading) and the picture with its columns (below it) can sit in the
 * order the owner reads them while one pick and one cursor drive both. The recommended reply is picked first and the decisive moment is the first stop.
 * "Before they ask" opens the other reply: the strategy block's link shows it as the path (adjusted while rendering, when the page's flag turns on).
 */
export function usePathsState(picture: OfferPictureView | null | undefined, resetKey: string | null, compareOpen: boolean | undefined, onCompareChange: ((open: boolean) => void) | undefined): PathsState {
  const paths = useMemo(() => picture?.paths ?? [], [picture]);
  const moments = useMemo(() => picture?.moments ?? [], [picture]);
  const [pickRaw, setPick] = useState<string | null>(null);
  const [stopRaw, setStop] = useState<number | null>(null);
  const [hoverKey, setHoverKey] = useState<string | null>(null);
  // Another offer starts on its own recommended reply and decisive moment, as when the paths were mounted per offer.
  const [seenKey, setSeenKey] = useState(resetKey);
  if (seenKey !== resetKey) {
    setSeenKey(resetKey);
    setPick(null);
    setStop(null);
    setHoverKey(null);
  }
  const recommended = paths.find((p) => p.recommended) ?? paths[0] ?? null;
  const pick = pickRaw && paths.some((p) => p.key === pickRaw) ? pickRaw : (recommended?.key ?? "");
  const decisive = Math.max(
    moments.findIndex((m) => m.decisive),
    0,
  );
  const stop = stopRaw !== null && stopRaw < moments.length ? stopRaw : decisive;
  const picked = paths.find((p) => p.key === pick) ?? null;

  const other = paths.find((p) => p.kind === "reply" && !p.recommended);
  const [seenCompare, setSeenCompare] = useState(Boolean(compareOpen));
  if (seenCompare !== Boolean(compareOpen)) {
    setSeenCompare(Boolean(compareOpen));
    if (compareOpen && other) setPick(other.key);
  }

  const { t } = useI18n();
  const [said, setSaid] = useState("");
  const onPick = useCallback(
    (key: string) => {
      setPick(key);
      const named = paths.find((x) => x.key === key);
      if (named) setSaid(t("biz.deals.reply.shows", { label: named.label }));
      const p = paths.find((x) => x.key === key);
      onCompareChange?.(Boolean(p && p.kind === "reply" && !p.recommended));
    },
    [paths, onCompareChange, t],
  );
  return { paths, moments, pick, onPick, stop, onStop: setStop, hoverKey, onHover: setHoverKey, picked, recommended, said };
}

type ReplyProps = { v: VerdictView; offerId: string; today: number; mode: Mode; negotiation: NegotiationView | null; compareOpen?: boolean; onCompareChange?: (open: boolean) => void };

/**
 * The reply, in the page's one raised bar for the picked path with the existing send (right under the heading, sticky from `lg`). While the picture is on
 * its way it is a quiet placeholder, never the counter cards (an owner who opened a send there would lose it when the paths arrive). Once the buyer has
 * answered, or when the server sent no paths (an older API) or no picture, it is the present card (`RecommendedResponse`): the outcome, or the counter
 * cards, with the server's sentence when the offer can no longer be drawn. Every word is the server's.
 */
export function PathsReply({ picture, state, ...props }: ReplyProps & { state: PathsState; /** The offer's picture read: undefined while it is on its way, null when it was not asked for, failed or an older server has none. */ picture: OfferPictureView | null | undefined }) {
  const { negotiation } = props;
  if (!negotiation && props.v.counters.length > 0 && picture === undefined) {
    return (
      <div data-testid="paths-loading">
        <LoadingBlock rows={3} />
      </div>
    );
  }
  if (!pathsUsable(picture, negotiation, props.v)) {
    const unavailable = picture && picture.available === false ? picture.unavailable_text : null;
    return (
      <>
        {unavailable ? (
          <p className="mb-3 text-sm text-ink-3" data-testid="paths-unavailable">
            {unavailable}
          </p>
        ) : null}
        <RecommendedResponse {...props} />
      </>
    );
  }
  const { picked, recommended, onPick } = state;
  return <RecommendedResponse {...props} reply={picked ? { path: picked, recommended, onBack: () => recommended && onPick(recommended.key) } : undefined} />;
}

/**
 * The picture of the three paths with its moments, then one column per path (a path per line: the offer as asked, then each reply FLOW has ready). Nothing
 * is drawn while there is nothing to compare (no paths, an outcome already, or the picture still on its way).
 */
export function PathsBody({ picture, state, v, negotiation }: { picture: OfferPictureView | null | undefined; state: PathsState; v: VerdictView; negotiation: NegotiationView | null }) {
  const { t } = useI18n();
  if (!pathsUsable(picture, negotiation, v)) return null;
  const full = picture as OfferPictureView & { paths: PicturePath[]; moments: PictureMoment[] };
  const economics = (p: PicturePath): CounterEconomics | null => v.counters.find((c) => c.id === p.key || (c.label_when ?? c.label) === p.label)?.economics ?? null;
  return (
    <section aria-labelledby="deal-paths-title" id="deal-paths" className="motion-reveal min-w-0" data-testid="deal-paths">
      <Card flat id="deal-paths-head" title={t("biz.deals.paths.title")}>
        <div className="space-y-3 pt-1">
          <p role="status" className="sr-only" data-testid="path-pick-status">
            {state.said}
          </p>
          <PathsPicture picture={full} pick={state.pick} hoverKey={state.hoverKey} onHover={state.onHover} stop={state.stop} onStop={state.onStop} />
          <PathColumns paths={state.paths} pick={state.pick} onPick={state.onPick} onHover={state.onHover} economics={economics} windowMonths={v.workspace?.financial_impact.window_months ?? null} />
        </div>
      </Card>
    </section>
  );
}
