import FlavorWheel from "@/components/flavor/FlavorWheel";

export default function FlavorPage() {
  return (
    <div className="mx-auto max-w-7xl px-4 py-8">
      <header className="mb-6">
        <h1 className="text-3xl font-bold text-coffee-900">Flavor Wheel</h1>
        <p className="mt-1 text-sm text-gray-600">
          The Coffee Taster&apos;s Flavor Wheel — 110 attributes derived from
          the WCR Sensory Lexicon. Click an outer leaf for its definition and
          sensory reference.
        </p>
      </header>
      <FlavorWheel />
    </div>
  );
}
