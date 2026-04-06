interface EntityPageProps {
  params: { entity: string };
}

export default function EntityPage({ params }: EntityPageProps) {
  return (
    <div className="mx-auto max-w-7xl px-4 py-8">
      <h1 className="mb-6 text-3xl font-bold text-coffee-900">
        Entity: {params.entity}
      </h1>
      <p className="text-gray-500">Entity detail view coming soon.</p>
    </div>
  );
}
