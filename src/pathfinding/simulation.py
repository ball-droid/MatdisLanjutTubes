"""Entry point simulasi Dijkstra dengan output terminal yang terstruktur."""
from __future__ import annotations

import argparse
import textwrap
from pathlib import Path
from typing import Iterable

from .dijkstra import dijkstra, reroute_after_closure
from .graph import Edge, Graph
from .io import load_scenario

DEFAULT_SCENARIO = Path(__file__).resolve().parents[2] / "data" / "pasar_johar_demo.yaml"
WIDTH = 78


def run_simulation(scenario_path: str | Path = DEFAULT_SCENARIO) -> int:
    graph, scenario = load_scenario(scenario_path)
    start, goal = str(scenario.get("start", "")), str(scenario.get("goal", ""))
    blocked = set(str(item) for item in scenario.get("blocked_edges", []))
    if not start or not goal:
        raise ValueError("Skenario harus menetapkan start dan goal.")

    metadata = scenario.get("metadata", {})
    unit_label = metadata.get("display_weight_unit", "unit simulasi")
    edge_count = len({edge.edge_id for node_id in graph.nodes for edge in graph.neighbors(node_id)})

    _print_header(
        title=str(metadata.get("title", scenario.get("title", "Simulasi Pathfinding"))),
        location=str(metadata.get("location", "Tidak dicantumkan")),
        event_date=_format_date(str(metadata.get("event_date", "Tidak dicantumkan"))),
        node_count=len(graph.nodes),
        edge_count=edge_count,
    )
    _print_section("KONFIGURASI SIMULASI")
    _print_field("Titik awal", graph.nodes.get(start, start))
    _print_field("Titik tujuan", graph.nodes.get(goal, goal))
    _print_field("Algoritma", "Dijkstra (baseline / pencarian ulang penuh)")
    _print_field("Ruas tertutup sejak awal", ", ".join(sorted(blocked)) if blocked else "Tidak ada")

    initial = dijkstra(graph, start, goal, blocked)
    if initial is None:
        _print_section("HASIL SIMULASI")
        print("  Rute tidak ditemukan dari titik awal ke tujuan.")
        return 1

    _print_route("01  RUTE AWAL", graph, initial.nodes, initial.cost, unit_label)

    closure_edge = scenario.get("closure_edge")
    if closure_edge:
        closure_edge = str(closure_edge)
        description = str(scenario.get("closure_description", "Ruas ditutup untuk keperluan simulasi."))
        edge_info = _find_edge(graph, closure_edge)
        _print_section("EVENT: AKSES JALAN TERHAMBAT")
        _print_field("ID ruas", closure_edge)
        if edge_info:
            source, edge = edge_info
            target_label = graph.nodes.get(edge.target, edge.target)
            _print_field("Ruas", f"{graph.nodes.get(source, source)} -> {target_label}")
            _print_field("Bobot ruas", f"{edge.weight:g} {unit_label}")
        print("  Keterangan :")
        _print_wrapped(description, indent="    ", width=WIDTH - 4)
        print("  Tindakan   : Ruas dikecualikan dari pencarian rute berikutnya.")

        updated = reroute_after_closure(graph, start, goal, {closure_edge} | blocked)
        if updated is None:
            _print_section("HASIL SETELAH PENUTUPAN")
            print(f"  Tidak ada rute alternatif setelah ruas {closure_edge} ditutup.")
            return 1
        _print_route("02  RUTE ALTERNATIF", graph, updated.nodes, updated.cost, unit_label)
        difference = updated.cost - initial.cost
        sign = "+" if difference >= 0 else ""
        _print_section("RINGKASAN HASIL")
        _print_field("Rute awal", f"{initial.cost:g} {unit_label} | {len(initial.nodes) - 1} ruas")
        _print_field("Rute alternatif", f"{updated.cost:g} {unit_label} | {len(updated.nodes) - 1} ruas")
        _print_field("Perubahan bobot total", f"{sign}{difference:g} {unit_label}")
        _print_field("Status", "Rute alternatif berhasil ditemukan")

    _print_section("CATATAN DATA")
    note = (
        "Graf dan pembagian bobot tiap ruas merupakan model demonstrasi berdasarkan "
        "screenshot peta. Total durasi diselaraskan dengan angka yang tampak pada peta; "
        "bukan hasil pengukuran GIS atau waktu aktual masing-masing ruas. Validasi "
        "topologi dan ruas penutupan tetap diperlukan."
    )
    _print_wrapped(note, indent="  ", width=WIDTH - 2)
    print("\nSimulasi selesai.\n")
    return 0


