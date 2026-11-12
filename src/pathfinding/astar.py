"""A*: pencarian rute terpendek dengan heuristik pada graf berbobot non-negatif.

A* adalah Dijkstra dengan kunci prioritas ``f(n) = g(n) + h(n)``:

- ``g(n)`` = biaya nyata start -> n (sama dengan Dijkstra).
- ``h(n)`` = perkiraan sisa biaya n -> goal (lihat ``heuristic.py``).

Dengan heuristik admissible, A* menghasilkan rute dengan biaya PERSIS sama
dengan Dijkstra - yang berbeda hanya jumlah node yang dieksplorasi, sehingga
keduanya adil untuk dibandingkan (biaya rute, waktu eksekusi, node
dieksplorasi). Bila heuristiknya nol (skenario tanpa koordinat), A* menyusut
menjadi Dijkstra.

Kontraknya sengaja identik dengan ``dijkstra.dijkstra``: input sama, hasil
``PathResult | None`` sama, penutupan ruas diperlakukan sama (ruas dikeluarkan
dari E, bukan bobotnya diganti angka besar), dan ID ruas tertutup yang tidak
dikenal tetap ditolak nyaring.
"""
from __future__ import annotations

import heapq
from math import inf, isfinite
from typing import AbstractSet, Mapping

from .dijkstra import PathResult, validate_search_inputs
from .graph import Graph
from .heuristic import build_heuristic

Coordinate = tuple[float, float]


def astar(
    graph: Graph,
    start: str,
    goal: str,
    blocked_edges: AbstractSet[str] | None = None,
    coordinates: Mapping[str, Coordinate] | None = None,
    stats: dict | None = None,
) -> PathResult | None:
    """Rute minimum dari start ke goal memakai A*, atau None bila tak terjangkau.

    ``coordinates`` (id -> (lat, lon)) dipakai untuk heuristik; tanpa koordinat
    pencarian tetap benar karena h = 0. ``stats`` diisi
    ``{"expanded": <jumlah node dieksplorasi>, "heuristic": <h(start) menit>}``
    bila diberikan, untuk perbandingan terhadap Dijkstra.
    """
    blocked = validate_search_inputs(graph, start, goal, blocked_edges)
    heuristic = build_heuristic(coordinates or {}, goal)
    if stats is not None:
        stats["heuristic"] = heuristic(start)

    if start == goal:
        if stats is not None:
            stats["expanded"] = 0
        return PathResult(nodes=[start], cost=0.0, edges=[])

    distances = {node_id: inf for node_id in graph.nodes}
    previous: dict[str, str] = {}
    previous_edge: dict[str, str] = {}
    distances[start] = 0.0
    # Antrian menyimpan (f, g, node); g ikut disimpan agar perbandingan f seri
    # tidak bergantung pada urutan string node.
    queue: list[tuple[float, float, str]] = [(heuristic(start), 0.0, start)]
    expanded = 0

    while queue:
        _f, current_distance, current = heapq.heappop(queue)
        if current_distance > distances[current]:
            continue  # entri basi: sudah ditemukan jalur lebih baik
        expanded += 1
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
                estimate = candidate + heuristic(edge.target)
                heapq.heappush(queue, (estimate, candidate, edge.target))

    if stats is not None:
        stats["expanded"] = expanded
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
