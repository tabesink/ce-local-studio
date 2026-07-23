import { cx } from "@/_shared/ui";

/* Theme-aware brand mark. Both variants render; globals.css shows the one
   matching the active data-theme so the swap is instant and SSR-safe. */
export function AppLogo({ className }: { className?: string }) {
  return (
    <span className={cx("relative inline-flex shrink-0", className)} aria-hidden>
      <img src="/logo-dark.svg" alt="" className="logo-dark h-full w-full object-contain" draggable={false} />
      <img src="/logo-light.svg" alt="" className="logo-light h-full w-full object-contain" draggable={false} />
    </span>
  );
}
