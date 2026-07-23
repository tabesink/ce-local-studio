import { cx } from "@/lib/cx";

export function PageState({
  title,
  message,
  tone = "default",
}: {
  title: string;
  message: string;
  tone?: "default" | "danger";
}) {
  return (
    <div className="flex h-full min-h-[520px] items-center justify-center p-6">
      <section className="w-full max-w-[520px]">
        <div
          className={cx(
            "mb-3 size-2 rounded-full",
            tone === "danger" ? "bg-[var(--ui-danger)]" : "bg-[var(--dim)]",
          )}
        />
        <h1 className="text-[length:var(--fs-2xl)] font-semibold leading-[var(--leading-tight)]">{title}</h1>
        <p className="mt-2 text-[length:var(--fs-base)] text-[var(--dim)]">{message}</p>
      </section>
    </div>
  );
}
