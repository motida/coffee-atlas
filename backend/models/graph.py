from pydantic import BaseModel


class GraphNode(BaseModel):
    id: str
    entity_type: str
    label: str
    properties: dict | None = None


class GraphEdge(BaseModel):
    source_id: str
    target_id: str
    edge_type: str
    properties: dict | None = None


class TraversalResult(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class PathResult(BaseModel):
    path: list[GraphNode]
    edges: list[GraphEdge]
    total_weight: float | None = None
