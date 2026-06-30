import Link from "next/link";
import { ApiVersion } from "@/components/help/ApiVersion";
import pkg from "../../package.json";

const FEATURES = [
  {
    href: "/",
    label: "Map",
    desc: "Explore coffee origins, specialty shops, and trade routes on an interactive world map. Toggle layers from the controls in the corner.",
  },
  {
    href: "/explore",
    label: "Explore",
    desc: "Search and browse every entity — varieties, origins, processing methods, roasters, products, flavors, and shops — with faceted filters.",
  },
  {
    href: "/roasters",
    label: "Roasters",
    desc: "Browse specialty roasters and the coffees they sell.",
  },
  {
    href: "/roasting",
    label: "Roasting",
    desc: "How coffee is roasted — phases, cracks, and roast levels — plus an interactive simulator that animates a bean roasting through any of the reference profiles.",
  },
  {
    href: "/flavor",
    label: "Flavor",
    desc: "The Coffee Taster's Flavor Wheel — 110 attributes from the WCR Sensory Lexicon. Click an outer leaf for its definition.",
  },
  {
    href: "/graph",
    label: "Graph",
    desc: "The knowledge-graph explorer. Seed a node by searching, click to inspect, expand its neighbors, and use “Max nodes” to keep the view readable.",
  },
  {
    href: "/account",
    label: "Account",
    desc: "Sign in to save favorites and record your own cupping notes on coffees and varieties.",
  },
];

export default function HelpPage() {
  return (
    <div className="mx-auto max-w-5xl px-4 py-8">
      <header className="mb-8">
        <h1 className="text-3xl font-bold text-coffee-900">Help &amp; About</h1>
        <p className="mt-1 text-sm text-gray-600">
          Coffee Atlas maps the global coffee ecosystem — from bean genetics and
          farm origins to roasting, distribution, and specialty coffee shops — as
          a connected knowledge graph.
        </p>
      </header>

      <section className="mb-8">
        <h2 className="text-lg font-semibold text-coffee-900">Getting around</h2>
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          {FEATURES.map((f) => (
            <Link
              key={f.href}
              href={f.href}
              className="rounded-lg border border-coffee-200 bg-white px-4 py-3 transition hover:border-coffee-400 hover:bg-coffee-50"
            >
              <div className="text-sm font-semibold text-coffee-800">
                {f.label}
              </div>
              <p className="mt-1 text-sm text-gray-600">{f.desc}</p>
            </Link>
          ))}
        </div>
      </section>

      <section className="mb-8">
        <h2 className="text-lg font-semibold text-coffee-900">Tips</h2>
        <ul className="mt-3 list-disc space-y-1.5 pl-5 text-sm text-gray-700">
          <li>
            Most lists support search and filtering — combine filters to narrow
            results.
          </li>
          <li>
            On the Graph, drag nodes to reposition, scroll to zoom, and click a
            node to inspect it or open its detail page.
          </li>
          <li>
            Sign in to save favorites and keep cupping notes; they stay attached
            to your account.
          </li>
        </ul>
      </section>

      <section>
        <h2 className="text-lg font-semibold text-coffee-900">About</h2>
        <div className="mt-3 rounded-lg border border-coffee-200 bg-white px-4 py-3 text-sm text-gray-700">
          <dl className="space-y-1.5">
            <div className="flex justify-between gap-4">
              <dt className="text-gray-500">Web app</dt>
              <dd className="font-medium text-coffee-800">v{pkg.version}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-gray-500">API</dt>
              <dd>
                <ApiVersion />
              </dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-gray-500">Data sources</dt>
              <dd className="text-right text-coffee-800">
                WCR, CQI, ICO / FAOSTAT, Overture Maps
              </dd>
            </div>
          </dl>
        </div>
      </section>
    </div>
  );
}
