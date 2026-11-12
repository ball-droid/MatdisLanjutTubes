"""Pengujian rute alternatif per unit damkar (multi-rute, titik layanan)."""
import pytest

from pathfinding.astar import astar
from pathfinding.dijkstra import dijkstra
from pathfinding.graph import Graph
from pathfinding.io import load_scenario
from pathfinding.rute_alternatif import plan_alternatives, route_via
from pathfinding.simulation import DEFAULT_SCENARIO, run_simulation


def _leg_search(graph, blocked, coordinates=None, algorithm="dijkstra"):
    """Bungkus pencarian sesuai algoritma dan himpunan ruas tertutup."""
    if algorithm == "dijkstra":
        return lambda a, b: dijkstra(graph, a, b, blocked)
    return lambda a, b: astar(graph, a, b, blocked, coordinates=coordinates or {})


def _scenario_env():
    graph, scenario = load_scenario(DEFAULT_SCENARIO)
    blocked = {str(scenario.get("closure_edge"))} | {
        str(item) for item in scenario.get("blocked_edges", [])
    }
    return graph, scenario, blocked


# ------------------------------------------------------------------ unit --


def test_route_via_merges_legs_into_single_path():
    graph = Graph()
    for node in ("A", "B", "C", "D"):
        graph.add_node(node)
    graph.add_edge("A", "B", 1, "ab")
    graph.add_edge("B", "D", 2, "bd")
    graph.add_edge("A", "C", 1, "ac")
    graph.add_edge("C", "D", 1, "cd")

    result = route_via(["A", "C", "D"], lambda a, b: dijkstra(graph, a, b))
    assert result is not None
    assert result.nodes == ["A", "C", "D"]
    assert result.cost == 2
    assert result.edges == ["ac", "cd"]

    # Titik layanan memaksa rute melewati B walau bukan jalur tercepat.
    forced = route_via(["A", "B", "D"], lambda a, b: dijkstra(graph, a, b))
    assert forced is not None
    assert forced.nodes == ["A", "B", "D"]
    assert forced.cost == 3
    assert forced.edges == ["ab", "bd"]


def test_route_via_returns_none_when_a_leg_is_impossible():
    graph = Graph()
    for node in ("A", "B", "C"):
        graph.add_node(node)
    graph.add_edge("A", "B", 1, "ab")  # C terpisah
    assert route_via(["A", "C"], lambda a, b: dijkstra(graph, a, b)) is None


def test_route_via_requires_two_points():
    with pytest.raises(ValueError, match="titik awal"):
        route_via(["A"], lambda a, b: None)


def test_plan_alternatives_keeps_failed_plan_visible():
    graph = Graph()
    for node in ("A", "B", "C"):
        graph.add_node(node)
    graph.add_edge("A", "B", 1, "ab")
    plans = [
        {"id": "biasa", "label": "Rute biasa", "waypoints": []},
        {"id": "gagal", "label": "Lewat C", "waypoints": ["C"]},
    ]
    computed = plan_alternatives(plans, "A", "B", lambda a, b: dijkstra(graph, a, b))
    assert computed[0]["result"] is not None
    assert computed[1]["result"] is None  # gagal dilaporkan, bukan dihapus


# ----------------------------------------------------- skenario damkar --


def test_three_alternatives_are_distinct_and_honor_waypoints():
    graph, scenario, blocked = _scenario_env()
    leg = _leg_search(graph, blocked, scenario["coordinates"])
    alternatives = plan_alternatives(
        scenario["alternatives"], scenario["start"], scenario["goal"], leg
    )
    assert len(alternatives) == 3
    results = [alt["result"] for alt in alternatives]
    assert all(result is not None for result in results)

    # Rutenya BERBEDA satu sama lain (permintaan multi-unit).
    sequences = {tuple(result.nodes) for result in results}
    assert len(sequences) == 3

    by_id = {alt["id"]: alt for alt in alternatives}
    southern = by_id["selatan_kawalan_polisi"]["result"]
    ambulance = by_id["bantuan_ambulance"]["result"]
    escort = by_id["kawalan_polda_akses_tirtoyoso"]["result"]

    # Alternatif tercepat tetap11,93 menit dan melewati kantor polisi.
    assert southern.cost == pytest.approx(11.93, abs=0.05)
    assert "simpang_cipto_bugangan" in southern.nodes

    # Rute ambulance melewati rumah sakit; rute kawalan melewati Polda dan
    # memakai akses Tirtoyoso XI (simpang_tirtoyoso_xi) sebagai simpul masuk.
    assert "rumah_sakit_kariadi" in ambulance.nodes
    assert ambulance.cost > southern.cost
    assert "polisi_polda_jateng" in escort.nodes
    assert "simpang_tirtoyoso_xi" in escort.nodes
    assert escort.cost > southern.cost

    # Semua alternatif tetap tujuan yang sama dan tidak memakai ruas tertutup.
    for result in results:
        assert result.nodes[0] == scenario["start"]
        assert result.nodes[-1] == scenario["goal"]
        assert scenario["closure_edge"] not in result.edges


