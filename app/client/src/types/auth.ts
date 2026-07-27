import type { components } from "@/lib/api/generated/openapi";

export type CurrentUser = components["schemas"]["CurrentUserDto"];
export type LoginRequest = components["schemas"]["LoginRequest"];

/** Auth session envelope — body is `{ user }` only (no public session projection). */
export type SessionUserResponse = {
  user: CurrentUser;
};
