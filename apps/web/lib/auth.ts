"use client";

/**
 * Owner credential handling. The owner types the token into the sign-in dialog; it lives in sessionStorage
 * only (gone when the tab closes) and is sent as X-Owner-Token on owner requests. It is never baked into
 * the bundle: see DEMO_BUILD in ./config for the local-demo prefill.
 */

import { createStore } from "./create-store";

export type SignInReason = "required" | "rejected" | "unconfigured";

interface AuthState {
  token: string | null;
  /** UI only, never persisted. */
  open: boolean;
  reason: SignInReason | null;
}

const INITIAL: AuthState = { token: null, open: false, reason: null };

const authStore = createStore<AuthState>(INITIAL, {
  storage: "session",
  key: "tl-owner-auth",
  sanitize: (s) => ({ token: s.token, open: false, reason: null }),
});

type Listener = () => void;
const signedInListeners = new Set<Listener>();

/** Runs after a successful sign-in, for example to resend the chat message that was refused with a 401. */
export function onSignedIn(l: Listener): () => void {
  signedInListeners.add(l);
  return () => {
    signedInListeners.delete(l);
  };
}

const signedOutListeners = new Set<Listener>();

/** Runs after the owner signs out, for example to drop the conversation and the draft the browser kept for them. */
export function onSignedOut(l: Listener): () => void {
  signedOutListeners.add(l);
  return () => {
    signedOutListeners.delete(l);
  };
}

export function getOwnerToken(): string | null {
  return authStore.get().token;
}

export function useAuth(): AuthState {
  return authStore.useValue();
}

export function requestSignIn(reason: SignInReason | null): void {
  authStore.set((s) => ({ ...s, open: true, reason }));
}

export function closeSignIn(): void {
  authStore.set((s) => ({ ...s, open: false, reason: null }));
}

export function setOwnerToken(token: string): void {
  authStore.set({ token: token.trim() || null, open: false, reason: null });
  signedInListeners.forEach((l) => l());
}

export function signOut(): void {
  authStore.set({ token: null, open: false, reason: null });
  signedOutListeners.forEach((l) => l());
}
