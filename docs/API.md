# API Reference

The backend exposes a REST API at `/api/v1/`. Interactive OpenAPI docs are
available at [http://localhost:8000/docs](http://localhost:8000/docs) when
the backend is running.

| Endpoint | Description |
|----------|-------------|
| `GET /health` | Health check |
| **Varieties** | |
| `GET /api/v1/varieties` | List/filter coffee varieties |
| `GET /api/v1/varieties/{id}` | Variety detail |
| `GET /api/v1/varieties/{id}/flavor` | Flavor profile for a variety |
| **Origins** | |
| `GET /api/v1/origins` | List origin countries |
| `GET /api/v1/origins/{id}` | Country detail |
| `GET /api/v1/origins/geo` | Countries as a GeoJSON FeatureCollection |
| `GET /api/v1/origins/regions/geo` | Regions as a GeoJSON FeatureCollection |
| `GET /api/v1/origins/regions/{id}` | Region detail |
| **Processing** | |
| `GET /api/v1/processing/methods` | List/filter processing methods |
| `GET /api/v1/processing/methods/{id}` | Processing method detail |
| `GET /api/v1/processing/methods/{id}/varieties` | Varieties prepared with a method |
| `GET /api/v1/processing/methods/{id}/flavor` | Flavors a method enhances/diminishes |
| **Roasting** | |
| `GET /api/v1/roasting/profiles` | List roast profiles |
| `GET /api/v1/roasting/profiles/{id}` | Roast profile detail |
| **Flavor** | |
| `GET /api/v1/flavor/wheel` | Flavor wheel hierarchy |
| `GET /api/v1/flavor/attributes/{id}` | Flavor attribute detail |
| **Distribution** | |
| `GET /api/v1/distribution/importers` | List green-coffee importers |
| `GET /api/v1/distribution/certifications` | List certifications |
| `GET /api/v1/distribution/trade-routes` | List trade routes |
| `GET /api/v1/distribution/trade-routes/geo` | Trade routes as GeoJSON LineStrings |
| **Shops** | |
| `GET /api/v1/shops` | List/filter shops |
| `GET /api/v1/shops/{id}` | Shop detail |
| `GET /api/v1/shops/geo` | Shop locations as GeoJSON |
| `GET /api/v1/shops/nearby` | Nearby shops (lat/lng + radius) |
| `GET /api/v1/shops/{id}/products` | Products a shop's roaster sells |
| **Products** | |
| `GET /api/v1/products` | List products (filters: `roaster_id`, `is_blend`) |
| `GET /api/v1/products/{id}` | Product detail (with roaster name) |
| `GET /api/v1/products/{id}/varieties` | Varieties a product consists of |
| `GET /api/v1/products/{id}/flavors` | Flavor attributes in the tasting notes |
| `GET /api/v1/products/{id}/origin` | Origin countries and regions named |
| **Graph & Search** | |
| `GET /api/v1/graph/traverse` | Graph traversal from a node |
| `GET /api/v1/graph/path` | Shortest path between nodes |
| `GET /api/v1/search/semantic` | Semantic similarity search |
| `GET /api/v1/search/text` | Full-text search |

## Query patterns

- List endpoints support `?limit=`, `?offset=`, `?sort=`, `?filter[field]=value`.
- Geo endpoints return GeoJSON `FeatureCollection` objects, ready for MapLibre.
- Graph endpoints accept `start_id`, `max_depth`, `edge_types[]` and return
  adjacency lists (BFS over the relational edge tables).
- Semantic search accepts a natural-language `query` and returns ranked
  results with similarity scores; with no Gemini key configured it falls back
  to text search.
