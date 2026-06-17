import Link from "next/link";
import { Popup } from "react-map-gl/maplibre";
import type { PopupState } from "./popups";

/** Renders an entity popup on the map: title, optional subtitle, and detail /
 *  website / multi-entity links depending on what the source feature carries. */
export function MapPopup({ popup, onClose }: { popup: PopupState; onClose: () => void }) {
  return (
    <Popup
      longitude={popup.longitude}
      latitude={popup.latitude}
      anchor="top"
      closeOnClick={false}
      onClose={onClose}
    >
      <div className="px-1 py-0.5">
        <div className="font-semibold text-coffee-900">{popup.title}</div>
        {popup.subtitle && <div className="text-xs text-gray-600">{popup.subtitle}</div>}
        <div className="mt-1 flex gap-3 text-xs">
          {popup.detailHref && (
            <Link href={popup.detailHref} className="text-coffee-700 underline">
              details →
            </Link>
          )}
          {popup.link && (
            <a
              href={popup.link}
              target="_blank"
              rel="noreferrer"
              className="text-amber-700 underline"
            >
              website
            </a>
          )}
        </div>
        {popup.links && (
          <div className="mt-1 flex flex-wrap gap-3 text-xs">
            {popup.links.map((l) => (
              <Link key={l.href} href={l.href} className="text-coffee-700 underline">
                {l.label}
              </Link>
            ))}
          </div>
        )}
      </div>
    </Popup>
  );
}
