import Link from "next/link";
import type { ReactNode } from "react";

interface EntityPageProps {
  type: string;
  title: string;
  subtitle?: string;
  children: ReactNode;
}

export function EntityPage({ type, title, subtitle, children }: EntityPageProps) {
  return (
    <div className="mx-auto max-w-5xl px-4 py-8">
      <div className="mb-6">
        <Link
          href="/explore"
          className="text-xs uppercase tracking-wide text-coffee-600 hover:text-coffee-800"
        >
          ← Explore
        </Link>
      </div>
      <header className="mb-8 border-b border-coffee-200 pb-4">
        <div className="text-xs uppercase tracking-wide text-coffee-600">
          {type}
        </div>
        <h1 className="mt-1 text-3xl font-bold text-coffee-900">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-gray-600">{subtitle}</p>}
      </header>
      <div className="space-y-8">{children}</div>
    </div>
  );
}

interface SectionProps {
  title: string;
  count?: number;
  children: ReactNode;
  empty?: string;
}

export function Section({ title, count, children, empty }: SectionProps) {
  return (
    <section>
      <h2 className="mb-3 text-lg font-semibold text-coffee-900">
        {title}
        {count !== undefined && (
          <span className="ml-2 text-sm font-normal text-gray-500">
            ({count})
          </span>
        )}
      </h2>
      {count === 0 && empty ? (
        <p className="text-sm text-gray-500">{empty}</p>
      ) : (
        children
      )}
    </section>
  );
}

interface FieldProps {
  label: string;
  value: string | number | null | undefined;
}

export function Field({ label, value }: FieldProps) {
  if (value === null || value === undefined || value === "") return null;
  return (
    <div>
      <dt className="text-xs uppercase tracking-wide text-gray-500">{label}</dt>
      <dd className="mt-0.5 text-sm text-gray-900">{value}</dd>
    </div>
  );
}

interface EntityCardProps {
  href: string;
  title: string;
  subtitle?: string;
}

export function EntityCard({ href, title, subtitle }: EntityCardProps) {
  return (
    <Link
      href={href}
      className="block rounded-lg border border-coffee-200 bg-white px-4 py-3 transition hover:border-coffee-400 hover:bg-coffee-50"
    >
      <div className="text-sm font-medium text-coffee-900">{title}</div>
      {subtitle && (
        <div className="mt-0.5 text-xs text-gray-500">{subtitle}</div>
      )}
    </Link>
  );
}

interface EntityDetailLoaderProps {
  type: string;
  error: string | null;
  loadingLabel: string;
}

/** The shared not-found / loading state every entity detail page renders while
 *  its main entity is unresolved. */
export function EntityDetailLoader({ type, error, loadingLabel }: EntityDetailLoaderProps) {
  return (
    <EntityPage type={type} title={error ? "Not found" : "Loading…"}>
      {error ? (
        <p className="text-sm text-red-600">{error}</p>
      ) : (
        <p className="text-sm text-gray-500">{loadingLabel}</p>
      )}
    </EntityPage>
  );
}

/** Responsive 1/2/3-column grid used for related-entity card lists. */
export function CardGrid({ children }: { children: ReactNode }) {
  return (
    <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 md:grid-cols-3">
      {children}
    </div>
  );
}
