"""Hybrid content + graph recommendation engine.

Two flavors of recommendation, both built on data already in the stores:

- ``similar(entity_type, entity_id)`` — "if you like this, try these". Ranks
  same-type peers by a blend of embedding cosine similarity (the dense
  "content" signal, the same ``array_cosine_similarity`` semantic search uses)
  and shared-neighbor overlap in the ``edges_*`` graph (the sparse, explainable
  "knowledge graph" signal — shared flavor notes, origin, varieties, ...).

- ``for_user(user_id, entity_type)`` — a personalized feed. Averages the
  embeddings of the entities a user has favorited / cupping-noted into a taste
  centroid, then cosine-ranks the catalog against it, excluding what they
  already saved. This is the one place the two stores meet: activity in
  Postgres, embeddings in DuckDB.

No Gemini call is ever made at request time — every embedding is pre-stored, so
recommendations work even where semantic search would fall back to text.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import duckdb
import psycopg
from psycopg.rows import DictRow

from backend.models.recommend import Recommendation
from backend.services.embeddings import DIMENSIONS

# How many embedding-nearest candidates to pull before graph re-ranking. Bounds
# the graph leg's work to a small set (no full Cartesian product).
_CANDIDATE_POOL = 50
# Weight of the (normalized) graph-overlap signal relative to the cosine score.
_GRAPH_WEIGHT = 0.5


@dataclass(frozen=True)
class NeighborEdge:
    """One edge table linking this entity type to neighbors used for overlap.

    ``self_col``/``neighbor_col`` name which column holds the seed's id and which
    holds the shared neighbor — so edges where this type is the source
    (``edges_product_flavor``) and the destination (``edges_country_variety``)
    are both expressed the same way. ``label`` is the singular noun for reasons.
    """

    edge_table: str
    self_col: str
    neighbor_col: str
    label: str


@dataclass(frozen=True)
class RecConfig:
    table: str
    label_col: str
    desc_col: str | None
    embedding_col: str
    neighbor_edges: list[NeighborEdge] = field(default_factory=list)
    # Extra SQL predicate (no bind params), e.g. shops filtered to specialty.
    extra_where: str | None = None


# Only the six entity types the embeddings stage populates are recommendable.
RECOMMENDABLE: dict[str, RecConfig] = {
    "variety": RecConfig(
        table="var_varieties",
        label_col="name",
        desc_col="description",
        embedding_col="name_embedding",
        neighbor_edges=[
            NeighborEdge("edges_variety_flavor", "variety_id", "flavor_id", "flavor note"),
            NeighborEdge(
                "edges_variety_processing", "variety_id", "method_id", "processing method"
            ),
            NeighborEdge("edges_country_variety", "variety_id", "country_id", "origin"),
            NeighborEdge("edges_region_variety", "variety_id", "region_id", "origin"),
            NeighborEdge("edges_roast_variety", "variety_id", "profile_id", "roast profile"),
        ],
    ),
    "flavor": RecConfig(
        table="flav_attributes",
        label_col="name",
        desc_col="description",
        embedding_col="name_embedding",
        neighbor_edges=[
            NeighborEdge("edges_variety_flavor", "flavor_id", "variety_id", "variety"),
            NeighborEdge("edges_product_flavor", "flavor_id", "product_id", "product"),
            NeighborEdge("edges_processing_flavor", "flavor_id", "method_id", "processing method"),
        ],
    ),
    "processing": RecConfig(
        table="proc_methods",
        label_col="name",
        desc_col="description",
        embedding_col="description_embedding",
        neighbor_edges=[
            NeighborEdge("edges_variety_processing", "method_id", "variety_id", "variety"),
            NeighborEdge("edges_processing_flavor", "method_id", "flavor_id", "flavor note"),
        ],
    ),
    "shop": RecConfig(
        table="shop_shops",
        label_col="name",
        desc_col="description",
        embedding_col="description_embedding",
        extra_where="is_specialty",
        neighbor_edges=[
            NeighborEdge("edges_shop_variety", "shop_id", "variety_id", "variety"),
            NeighborEdge("edges_shop_roaster", "shop_id", "roaster_id", "roaster"),
            NeighborEdge("edges_shop_product", "shop_id", "product_id", "product"),
        ],
    ),
    "roast_profile": RecConfig(
        table="roast_profiles",
        label_col="name",
        desc_col="description",
        embedding_col="description_embedding",
        neighbor_edges=[
            NeighborEdge("edges_roast_variety", "profile_id", "variety_id", "variety"),
            NeighborEdge("edges_product_roast", "profile_id", "product_id", "product"),
        ],
    ),
    "product": RecConfig(
        table="prod_products",
        label_col="name",
        desc_col="description",
        embedding_col="description_embedding",
        neighbor_edges=[
            NeighborEdge("edges_product_variety", "product_id", "variety_id", "variety"),
            NeighborEdge("edges_product_flavor", "product_id", "flavor_id", "flavor note"),
            NeighborEdge("edges_product_country", "product_id", "country_id", "origin"),
            NeighborEdge("edges_product_region", "product_id", "region_id", "origin"),
            NeighborEdge("edges_product_roast", "product_id", "profile_id", "roast profile"),
        ],
    ),
}


def _pluralize(noun: str, n: int) -> str:
    if n == 1:
        return f"1 {noun}"
    plural = f"{noun[:-1]}ies" if noun.endswith("y") else f"{noun}s"
    return f"{n} {plural}"


def _build_reason(counts: dict[str, int]) -> str | None:
    """Turn {"flavor note": 3, "origin": 1} into "Shares 3 flavor notes, 1 origin"."""
    if not counts:
        return None
    # Most-shared neighbor kinds first; cap at three to keep it readable.
    parts = [
        _pluralize(label, n)
        for label, n in sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
        if n > 0
    ][:3]
    return ("Shares " + ", ".join(parts)) if parts else None


class RecommendationService:
    """Stateless; takes connections per call (mirrors the router DI shape)."""

    def similar(
        self,
        db: duckdb.DuckDBPyConnection,
        entity_type: str,
        entity_id: str,
        limit: int,
    ) -> list[Recommendation]:
        cfg = RECOMMENDABLE[entity_type]  # caller validates membership first

        seed_vec = self._seed_embedding(db, cfg, entity_id)
        cosine = self._embedding_candidates(db, cfg, entity_id, seed_vec)
        overlap = self._graph_overlap(db, cfg, entity_id)

        # Universe = everything either leg surfaced. Backfill labels for peers
        # that graph overlap found but the embedding scan didn't.
        labels = self._labels(db, cfg, set(cosine) | set(overlap))

        max_shared = max((sum(c.values()) for c in overlap.values()), default=0)
        recs: list[Recommendation] = []
        for peer_id, (label, desc) in labels.items():
            emb_score = cosine.get(peer_id, 0.0)
            counts = overlap.get(peer_id, {})
            shared = sum(counts.values())
            graph_score = (shared / max_shared) if max_shared else 0.0
            # With no usable seed embedding, rank on the graph signal alone.
            score = graph_score if seed_vec is None else emb_score + _GRAPH_WEIGHT * graph_score
            recs.append(
                Recommendation(
                    id=peer_id,
                    entity_type=entity_type,
                    label=label,
                    description=desc,
                    score=round(score, 6),
                    reason=_build_reason(counts),
                )
            )

        recs.sort(key=lambda r: r.score, reverse=True)
        return recs[:limit]

    def for_user(
        self,
        db: duckdb.DuckDBPyConnection,
        pg: psycopg.Connection[DictRow],
        user_id: str,
        entity_type: str,
        limit: int,
    ) -> list[Recommendation]:
        cfg = RECOMMENDABLE[entity_type]  # caller validates membership first

        seed_ids = self._user_entity_ids(pg, user_id, entity_type)
        if not seed_ids:
            return []
        centroid = self._centroid(db, cfg, seed_ids)
        if centroid is None:
            return []

        reason = f"Based on {_pluralize(entity_type, len(seed_ids))} you saved"
        placeholders = ", ".join(["?"] * len(seed_ids))
        where = [f"{cfg.embedding_col} IS NOT NULL", f"id NOT IN ({placeholders})"]
        if cfg.extra_where:
            where.append(cfg.extra_where)
        cols = f"id, {cfg.label_col}" + (f", {cfg.desc_col}" if cfg.desc_col else "")
        sql = (
            f"SELECT {cols}, "
            f"array_cosine_similarity({cfg.embedding_col}, ?::FLOAT[{DIMENSIONS}]) AS sim "
            f"FROM {cfg.table} WHERE {' AND '.join(where)} ORDER BY sim DESC LIMIT ?"
        )
        # Param order must match placeholder order in the SQL text: centroid
        # (SELECT), seed_ids (WHERE id NOT IN (...)), then limit.
        rows = db.execute(sql, [centroid, *seed_ids, limit]).fetchall()
        return [
            Recommendation(
                id=row[0],
                entity_type=entity_type,
                label=row[1],
                description=row[2] if cfg.desc_col else None,
                score=round(row[-1], 6),
                reason=reason,
            )
            for row in rows
        ]

    # --- internals ---
    def _seed_embedding(
        self, db: duckdb.DuckDBPyConnection, cfg: RecConfig, entity_id: str
    ) -> list[float] | None:
        row = db.execute(
            f"SELECT {cfg.embedding_col} FROM {cfg.table} WHERE id = ?", [entity_id]
        ).fetchone()
        return list(row[0]) if row and row[0] is not None else None

    def _embedding_candidates(
        self,
        db: duckdb.DuckDBPyConnection,
        cfg: RecConfig,
        entity_id: str,
        seed_vec: list[float] | None,
    ) -> dict[str, float]:
        if seed_vec is None:
            return {}
        where = [f"{cfg.embedding_col} IS NOT NULL", "id != ?"]
        if cfg.extra_where:
            where.append(cfg.extra_where)
        cols = f"id, {cfg.label_col}" + (f", {cfg.desc_col}" if cfg.desc_col else "")
        sql = (
            f"SELECT {cols}, "
            f"array_cosine_similarity({cfg.embedding_col}, ?::FLOAT[{DIMENSIONS}]) AS sim "
            f"FROM {cfg.table} WHERE {' AND '.join(where)} ORDER BY sim DESC LIMIT ?"
        )
        rows = db.execute(sql, [seed_vec, entity_id, _CANDIDATE_POOL]).fetchall()
        return {row[0]: row[-1] for row in rows}

    def _graph_overlap(
        self, db: duckdb.DuckDBPyConnection, cfg: RecConfig, entity_id: str
    ) -> dict[str, dict[str, int]]:
        """Per-peer counts of shared neighbors, keyed by neighbor-kind label."""
        overlap: dict[str, dict[str, int]] = {}
        for edge in cfg.neighbor_edges:
            # Peers that share at least one neighbor with the seed via this edge.
            sql = (
                f"WITH seed_n AS ("
                f"  SELECT {edge.neighbor_col} AS n FROM {edge.edge_table} WHERE {edge.self_col} = ?"
                f") "
                f"SELECT e.{edge.self_col} AS peer, COUNT(*) AS shared "
                f"FROM {edge.edge_table} e JOIN seed_n ON e.{edge.neighbor_col} = seed_n.n "
                f"WHERE e.{edge.self_col} != ? "
                f"GROUP BY e.{edge.self_col}"
            )
            for peer, shared in db.execute(sql, [entity_id, entity_id]).fetchall():
                overlap.setdefault(peer, {})
                overlap[peer][edge.label] = overlap[peer].get(edge.label, 0) + int(shared)
        return overlap

    def _labels(
        self, db: duckdb.DuckDBPyConnection, cfg: RecConfig, ids: set[str]
    ) -> dict[str, tuple[str, str | None]]:
        if not ids:
            return {}
        placeholders = ", ".join(["?"] * len(ids))
        where: list[str] = [f"id IN ({placeholders})"]
        if cfg.extra_where:  # keep non-specialty shops out of graph-only peers too
            where.append(cfg.extra_where)
        cols = f"id, {cfg.label_col}" + (f", {cfg.desc_col}" if cfg.desc_col else "")
        rows = db.execute(
            f"SELECT {cols} FROM {cfg.table} WHERE {' AND '.join(where)}", list(ids)
        ).fetchall()
        return {row[0]: (row[1], row[2] if cfg.desc_col else None) for row in rows}

    def _user_entity_ids(
        self, pg: psycopg.Connection[DictRow], user_id: str, entity_type: str
    ) -> list[str]:
        with pg.cursor() as cur:
            cur.execute(
                """
                SELECT entity_id FROM usr_favorites
                WHERE user_id = %s AND entity_type = %s
                UNION
                SELECT entity_id FROM usr_cupping_notes
                WHERE user_id = %s AND entity_type = %s
                """,
                [user_id, entity_type, user_id, entity_type],
            )
            return [r["entity_id"] for r in cur.fetchall()]

    def _centroid(
        self, db: duckdb.DuckDBPyConnection, cfg: RecConfig, ids: list[str]
    ) -> list[float] | None:
        placeholders = ", ".join(["?"] * len(ids))
        rows = db.execute(
            f"SELECT {cfg.embedding_col} FROM {cfg.table} "
            f"WHERE id IN ({placeholders}) AND {cfg.embedding_col} IS NOT NULL",
            ids,
        ).fetchall()
        vectors = [list(r[0]) for r in rows]
        if not vectors:
            return None
        n = len(vectors)
        return [sum(v[i] for v in vectors) / n for i in range(DIMENSIONS)]
