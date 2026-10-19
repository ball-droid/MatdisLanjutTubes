"""Entry point simulasi Dijkstra untuk studi kasus Pasar Johar."""
from __future__ import annotations
import argparse
from pathlib import Path
from .dijkstra import dijkstra, reroute_after_closure
from .io import load_scenario

DEFAULT_SCENARIO = Path(__file__).resolve().parents[2] / "data" / "pasar_johar_demo.yaml"


def run_simulation(scenario_path: str | Path = DEFAULT_SCENARIO) -> int:
    graph, scenario = load_scenario(scenario_path)
    start, goal = str(scenario.get("start", "")), str(scenario.get("goal", ""))
    blocked = set(str(item) for item in scenario.get("blocked_edges", []))
    if not start or not goal:
        raise ValueError("Skenario harus menetapkan start dan goal.")

    print(f"Skenario : {scenario.get('title', 'Tanpa judul')}")
    print(f"Awal     : {graph.nodes.get(start, start)} ({start})")
    print(f"Tujuan   : {graph.nodes.get(goal, goal)} ({goal})")
    print(f"Edge ditutup sejak awal: {', '.join(sorted(blocked)) if blocked else 'tidak ada'}")
    metadata = scenario.get("metadata", {})
    unit_label = metadata.get("display_weight_unit", "unit simulasi")
    initial = dijkstra(graph, start, goal, blocked)
    if initial is None:
        print("Rute tidak ditemukan.")
        return 1
    _print_route("Rute awal", graph, initial.nodes, initial.cost, unit_label)

    # Simulasi event dari skema YAML referensi: ruas yang ditutup dibuat
    # tidak dapat dilalui melalui blocked_edges; event pertama dipilih manual
    # sebagai konfigurasi untuk baseline.
    closed = scenario.get("closure_edge")
    if closed:
        description = scenario.get("closure_description")
        print(f"Event penutupan ({closed}): {description or 'ruas ditutup untuk simulasi.'}")
        updated = reroute_after_closure(graph, start, goal, {str(closed)} | blocked)
        if updated is None:
            print(f"Tidak ada rute alternatif setelah ruas {closed} ditutup.")
            return 1
        _print_route(f"Rute alternatif setelah penutupan {closed}", graph, updated.nodes, updated.cost, unit_label)
    print("Catatan: bobot per ruas didistribusikan sebagai estimasi untuk menguji algoritma, bukan hasil pengukuran jarak/waktu aktual tiap ruas.")
    return 0


def _print_route(title: str, graph, nodes: list[str], cost: float, unit_label: str = "unit simulasi") -> None:
    labels = [graph.nodes[node_id] for node_id in nodes]
    print(f"{title}: " + " -> ".join(labels))
    print(f"Total bobot: {cost:g} {unit_label} | Jumlah ruas: {len(nodes) - 1}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Simulasi pencarian rute Dijkstra.")
    parser.add_argument("--scenario", default=str(DEFAULT_SCENARIO), help="Path file YAML skenario.")
    args = parser.parse_args()
    raise SystemExit(run_simulation(args.scenario))


if __name__ == "__main__":
    main()
