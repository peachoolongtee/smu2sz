"use client";

import { useCallback, useMemo, useState } from "react";
import { PathColumns } from "@/components/deals/path-columns";
import { PathsPicture } from "@/components/deals/paths-picture";
import { RecommendedResponse } from "@/components/deals/response";
import { Card, LoadingBlock } from "@/components/ui";
import { useI18n } from "@/lib/i18n";
import type { Mode } from "@/lib/mode";
import type { NegotiationView, OfferPictureView, PictureMoment, PicturePath, VerdictView } from "@/lib/types";

/** True when the picture carries paths and there is a reply to make (no outcome yet, at least one counter). */
export function pathsUsable(picture: OfferPictureView | null | undefined, negotiation: NegotiationView | null, v: VerdictView): boolean {
  return Boolean(picture?.paths?.length && !negotiation && v.counters.length > 0);
}

/**
 * The reply, as three paths on one chart (a path per line: the offer as asked, then each reply FLOW has ready): the picture with its stops and Play,
 * one column per path and, in the page's one raised bar, the reply for the picked path with the existing send. The recommended reply is picked first and the
 * decisive moment is the first stop. The page reads the picture (it also decides whether the cash facts are said by the chart). Once the buyer has answered, or when the server sent no paths (an older API) or no picture, the card is the
 * present one (`RecommendedResponse`): the outcome, or the counter cards. Every word is the server's.
 */
export function PathsSection({ picture, pictureLoading, ...props }: { v: VerdictView; offerId: string; today: number; mode: Mode; negotiation: NegotiationView | null; compareOpen?: boolean; onCompareChange?: (open: boolean) => void; /** The offer's picture read (null when it could not be read or an older server has none), and whether it is still loading. */ picture: OfferPictureView | null | undefined; pictureLoading: boolean }) {
  const { t } = useI18n();
  const { negotiation, compareOpen } = props;
  const paths = useMemo(() => picture?.paths ?? [], [picture]);
  const moments = useMemo(() => picture?.moments ?? [], [picture]);
  const [pickRaw, setPick] = useState<string | null>(null);
  const [stopRaw, setStop] = useState<number | null>(null);
  const [playing, setPlaying] = useState(false);
  const recommended = paths.find((p) => p.recommended) ?? paths[0] ?? null;
  const pick = pickRaw && paths.some((p) => p.key === pickRaw) ? pickRaw : (recommended?.key ?? "");
  const decisive = Math.max(
    moments.findIndex((m) => m.decisive),
    0,
  );
  const stop = stopRaw !== null && stopRaw < moments.length ? stopRaw : decisive;
  const picked = paths.find((p) => p.key === pick) ?? null;

  // "Before they ask" opens the other reply: the strategy block's link shows it as the path (adjusted while rendering, when the page's flag turns on).
  const other = paths.find((p) => p.kind === "reply" && !p.recommended);
  const [seenCompare, setSeenCompare] = useState(Boolean(compareOpen));
  if (seenCompare !== Boolean(compareOpen)) {
    setSeenCompare(Boolean(compareOpen));
    if (compareOpen && other) setPick(other.key);
  }

  const { onCompareChange } = props;
  const onPick = useCallback(
    (key: string) => {
      setPick(key);
      const p = paths.find((x) => x.key === key);
      onCompareChange?.(Boolean(p && p.kind === "reply" && !p.recommended));
    },
    [paths, onCompareChange],
  );

  const usable = pathsUsable(picture, negotiation, props.v);
  if (!usable) {
    // The outcome, the counter cards, or nothing to compare: the present card. While the picture is still loading the page shows a block, not a flash of cards.
    if (!negotiation && props.v.counters.length > 0 && pictureLoading && picture === undefined) return <LoadingBlock rows={3} />;
    return <RecommendedResponse {...props} />;
  }
  const full = picture as OfferPictureView & { paths: PicturePath[]; moments: PictureMoment[] };
  return (
    <section aria-labelledby="deal-paths-title" id="deal-paths" className="motion-reveal flex min-w-0 flex-col gap-4" data-testid="deal-paths">
      <Card flat id="deal-paths-head" title={t("biz.deals.paths.title")} subtitle={t("biz.deals.paths.sub")}>
        <div className="space-y-4 pt-1">
          <PathsPicture picture={full} pick={pick} onPick={onPick} stop={stop} onStop={setStop} playing={playing} onPlaying={setPlaying} />
          <PathColumns paths={paths} pick={pick} onPick={onPick} moment={moments[stop] ?? null} />
        </div>
      </Card>
      {/* On a phone the reply bar comes first (the answer, then the comparison); from lg it follows the columns. */}
      <div className="max-lg:-order-1">
        <RecommendedResponse
          {...props}
          reply={picked ? { path: picked, recommended, onBack: () => recommended && onPick(recommended.key) } : undefined}
        />
      </div>
    </section>
  );
}
