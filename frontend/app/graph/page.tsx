import dynamic from "next/dynamic";

const GraphViewer = dynamic(() => import("@/components/graph/GraphViewer"), {
  ssr: false,
  loading: () => (
    <div className="flex h-[calc(100vh-57px)] items-center justify-center">
      <p className="text-coffee-600">Loading graph...</p>
    </div>
  ),
});

export default function GraphPage() {
  return (
    <div className="h-[calc(100vh-57px)]">
      <div className="flex h-full flex-col">
        <div className="border-b border-coffee-200 bg-white px-4 py-3">
          <h1 className="text-lg font-bold text-coffee-900">
            Knowledge Graph Explorer
          </h1>
        </div>
        <div className="flex-1">
          <GraphViewer />
        </div>
      </div>
    </div>
  );
}
