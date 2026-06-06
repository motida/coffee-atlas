import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

const SITE_URL =
  process.env.NEXT_PUBLIC_SITE_URL ?? "https://motidav-coffee-atlas-web.hf.space";

const DESCRIPTION =
  "Explore the global coffee ecosystem — from bean genetics and farm origins to roasting science and specialty shops.";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: "Coffee Atlas",
    template: "%s · Coffee Atlas",
  },
  description: DESCRIPTION,
  applicationName: "Coffee Atlas",
  keywords: [
    "coffee",
    "specialty coffee",
    "coffee varieties",
    "coffee origins",
    "knowledge graph",
    "geospatial",
    "flavor wheel",
  ],
  openGraph: {
    type: "website",
    siteName: "Coffee Atlas",
    title: "Coffee Atlas",
    description: DESCRIPTION,
    url: SITE_URL,
  },
  twitter: {
    card: "summary_large_image",
    title: "Coffee Atlas",
    description: DESCRIPTION,
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-coffee-50 text-gray-900">
        <nav className="border-b border-coffee-200 bg-white">
          <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3">
            <Link href="/" className="text-xl font-bold text-coffee-800">
              Coffee Atlas
            </Link>
            <div className="flex gap-6">
              <Link
                href="/"
                className="text-sm font-medium text-gray-600 hover:text-coffee-700"
              >
                Map
              </Link>
              <Link
                href="/explore"
                className="text-sm font-medium text-gray-600 hover:text-coffee-700"
              >
                Explore
              </Link>
              <Link
                href="/flavor"
                className="text-sm font-medium text-gray-600 hover:text-coffee-700"
              >
                Flavor
              </Link>
              <Link
                href="/graph"
                className="text-sm font-medium text-gray-600 hover:text-coffee-700"
              >
                Graph
              </Link>
            </div>
          </div>
        </nav>
        <main>{children}</main>
      </body>
    </html>
  );
}
