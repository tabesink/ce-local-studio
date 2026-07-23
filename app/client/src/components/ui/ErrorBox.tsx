import { cx } from "@/lib/cx";

export function ErrorBox({ message, className }: { message: string; className?: string }) {
  return (
    <p
      role="alert"
      className={cx(
        "rounded-[var(--rad-lg)] border border-[color-mix(in_srgb,var(--ui-danger)_40%,transparent)] bg-[color-mix(in_srgb,var(--ui-danger)_12%,transparent)] px-3 py-2 text-[length:var(--fs-sm)] text-[var(--fg)]",
        className,
      )}
    >
      {message}
    </p>
  );
}
