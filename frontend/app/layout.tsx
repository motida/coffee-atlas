import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "Coffee Atlas",
  description:
    "Explore the global coffee ecosystem — from bean genetics and farm origins to roasting science and specialty shops.",
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
