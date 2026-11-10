import pytest
from pathfinding.dijkstra import dijkstra, reroute_after_closure
from pathfinding.graph import Graph
from pathfinding.io import load_scenario
from pathfinding.simulation import DEFAULT_SCENARIO, DEMO_SCENARIO


def make_graph() -> Graph:
    graph = Graph()
    for node in ["A", "B", "C", "D"]:
        graph.add_node(node)
    graph.add_edge("A", "B", 1, "ab")
    graph.add_edge("B", "D", 5, "bd")
    graph.add_edge("A", "C", 2, "ac")
    graph.add_edge("C", "D", 1, "cd")
    return graph


def test_finds_shortest_weight_path():
    result = dijkstra(make_graph(), "A", "D")
    assert result is not None
    assert result.nodes == ["A", "C", "D"]
    assert result.cost == 3


def test_closed_edge_is_not_used():
    result = reroute_after_closure(make_graph(), "A", "D", {"cd"})
    assert result is not None
    assert result.nodes == ["A", "B", "D"]
    assert result.cost == 6


def test_returns_none_when_no_route():
    graph = Graph()
    graph.add_node("A")
    graph.add_node("B")
    assert dijkstra(graph, "A", "B") is None


def test_start_equals_goal():
    result = dijkstra(make_graph(), "A", "A")
    assert result is not None
    assert result.nodes == ["A"]
    assert result.cost == 0


def test_unknown_node_raises_key_error():
    with pytest.raises(KeyError):
        dijkstra(make_graph(), "X", "D")


def test_negative_weight_is_rejected():
    graph = Graph()
    graph.add_node("A")
    graph.add_node("B")
    with pytest.raises(ValueError):
        graph.add_edge("A", "B", -1, "negative")


def test_pasar_johar_main_route_matches_map_time_estimate():
    graph, scenario = load_scenario(DEMO_SCENARIO)
    result = dijkstra(graph, scenario["start"], scenario["goal"])
    assert result is not None
    assert result.nodes == [
        "pos_damkar_barito",
        "koridor_keluar_barito",
        "simpang_rute_utama",
        "simpang_pendekat_pasar",
        "akses_utara_terhambat",
        "akses_selatan_pasar",
        "titik_kebakaran_blok_f",
    ]
    # Bobot dibagi secara simulatif agar jumlahnya sejalan dengan label 9 menit pada screenshot.
    assert result.cost == pytest.approx(9.0)


def test_pasar_johar_reroutes_around_annotated_blockage():
    graph, scenario = load_scenario(DEMO_SCENARIO)
    result = reroute_after_closure(
        graph, scenario["start"], scenario["goal"], {scenario["closure_edge"]}
    )
    assert result is not None
    assert result.nodes == [
        "pos_damkar_barito",
        "koridor_keluar_barito",
        "simpang_rute_utama",
        "simpang_pendekat_pasar",
        "jalan_lingkungan_barat_utara",
        "jalan_lingkungan_barat_tengah",
        "jalan_lingkungan_barat_selatan",
        "titik_kebakaran_blok_f",
    ]
    # Waktu alternatif 10 menit adalah estimasi dari anotasi peta, bukan hasil ukur per ruas.
    assert result.cost == pytest.approx(10.0)


def test_demo_yaml_has_ten_edges_and_ten_nodes():
    graph, _ = load_scenario(DEMO_SCENARIO)
    assert len(graph.nodes) == 10
    edge_ids = {edge.edge_id for node_id in graph.nodes for edge in graph.neighbors(node_id)}
    assert edge_ids == {f"e{i:02d}" for i in range(1, 11)}


