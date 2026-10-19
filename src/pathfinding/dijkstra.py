"""Dijkstra baseline: shortest path pada graf berbobot non-negatif."""
from __future__ import annotations
import heapq
from dataclasses import dataclass
from math import inf, isfinite
from typing import AbstractSet
from .graph import Graph


@dataclass(frozen=True, slots=True)
class PathResult:
    nodes: list[str]
    cost: float


def dijkstra(graph: Graph, start: str, goal: str,
             blocked_edges: AbstractSet[str] | None = None) -> PathResult | None:
    """Menghasilkan rute minimum atau None jika tujuan tidak terjangkau."""
    if not graph.has_node(start):
        raise KeyError(f"Node awal tidak ditemukan: {start!r}.")
    if not graph.has_node(goal):
        raise KeyError(f"Node tujuan tidak ditemukan: {goal!r}.")
    if start == goal:
        return PathResult(nodes=[start], cost=0.0)

    blocked = blocked_edges or set()
    distances = {node_id: inf for node_id in graph.nodes}
    previous: dict[str, str] = {}
    distances[start] = 0.0
    queue: list[tuple[float, str]] = [(0.0, start)]

    while queue:
        current_distance, current = heapq.heappop(queue)
        if current_distance > distances[current]:
            continue
        if current == goal:
            break
        for edge in graph.neighbors(current):
            if edge.edge_id in blocked:
                continue
            if not isfinite(edge.weight) or edge.weight < 0:
                raise ValueError(f"Bobot edge {edge.edge_id!r} harus finite dan non-negatif.")
            candidate = current_distance + edge.weight
            if candidate < distances[edge.target]:
                distances[edge.target] = candidate
                previous[edge.target] = current
                heapq.heappush(queue, (candidate, edge.target))

    if distances[goal] == inf:
        return None
    route = [goal]
    while route[-1] != start:
        route.append(previous[route[-1]])
    route.reverse()
    return PathResult(nodes=route, cost=distances[goal])


def reroute_after_closure(graph: Graph, start: str, goal: str,
                          closed_edges: AbstractSet[str]) -> PathResult | None:
    """Hitung ulang rute setelah ruas ditutup; tetap baseline Dijkstra.

    Ini bukan D* Lite: pencarian dihitung lagi pada tiap pemanggilan.
    """
    return dijkstra(graph, start, goal, closed_edges)
