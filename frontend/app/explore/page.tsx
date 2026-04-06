export default function ExplorePage() {
  return (
    <div className="mx-auto max-w-7xl px-4 py-8">
      <h1 className="mb-6 text-3xl font-bold text-coffee-900">Explore</h1>

      <div className="mb-8">
        <input
          type="text"
          placeholder="Search varieties, origins, flavors, shops..."
          className="w-full rounded-lg border border-coffee-200 px-4 py-3 text-sm focus:border-coffee-500 focus:outline-none focus:ring-1 focus:ring-coffee-500"
        />
      </div>

      <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
        <p className="col-span-full text-center text-gray-500">
          Search results will appear here.
        </p>
      </div>
    </div>
  );
}
