"""Pengujian validasi fasilitas node: hydrant, kantor polisi, kantor damkar.

Aturan model yang dijaga loader:
- bila metadata ``facilities: true``: setiap node wajib hydrant KECUALI node
  kantor polisi; node kantor polisi justru dilarang punya hydrant;
- hydrant terverifikasi peta wajib menyebut ``osm_node``;
- hydrant asumsi model wajib menyebut ``source`` (agar tidak terbaca fakta);
- kantor damkar wajib memuat ``trucks``/``personnel`` bulat >= 0;
- tanpa bendera ``facilities``, aturan tidak dipaksakan (skenario lama aman).
"""
import pytest

from pathfinding.io import load_scenario
from pathfinding.simulation import DEFAULT_SCENARIO, DEMO_SCENARIO

HYDRANT_A = """    hydrant:
      verified: false
      distance_m: 0
      source: "asumsi model"
"""

BASE = f"""metadata:
  facilities: true
nodes:
  - id: A
    label: "A"
{HYDRANT_A}  - id: B
    label: "B"
{HYDRANT_A}  - id: C
    label: "C"
    facility:
      type: police_station
      verified: true
      name: "Polsek Contoh"
edges:
  - id: ab
    from: A
    to: B
    weight: 1
    road: "Jl. AB"
  - id: bc
    from: B
    to: C
    weight: 1
    road: "Jl. BC"
simulation:
  title: "kasus fasilitas"
  start: A
  goal: B
  blocked_edges: []
"""


def _write(tmp_path, text):
    path = tmp_path / "fasilitas.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def test_base_facility_scenario_loads(tmp_path):
    graph, scenario = load_scenario(_write(tmp_path, BASE))
    assert scenario["metadata"]["facilities"] is True
    assert len(graph.nodes) == 3


def test_node_without_hydrant_rejected_when_facilities_enabled(tmp_path):
    text = BASE.replace(HYDRANT_A, "", 1)  # buang hydrant node A
    with pytest.raises(ValueError, match="wajib memiliki hydrant"):
        load_scenario(_write(tmp_path, text))


def test_police_node_must_not_have_hydrant(tmp_path):
    text = BASE.replace(
        """    facility:
      type: police_station
      verified: true
      name: "Polsek Contoh"
""",
        """    facility:
      type: police_station
      verified: true
      name: "Polsek Contoh"
""" + HYDRANT_A,
        1,
    )
    with pytest.raises(ValueError, match="kantor polisi"):
        load_scenario(_write(tmp_path, text))


def test_police_node_without_hydrant_is_allowed(tmp_path):
    graph, scenario = load_scenario(_write(tmp_path, BASE))
    assert scenario["metadata"]["facilities"] is True
    assert graph.has_node("C")


def test_verified_hydrant_requires_osm_node(tmp_path):
    text = BASE.replace(
        HYDRANT_A,
        """    hydrant:
      verified: true
      distance_m: 120
""",
        1,
    )
    with pytest.raises(ValueError, match="osm_node"):
        load_scenario(_write(tmp_path, text))


def test_model_hydrant_requires_source(tmp_path):
    text = BASE.replace('      source: "asumsi model"\n', "", 1)
    with pytest.raises(ValueError, match="source"):
        load_scenario(_write(tmp_path, text))


def test_hydrant_distance_must_be_non_negative(tmp_path):
    text = BASE.replace("      distance_m: 0\n", "      distance_m: -5\n", 1)
    with pytest.raises(ValueError, match="distance_m"):
        load_scenario(_write(tmp_path, text))


def test_unknown_facility_type_rejected(tmp_path):
    text = BASE.replace("type: police_station", "type: warehouse", 1)
    with pytest.raises(ValueError, match="facility.type"):
        load_scenario(_write(tmp_path, text))


def test_fire_station_requires_trucks_and_personnel(tmp_path):
    without_personnel = BASE.replace(
        """    facility:
      type: police_station
      verified: true
      name: "Polsek Contoh"
""",
        """    facility:
      type: fire_station
      verified: true
      trucks: 2
""",
        1,
    )
    with pytest.raises(ValueError, match="personnel"):
        load_scenario(_write(tmp_path, without_personnel))

    negative = BASE.replace(
        """    facility:
      type: police_station
      verified: true
      name: "Polsek Contoh"
""",
        """    facility:
      type: fire_station
      verified: true
      trucks: -1
      personnel: 8
""",
        1,
    )
    with pytest.raises(ValueError, match="trucks"):
        load_scenario(_write(tmp_path, negative))


def test_police_facility_requires_name(tmp_path):
    text = BASE.replace('      name: "Polsek Contoh"\n', "", 1)
    with pytest.raises(ValueError, match="name"):
        load_scenario(_write(tmp_path, text))


def test_facilities_flag_must_be_boolean(tmp_path):
    text = BASE.replace("  facilities: true", "  facilities: \"ya\"")
    with pytest.raises(ValueError, match="boolean"):
        load_scenario(_write(tmp_path, text))


def test_facility_rules_not_enforced_without_flag(tmp_path):
    """Skenario tanpa bendera facilities (mis. demo lama) tidak dipaksa."""
    text = BASE.replace("  facilities: true\n", "").replace(HYDRANT_A, "", 2)
    graph, scenario = load_scenario(_write(tmp_path, text))
    assert "facilities" not in scenario["metadata"]
    assert len(graph.nodes) == 3


def test_default_scenario_facility_inventory():
    """Isi fasilitas skenario damkar sesuai hasil pemeriksaan peta."""
    graph, scenario = load_scenario(DEFAULT_SCENARIO)
    assert scenario["metadata"]["facilities"] is True

    hydrant_nodes = []
    police_nodes = []
    fire_stations = []
    for node_id in graph.nodes:
        item = next(
            n for n in _raw_nodes(DEFAULT_SCENARIO) if str(n["id"]) == node_id
        )
        facility = item.get("facility") or {}
        if facility.get("type") == "police_station":
            police_nodes.append(node_id)
            assert "hydrant" not in item, "node kantor polisi tidak boleh ber-hydrant"
        elif facility.get("type") == "fire_station":
            fire_stations.append(node_id)
            assert item.get("hydrant") is not None
        elif "hydrant" in item:
            hydrant_nodes.append(node_id)

    assert police_nodes == ["simpang_cipto_bugangan"]
    assert sorted(fire_stations) == [
        "pos_damkar_tambahan_barat",
        "pos_damkar_tambahan_utara",
        "pos_damkar_tambahan_walisongo",
    ]
    # 34 node - 1 kantor polisi = 33 node ber-hydrant.
    assert len(hydrant_nodes) + len(fire_stations) == 33

    verified = next(
        n for n in _raw_nodes(DEFAULT_SCENARIO) if str(n["id"]) == "simpang_depok_wahidhasyim"
    )["hydrant"]
    assert verified["verified"] is True
    assert verified["osm_node"] == 5466104936
    assert verified["name"] == "Hydrant BCA"


def _raw_nodes(path):
    import yaml

    return yaml.safe_load(open(path, encoding="utf-8"))["nodes"]


def test_demo_scenario_has_no_facility_requirement():
    graph, scenario = load_scenario(DEMO_SCENARIO)
    assert "facilities" not in scenario["metadata"]
    assert len(graph.nodes) == 10
