"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import type { FormEvent } from "react";
import { AppLogo } from "@/components/ui/AppLogo";
import { ErrorBox } from "@/components/ui/ErrorBox";
import { Button, Input } from "@/ui";
import { isApiError } from "@/lib/api/errors";
import { useAuthStore } from "@/state/auth-store";

function loginErrorMessage(error: unknown) {
  if (isApiError(error)) return error.message;
  return "Sign in failed.";
}

export default function LoginPage() {
  const router = useRouter();
  const login = useAuthStore((state) => state.login);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(username.trim(), password);
      router.replace("/chat");
    } catch (err) {
      setError(loginErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-[var(--bg)] px-6 py-10">
      <form
        onSubmit={onSubmit}
        className="w-full max-w-[360px] rounded-[var(--rad-xl)] border border-[var(--ui-border)] bg-[var(--color-panel)] p-5"
      >
        <div className="mb-5 text-center">
          <div className="mx-auto mb-3 flex size-24 items-center justify-center rounded-[var(--rad-lg)] bg-[var(--rail)] p-2">
            <AppLogo className="h-full w-full" />
          </div>
          <h1 className="text-[length:var(--fs-2xl)] font-semibold leading-[var(--leading-tight)] text-[var(--fg)]">
            Context Engine
          </h1>
          <p className="mt-1 text-[length:var(--fs-sm)] text-[var(--dim)]">Sign in with your team account.</p>
        </div>

        <div className="space-y-3">
          <Input
            id="username"
            label="Username"
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            autoComplete="username"
            required
          />
          <Input
            id="password"
            label="Password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            type="password"
            autoComplete="current-password"
            required
          />
        </div>

        {error ? <ErrorBox className="mt-4" message={error} /> : null}

        <Button className="mt-5 w-full" type="submit" loading={busy}>
          Sign in
        </Button>
      </form>
    </main>
  );
}
