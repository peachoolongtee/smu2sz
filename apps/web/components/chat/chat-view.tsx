"use client";

import { usePathname } from "next/navigation";
import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { Badge, Button, EmptyState, Segmented } from "@/components/ui";
import { Spinner } from "@/components/icons";
import { requestSignIn, useAuth } from "@/lib/auth";
import {
  COUNTERPARTIES,
  newConversation,
  retryLast,
  sendMessage,
  setCounterparty,
  setRole,
  useChat,
  type ChatMessage,
  type CounterpartyId,
} from "@/lib/chat";
import { promptsFor, type Prompt } from "@/lib/chat-prompts";
import type { DictKey } from "@/lib/dictionary";
import { useI18n } from "@/lib/i18n";
import type { NlActor } from "@/lib/types";
import { AssistantTurn } from "./assistant-turn";

function Bubble({ from, children, label }: { from: "user" | "error"; children: React.ReactNode; label: string }) {
  return (
    <div className={`flex ${from === "user" ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[92%] rounded-lg px-3 py-2 text-sm ${
          from === "user" ? "bg-brand-600 text-white" : "border border-bad-line bg-bad-bg text-bad-fg"
        }`}
      >
        <p className={`mb-0.5 text-[0.7rem] font-semibold uppercase tracking-wide ${from === "user" ? "text-white/80" : ""}`}>{label}</p>
        {children}
      </div>
    </div>
  );
}

function Composer({ role, counterpartyId, busy }: { role: NlActor; counterpartyId: CounterpartyId; busy: boolean }) {
  const { t } = useI18n();
  const [text, setText] = useState("");
  const ref = useRef<HTMLTextAreaElement>(null);

  function submit() {
    if (!text.trim() || busy) return;
    void sendMessage(text);
    setText("");
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
          onChange={(e) => setText(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder={role === "OWNER" ? t("chat.placeholder.owner") : t("chat.placeholder.buyer", { who: counterpartyId })}
          className="block max-h-40 min-h-[3.25rem] w-full resize-y rounded-md border border-line-strong bg-surface px-3 py-2 text-sm text-ink placeholder:text-ink-3"
        />
      </div>
      <Button type="submit" variant="primary" disabled={!text.trim() || busy} loading={busy} data-testid="chat-send">
        {t("chat.send")}
      </Button>
    </form>
  );
}

function Suggestions({ prompts, disabled, compact }: { prompts: Prompt[]; disabled: boolean; compact: boolean }) {
  const { t } = useI18n();
  return (
    <div>
      <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-ink-3">{t("chat.suggested")}</p>
      <ul className={`flex gap-2 ${compact ? "overflow-x-auto pb-1" : "flex-wrap"}`}>
        {prompts.map((p) => (
          <li key={p.id} className="shrink-0">
            <button
              type="button"
              disabled={disabled}
              data-testid={`prompt-${p.id}`}
              onClick={() => {
                if (p.counterparty) setCounterparty(p.counterparty);
                void sendMessage(p.text, p.text);
              }}
              className="max-w-72 rounded-full border border-line-strong bg-surface px-3 py-1.5 text-left text-xs font-medium text-ink-2 hover:bg-subtle hover:text-ink disabled:cursor-not-allowed disabled:opacity-50"
            >
              <span className="line-clamp-2 break-words">{t(p.label)}</span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** The conversation: role switch, transcript, suggested prompts and composer. Used by /chat and the slide-over. */
export function ChatView({ variant }: { variant: "page" | "panel" }) {
  const { t, lang } = useI18n();
  const chat = useChat();
  const { token } = useAuth();
  const conv = chat.convs[chat.role];
  const logRef = useRef<HTMLDivElement>(null);
  const lastRef = useRef<HTMLDivElement>(null);
  const last = conv.messages.at(-1);
  const pathname = usePathname();
  const prompts = promptsFor(chat.role, lang, pathname);
  const signedOut = chat.role === "OWNER" && !token;

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

  const who = chat.role === "OWNER" ? t("chat.you") : t("chat.youBuyer", { who: chat.counterpartyId });

  return (
    <div className={`flex min-h-0 flex-col gap-3 ${variant === "panel" ? "h-full" : ""}`}>
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
        {chat.role === "COUNTERPARTY" ? (
          <div>
            <label htmlFor={`chat-cp-${variant}`} className="mb-0.5 block text-xs font-medium text-ink-3">
              {t("chat.counterparty")}
            </label>
            <select
              id={`chat-cp-${variant}`}
              value={chat.counterpartyId}
              onChange={(e) => setCounterparty(e.target.value as CounterpartyId)}
              className="min-h-9 rounded-md border border-line-strong bg-surface px-2 text-sm text-ink"
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

      <p className="text-xs text-ink-3">{chat.role === "OWNER" ? t("chat.hint.owner") : t("chat.hint.buyer")}</p>

      <div
        ref={logRef}
        role="log"
        aria-label={t("chat.log")}
        aria-live="polite"
        aria-relevant="additions"
        tabIndex={0}
        data-testid="chat-log"
        className={`min-h-48 space-y-3 overflow-y-auto rounded-lg border border-line bg-canvas p-3 ${
          variant === "panel" ? "flex-1" : "max-h-[60dvh] min-h-[20rem]"
        }`}
      >
        {conv.messages.length === 0 ? (
          <EmptyState
            title={t("chat.empty.title")}
            body={chat.role === "OWNER" ? t("chat.empty.owner") : t("chat.empty.buyer")}
          />
        ) : (
          conv.messages.map((m: ChatMessage) => (
            <div key={m.id} ref={m === last ? lastRef : undefined} >
              {m.from === "assistant" ? (
                <AssistantTurn response={m.response} active={m === last} busy={conv.busy} onSend={(text, display) => void sendMessage(text, display)} />
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
        <div className="flex flex-wrap items-center gap-2 rounded-md border border-warn-line bg-warn-bg px-3 py-2 text-sm text-warn-fg" data-testid="chat-signed-out">
          <Badge tone="warn">{t("auth.signedIn")}</Badge>
          <span className="min-w-0 flex-1">{t("chat.signinBanner")}</span>
          <Button size="sm" variant="secondary" onClick={() => requestSignIn("required")}>
            {t("auth.signin")}
          </Button>
        </div>
      ) : null}

      <Suggestions prompts={prompts} disabled={conv.busy} compact={conv.messages.length > 0} />
      <Composer role={chat.role} counterpartyId={chat.counterpartyId} busy={conv.busy} />
    </div>
  );
}
