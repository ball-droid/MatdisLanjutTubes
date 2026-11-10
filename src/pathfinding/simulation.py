"""Entry point simulasi Dijkstra dengan output terminal yang terstruktur."""
from __future__ import annotations

import argparse
import textwrap
from pathlib import Path

from .dijkstra import PathResult, dijkstra, reroute_after_closure
from .graph import Graph
from .io import load_scenario

DEMO_SCENARIO = Path(__file__).resolve().parents[2] / "data" / "pasar_johar_demo.yaml"
DEFAULT_SCENARIO = Path(__file__).resolve().parents[2] / "data" / "pasar_johar_damkar.yaml"
WIDTH = 78


def run_simulation(scenario_path: str | Path = DEFAULT_SCENARIO) -> int:
    graph, scenario = load_scenario(scenario_path)
    start, goal = str(scenario.get("start", "")), str(scenario.get("goal", ""))
    blocked = set(str(item) for item in scenario.get("blocked_edges", []))
    if not start or not goal:
        raise ValueError("Skenario harus menetapkan start dan goal.")

    metadata = scenario.get("metadata", {}) or {}
    unit_label = metadata.get("display_weight_unit", "unit simulasi")
    access_status = scenario.get("access_status", {}) or {}
    catalog = _edge_catalog(graph)

    initial = dijkstra(graph, start, goal, blocked)
    closure_edge = str(scenario.get("closure_edge") or "")
    updated = (
        reroute_after_closure(graph, start, goal, {closure_edge} | blocked)
        if closure_edge
        else None
    )

    _print_header(
        title=str(metadata.get("title", scenario.get("title", "Simulasi Pathfinding"))),
        location=str(metadata.get("location", "Tidak dicantumkan")),
        event_date=_format_date(str(metadata.get("event_date", "Tidak dicantumkan"))),
        node_count=len(graph.nodes),
        edge_count=len(catalog),
    )
    _print_section("01  KONFIGURASI SIMULASI")
    _print_field("Titik awal", graph.nodes.get(start, start))
    _print_field("Titik tujuan", graph.nodes.get(goal, goal))
    _print_field("Algoritma", "Dijkstra (baseline / pencarian ulang penuh)")
    _print_field("Model graf", str(metadata.get("graph_type", "tidak berarah (dua arah)")))
    _print_field("Satuan bobot", str(unit_label))
    _print_field("Ruas tertutup sejak awal", ", ".join(sorted(blocked)) if blocked else "Tidak ada")

    _print_sources(metadata)
    _print_node_index(graph, start, goal, initial, updated)
    _print_edge_index(catalog, access_status, unit_label)

    if initial is None:
        _print_section("03  RUTE AWAL")
        print("  Rute tidak ditemukan dari titik awal ke tujuan.")
        return 1

    _print_route("05  RUTE AWAL", graph, initial, unit_label, catalog)

    if closure_edge:
        description = str(
            scenario.get("closure_description", "Ruas ditutup untuk keperluan simulasi.")
        )
        _print_section("06  EVENT: AKSES JALAN TERHAMBAT")
        _print_field("ID ruas", closure_edge)
        if closure_edge in catalog:
            source, target, weight, road = catalog[closure_edge]
            _print_field("Ruas", f"{graph.nodes.get(source, source)} -> {graph.nodes.get(target, target)}")
            _print_field("Keterangan ruas", road if road else "Tidak dicantumkan")
            _print_field("Bobot ruas", f"{weight:g} {unit_label}")
        status = access_status.get(closure_edge)
        if status:
            _print_field("Status akses", status)
        print("  Keterangan :")
        _print_wrapped(description, indent="    ", width=WIDTH - 4)
        print("  Tindakan   : Ruas dikecualikan dari pencarian rute berikutnya.")

        if updated is None:
            _print_section("07  HASIL SETELAH PENUTUPAN")
            print(f"  Tidak ada rute alternatif setelah ruas {closure_edge} ditutup.")
            return 1
        _print_route("07  RUTE ALTERNATIF", graph, updated, unit_label, catalog)
        difference = updated.cost - initial.cost
        sign = "+" if difference >= 0 else ""
        _print_section("08  RINGKASAN HASIL")
        _print_field("Rute awal", f"{initial.cost:g} {unit_label} | {len(initial.nodes) - 1} ruas")
        _print_field("Rute alternatif", f"{updated.cost:g} {unit_label} | {len(updated.nodes) - 1} ruas")
        _print_field("Perubahan bobot total", f"{sign}{difference:g} {unit_label}")
        _print_field(
            "Selisih ruas",
            f"{len(updated.nodes) - len(initial.nodes):+d} ruas",
        )
        _print_field("Status", "Rute alternatif berhasil ditemukan")

    _print_data_notes(metadata)
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


def _edge_catalog(graph: Graph) -> dict[str, tuple[str, str, float, str]]:
    """Pemetaan ID ruas -> (asal, tujuan, bobot, nama jalan) sesuai urutan YAML."""
    catalog: dict[str, tuple[str, str, float, str]] = {}
    for source in graph.nodes:
        for edge in graph.neighbors(source):
            catalog.setdefault(edge.edge_id, (source, edge.target, edge.weight, edge.road_name))
    return catalog


