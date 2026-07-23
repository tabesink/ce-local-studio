import { ceFetch } from "@/lib/api/client";
import type { LoginRequest, SessionUserResponse } from "@/types/auth";

export const authApi = {
  login(payload: LoginRequest) {
    return ceFetch<SessionUserResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify(payload),
      handleUnauthorized: false,
    });
  },
  me() {
    return ceFetch<SessionUserResponse>("/auth/me", { handleUnauthorized: false });
  },
  logout() {
    return ceFetch<{ ok: boolean }>("/auth/logout", { method: "POST", handleUnauthorized: false });
  },
};
