// @vitest-environment node
import { describe, expect, it } from "vitest";
import { capNodes, pruneEdges } from "./graph-display";

const node = (id: string) => ({ id });

describe("capNodes", () => {
  const nodes = ["seed", "a", "b", "c", "d"].map(node);

  it("returns all nodes unchanged when the limit is null", () => {
    expect(capNodes(nodes, null)).toBe(nodes);
  });

  it("returns all nodes when there are fewer than the limit", () => {
    expect(capNodes(nodes, 10)).toBe(nodes);
  });

  it("keeps the first N in order (seed preserved)", () => {
    expect(capNodes(nodes, 3).map((n) => n.id)).toEqual(["seed", "a", "b"]);
  });

  it("appends a selected node that falls outside the cap", () => {
    const kept = capNodes(nodes, 2, "d");
    expect(kept.map((n) => n.id)).toEqual(["seed", "a", "d"]);
  });

  it("does not duplicate a selected node already within the cap", () => {
    expect(capNodes(nodes, 3, "a").map((n) => n.id)).toEqual([
      "seed",
      "a",
      "b",
    ]);
  });
});

describe("pruneEdges", () => {
  const visible = new Set(["seed", "a", "b"]);

  it("keeps edges whose string endpoints are both visible", () => {
    const edges = [
      { source: "seed", target: "a" },
      { source: "a", target: "c" }, // c trimmed
    ];
    expect(pruneEdges(edges, visible)).toEqual([{ source: "seed", target: "a" }]);
  });

  it("drops edges whose source or target was trimmed", () => {
    const edges = [
      { source: "c", target: "a" }, // c trimmed
      { source: "b", target: "d" }, // d trimmed
    ];
    expect(pruneEdges(edges, visible)).toEqual([]);
  });

  it("resolves post-simulation object endpoints", () => {
    const edges = [
      { source: { id: "seed" }, target: { id: "b" } },
      { source: { id: "a" }, target: { id: "z" } }, // z trimmed
    ];
    expect(pruneEdges(edges, visible)).toEqual([
      { source: { id: "seed" }, target: { id: "b" } },
    ]);
  });
});
