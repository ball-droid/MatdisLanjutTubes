"""Pengujian A* dan heuristiknya sebagai pembanding Dijkstra.

Prinsipnya: A* dengan heuristik admissible harus menghasilkan biaya rute
PERSIS sama dengan Dijkstra pada skenario yang sama; yang boleh berbeda hanya
jumlah node dieksplorasi. Seluruh kontrak input (ruas tertutup, node tak
dikenal, kasus tanpa rute) juga diuji sama ketatnya dengan baseline.
"""
import heapq

import pytest

from pathfinding.astar import astar
from pathfinding.dijkstra import dijkstra, reroute_after_closure
from pathfinding.graph import Graph
from pathfinding.heuristic import build_heuristic, estimate_minutes, haversine_m
from pathfinding.io import load_scenario
from pathfinding.simulation import DEFAULT_SCENARIO, DEMO_SCENARIO, run_simulation


def _search_pair(path):
    """Jalankan Dijkstra dan A* pada skenario (termasuk setelah penutupan)."""
    graph, scenario = load_scenario(path)
    coordinates = scenario["coordinates"]
    start, goal = scenario["start"], scenario["goal"]
    closure = scenario.get("closure_edge")

    initial_d = dijkstra(graph, start, goal)
    initial_a = astar(graph, start, goal, coordinates=coordinates)
    pair = [(initial_d, initial_a)]

    if closure:
        pair.append(
            (
                reroute_after_closure(graph, start, goal, {closure}),
                astar(graph, start, goal, {closure}, coordinates=coordinates),
            )
        )
    return graph, scenario, pair


@pytest.mark.parametrize("path", [DEFAULT_SCENARIO, DEMO_SCENARIO])
def test_astar_matches_dijkstra_cost_and_route(path):
    """Biaya dan urutan node harus identik, termasuk setelah ruas ditutup."""
    _graph, _scenario, pairs = _search_pair(path)
    for baseline, candidate in pairs:
        assert baseline is not None and candidate is not None
        assert candidate.cost == pytest.approx(baseline.cost)
        assert candidate.nodes == baseline.nodes
        assert candidate.edges == baseline.edges


def test_astar_route_edges_sum_to_cost():
    graph, scenario = load_scenario(DEFAULT_SCENARIO)
    coordinates = scenario["coordinates"]
    result = astar(graph, scenario["start"], scenario["goal"], coordinates=coordinates)
    assert result is not None
    assert len(result.edges) == len(result.nodes) - 1
    total = sum(
        next(
            e.weight
            for e in graph.neighbors(source)
            if e.target == target and e.edge_id == edge_id
        )
        for source, target, edge_id in zip(result.nodes, result.nodes[1:], result.edges)
    )
    assert total == pytest.approx(result.cost)


def test_astar_without_coordinates_behaves_like_dijkstra():
    """Skenario tanpa jejak peta (h = 0) harus persis Dijkstra."""
    graph, scenario = load_scenario(DEMO_SCENARIO)
    assert scenario["coordinates"] == {}
    result = astar(graph, scenario["start"], scenario["goal"])
    baseline = dijkstra(graph, scenario["start"], scenario["goal"])
    assert result is not None and baseline is not None
    assert result.cost == pytest.approx(9.0)
    assert result.nodes == baseline.nodes


def test_astar_expands_no_more_nodes_than_dijkstra():
    """A* boleh lebih hemat eksplorasi, tidak boleh lebih boros pada rute awal."""
    graph, scenario = load_scenario(DEFAULT_SCENARIO)
    stats_d, stats_a = {}, {}
    dijkstra(graph, scenario["start"], scenario["goal"], stats=stats_d)
    astar(
        graph, scenario["start"], scenario["goal"],
        coordinates=scenario["coordinates"], stats=stats_a,
    )
    assert stats_a["expanded"] <= stats_d["expanded"]
    assert stats_a["heuristic"] > 0  # heuristik benar-benar dipakai


def test_heuristic_is_admissible_on_damkar_scenario():
    """Untuk SEMUA node: h(node) tidak boleh melebihi biaya nyata ke goal."""
    graph, scenario = load_scenario(DEFAULT_SCENARIO)
    goal = scenario["goal"]
    heuristic = build_heuristic(scenario["coordinates"], goal)

    # Biaya nyata menuju goal: Dijkstra dari goal (graf model ini simetris).
    true_cost = {node_id: float("inf") for node_id in graph.nodes}
    true_cost[goal] = 0.0
    queue = [(0.0, goal)]
    while queue:
        distance, current = heapq.heappop(queue)
        if distance > true_cost[current]:
            continue
        for edge in graph.neighbors(current):
            if distance + edge.weight < true_cost[edge.target]:
                true_cost[edge.target] = distance + edge.weight
                heapq.heappush(queue, (true_cost[edge.target], edge.target))

    for node_id in graph.nodes:
        assert heuristic(node_id) <= true_cost[node_id] + 1e-9, node_id
    # Heuristik memberi informasi nyata (bukan nol) pada skenario berkoordinat.
    assert heuristic(scenario["start"]) > 0