def test_reference_style_execution_plan_yaml_is_supported(tmp_path):
    path = tmp_path / "reference_case.yaml"
    path.write_text(
        """case_id: ref_case
title: Contoh referensi
nodes:
  - {id: 0, label: Start}
  - {id: 1, label: Goal}
edges:
  - {from: 0, to: 1, weight: 2}
execution_plan:
  start_node: 0
  goal_node: 1
  events: []
""",
        encoding="utf-8",
    )
    graph, scenario = load_scenario(path)
    result = dijkstra(graph, scenario["start"], scenario["goal"])
    assert result is not None
    assert result.nodes == ["0", "1"]
    assert result.cost == 2
    assert len(list(graph.neighbors("1"))) == 0  # directed, seperti DiGraph referensi


# --- Skenario damkar berbasis jaringan jalan asli (OpenStreetMap) ---


def _street_sequence(graph, nodes):
    """Urutan nama jalan yang dilalui rute tersebut."""
    streets = []
    for source, target in zip(nodes, nodes[1:]):
        edge = next(e for e in graph.neighbors(source) if e.target == target)
        if edge.road_name and edge.road_name not in streets:
            streets.append(edge.road_name)
    return streets


def test_damkar_scenario_uses_default_and_has_around_thirty_nodes():
    graph, scenario = load_scenario(DEFAULT_SCENARIO)
    assert DEFAULT_SCENARIO.name == "pasar_johar_damkar.yaml"
    assert len(graph.nodes) == 31
    edge_ids = {edge.edge_id for node_id in graph.nodes for edge in graph.neighbors(node_id)}
    assert len(edge_ids) == 33
    assert scenario["start"] == "pos_damkar_madukoro"
    assert scenario["goal"] == "pasar_johar_relokasi"


def test_damkar_every_edge_has_real_street_name_and_positive_weight():
    graph, _ = load_scenario(DEFAULT_SCENARIO)
    seen = set()
    for node_id in graph.nodes:
        for edge in graph.neighbors(node_id):
            if edge.edge_id in seen:
                continue
            seen.add(edge.edge_id)
            assert edge.road_name.startswith("Jl. "), edge.edge_id
            assert edge.weight > 0
    assert len(seen) == 33


def test_damkar_initial_route_follows_northern_corridor():
    graph, scenario = load_scenario(DEFAULT_SCENARIO)
    result = dijkstra(graph, scenario["start"], scenario["goal"])
    assert result is not None
    assert result.nodes[0] == "pos_damkar_madukoro"
    assert result.nodes[-1] == "pasar_johar_relokasi"
    assert result.cost == pytest.approx(10.74, abs=0.05)
    streets = _street_sequence(graph, result.nodes)
    # Damkar keluar lewat Jl. Madukoro, lalu arteri utara: Sudirman - Pandanaran -
    # Pekunden - Panjaitan - Kartini - Barito.
    assert "Jl. Pandanaran" in streets
    assert "Jl. Mayjend. D.I. Panjaitan" in streets
    assert streets[-1] == "Jl. Barito"


def test_damkar_reroutes_to_southern_corridor_when_barito_access_blocked():
    graph, scenario = load_scenario(DEFAULT_SCENARIO)
    result = reroute_after_closure(
        graph, scenario["start"], scenario["goal"], {scenario["closure_edge"]}
    )
    assert result is not None
    assert result.cost == pytest.approx(11.93, abs=0.05)
    assert result.cost > 10.74  # memutar lebih jauh
    streets = _street_sequence(graph, result.nodes)
    # Akses Jl. Barito terputus -> damkar memutar lewat koridor selatan.
    assert "Jl. Barito" not in streets
    for expected in ("Jl. Indraprasta", "Jl. Kapten Piere Tendean", "Jl. Petudungan",
                     "Jl. Bugangan", "Jl. Tirtoyoso V"):
        assert expected in streets, expected
    # Jumlah simpang yang dilewati lebih banyak dari rute awal.
    assert len(result.nodes) == 18


def test_damkar_simulation_runs_and_prints_damkar_route(capsys):
    from pathfinding.simulation import run_simulation

    assert run_simulation(DEFAULT_SCENARIO) == 0
    output = capsys.readouterr().out
    assert "JALUR DAMKAR" in output
    assert "Jl. Pandanaran" in output
    assert "Rute alternatif berhasil ditemukan" in output
