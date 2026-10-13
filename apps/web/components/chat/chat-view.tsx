"use client";

import { usePathname, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, type KeyboardEvent } from "react";
import { Badge, Button, EmptyState, Segmented, inputClass } from "@/components/ui";
import { Spinner } from "@/components/icons";
import { requestSignIn, useAuth } from "@/lib/auth";
import {
  COUNTERPARTIES,
  newConversation,
  retryLast,
  sendMessage,
  setCounterparty,
  setDraft,
  setRole,
  useChat,
  useDraft,
  type ChatMessage,
  type CounterpartyId,
} from "@/lib/chat";
import { promptsFor, type Prompt } from "@/lib/chat-prompts";
import type { DictKey } from "@/lib/dictionary";
import { useI18n } from "@/lib/i18n";
import type { NlActor, NlContextEcho, NlScopeUsed } from "@/lib/types";
import { useBusinessShell } from "@/lib/use-business-today";
import { useChatFacts } from "@/lib/use-chat-facts";
import { AssistantTurn } from "./assistant-turn";

function Bubble({ from, children, label }: { from: "user" | "error"; children: React.ReactNode; label: string }) {
  return (
    <div className={`flex ${from === "user" ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[92%] rounded-card px-4 py-2.5 text-sm ${
          from === "user" ? "bg-brand-600 text-white" : "border border-bad-line bg-bad-bg text-bad-fg"
        }`}
      >
        <p className={`mb-0.5 text-meta font-semibold uppercase tracking-wide ${from === "user" ? "text-white" : ""}`}>{label}</p>
        {children}
      </div>
    </div>
  );
}

function Composer({ role, counterpartyId, busy, business }: { role: NlActor; counterpartyId: CounterpartyId; busy: boolean; business: boolean }) {
  const { t } = useI18n();
  // The draft is kept in the browser (tl-chat-draft): a refresh or a closed panel does not lose a half-typed question.
  const text = useDraft();
  const ref = useRef<HTMLTextAreaElement>(null);

  function submit() {
    if (!text.trim() || busy) return;
    void sendMessage(text, undefined, role);
    setDraft("");
    ref.current?.focus();
  }

  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    // Enter sends, Shift+Enter adds a line. Enter while an IME (Chinese input) is composing only confirms the candidate.
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      submit();
    }
  }

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        submit();
      }}
      className="flex items-end gap-2"
    >
      <div className="min-w-0 flex-1">
        <label htmlFor="chat-input" className="sr-only">
          {t("chat.label")}
        </label>
        <textarea
          id="chat-input"
          ref={ref}
          rows={2}
          maxLength={4000}
          value={text}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder={role === "OWNER" ? t(business ? "chat.placeholder.business" : "chat.placeholder.owner") : t("chat.placeholder.buyer", { who: counterpartyId })}
          className="block max-h-40 min-h-13 w-full resize-none rounded-pill border border-line-ui bg-surface px-5 py-3 text-sm text-ink placeholder:text-ink-3"
        />
      </div>
      <Button type="submit" variant="primary" disabled={!text.trim() || busy} loading={busy} data-testid="chat-send">
        {t("chat.send")}
      </Button>
    </form>
  );
}

