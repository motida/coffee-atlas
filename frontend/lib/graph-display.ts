/**
 * Pure helpers for capping the graph to a manageable number of displayed nodes.
 *
 * Kept free of d3 types so they can be unit-tested apart from the DOM/simulation.
 * The graph API returns nodes in BFS/insertion order with the seed first, so
 * "keep the first N" == "keep the seed and its N nearest nodes".
 */

/**
 * An edge endpoint is a string id before d3 runs and a node object after. The
 * `number` arm matches d3's link-datum type (positional indexing); we never use
 * it, so it resolves to a value no node id will match.
 */
type EdgeEndpoint = string | number | { id: string };

const endpointId = (e: EdgeEndpoint): string =>
  typeof e === "string" ? e : typeof e === "number" ? String(e) : e.id;

/**
 * Trim `nodes` to the first `limit` (BFS order, seed first). A `null` limit
 * means "show all". `selectedId`, when set, is always kept — appended if the cap
 * would otherwise drop it — so selecting a distant node can't make it vanish.
 */
export function capNodes<T extends { id: string }>(
  nodes: T[],
  limit: number | null,
  selectedId?: string,
): T[] {
  if (limit == null || nodes.length <= limit) return nodes;
  const kept = nodes.slice(0, limit);
  if (selectedId && !kept.some((n) => n.id === selectedId)) {
    const selected = nodes.find((n) => n.id === selectedId);
    if (selected) kept.push(selected);
  }
  return kept;
}

/**
 * Drop any edge whose source or target node was trimmed away. d3's
 * `forceLink().id(...)` throws "node not found" if a link references an id that
 * isn't in the simulation's node set, so this guard is required, not cosmetic.
 */
export function pruneEdges<
  T extends { source: EdgeEndpoint; target: EdgeEndpoint },
>(edges: T[], nodeIds: Set<string>): T[] {
  return edges.filter(
    (e) => nodeIds.has(endpointId(e.source)) && nodeIds.has(endpointId(e.target)),
  );
}
