"""Eksperimen: bagaimana rute damkar bila aturan satu arah OSM diterapkan per edge.

Bahan keputusan jenis graf (dokumen docs/analisis_studi_kasus.md bagian 5).
Klasifikasi arah di bawah berasal dari keluaran `tools/validasi_peta.py`
(ekstraksi OSM 2026-11-10). Tidak mengubah file data maupun kode sumber.

Pemakaian:  python tools/eksperimen_arah.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pathfinding.dijkstra import dijkstra  # noqa: E402  (path disetel di atas)
from pathfinding.graph import Graph  # noqa: E402

SCENARIO = Path(__file__).resolve().parents[1] / "data" / "pasar_johar_damkar.yaml"

# Hasil audit tools/validasi_peta.py: edge di ruas satu arah.
ONEWAY_SEARAH = {"e11", "e12", "e13", "e19", "e21", "e22", "e23", "e24", "e26", "e28", "e30"}
ONEWAY_BERLAWANAN = {"e05", "e06", "e07", "e08", "e27", "e29"}
# Sisanya (14 dua arah + 2 campuran) tetap tidak berarah.
DUA_ARAH = {
    "e01", "e02", "e03", "e04", "e09", "e10", "e14", "e15", "e16", "e17",
    "e18", "e31", "e32", "e33", "e20", "e25",
}


def build(directed_mode: str) -> tuple[Graph, dict]:
    """Bangun graf; directed_mode 'undirected' atau 'osm' (ikuti aturan OSM)."""
    data = yaml.safe_load(SCENARIO.read_text(encoding="utf-8"))
    graph = Graph()
    for node in data["nodes"]:
        graph.add_node(node["id"], node["label"])
    for edge in data["edges"]:
        if directed_mode not in {"undirected", "osm"}:
            raise ValueError(f"Mode tidak dikenal: {directed_mode!r}")
        if edge["id"] not in ONEWAY_SEARAH | ONEWAY_BERLAWANAN | DUA_ARAH:
            raise ValueError(f"Edge {edge['id']} belum terklasifikasi dalam audit.")
        source, target, directed = edge["from"], edge["to"], False
        if directed_mode == "osm":
            if edge["id"] in ONEWAY_SEARAH:
                directed = True
            elif edge["id"] in ONEWAY_BERLAWANAN:
                source, target, directed = target, source, True
        graph.add_edge(
            source, target, edge["weight"], edge["id"],
            edge.get("road", ""), directed=directed,
        )
    return graph, data["simulation"]


def describe(graph: Graph, result) -> str:
    """Ringkas rute: total bobot, jumlah ruas, dan urutan nama jalan."""
    if result is None:
        return "TIDAK ADA RUTE"
    streets: list[str] = []
    for start, end in zip(result.nodes, result.nodes[1:]):
        edge = next(e for e in graph.neighbors(start) if e.target == end)
        if edge.road_name and edge.road_name not in streets:
            streets.append(edge.road_name)
    return (
        f"{result.cost:.2f} menit | {len(result.nodes) - 1} ruas | "
        + " -> ".join(streets)
    )


def main() -> int:
    for mode in ("undirected", "osm"):
        graph, simulation = build(mode)
        print(f"\n=== MODE: {mode} ===")
        initial = dijkstra(graph, simulation["start"], simulation["goal"])
        print("rute awal          :", describe(graph, initial))
        closure = simulation["closure_edge"]
        alternate = dijkstra(graph, simulation["start"], simulation["goal"], {closure})
        print(f"setelah {closure} ditutup :", describe(graph, alternate))
        if initial and alternate:
            print(f"selisih            : {alternate.cost - initial.cost:+.2f} menit")
    print(
        "\nKesimpulan: penerapan aturan satu arah apa adanya membuat rute awal dan\n"
        "alternatif putus, sehingga graf tetap dimodelkan tidak berarah sebagai\n"
        "penyederhanaan yang terdokumentasi."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