def test_heuristic_helpers():
    # Satu derajat lintang di bumi ≈ 111.19 km.
    assert haversine_m(0.0, 0.0, 1.0, 0.0) == pytest.approx(111_195, rel=1e-3)
    # 70 km pada 35 km/jam = 120 menit.
    assert estimate_minutes(70_000, 35.0) == pytest.approx(120.0)
    # Tanpa koordinat, heuristik identik-nol (A* menyusut jadi Dijkstra).
    assert build_heuristic({}, "goal")("node") == 0.0


def test_astar_rejects_unknown_blocked_edge_and_nodes():
    graph = Graph()
    for node in ("A", "B", "C"):
        graph.add_node(node)
    graph.add_edge("A", "B", 1, "ab")
    graph.add_edge("B", "C", 1, "bc")
    with pytest.raises(ValueError, match="tidak dikenal"):
        astar(graph, "A", "C", {"bukan_edge"})
    with pytest.raises(KeyError):
        astar(graph, "Z", "C")
    with pytest.raises(KeyError):
        astar(graph, "A", "Z")


def test_astar_start_equals_goal_and_no_route():
    graph = Graph()
    for node in ("A", "B"):
        graph.add_node(node)
    same = astar(graph, "A", "A")
    assert same is not None
    assert same.nodes == ["A"] and same.cost == 0 and same.edges == []

    graph2 = Graph()
    for node in ("A", "B"):
        graph2.add_node(node)
    assert astar(graph2, "A", "B") is None


def test_astar_closure_that_disconnects_goal_returns_none():
    graph = Graph()
    for node in ("A", "B", "C"):
        graph.add_node(node)
    graph.add_edge("A", "B", 1, "ab")
    graph.add_edge("B", "C", 1, "bc")
    assert astar(graph, "A", "C") is not None
    assert astar(graph, "A", "C", {"bc"}) is None


def test_loader_extracts_coordinates_for_damkar_only():
    _, damkar = load_scenario(DEFAULT_SCENARIO)
    assert len(damkar["coordinates"]) == 31
    lat, lon = damkar["coordinates"]["pos_damkar_madukoro"]
    assert lat == pytest.approx(-6.9786176)
    assert lon == pytest.approx(110.4001383)
    _, demo = load_scenario(DEMO_SCENARIO)
    assert demo["coordinates"] == {}


def test_simulation_runs_with_astar(capsys):
    assert run_simulation(DEFAULT_SCENARIO, algorithm="astar") == 0
    output = capsys.readouterr().out
    assert "A* (heuristik haversine admissible" in output
    assert "Node dieksplorasi" in output
    assert "Rute alternatif berhasil ditemukan" in output
    # Angka rute tidak berubah hanya karena algoritma berganti.
    assert "10.74" in output and "11.93" in output


def test_simulation_rejects_unknown_algorithm():
    with pytest.raises(ValueError, match="Algoritma tidak dikenal"):
        run_simulation(DEFAULT_SCENARIO, algorithm="dstar")


def test_benchmark_compare_reports_both_algorithms():
    from pathfinding.benchmark import benchmark_compare

    report = benchmark_compare(DEFAULT_SCENARIO, repeats=20)
    assert report["repeats"] == 20
    baseline = report["algorithms"]["dijkstra"]
    candidate = report["algorithms"]["astar"]
    for entry in (baseline, candidate):
        assert entry["mean_ms"] >= 0
        assert entry["min_ms"] <= entry["max_ms"]
        assert entry["route_edges"] == entry["route_nodes"] - 1
    # Perbandingan yang sah: biaya sama, A* tidak lebih boros eksplorasi.
    assert candidate["cost"] == pytest.approx(baseline["cost"])
    assert candidate["expanded"] <= baseline["expanded"]
    assert report["speedup_dijkstra_over_astar"] > 0
    assert report["expanded_saved"] == baseline["expanded"] - candidate["expanded"]

    with pytest.raises(ValueError, match="pengulangan"):
        benchmark_compare(DEFAULT_SCENARIO, repeats=0)
