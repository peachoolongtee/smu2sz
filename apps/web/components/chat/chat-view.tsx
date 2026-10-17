"use client";

import { usePathname } from "next/navigation";
import { Suspense, useEffect, useRef, type KeyboardEvent } from "react";
import { Badge, Button, Segmented, inputClass } from "@/components/ui";
import { SegmentedTabs } from "@/components/ui/segmented-tabs";
import { ArrowUpIcon, Spinner } from "@/components/icons";
import { requestSignIn, useAuth } from "@/lib/auth";
import {
  COUNTERPARTIES,
  newConversation,
  retryLast,
  sendMessage,
  setCounterparty,
  setDraft,
  setRole,
  startOpener,
  useChat,
  useDraft,
  type ChatMessage,
  type CounterpartyId,
} from "@/lib/chat";
import { promptsFor, type Prompt } from "@/lib/chat-prompts";
import type { DictKey } from "@/lib/dictionary";
import { useI18n } from "@/lib/i18n";
import type { NlActor, NlScopeUsed } from "@/lib/types";
import { useChatScope } from "@/lib/chat-scope";
import { useDecision } from "@/lib/use-decision";
import type { ScopeKind } from "@/lib/selection";
import { useBusinessShell } from "@/lib/use-business-today";
import { useChatFacts } from "@/lib/use-chat-facts";
import { AssistantTurn } from "./assistant-turn";
import { FlowMark } from "./flow-mark";

/** Where the conversation is shown: the Demo's /chat page, the side panel, or the Ask FLOW page (`/ask`, the panel expanded). */
export type ChatVariant = "page" | "panel" | "full";

/** The owner's message: a light bubble on the right, unlabelled (a screen reader hears who said it). */
function UserBubble({ children, who }: { children: React.ReactNode; who: string }) {
  return (
    <div className="flex justify-end ask-in" data-testid="chat-user">
      <div className="max-w-[85%] rounded-[20px] rounded-br-md bg-f-purple-soft px-4 py-2.5 text-sm text-f-ink">
        <span className="sr-only">{who}: </span>
        {children}
      </div>
    </div>
  );
}

/** A turn that did not go through: on FLOW's side, in the risk tone, with Retry. */
function ErrorBubble({ children, title }: { children: React.ReactNode; title: string }) {
  return (
    <div className="flex items-start gap-2.5">
      <FlowMark />
      <div className="min-w-0 flex-1 rounded-[16px] border border-bad-line bg-bad-bg px-4 py-2.5 text-sm text-bad-fg">
        <p className="mb-0.5 text-meta font-semibold">{title}</p>
        {children}
      </div>
    </div>
  );
}

/** FLOW is working it out: three dots on FLOW's side (still under reduced motion), and the words for a screen reader. */
function Typing() {
  const { t } = useI18n();
  return (
    <div role="status" className="flex items-center gap-2.5" data-testid="chat-busy">
      <FlowMark />
      <span className="inline-flex items-center gap-1 rounded-pill bg-panel px-3 py-2.5" aria-hidden>
        <span className="ask-dot size-1.5 rounded-pill bg-ink-3" />
        <span className="ask-dot size-1.5 rounded-pill bg-ink-3" />
        <span className="ask-dot size-1.5 rounded-pill bg-ink-3" />
      </span>
      <span className="sr-only">{t("ask.typing")}</span>
    </div>
  );
}

/** The kind words of the chip, in the dictionary. */
const KIND_LABEL: Record<ScopeKind, DictKey> = { company: "chat.scope.company", customer: "chat.scope.customer", invoice: "chat.scope.invoice", decision: "chat.scope.decision" };

/**
 * The scope chip, inside the composer (ticket #130): what the next question is about, from the address, with the kinds it can be asked at (Company always; Customer, Invoice and
 * Decision when the page holds them). The owner can widen it; the choice is for this route and is gone when the route changes. It names what it is about in words (the deal's
 * decision record names the customer), never an id.
 */
