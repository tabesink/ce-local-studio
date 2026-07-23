import type { InputHTMLAttributes } from "react";

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string;
}

export function Input({ id, label, className = "", ...props }: InputProps) {
  return (
    <label htmlFor={id} className="block">
      <span className="mb-1 block text-[length:var(--fs-sm)] font-medium text-[var(--fg)]">{label}</span>
      <input
        id={id}
        className={`h-7 w-full rounded-[var(--rad-md)] border border-[var(--ui-border)] bg-[var(--color-input)] px-2 text-[length:var(--fs-md)] text-[var(--fg)] outline-none transition-colors placeholder:text-[var(--dim)] focus:border-[var(--color-border-hover)] focus:ring-1 focus:ring-[var(--ring)] ${className}`}
        {...props}
      />
    </label>
  );
}
