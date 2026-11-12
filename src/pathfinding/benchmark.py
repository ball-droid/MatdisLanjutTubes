"""Benchmark sederhana untuk mengukur waktu eksekusi Dijkstra dan A*.

``benchmark()`` mengukur satu algoritma (Dijkstra, perilaku lama dipertahankan);
``benchmark_compare()`` menjalankan keduanya pada skenario yang sama sehingga
kecepatan, biaya rute, dan jumlah node dieksplorasi bisa dibandingkan langsung
dalam satu tabel.
"""

from __future__ import annotations

import argparse
from statistics import mean
from time import perf_counter
from pathlib import Path
from typing import Callable

from .astar import astar
from .dijkstra import PathResult, dijkstra
from .io import load_scenario
from .simulation import DEFAULT_SCENARIO


def benchmark(scenario_path: str | Path = DEFAULT_SCENARIO, repeats: int = 1000) -> dict[str, float | int]:
    if repeats < 1:
        raise ValueError("Jumlah pengulangan harus minimal 1.")
    graph, scenario = load_scenario(scenario_path)
    start, goal = str(scenario["start"]), str(scenario["goal"])
    blocked = set(str(item) for item in scenario.get("blocked_edges", []))
    durations: list[float] = []

    for _ in range(repeats):
        begin = perf_counter()
        dijkstra(graph, start, goal, blocked)
        durations.append(perf_counter() - begin)

    return {
        "repeats": repeats,
        "mean_ms": mean(durations) * 1000,
        "min_ms": min(durations) * 1000,
        "max_ms": max(durations) * 1000,
    }


def _measure(search: Callable[[], object], repeats: int) -> dict[str, float]:
    """Waktu eksekusi `repeats` kali dalam milidetik."""
    durations: list[float] = []
    for _ in range(repeats):
        begin = perf_counter()
        search()
        durations.append(perf_counter() - begin)
    return {
        "mean_ms": mean(durations) * 1000,
        "min_ms": min(durations) * 1000,
        "max_ms": max(durations) * 1000,
    }


def benchmark_compare(
    scenario_path: str | Path = DEFAULT_SCENARIO, repeats: int = 1000
) -> dict:
    """Bandingkan Dijkstra dan A* pada skenario yang sama.

    Mengembalikan per-algoritma: waktu (ms), biaya rute, jumlah node rute, dan
    jumlah node dieksplorasi; plus rasio kecepatan Dijkstra/A* (> 1 berarti A*
    lebih cepat pada mesin ini).
    """
    if repeats < 1:
        raise ValueError("Jumlah pengulangan harus minimal 1.")
    graph, scenario = load_scenario(scenario_path)
    start, goal = str(scenario["start"]), str(scenario["goal"])
    blocked = set(str(item) for item in scenario.get("blocked_edges", []))
    coordinates = scenario.get("coordinates", {}) or {}

    searches: dict[str, Callable[[dict], PathResult | None]] = {
        "dijkstra": lambda stats: dijkstra(graph, start, goal, blocked, stats=stats),
        "astar": lambda stats: astar(
            graph, start, goal, blocked, coordinates=coordinates, stats=stats
        ),
    }

    report: dict = {"scenario": str(scenario_path), "repeats": repeats, "algorithms": {}}
    for name, search in searches.items():
        stats: dict = {}
        result = search(stats)
        timing = _measure(lambda s=search: s({}), repeats)
        report["algorithms"][name] = {
            **timing,
            "cost": None if result is None else result.cost,
            "route_nodes": None if result is None else len(result.nodes),
            "route_edges": None if result is None else len(result.edges),
            "expanded": stats.get("expanded"),
        }

    base = report["algorithms"]["dijkstra"]["mean_ms"]
    candidate = report["algorithms"]["astar"]["mean_ms"]
    report["speedup_dijkstra_over_astar"] = base / candidate if candidate else float("inf")
    base_exp = report["algorithms"]["dijkstra"]["expanded"]
    cand_exp = report["algorithms"]["astar"]["expanded"]
    report["expanded_saved"] = (
        None if base_exp is None or cand_exp is None else base_exp - cand_exp
    )
    return report


def _format_compare(report: dict) -> str:
    unit = "ms"
    lines = [
        f"Perbandingan Dijkstra vs A*  |  skenario: {report['scenario']}",
        f"Pengulangan per algoritma : {report['repeats']}",
        "",
        f"  {'algoritma':<10} {'rata-rata':>14} {'minimum':>14} {'maksimum':>14}"
        f" {'biaya rute':>14} {'node rute':>10} {'dieksplorasi':>13}",
    ]
    for name, entry in report["algorithms"].items():
        cost = "n/a" if entry["cost"] is None else f"{entry['cost']:g} menit"
        route_nodes = "n/a" if entry["route_nodes"] is None else str(entry["route_nodes"])
        lines.append(
            f"  {name:<10} {entry['mean_ms']:>12.6f} {unit} {entry['min_ms']:>12.6f} {unit}"
            f" {entry['max_ms']:>12.6f} {unit} {cost:>14} {route_nodes:>10}"
            f" {str(entry['expanded']):>13}"
        )
    lines += [
        "",
        f"  Rasio kecepatan (Dijkstra / A*) : {report['speedup_dijkstra_over_astar']:.3f}x"
        "  (> 1 berarti A* lebih cepat)",
        f"  Selisih node dieksplorasi       : {report['expanded_saved']}",
        "Catatan: biaya rute kedua algoritma wajib sama; angka waktu hanya berlaku"
        " untuk mesin, versi Python, dan skenario saat benchmark dijalankan.",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark Dijkstra/A* pada skenario YAML.")
    parser.add_argument("--scenario", default=str(DEFAULT_SCENARIO))
    parser.add_argument("--repeats", type=int, default=1000)
    parser.add_argument(
        "--compare", action="store_true",
        help="Bandingkan Dijkstra dan A* dalam satu tabel (default: Dijkstra saja).",
    )
    args = parser.parse_args()
    if args.compare:
        print(_format_compare(benchmark_compare(args.scenario, args.repeats)))
        return
    result = benchmark(args.scenario, args.repeats)
    print(f"Pengulangan : {result['repeats']}")
    print(f"Rata-rata   : {result['mean_ms']:.6f} ms")
    print(f"Minimum     : {result['min_ms']:.6f} ms")
    print(f"Maksimum    : {result['max_ms']:.6f} ms")
    print("Catatan: hasil hanya berlaku untuk mesin, versi Python, dan graf yang dipakai saat benchmark.")


if __name__ == "__main__":
    main()