function ScopeChip({ disabled }: { disabled: boolean }) {
  const { t } = useI18n();
  const { kinds, chosen, choose } = useChatScope();
  const record = useDecision(chosen.decision ?? null).data;
  const name = chosen.decision ? (record?.headline ?? record?.counterparty_name ?? null) : null;
  return (
    <div className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1" role="group" aria-label={t("chat.scope.label")} data-testid="chat-scope" data-kind={chosen.kind}>
      <span className="text-supporting font-semibold text-ink-3">{t("chat.scope.about")}</span>
      <SegmentedTabs
        compact
        label={t("chat.scope.label")}
        value={chosen.kind}
        onChange={(k) => !disabled && choose(k)}
        tabs={kinds.map((k) => ({ value: k, label: t(KIND_LABEL[k]), testId: `chat-scope-${k}` }))}
      />
      {name ? (
        <span className="min-w-0 truncate text-supporting text-ink-3" data-testid="chat-scope-name">
          {name}
        </span>
      ) : null}
    </div>
  );
}

/**
 * What the server used for the last answer, said quietly above the composer: "Answered about: Customer, Foshan Home Retail Co.". When it used another kind than the one the
 * owner chose, that is said too, not hidden.
 */
function Discussing({ used, asked }: { used: NlScopeUsed; asked: ScopeKind | null }) {
  const { t } = useI18n();
  const mismatch = asked !== null && used.kind !== asked;
  return (
    <p className={`px-1 text-supporting ${mismatch ? "font-medium text-warn-fg" : "text-ink-3"}`} data-testid="chat-discussing" data-mismatch={mismatch ? "true" : "false"}>
      {mismatch ? t("chat.scope.mismatch", { asked: t(KIND_LABEL[asked]), used: used.label }) : t("chat.scope.used", { what: used.label })}
    </p>
  );
}

/**
 * The composer: one rounded box holding what the question is about (the owner's scope chip), the message (multi-line: Enter sends, Shift+Enter adds a line, and Enter while an IME
 * is composing a Chinese word only confirms it) and the round send button. The draft is kept in the browser (tl-chat-draft): a refresh or a closed panel does not lose it.
 */
function Composer({ role, counterpartyId, busy, business, variant }: { role: NlActor; counterpartyId: CounterpartyId; busy: boolean; business: boolean; variant: ChatVariant }) {
  const { t } = useI18n();
  const text = useDraft();
  const ref = useRef<HTMLTextAreaElement>(null);

  // The box grows with the message up to its cap, then scrolls.
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  }, [text]);

  function submit() {
    if (!text.trim() || busy) return;
    void sendMessage(text, undefined, role);
    setDraft("");
    ref.current?.focus();
  }

  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    // Enter sends, Shift+Enter adds a line. Enter while an IME (Chinese input) is composing only confirms the candidate (keyCode 229 is the IME's own Enter in older engines).
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing && e.keyCode !== 229) {
      e.preventDefault();
      submit();
    }
  }

  const placeholder =
    role === "OWNER" ? t(variant === "full" ? "ask.placeholder" : business ? "chat.placeholder.business" : "chat.placeholder.owner") : t("chat.placeholder.buyer", { who: counterpartyId });

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        submit();
      }}
      className="rounded-[24px] border border-line-ui bg-card px-3 pb-2 pt-2.5 shadow-(--shadow-f) focus-within:border-ink"
      data-testid="chat-composer"
    >
      {role === "OWNER" ? (
        <div className="mb-1.5 px-1">
          <ScopeChip disabled={busy} />
        </div>
      ) : null}
      <label htmlFor={`chat-input-${variant}`} className="sr-only">
        {t("chat.label")}
      </label>
      <textarea
        id={`chat-input-${variant}`}
        ref={ref}
        rows={1}
        maxLength={4000}
        value={text}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={onKeyDown}
        placeholder={placeholder}
        aria-describedby={`chat-hint-${variant}`}
        className="block max-h-40 min-h-11 w-full resize-none bg-transparent px-1.5 py-2 text-sm leading-relaxed text-ink outline-none focus-own placeholder:text-ink-3"
        data-testid="chat-input"
      />
      <div className="flex items-center justify-between gap-2">
        <p id={`chat-hint-${variant}`} className="min-w-0 truncate px-1.5 text-supporting text-ink-3 max-sm:sr-only">
          {t("ask.enterHint")}
        </p>
        <button
          type="submit"
          disabled={!text.trim() || busy}
          aria-label={t("chat.send")}
          title={t("chat.send")}
          data-testid="chat-send"
          className="motion-press ml-auto grid size-10 shrink-0 place-items-center rounded-pill bg-f-btn text-f-btn-ink hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-35 touch:size-11"
        >
          {busy ? <Spinner /> : <ArrowUpIcon width={18} height={18} />}
        </button>
      </div>
    </form>
  );
}