function Suggestions({ prompts, disabled, compact, role }: { prompts: Prompt[]; disabled: boolean; compact: boolean; role: NlActor }) {
  const { t } = useI18n();
  if (prompts.length === 0) return null;
  return (
    <div>
      <p className="mb-1.5 text-meta font-semibold uppercase tracking-wide text-ink-3">{t("chat.suggested")}</p>
      {/* The chips wrap: a row that scrolls sideways hides questions off the edge. In the panel the rows are capped and scroll up and down. */}
      <ul className={`flex flex-wrap gap-2 ${compact ? "max-h-32 overflow-y-auto pb-1" : ""}`}>
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
              className="motion-press max-w-full rounded-pill border border-line-ui bg-surface px-3 py-1.5 touch:min-h-11 text-left text-meta font-medium text-ink-2 hover:bg-subtle hover:text-ink disabled:cursor-not-allowed disabled:opacity-50"
            >
              <span className="line-clamp-2 break-words">{t(p.label)}</span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

/**
 * The scope chip: what the next question is about, said before it is asked and after. On the Home it follows the address (this deal, this customer, this invoice, your company: the dictionary's words);
 * once an answer has come, the server's own label for the scope it answered in ("The negotiation with Foshan Home Retail Co.") replaces it. Other pages have no scope and show none.
 */
function ScopeChip({ used }: { used: NlScopeUsed | null }) {
  const { t } = useI18n();
  const pathname = usePathname();
  const params = useSearchParams();
  if (pathname !== "/") return null;
  const key = params.get("decision") ? "decision" : params.get("invoice") ? "invoice" : params.get("customer") ? "customer" : "company";
  return (
    <p className="inline-flex w-fit max-w-full items-center gap-1.5 rounded-pill bg-subtle px-3 py-1 text-supporting text-ink-2" data-testid="chat-scope" data-scope={used?.kind ?? key}>
      <span className="truncate">{used ? t("chat.scope.label", { what: used.label }) : t("chat.scope.label", { what: t(`chat.scope.${key}` as DictKey) })}</span>
    </p>
  );
}

/** What the server used from the page for the last answer, said quietly above the composer: "Discussing: the Foshan Home Retail Co. offer". Names, never ids. */
function Discussing({ echo }: { echo: NlContextEcho }) {
  const { t } = useI18n();
  const what = echo.counterparty_name ? t("chat.discussing.offer", { who: echo.counterparty_name }) : echo.invoice_id ? t("chat.discussing.invoice") : null;
  if (!what) return null;
  return (
    <p className="text-meta text-ink-3" data-testid="chat-discussing">
      {t("chat.discussing", { what })}
    </p>
  );
}

/** The conversation: role switch, transcript, suggested prompts and composer. Used by /chat and the slide-over. */
export function ChatView({ variant }: { variant: "page" | "panel" }) {
  const { t, lang } = useI18n();
  const chat = useChat();
  const { token } = useAuth();
  // The Business shell is the owner's alone: no buyer role-play there (it lives in Demo), whatever role a Demo visit left behind.
  const business = useBusinessShell();
  const role: NlActor = business ? "OWNER" : chat.role;
  const conv = chat.convs[role];
  const logRef = useRef<HTMLDivElement>(null);
  const lastRef = useRef<HTMLDivElement>(null);
  const last = conv.messages.at(-1);
  const pathname = usePathname();
  const facts = useChatFacts(role === "OWNER", conv.messages.length);
  const prompts = promptsFor(role, lang, pathname, { business, facts });
  const signedOut = role === "OWNER" && !token;
  const lastAnswer = [...conv.messages].reverse().find((m): m is Extract<ChatMessage, { from: "assistant" }> => m.from === "assistant");
  const echo = lastAnswer?.response.context_echo ?? null;
  const scopeUsed = lastAnswer?.response.scope_used ?? null;

  useEffect(() => {
    // While waiting, show the spinner under the question. Once an answer lands, show it from its first line
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

  return (
    <div className={`flex min-h-0 flex-col gap-3 ${variant === "panel" ? "h-full" : ""}`}>
      <div className="flex flex-wrap items-end gap-x-4 gap-y-2">
        {business ? null : (
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
        )}
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
        <Button size="sm" variant="ghost" className="ml-auto" onClick={newConversation} disabled={conv.messages.length === 0 && !conv.busy} data-testid="chat-new">
          {t("chat.new")}
        </Button>
      </div>

      {business ? null : <p className="text-meta text-ink-3">{role === "OWNER" ? t("chat.hint.owner") : t("chat.hint.buyer")}</p>}

      <div
        ref={logRef}
        role="log"
        aria-label={t("chat.log")}
        aria-live="polite"
        aria-relevant="additions"
        tabIndex={0}
        data-testid="chat-log"
        className={`min-h-48 space-y-3 overflow-y-auto rounded-tile border border-line bg-canvas p-3 ${
          variant === "panel" ? "flex-1" : "max-h-[60dvh] min-h-[20rem]"
        }`}
      >
        {conv.messages.length === 0 ? (
          <EmptyState
            title={t("chat.empty.title")}
            body={role === "OWNER" ? t(business ? "chat.empty.business" : "chat.empty.owner") : t("chat.empty.buyer")}
          />
        ) : (
          conv.messages.map((m: ChatMessage) => (
            <div key={m.id} ref={m === last ? lastRef : undefined} >
              {m.from === "assistant" ? (
                <AssistantTurn response={m.response} active={m === last && !m.restored} busy={conv.busy} restored={m.restored} onSend={(text, display) => void sendMessage(text, display, role)} />
              ) : m.from === "user" ? (
                <Bubble from="user" label={who}>
                  <p className="whitespace-pre-wrap break-words">{m.text}</p>
                </Bubble>
              ) : (
              <Bubble from="error" label={t("chat.err.title")}>
                <div role="alert">
                  <p className="break-words">{m.text}</p>
                  {m === last ? (
                    <div className="mt-2 flex flex-wrap gap-2">
                      {m.status === 401 ? (
                        <Button size="sm" variant="secondary" onClick={() => requestSignIn("required")}>
                          {t("auth.signin")}
                        </Button>
                      ) : null}
                      <Button size="sm" variant="secondary" disabled={conv.busy} onClick={() => void retryLast()} data-testid="chat-retry">
                        {t("common.retry")}
                      </Button>
                    </div>
                  ) : null}
                </div>
              </Bubble>
              )}
            </div>
          ))
        )}
        {conv.busy ? (
          <div role="status" className="flex items-center gap-2 text-sm text-ink-2" data-testid="chat-busy">
            <Spinner />
            {t("chat.thinking")}
          </div>
        ) : null}
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

      <Suggestions prompts={prompts} disabled={conv.busy} compact={conv.messages.length > 0} role={role} />
      {role === "OWNER" ? (
        <Suspense fallback={null}>
          <ScopeChip used={scopeUsed} />
        </Suspense>
      ) : null}
      {echo ? <Discussing echo={echo} /> : null}
      <Composer role={role} counterpartyId={chat.counterpartyId} busy={conv.busy} business={business} />
    </div>
  );
}
