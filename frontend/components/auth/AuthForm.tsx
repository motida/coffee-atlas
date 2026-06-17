"use client";

import Link from "next/link";
import type { FormEvent, ReactNode } from "react";

/** Shared chrome for the login/register forms: centered card, title, error
 *  banner, submit button, and a footer link to the other page. */
export function AuthFormShell({
  title,
  error,
  submitting,
  submitLabel,
  onSubmit,
  children,
  footer,
}: {
  title: string;
  error: string | null;
  submitting: boolean;
  submitLabel: string;
  onSubmit: (e: FormEvent) => void;
  children: ReactNode;
  footer: ReactNode;
}) {
  return (
    <div className="mx-auto max-w-md px-4 py-12">
      <h1 className="mb-6 text-2xl font-bold text-coffee-900">{title}</h1>
      <form onSubmit={onSubmit} className="space-y-4">
        {children}
        {error && <p className="text-sm text-red-600">{error}</p>}
        <button
          type="submit"
          disabled={submitting}
          className="w-full rounded-md bg-coffee-700 px-4 py-2 text-sm font-medium text-white hover:bg-coffee-800 disabled:opacity-50"
        >
          {submitting ? "…" : submitLabel}
        </button>
      </form>
      <p className="mt-4 text-sm text-gray-600">{footer}</p>
    </div>
  );
}

export function AuthField({
  label,
  type,
  value,
  onChange,
  required,
  minLength,
  autoComplete,
}: {
  label: string;
  type: string;
  value: string;
  onChange: (v: string) => void;
  required?: boolean;
  minLength?: number;
  autoComplete?: string;
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs uppercase tracking-wide text-gray-500">{label}</span>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        required={required}
        minLength={minLength}
        autoComplete={autoComplete}
        className="w-full rounded-md border border-coffee-200 px-3 py-2 text-sm focus:border-coffee-500 focus:outline-none"
      />
    </label>
  );
}

export function AuthFooterLink({ href, prompt, action }: { href: string; prompt: string; action: string }) {
  return (
    <>
      {prompt}{" "}
      <Link href={href} className="font-medium text-coffee-700 hover:underline">
        {action}
      </Link>
    </>
  );
}