def _print_header(title: str, location: str, event_date: str, node_count: int, edge_count: int) -> None:
    print("╔" + "═" * (WIDTH - 2) + "╗")
    _print_box_lines("PATHFINDING C  |  DIJKSTRA ENGINE BASE")
    print("╠" + "═" * (WIDTH - 2) + "╣")
    _print_box_lines(title)
    print("╟" + "─" * (WIDTH - 2) + "╢")
    _print_box_lines(f"Lokasi  : {location}")
    _print_box_lines(f"Tanggal : {event_date}")
    _print_box_lines(f"Graf    : {node_count} node | {edge_count} ruas")
    print("╚" + "═" * (WIDTH - 2) + "╝")
    print()


def _print_box_lines(content: str) -> None:
    for line in textwrap.wrap(content, width=WIDTH - 4) or [""]:
        print("║ " + line.ljust(WIDTH - 4) + " ║")


def _format_date(value: str) -> str:
    """Ubah tanggal YYYY-MM-DD menjadi tanggal berbahasa Indonesia."""
    month_names = {
        1: "Januari", 2: "Februari", 3: "Maret", 4: "April",
        5: "Mei", 6: "Juni", 7: "Juli", 8: "Agustus",
        9: "September", 10: "Oktober", 11: "November", 12: "Desember",
    }
    try:
        year, month, day = (int(part) for part in value.split("-"))
        return f"{day} {month_names[month]} {year}"
    except (ValueError, KeyError):
        return value


def _print_section(title: str) -> None:
    print("\n" + "─" * WIDTH)
    print(title)
    print("─" * WIDTH)


def _print_field(label: str, value: str) -> None:
    prefix = f"  {label:<24}: "
    continuation_indent = " " * len(prefix)
    lines = textwrap.wrap(str(value), width=WIDTH - len(prefix)) or [""]
    print(prefix + lines[0])
    for line in lines[1:]:
        print(continuation_indent + line)


def _print_wrapped(content: str, indent: str, width: int) -> None:
    for line in textwrap.wrap(content, width=max(20, width - len(indent))) or [""]:
        print(indent + line)


def _print_route(title: str, graph: Graph, nodes: list[str], cost: float, unit_label: str) -> None:
    _print_section(title)
    for index, node_id in enumerate(nodes):
        label = graph.nodes.get(node_id, node_id)
        print(f"  {index + 1:02d}. {label}")
        if index == 0:
            print("       [TITIK AWAL]")
        elif index < len(nodes):
            incoming = _find_edge_between(graph, nodes[index - 1], node_id)
            if incoming:
                edge_id, weight, road_name = incoming
                detail = f"Lewat {edge_id} · {weight:g} {unit_label}"
                for detail_line in textwrap.wrap(detail, width=WIDTH - 9):
                    print("       " + detail_line)
        if index < len(nodes) - 1:
            print("       │")
            print("       ▼")
    print("\n  Total bobot : " + f"{cost:g} {unit_label}")
    print(f"  Jumlah ruas : {max(0, len(nodes) - 1)}")


def _find_edge(graph: Graph, edge_id: str) -> tuple[str, Edge] | None:
    for source in graph.nodes:
        for edge in graph.neighbors(source):
            if edge.edge_id == edge_id:
                return source, edge
    return None


def _find_edge_between(graph: Graph, source: str, target: str) -> tuple[str, float, str] | None:
    for edge in graph.neighbors(source):
        if edge.target == target:
            return edge.edge_id, edge.weight, edge.road_name
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Simulasi pencarian rute Dijkstra.")
    parser.add_argument("--scenario", default=str(DEFAULT_SCENARIO), help="Path file YAML skenario.")
    args = parser.parse_args()
    raise SystemExit(run_simulation(args.scenario))


if __name__ == "__main__":
    main()
