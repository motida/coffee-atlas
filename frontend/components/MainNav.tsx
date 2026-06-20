"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const TABS = [
  { href: "/", label: "Map" },
  { href: "/explore", label: "Explore" },
  { href: "/roasters", label: "Roasters" },
  { href: "/flavor", label: "Flavor" },
  { href: "/graph", label: "Graph" },
  { href: "/help", label: "Help" },
] as const;

function isActive(pathname: string, href: string): boolean {
  return href === "/" ? pathname === "/" : pathname.startsWith(href);
}

export function MainNav() {
  const pathname = usePathname();
  return (
    <>
      {TABS.map((tab) => (
        <Link
          key={tab.href}
          href={tab.href}
          className={
            isActive(pathname, tab.href)
              ? "text-sm font-medium text-coffee-800"
              : "text-sm font-medium text-gray-600 hover:text-coffee-700"
          }
        >
          {tab.label}
        </Link>
      ))}
    </>
  );
}
