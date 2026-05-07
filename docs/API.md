# API Reference

The backend exposes a REST API at `/api/v1/`. Interactive OpenAPI docs are
available at [http://localhost:8000/docs](http://localhost:8000/docs) when
the backend is running.

| Endpoint | Description |
|----------|-------------|
| `GET /health` | Health check |
| `GET /api/v1/varieties` | List/filter coffee varieties |
| `GET /api/v1/origins` | List origin countries/regions |
| `GET /api/v1/origins/geo` | GeoJSON feature collection |
| `GET /api/v1/roasting/profiles` | List roast profiles |
| `GET /api/v1/flavor/wheel` | Flavor wheel hierarchy |
| `GET /api/v1/shops` | List/filter shops |
| `GET /api/v1/shops/geo` | Shop locations as GeoJSON |
| `GET /api/v1/shops/nearby` | Nearby shops (lat/lng + radius) |
| `GET /api/v1/graph/traverse` | Graph traversal from a node |
| `GET /api/v1/graph/path` | Shortest path between nodes |
| `GET /api/v1/search/semantic` | Semantic similarity search |
| `GET /api/v1/search/text` | Full-text search |

## Query patterns

- List endpoints support `?limit=`, `?offset=`, `?sort=`, `?filter[field]=value`.
- Geo endpoints return GeoJSON `FeatureCollection` objects, ready for MapLibre.
- Graph endpoints accept `start_id`, `max_depth`, `edge_types[]` and return
  adjacency lists.
- Semantic search accepts a natural-language `query` and returns ranked
  results with similarity scores.