function Suggestions({ prompts, disabled, compact, role }: { prompts: Prompt[]; disabled: boolean; compact: boolean; role: NlActor }) {
  const { t } = useI18n();
  if (prompts.length === 0) return null;
  return (
    <div>
      <p className="sr-only">{t("chat.suggested")}</p>
      {/* The chips wrap: a row that scrolls sideways hides questions off the edge. In the panel the rows are capped and scroll up and down. */}
      <ul className={`flex flex-wrap gap-2 ${compact ? "max-h-32 overflow-y-auto pb-1" : ""}`} aria-label={t("chat.suggested")}>
        {prompts.map((p) => (
          <li key={p.id} className="min-w-0 max-w-full">
            <button
              type="button"
              disabled={disabled}
              data-testid={`prompt-${p.id}`}
              onClick={() => {
                if (p.counterparty) setCounterparty(p.counterparty);
                void sendMessage(p.text, p.text, role);
              }}
              className="motion-press max-w-full rounded-pill border border-line bg-card px-3 py-1.5 text-left text-meta font-medium text-ink-2 hover:border-[color-mix(in_srgb,var(--color-f-purple)_45%,var(--color-f-line))] hover:bg-f-purple-soft hover:text-f-purple-ink disabled:cursor-not-allowed disabled:opacity-50 touch:min-h-11"
            >
              <span className="line-clamp-2 break-words">{t(p.label)}</span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** The Ask FLOW page's empty state: the greeting and four questions as cards (a title and one line), then the composer below. */
function Welcome({ prompts, disabled, role, children }: { prompts: Prompt[]; disabled: boolean; role: NlActor; children?: React.ReactNode }) {
  const { t } = useI18n();
  return (
    <div className="flex flex-col items-center gap-6 py-4 text-center sm:py-8" data-testid="ask-welcome">
      <FlowMark size="md" />
      <div className="space-y-1.5">
        <h2 className="font-display text-2xl font-bold tracking-[-0.02em] text-f-ink sm:text-[28px]">{t("ask.greeting")}</h2>
        <p className="mx-auto max-w-[46ch] text-pretty text-sm text-ink-3">{t("ask.greeting.sub")}</p>
      </div>
      {/* FLOW's opener, when something needs the owner, before the questions. */}
      {children ? <div className="w-full space-y-5 text-left">{children}</div> : null}
      <ul className="grid w-full gap-3 text-left sm:grid-cols-2" aria-label={t("ask.suggestions")}>
        {prompts.map((p) => (
          <li key={p.id} className="min-w-0">
            <button
              type="button"
              disabled={disabled}
              data-testid={`prompt-${p.id}`}
              onClick={() => void sendMessage(p.text, p.text, role)}
              className="motion-press flex h-full w-full flex-col items-start gap-1 rounded-[18px] border border-line bg-card px-4 py-3.5 text-left shadow-(--shadow-f) hover:border-[color-mix(in_srgb,var(--color-f-purple)_45%,var(--color-f-line))] hover:shadow-(--shadow-lift) disabled:cursor-not-allowed disabled:opacity-50"
            >
              <span className="text-sm font-semibold text-f-ink">{t(p.label)}</span>
              {p.sub ? <span className="text-supporting text-ink-3">{t(p.sub)}</span> : null}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** The conversation: role switch (Demo), transcript, suggested prompts and composer. Used by /chat, the side panel and the Ask FLOW page. */
export function ChatView({ variant }: { variant: ChatVariant }) {
  // The scope reads the address, which a statically built page may not have yet: the conversation waits for it.
  return (
    <Suspense fallback={null}>
      <ChatViewInner variant={variant} />
    </Suspense>
  );
}

function ChatViewInner({ variant }: { variant: ChatVariant }) {
  const { t, lang } = useI18n();
  const chat = useChat();
  const { token } = useAuth();
  // The Business shell is the owner's alone: no buyer role-play there (it lives in Demo), whatever role a Demo visit left behind.
  const business = useBusinessShell();
  const role: NlActor = business || variant === "full" ? "OWNER" : chat.role;
  const conv = chat.convs[role];
  const draft = useDraft();
  const logRef = useRef<HTMLDivElement>(null);
  const lastRef = useRef<HTMLDivElement>(null);
  const last = conv.messages.at(-1);
  const pathname = usePathname();
  const facts = useChatFacts(role === "OWNER", conv.messages.length);
  const prompts = promptsFor(role, lang, pathname, { business, facts });
  const signedOut = role === "OWNER" && !token;
  const lastAnswer = [...conv.messages].reverse().find((m): m is Extract<ChatMessage, { from: "assistant" }> => m.from === "assistant");
  // The server's `scope_used`; a server that does not send it yet still echoes what it bound (`context_echo`), which says the same in fewer words.
  const echo = lastAnswer?.response.context_echo ?? null;
  const used: NlScopeUsed | null = lastAnswer?.response.scope_used ?? (echo?.counterparty_name ? { kind: echo.offer_id ? "decision" : "customer", label: echo.counterparty_name } : echo?.invoice_id ? { kind: "invoice", label: t("chat.discussing.invoice") } : null);
  const empty = conv.messages.length === 0;

  // FLOW speaks first when the side panel or the Ask FLOW page opens on the owner's empty conversation (lib/chat.ts startOpener: once per conversation, owner only).
  useEffect(() => {
    if (variant !== "page" && role === "OWNER" && token) void startOpener(lang);
    // Once per opening: "New conversation" leaves the fresh conversation empty until the panel or the page is opened again.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [variant, role, Boolean(token)]);

  useEffect(() => {
    // While waiting, show the typing dots under the question. Once an answer lands, show it from its first line
    // (a long answer scrolled to its end would hide the verdict and the reply).
    const log = logRef.current;
    if (!log) return;
    const id = requestAnimationFrame(() => {
      if (conv.busy) log.scrollTop = log.scrollHeight;
      else if (lastRef.current) log.scrollTop += lastRef.current.getBoundingClientRect().top - log.getBoundingClientRect().top - 12;
    });
    return () => cancelAnimationFrame(id);
  }, [conv.messages.length, conv.busy]);

  const who = role === "OWNER" ? t("chat.you") : t("chat.youBuyer", { who: chat.counterpartyId });
  // The Ask FLOW page greets until the owner has asked something: FLOW's opener (if it spoke) sits under the greeting, above the four questions.
  const welcome = variant === "full" && !conv.messages.some((m) => m.from !== "assistant");
  const transcript = conv.messages.map((m: ChatMessage) => (
    <div key={m.id} ref={m === last ? lastRef : undefined}>
      {m.from === "assistant" ? (
        <AssistantTurn response={m.response} active={m === last && !m.restored} busy={conv.busy} restored={m.restored} onSend={(text, display) => void sendMessage(text, display, role)} />
      ) : m.from === "user" ? (
        <UserBubble who={who}>
          <p className="whitespace-pre-wrap break-words">{m.text}</p>
        </UserBubble>
      ) : (
        <ErrorBubble title={t("chat.err.title")}>
          <div role="alert">
            <p className="break-words">{m.text}</p>
            {m === last ? (
              <div className="mt-2 flex flex-wrap gap-2">
                {m.status === 401 ? (
                  <Button size="sm" variant="secondary" onClick={() => requestSignIn("required")}>
                    {t("auth.signin")}
                  </Button>
                ) : null}
                <Button size="sm" variant="secondary" disabled={conv.busy} onClick={() => void retryLast(role)} data-testid="chat-retry">
                  {t("common.retry")}
                </Button>
              </div>
            ) : null}
          </div>
        </ErrorBubble>
      )}
    </div>
  ));
  // The chips sit above the box while the conversation is empty or the box is (a half-typed question is not crowded by them); the Ask FLOW page's empty state shows its cards instead.
  const showChips = !welcome && (empty || draft.trim() === "");

  return (
    <div className={`flex min-h-0 flex-col gap-3 ${variant === "panel" ? "h-full" : ""}`}>
      {business || variant === "full" ? null : (
        <div className="flex flex-wrap items-end gap-x-4 gap-y-2">
          <Segmented<NlActor>
            label={t("chat.role")}
            name={`chat-role-${variant}`}
            value={chat.role}
            onChange={setRole}
            options={[
              { value: "OWNER", label: t("chat.role.owner") },
              { value: "COUNTERPARTY", label: t("chat.role.buyer") },
            ]}
          />
          {role === "COUNTERPARTY" ? (
            <div>
              <label htmlFor={`chat-cp-${variant}`} className="mb-0.5 block text-meta font-medium text-ink-3">
                {t("chat.counterparty")}
              </label>
              <select
                id={`chat-cp-${variant}`}
                value={chat.counterpartyId}
                onChange={(e) => setCounterparty(e.target.value as CounterpartyId)}
                className={inputClass}
                data-testid="chat-counterparty"
              >
                {COUNTERPARTIES.map((id) => (
                  <option key={id} value={id}>
                    {t(`chat.cp.${id}` as DictKey)}
                  </option>
                ))}
              </select>
            </div>
          ) : null}
          {/* The side panel and the Ask FLOW page carry "New conversation" in their header; the Demo's /chat page keeps it here. */}
          {variant === "page" ? (
            <Button size="sm" variant="ghost" className="ml-auto" onClick={() => newConversation(role)} disabled={conv.messages.length === 0 && !conv.busy && conv.sessionId === null} data-testid="chat-new">
              {t("chat.new")}
            </Button>
          ) : null}
        </div>
      )}
      {business && variant === "page" ? (
        <div className="flex justify-end">
          <Button size="sm" variant="ghost" onClick={() => newConversation(role)} disabled={conv.messages.length === 0 && !conv.busy && conv.sessionId === null} data-testid="chat-new">
            {t("chat.new")}
          </Button>
        </div>
      ) : null}

      {business || variant === "full" ? null : <p className="text-meta text-ink-3">{role === "OWNER" ? t("chat.hint.owner") : t("chat.hint.buyer")}</p>}

      <div
        ref={logRef}
        role="log"
        aria-label={t("chat.log")}
        aria-live="polite"
        aria-relevant="additions"
        tabIndex={0}
        data-testid="chat-log"
        className={`min-h-0 space-y-5 overflow-y-auto rounded-tile px-1 py-2 outline-none focus-own ${
          variant === "panel" ? "flex-1" : variant === "full" ? (welcome ? "" : "max-h-[calc(100dvh-19rem)] min-h-[12rem]") : "max-h-[60dvh] min-h-[20rem]"
        }`}
      >
        {welcome ? (
          <Welcome prompts={prompts} disabled={conv.busy} role={role}>
            {transcript}
            {conv.busy ? <Typing /> : null}
          </Welcome>
        ) : empty && !conv.busy ? (
          <div className="flex flex-col items-start gap-2 px-1 py-4" data-testid="chat-empty">
            <div className="flex items-center gap-2.5">
              <FlowMark />
              <p className="text-base font-semibold text-f-ink">{t("ask.greeting")}</p>
            </div>
            <p className="pl-[38px] text-sm text-ink-3">{role === "OWNER" ? t(business ? "chat.empty.business" : "chat.empty.owner") : t("chat.empty.buyer")}</p>
          </div>
        ) : (
          transcript
        )}
        {conv.busy && !welcome ? <Typing /> : null}
      </div>

      {signedOut ? (
        <div className="flex flex-wrap items-center gap-2 rounded-tile border border-warn-line bg-warn-bg px-3 py-2 text-sm text-warn-fg" data-testid="chat-signed-out">
          <Badge tone="warn">{t("auth.signedIn")}</Badge>
          <span className="min-w-0 flex-1">{t("chat.signinBanner")}</span>
          <Button size="sm" variant="secondary" onClick={() => requestSignIn("required")}>
            {t("auth.signin")}
          </Button>
        </div>
      ) : null}

      {showChips ? <Suggestions prompts={prompts} disabled={conv.busy} compact={!empty} role={role} /> : null}
      {used ? <Discussing used={used} asked={lastAnswer?.asked?.kind ?? null} /> : null}
      <Composer role={role} counterpartyId={chat.counterpartyId} busy={conv.busy} business={business} variant={variant} />
    </div>
  );
}
