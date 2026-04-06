import dynamic from "next/dynamic";

const CoffeeMap = dynamic(() => import("@/components/map/CoffeeMap"), {
  ssr: false,
  loading: () => (
    <div className="flex h-[calc(100vh-57px)] items-center justify-center bg-coffee-100">
      <p className="text-coffee-600">Loading map...</p>
    </div>
  ),
});

export default function HomePage() {
  return (
    <div className="h-[calc(100vh-57px)]">
      <CoffeeMap />
    </div>
  );
}
