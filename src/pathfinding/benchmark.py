"""Benchmark sederhana untuk mengukur waktu eksekusi Dijkstra."""

from __future__ import annotations

import argparse
from statistics import mean
from time import perf_counter
from pathlib import Path

from .dijkstra import dijkstra
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark Dijkstra pada skenario YAML.")
    parser.add_argument("--scenario", default=str(DEFAULT_SCENARIO))
    parser.add_argument("--repeats", type=int, default=1000)
    args = parser.parse_args()
    result = benchmark(args.scenario, args.repeats)
    print(f"Pengulangan : {result['repeats']}")
    print(f"Rata-rata   : {result['mean_ms']:.6f} ms")
    print(f"Minimum     : {result['min_ms']:.6f} ms")
    print(f"Maksimum    : {result['max_ms']:.6f} ms")
    print("Catatan: hasil hanya berlaku untuk mesin, versi Python, dan graf yang dipakai saat benchmark.")


if __name__ == "__main__":
    main()
