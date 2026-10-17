"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { ApiError, verifyOwnerToken } from "@/lib/api";
import { closeSignIn, requestSignIn, setOwnerToken, signOut, useAuth } from "@/lib/auth";
import { DEMO_BUILD, DEMO_OWNER_TOKEN } from "@/lib/config";
import { bump } from "@/lib/demo-store";
import { useI18n } from "@/lib/i18n";
import { errorText } from "@/lib/error-text";
import { playRipple } from "@/lib/ripple";
import { Badge, Button, inputClass } from "./ui";

function SignInForm() {
  const { t } = useI18n();
  const { reason } = useAuth();
  const [token, setToken] = useState(DEMO_OWNER_TOKEN);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!token.trim()) {
      setError(t("auth.err.empty"));
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await verifyOwnerToken(token.trim());
      await playRipple(document.querySelector<HTMLElement>("dialog[data-testid=owner-signin]"));
      setOwnerToken(token);
      bump(); // screens that failed with a 401 reload with the new token
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) setError(t("auth.err.rejected"));
      else if (err instanceof ApiError && err.status === 503) setError(t("auth.err.unconfigured"));
      else setError(errorText(err, t));
    } finally {
      setBusy(false);
    }
  }

  const notice = error ?? (reason === "rejected" ? t("auth.rejected") : reason === "required" ? t("auth.required") : null);

  return (
    <form onSubmit={(e) => void submit(e)} className="space-y-4" noValidate>
      <div className="flex items-start justify-between gap-3">
        <h2 id="owner-auth-title" className="text-base font-semibold text-ink">
          {t("auth.title")}
        </h2>
        {DEMO_BUILD ? (
          <Badge tone="warn" title={t("auth.demo.hint")}>
            {t("auth.demo")}
          </Badge>
        ) : null}
      </div>
      {notice ? (
        <p role={error ? "alert" : "status"} className={`rounded-tile border px-3 py-2 text-sm ${error ? "border-bad-line bg-bad-bg text-bad-fg" : "border-info-line bg-info-bg text-info-fg"}`}>
          {notice}
        </p>
      ) : null}
      <div>
        <label htmlFor="owner-token" className="block text-sm font-medium text-ink">
          {t("auth.label")}
        </label>
        <input
          id="owner-token"
          name="owner-token"
          type="password"
          autoComplete="off"
          spellCheck={false}
          autoFocus
          value={token}
          onChange={(e) => setToken(e.target.value)}
          aria-invalid={error ? true : undefined}
          className={`mt-1 w-full font-mono ${inputClass}`}
        />
        {DEMO_BUILD ? <p className="mt-1 text-meta text-ink-3">{t("auth.demo.hint")}</p> : null}
      </div>
      <div className="flex justify-end gap-2">
        <Button variant="ghost" onClick={closeSignIn}>
          {t("auth.cancel")}
        </Button>
        <Button type="submit" variant="primary" loading={busy}>
          {busy ? t("auth.checking") : t("auth.submit")}
        </Button>
      </div>
    </form>
  );
}

/** Modal owner sign-in. A 401 from any owner request opens it (lib/live/http.ts); Esc or Cancel closes it. */
export function OwnerSignInDialog() {
  const { open } = useAuth();
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) d.showModal();
    if (!open && d.open) d.close();
  }, [open]);

  return (
    <dialog
      ref={ref}
      aria-labelledby="owner-auth-title"
      data-testid="owner-signin"
      onClose={closeSignIn}
      className="fixed inset-0 m-auto h-fit max-h-[calc(100dvh-2rem)] w-[min(28rem,calc(100vw-2rem))] overflow-y-auto rounded-card border border-line bg-surface p-5 text-ink shadow-pop backdrop:bg-ink/50 backdrop:backdrop-blur-sm"
    >
      {open ? <SignInForm /> : null}
    </dialog>
  );
}

/** Header control: sign in, or show the owner badge with sign out. */
export function OwnerSessionControl() {
  const { t } = useI18n();
  const { token } = useAuth();
  return token ? (
    <div className="flex items-center gap-1">
      <Badge tone="ok" title={t("auth.body")}>
        {t("auth.signedIn")}
      </Badge>
      <Button size="sm" variant="ghost" onClick={signOut} data-testid="owner-signout">
        {t("auth.signout")}
      </Button>
    </div>
  ) : (
    <Button size="sm" variant="secondary" onClick={() => requestSignIn(null)} data-testid="owner-signin-open">
      {t("auth.signin")}
    </Button>
  );
}
