import Link from "next/link";

interface GraphDetailSidebarProps {
  entityType: string;
  label: string;
  detailHref: string | null;
  isLoading: boolean;
  onClose: () => void;
  onExpand: () => void;
}

/** The right-hand panel describing the selected node, with expand + detail-link actions. */
export function GraphDetailSidebar({
  entityType,
  label,
  detailHref,
  isLoading,
  onClose,
  onExpand,
}: GraphDetailSidebarProps) {
  return (
    <div className="absolute right-4 top-4 z-10 w-72 rounded-lg border border-coffee-200 bg-white p-4 shadow-sm">
      <button
        onClick={onClose}
        className="float-right text-xs text-gray-400 hover:text-gray-700"
        aria-label="Close"
      >
        ✕
      </button>
      <div className="text-xs uppercase tracking-wide text-coffee-600">
        {entityType.replace("_", " ")}
      </div>
      <div className="mt-1 text-base font-semibold text-coffee-900">{label}</div>
      <div className="mt-3 flex flex-col gap-2">
        <button
          onClick={onExpand}
          disabled={isLoading}
          className="rounded bg-coffee-600 px-3 py-1.5 text-sm text-white hover:bg-coffee-700 disabled:opacity-50"
        >
          Expand neighbors
        </button>
        {detailHref && (
          <Link
            href={detailHref}
            className="rounded border border-coffee-300 px-3 py-1.5 text-center text-sm text-coffee-700 hover:bg-coffee-50"
          >
            View details →
          </Link>
        )}
      </div>
    </div>
  );
}
