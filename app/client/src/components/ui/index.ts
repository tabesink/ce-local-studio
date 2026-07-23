/* App-facing UI barrel — agent/feature import path: `@/components/ui`.
   Inventory SoT: re-exports the shared Local Studio kit from `@/_shared/ui`,
   plus CE-only surfaces below. `@/_shared/ui` remains an implementation detail;
   CE-only modules must import helpers from `@/_shared/ui` directly (never this
   barrel) to avoid circular dependencies. Thin parallel files in this folder
   (e.g. `Button.tsx`) are legacy deep-import targets, not the inventory SoT. */

export * from "@/_shared/ui";

export { AppLogo } from "@/components/ui/AppLogo";
export { ErrorBox } from "@/components/ui/ErrorBox";
export { PageState } from "@/components/ui/PageState";