def _print_sources(metadata: dict) -> None:
    _print_section("02  SUMBER BERITA DAN BATAS DATA")
    articles = metadata.get("source_articles") or []
    if isinstance(articles, list) and articles:
        for index, url in enumerate(articles, start=1):
            _print_field(f"Sumber berita {index}", str(url))
    else:
        _print_field("Sumber berita", "Tidak dicantumkan")

    boundary = metadata.get("fact_boundary") or {}
    if isinstance(boundary, dict) and boundary:
        _print_field("Fakta dari berita", str(boundary.get("from_news", "Tidak dicantumkan")))
        _print_field("Model peta / simulasi", str(boundary.get("from_map_model", "Tidak dicantumkan")))
        _print_field(
            "Tidak tersedia dalam berita",
            str(boundary.get("not_available_in_news", "Tidak dicantumkan")),
        )
    else:
        _print_field("Fakta dari berita", str(metadata.get("reported_fact", "Tidak dicantumkan")))


def _node_role(node_id: str, start: str, goal: str,
               initial: PathResult | None, alternate: PathResult | None) -> str:
    """Peran node dalam konteks rute damkar pada skenario yang sedang dijalankan."""
    roles: list[str] = []
    if node_id == start:
        roles.append("titik awal")
    if node_id == goal:
        roles.append("tujuan")
    if initial and node_id in initial.nodes:
        roles.append("dilalui rute awal")
    if alternate and node_id in alternate.nodes:
        roles.append("dilalui rute alternatif")
    return ", ".join(roles) if roles else "jaringan pendukung (belum dilalui rute)"


def _print_node_index(graph: Graph, start: str, goal: str,
                      initial: PathResult | None, alternate: PathResult | None) -> None:
    _print_section(f"03  DAFTAR NODE ({len(graph.nodes)} node)")
    for index, (node_id, label) in enumerate(graph.nodes.items(), start=1):
        role = _node_role(node_id, start, goal, initial, alternate)
        print(f"  {index:02d}. {node_id} · {role}")
        if label != node_id:
            _print_wrapped(label, indent="       ", width=WIDTH - 2)


def _print_edge_index(catalog: dict[str, tuple[str, str, float, str]],
                      access_status: dict[str, str], unit_label: str) -> None:
    _print_section(f"04  DAFTAR RUAS JALAN ({len(catalog)} ruas)")
    for edge_id in sorted(catalog):
        source, target, weight, road = catalog[edge_id]
        print(f"  {edge_id} · {source} -> {target}")
        detail = f"{weight:g} {unit_label}" + (f" · {road}" if road else "")
        _print_wrapped(detail, indent="       ", width=WIDTH - 2)
        status = access_status.get(edge_id)
        if status:
            _print_wrapped(f"status akses: {status}", indent="       ", width=WIDTH - 2)


def _print_route(title: str, graph: Graph, result: PathResult,
                 unit_label: str, catalog: dict[str, tuple[str, str, float, str]]) -> None:
    _print_section(title)
    streets: list[str] = []
    nodes = result.nodes
    for index, node_id in enumerate(nodes):
        label = graph.nodes.get(node_id, node_id)
        print(f"  {index + 1:02d}. {label}")
        if index > 0:
            edge_id = result.edges[index - 1]
            _, _, weight, road_name = catalog[edge_id]
            if road_name:
                detail = f"Lewat {edge_id} · {road_name} · {weight:g} {unit_label}"
                if road_name not in streets:
                    streets.append(road_name)
            else:
                detail = f"Lewat {edge_id} · {weight:g} {unit_label}"
            for detail_line in textwrap.wrap(detail, width=WIDTH - 9):
                print("       " + detail_line)
        if index == 0:
            print("       [TITIK AWAL]")
        elif index == len(nodes) - 1:
            print("       [TUJUAN]")
        if index < len(nodes) - 1:
            print("       │")
            print("       ▼")
    print("\n  Total bobot : " + f"{result.cost:g} {unit_label}")
    print(f"  Jumlah ruas : {max(0, len(nodes) - 1)}")
    if streets:
        print("\n  JALUR DAMKAR (urutan jalan yang dilalui)")
        sequence = "  ->  ".join(streets)
        _print_wrapped(sequence, indent="    ", width=WIDTH - 2)


def _print_data_notes(metadata: dict) -> None:
    _print_section("09  CATATAN VALIDITAS DATA")
    note = str(
        metadata.get(
            "data_note",
            "Graf dan pembagian bobot tiap ruas merupakan model demonstrasi berdasarkan "
            "screenshot peta. Total durasi diselaraskan dengan angka yang tampak pada peta; "
            "bukan hasil pengukuran GIS atau waktu aktual masing-masing ruas. Validasi "
            "topologi dan ruas penutupan tetap diperlukan.",
        )
    )
    _print_wrapped(note, indent="  ", width=WIDTH - 2)

    verification = metadata.get("verification") or {}
    if isinstance(verification, dict) and verification:
        checked_on = verification.get("checked_on")
        _print_field("Terverifikasi", f"pemeriksaan {checked_on}" if checked_on else "ada")
        for key, value in verification.items():
            if key == "checked_on":
                continue
            _print_wrapped(f"- {value}", indent="      ", width=WIDTH - 6)

    not_verified = metadata.get("not_verified") or []
    if isinstance(not_verified, list) and not_verified:
        print("  Belum diverifikasi:")
        for item in not_verified:
            _print_wrapped(f"- {item}", indent="      ", width=WIDTH - 6)


def main() -> None:
    parser = argparse.ArgumentParser(description="Simulasi pencarian rute Dijkstra.")
    parser.add_argument("--scenario", default=str(DEFAULT_SCENARIO), help="Path file YAML skenario.")
    args = parser.parse_args()
    raise SystemExit(run_simulation(args.scenario))


if __name__ == "__main__":
    main()
