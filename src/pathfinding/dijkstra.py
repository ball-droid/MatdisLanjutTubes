"""Dijkstra baseline: shortest path pada graf berbobot non-negatif.

Notasi matematika yang dipakai (lihat juga README):

- G = (V, E): graf berbobot, V himpunan node, E himpunan ruas jalan.
- w(e) >= 0: bobot ruas e dalam menit estimasi.
- Jalur p = (v0, v1, ..., vk) dengan setiap pasangan (vi, vi+1) termasuk E.
- Bobot jalur: W(p) = jumlah w(vi, vi+1).
- Shortest path: jalur dengan W(p) minimum; Dijkstra menghitungnya selama
  seluruh bobot non-negatif.
- Penutupan akses: ruas dikeluarkan dari E saat pencarian, bukan bobotnya
  diganti angka besar.
"""
from __future__ import annotations
import heapq
from dataclasses import dataclass, field
from math import inf, isfinite
from typing import AbstractSet
from .graph import Graph


@dataclass(frozen=True, slots=True)
class PathResult:
    """Hasil pencarian rute: urutan node, urutan ruas, dan total bobot."""

    nodes: list[str]
    cost: float
    edges: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if len(self.edges) != max(0, len(self.nodes) - 1):
            raise ValueError("Jumlah ruas rute harus sama dengan jumlah node rute - 1.")


def dijkstra(graph: Graph, start: str, goal: str,
             blocked_edges: AbstractSet[str] | None = None) -> PathResult | None:
    """Menghasilkan rute minimum atau None jika tujuan tidak terjangkau.

    `blocked_edges` adalah himpunan ID ruas yang dikeluarkan dari graf (skenario
    akses terhambat). ID yang tidak dikenal ditolak, agar penutupan yang salah
    ketik tidak terlihat seperti penutupan yang berhasil.
    """
    if not graph.has_node(start):
        raise KeyError(f"Node awal tidak ditemukan: {start!r}.")
    if not graph.has_node(goal):
        raise KeyError(f"Node tujuan tidak ditemukan: {goal!r}.")
    blocked = set(blocked_edges or set())
    unknown = sorted(blocked - graph.edge_ids)
    if unknown:
        raise ValueError(
            "Ruas ditutup tidak dikenal dalam graf: "
            + ", ".join(repr(item) for item in unknown)
            + "."
        )
    if start == goal:
        return PathResult(nodes=[start], cost=0.0, edges=[])

    distances = {node_id: inf for node_id in graph.nodes}
    previous: dict[str, str] = {}
    previous_edge: dict[str, str] = {}
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
                previous_edge[edge.target] = edge.edge_id
                heapq.heappush(queue, (candidate, edge.target))

    if distances[goal] == inf:
        return None

    route_nodes = [goal]
    route_edges: list[str] = []
    while route_nodes[-1] != start:
        node_id = route_nodes[-1]
        route_edges.append(previous_edge[node_id])
        route_nodes.append(previous[node_id])
    route_nodes.reverse()
    route_edges.reverse()
    return PathResult(nodes=route_nodes, cost=distances[goal], edges=route_edges)


def reroute_after_closure(graph: Graph, start: str, goal: str,
                          closed_edges: AbstractSet[str]) -> PathResult | None:
    """Hitung ulang rute setelah ruas ditutup; tetap baseline Dijkstra.

    Ini bukan D* Lite: pencarian dihitung lagi pada tiap pemanggilan.
    Mengembalikan None bila setelah penutupan tujuan menjadi tidak terjangkau.
    """
    return dijkstra(graph, start, goal, closed_edges)
