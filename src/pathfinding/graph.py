"""Struktur graf berbobot untuk jaringan jalan.

Bobot edge harus non-negatif. Edge default dua arah; edge satu arah dapat
mengatur directed=True saat ditambahkan.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True, slots=True)
class Edge:
    target: str
    weight: float
    edge_id: str
    road_name: str = ""


class Graph:
    """Graf berbobot dengan adjacency list."""

    def __init__(self) -> None:
        self.nodes: dict[str, str] = {}
        self.adjacency: dict[str, list[Edge]] = {}
        self._edge_ids: set[str] = set()

    def add_node(self, node_id: str, label: str | None = None) -> None:
        if not node_id:
            raise ValueError("ID node tidak boleh kosong.")
        self.nodes[node_id] = label or node_id
        self.adjacency.setdefault(node_id, [])

    def add_edge(
        self,
        source: str,
        target: str,
        weight: float,
        edge_id: str,
        road_name: str = "",
        directed: bool = False,
    ) -> None:
        if source not in self.nodes or target not in self.nodes:
            raise ValueError(f"Node edge tidak dikenal: {source!r} -> {target!r}.")
        if weight < 0:
            raise ValueError("Dijkstra hanya menerima bobot non-negatif.")
        if edge_id in self._edge_ids:
            raise ValueError(f"ID edge duplikat: {edge_id!r}.")
        self._edge_ids.add(edge_id)
        self.adjacency[source].append(Edge(target, float(weight), edge_id, road_name))
        if not directed:
            # ID yang sama mewakili ruas fisik yang sama untuk kedua arah.
            self.adjacency[target].append(Edge(source, float(weight), edge_id, road_name))

    def neighbors(self, node_id: str) -> Iterable[Edge]:
        if node_id not in self.adjacency:
            raise KeyError(f"Node tidak ditemukan: {node_id!r}.")
        return self.adjacency[node_id]

    def has_node(self, node_id: str) -> bool:
        return node_id in self.nodes
