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

    entries = scenario["node_facilities"]
    hydrant_nodes = [
        node_id for node_id, fields in entries.items() if "hydrant" in fields
    ]
    police_nodes = [
        node_id for node_id, fields in entries.items()
        if (fields.get("facility") or {}).get("type") == "police_station"
    ]
    fire_stations = [
        node_id for node_id, fields in entries.items()
        if (fields.get("facility") or {}).get("type") == "fire_station"
    ]

    assert len(graph.nodes) == 36
    assert sorted(police_nodes) == ["polisi_polda_jateng", "simpang_cipto_bugangan"]
    for node_id in police_nodes:
        assert "hydrant" not in entries[node_id]
    assert sorted(fire_stations) == [
        "pos_damkar_tambahan_barat",
        "pos_damkar_tambahan_utara",
        "pos_damkar_tambahan_walisongo",
    ]
    hospitals = [
        node_id for node_id, fields in entries.items()
        if (fields.get("facility") or {}).get("type") == "hospital"
    ]
    assert hospitals == ["rumah_sakit_kariadi"]
    assert entries["rumah_sakit_kariadi"]["facility"]["ambulances"] == 3
    assert entries["rumah_sakit_kariadi"]["facility"]["emergency"] is True
    # 36 node - 2 kantor polisi = 34 node ber-hydrant.
    assert len(hydrant_nodes) == 34

    verified = entries["simpang_depok_wahidhasyim"]["hydrant"]
    assert verified["verified"] is True
    assert verified["osm_node"] == 5466104936
    assert verified["name"] == "Hydrant BCA"


def test_simulation_prints_water_and_facility_section(capsys):
    from pathfinding.simulation import run_simulation

    assert run_simulation(DEFAULT_SCENARIO) == 0
    output = capsys.readouterr().out
    assert "04B  SUMBER AIR DAN FASILITAS" in output
    assert "Hydrant BCA" in output
    assert "Polsek Semarang Timur" in output
    assert "pos_damkar_tambahan_walisongo - 3 mobil, 10 personel" in output
    # Rute awal (utara) melewati node ber-hydrant, termasuk hydrant nyata.
    assert "Sumber air di rute" in output
    assert "node rute ber-hydrant (isi air di node tersebut)" in output
    assert "Hydrant BCA @ simpang_depok_wahidhasyim" in output


def test_simulation_alternative_route_notes_police_node_without_water(capsys):
    """Rute alternatif (selatan) melewati node kantor polisi: tanpa hydrant."""
    from pathfinding.simulation import run_simulation

    assert run_simulation(DEFAULT_SCENARIO) == 0
    output = capsys.readouterr().out
    assert "melewati kantor polisi tanpa hydrant: simpang_cipto_bugangan" in output


def test_demo_scenario_has_no_facility_section(capsys):
    from pathfinding.simulation import run_simulation

    assert run_simulation(DEMO_SCENARIO) == 0
    output = capsys.readouterr().out
    assert "SUMBER AIR DAN FASILITAS" not in output
    assert "Sumber air di rute" not in output


def test_demo_scenario_has_no_facility_requirement():
    graph, scenario = load_scenario(DEMO_SCENARIO)
    assert "facilities" not in scenario["metadata"]
    assert len(graph.nodes) == 10
