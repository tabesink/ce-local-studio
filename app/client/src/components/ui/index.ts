/* Legacy alias barrel (P9-01 U4).
   Product-neutral starters (Button, Input, StatusPill) live in `@/ui`.
   Residual mega-kit symbols reach consumers via `@/_shared/ui` re-exports
   until FE-01; `_shared` itself re-exports the `@/ui` starters (no second bodies).
   CE-only AppLogo / ErrorBox / PageState remain physical modules in this folder.
   New work must import starters from `@/ui` (or Settings/shell feature homes);
   do not add competing implementations here. */

export * from "@/_shared/ui";

export { AppLogo } from "@/components/ui/AppLogo";
export { ErrorBox } from "@/components/ui/ErrorBox";
export { PageState } from "@/components/ui/PageState";
