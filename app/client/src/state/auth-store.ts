"use client";

import { useSyncExternalStore } from "react";
import { authApi } from "@/lib/api/auth";
import type { CurrentUser, SessionInfo } from "@/types/auth";

type AuthStatus = "idle" | "loading" | "authenticated" | "unauthenticated";

type AuthState = {
  user: CurrentUser | null;
  session: SessionInfo | null;
  status: AuthStatus;
  bootstrap: () => Promise<void>;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
  markUnauthenticated: () => void;
};

const listeners = new Set<() => void>();

let state: AuthState = {
  user: null,
  session: null,
  status: "idle",
  bootstrap,
  login,
  logout,
  refresh,
  markUnauthenticated,
};

function emit() {
  listeners.forEach((listener) => listener());
}

function setState(patch: Partial<AuthState>) {
  state = { ...state, ...patch };
  emit();
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

function getSnapshot() {
  return state;
}

async function bootstrap() {
  if (state.status === "loading" || state.status === "authenticated") return;
  setState({ status: "loading" });
  try {
    const response = await authApi.me();
    setState({ user: response.user, session: response.session, status: "authenticated" });
  } catch {
    setState({ user: null, session: null, status: "unauthenticated" });
  }
}

async function login(username: string, password: string) {
  setState({ status: "loading" });
  try {
    const response = await authApi.login({ username, password });
    setState({ user: response.user, session: response.session, status: "authenticated" });
  } catch (error) {
    setState({ user: null, session: null, status: "unauthenticated" });
    throw error;
  }
}

async function logout() {
  try {
    await authApi.logout();
  } finally {
    markUnauthenticated();
    if (typeof window !== "undefined" && window.location.pathname !== "/login") {
      window.location.replace("/login");
    }
  }
}

async function refresh() {
  const response = await authApi.me();
  setState({ user: response.user, session: response.session, status: "authenticated" });
}

function markUnauthenticated() {
  if (state.status === "unauthenticated" && state.user === null && state.session === null) return;
  setState({ user: null, session: null, status: "unauthenticated" });
}

export function useAuthStore<T = AuthState>(selector: (state: AuthState) => T = (value) => value as T): T {
  return useSyncExternalStore(subscribe, () => selector(getSnapshot()), () => selector(getSnapshot()));
}