def test_alternatives_give_same_cost_with_astar():
    graph, scenario, blocked = _scenario_env()
    coords = scenario["coordinates"]
    plans = scenario["alternatives"]
    dijkstra_alts = plan_alternatives(
        plans, scenario["start"], scenario["goal"], _leg_search(graph, blocked, coords)
    )
    astar_alts = plan_alternatives(
        plans, scenario["start"], scenario["goal"],
        _leg_search(graph, blocked, coords, algorithm="astar"),
    )
    for base, candidate in zip(dijkstra_alts, astar_alts):
        assert candidate["result"] is not None and base["result"] is not None
        assert candidate["result"].cost == pytest.approx(base["result"].cost)
        assert candidate["result"].nodes == base["result"].nodes


def test_every_node_is_visited_by_something():
    """Seluruh node jaringan (36) dikunjungi minimal satu rute armada."""
    graph, scenario, blocked = _scenario_env()
    leg = _leg_search(graph, blocked, scenario["coordinates"])
    start, goal = scenario["start"], scenario["goal"]

    visited = set()
    initial = dijkstra(graph, start, goal)
    assert initial is not None
    visited |= set(initial.nodes)
    for alt in plan_alternatives(scenario["alternatives"], start, goal, leg):
        assert alt["result"] is not None
        visited |= set(alt["result"].nodes)
    for node_id, fields in scenario["node_facilities"].items():
        if (fields.get("facility") or {}).get("type") != "fire_station":
            continue
        route = dijkstra(graph, node_id, goal)
        assert route is not None
        visited |= set(route.nodes)

    assert len(visited) == len(graph.nodes) == 36
    assert visited == set(graph.nodes)


# ------------------------------------------------------------- loader --


def _write(tmp_path, text):
    path = tmp_path / "alternatif.yaml"
    path.write_text(text, encoding="utf-8")
    return path


BASE = """
metadata:
  facilities: true
nodes:
  - id: A
    label: "A"
    hydrant: {verified: false, distance_m: 0, source: "asumsi model"}
  - id: B
    label: "B"
    hydrant: {verified: false, distance_m: 0, source: "asumsi model"}
  - id: C
    label: "C"
    hydrant: {verified: false, distance_m: 0, source: "asumsi model"}
edges:
  - {id: ab, from: A, to: B, weight: 1, road: "Jl. AB"}
  - {id: bc, from: B, to: C, weight: 1, road: "Jl. BC"}
simulation:
  title: "kasus alternatif"
  start: A
  goal: C
  blocked_edges: []
  alternatives:
    - id: lewat_b
      label: "Lewat B"
      purpose: "contoh"
      waypoints: [B]
"""


def test_loader_accepts_alternatives_block(tmp_path):
    graph, scenario = load_scenario(_write(tmp_path, BASE))
    assert scenario["alternatives"][0]["id"] == "lewat_b"
    assert scenario["alternatives"][0]["waypoints"] == ["B"]
    assert graph.has_node("B")


def test_loader_rejects_unknown_waypoint(tmp_path):
    text = BASE.replace("waypoints: [B]", "waypoints: [Z]")
    with pytest.raises(ValueError, match="Waypoint"):
        load_scenario(_write(tmp_path, text))


def test_loader_rejects_duplicate_alternative_id(tmp_path):
    text = BASE.replace(
        "      waypoints: [B]\n",
        "      waypoints: [B]\n"
        "    - id: lewat_b\n"
        "      label: \"Duplikat\"\n"
        "      waypoints: []\n",
    )
    with pytest.raises(ValueError, match="duplikat"):
        load_scenario(_write(tmp_path, text))


def test_loader_rejects_alternative_without_label(tmp_path):
    text = BASE.replace('      label: "Lewat B"\n', "")
    with pytest.raises(ValueError, match="label"):
        load_scenario(_write(tmp_path, text))


# --------------------------------------------------------- simulasi --


def test_simulation_prints_every_alternative(capsys):
    assert run_simulation(DEFAULT_SCENARIO) == 0
    output = capsys.readouterr().out
    assert "07  RUTE ALTERNATIF (3 dari 3 unit damkar)" in output
    assert "07.1  Koridor selatan - kawalan polisi" in output
    assert "07.2  Via IGD rumah sakit - bantuan ambulance" in output
    assert "07.3  Kawalan Polda + akses Tirtoyoso XI" in output
    assert "Titik layanan (dilewati rute ini): rumah_sakit_kariadi" in output
    assert "Titik layanan (dilewati rute ini): polisi_polda_jateng" in output
    assert "simpang_tirtoyoso_xi" in output  # waypoint kedua pada rute07.3
    # Ringkasan memuat biaya tiap alternatif dan cakupan node.
    assert "Alternatif selatan_kawalan_polisi" in output
    assert "Alternatif bantuan_ambulance" in output
    assert "Alternatif kawalan_polda_akses_tirtoyoso" in output
    assert "Node unik dikunjungi    : 36/36 node" in output
    assert "Rute alternatif berhasil ditemukan" in output


def test_simulation_also_works_with_astar(capsys):
    assert run_simulation(DEFAULT_SCENARIO, algorithm="astar") == 0
    output = capsys.readouterr().out
    assert "07  RUTE ALTERNATIF (3 dari 3 unit damkar)" in output
    assert "36/36 node" in output
    assert "11.93" in output  # biaya alternatif tercepat tidak berubah
