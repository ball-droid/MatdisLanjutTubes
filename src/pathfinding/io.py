"""Pembaca YAML untuk skenario graf jalan.

Seluruh pemeriksaan struktur dilakukan di sini supaya data yang tidak valid
(ID duplikat, bobot negatif/tidak finite, node atau ruas yang tidak dikenal,
referensi skenario yang menggantung) ditolak saat pemuatan dengan pesan yang
menunjuk sumber masalahnya, bukan muncul sebagai hasil rute yang menyesatkan.
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Any
import yaml
from .graph import Graph

_MAP_FIELDS = {"lat", "lon", "osm_node"}


def load_scenario(path: str | Path) -> tuple[Graph, dict[str, Any]]:
    """Muat file YAML dengan skema nodes, edges, simulation.

    Mendukung juga skema referensi Matdis: metadata, nodes, edges, dan
    execution_plan. Keduanya dinormalisasi ke kontrak yang sama untuk C.
    """
    file_path = Path(path)
    try:
        with file_path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"File skenario tidak ditemukan: {file_path}") from exc
    except yaml.YAMLError as exc:
        raise ValueError(f"YAML tidak valid pada {file_path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("Isi YAML harus berupa object/dictionary.")
    if not isinstance(data.get("nodes"), list) or not isinstance(data.get("edges"), list):
        raise ValueError("YAML harus memiliki daftar 'nodes' dan 'edges'.")

    graph = Graph()
    _load_nodes(data["nodes"], graph)
    access_status = _load_edges(data["edges"], graph, reference_schema="execution_plan" in data)
    scenario = _load_scenario_block(data, graph)
    scenario["access_status"] = access_status
    scenario["coordinates"] = _collect_coordinates(data["nodes"])
    return graph, scenario


def _collect_coordinates(items: list[Any]) -> dict[str, tuple[float, float]]:
    """Koordinat node untuk heuristik A*; kosong bila skenario tanpa jejak peta.

    Graph sendiri hanya menyimpan id dan label, jadi lat/lon diekstrak di sini
    (validasi kelengkapan field peta sudah dilakukan ``_load_nodes``).
    """
    coordinates: dict[str, tuple[float, float]] = {}
    for item in items:
        if not isinstance(item, dict) or "id" not in item:
            continue
        if "lat" not in item or "lon" not in item:
            return {}
        try:
            coordinates[str(item["id"]).strip()] = (float(item["lat"]), float(item["lon"]))
        except (TypeError, ValueError):
            return {}
    return coordinates


def _load_nodes(items: list[Any], graph: Graph) -> None:
    map_fields_seen: set[str] = set()
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict) or "id" not in item:
            raise ValueError(f"Setiap node harus memiliki field 'id' (node ke-{index}).")
        node_id = str(item["id"]).strip()
        if not node_id:
            raise ValueError(f"ID node tidak boleh kosong (node ke-{index}).")
        label = item.get("label", item["id"])
        if not isinstance(label, (str, int, float)):
            raise ValueError(f"Label node {node_id!r} harus teks.")
        # add_node menolak ID duplikat dengan pesannya sendiri.
        graph.add_node(node_id, str(label))
        map_fields_seen |= _MAP_FIELDS.intersection(item)

    missing_map_fields = _MAP_FIELDS - map_fields_seen
    if map_fields_seen and missing_map_fields:
        raise ValueError(
            "Field peta tidak lengkap: "
            + ", ".join(sorted(missing_map_fields))
            + " harus ada di semua node bila salah satunya dipakai."
        )


def _load_edges(
    items: list[Any], graph: Graph, reference_schema: bool
) -> dict[str, str]:
    """Muat seluruh edge; kembalikan pemetaan ID ruas ke status aksesnya."""
    access_status: dict[str, str] = {}
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"Setiap edge harus berupa object/dictionary (edge ke-{index}).")
        missing = {"from", "to", "weight"}.difference(item)
        if missing:
            raise ValueError(
                f"Field edge belum lengkap: {', '.join(sorted(missing))} (edge ke-{index})."
            )
        edge_id = str(item.get("id", f"e{index:02d}"))
        _validate_edge_fields(item, edge_id, index)
        if "access_status" in item:
            access_status[edge_id] = str(item["access_status"]).strip()

        # Skema referensi memiliki edge searah secara default (NetworkX DiGraph).
        # Skema proyek C memakai dua arah secara default kecuali directed: true.
        directed = item.get("directed", reference_schema)
        graph.add_edge(
            source=str(item["from"]), target=str(item["to"]),
            weight=float(item["weight"]), edge_id=edge_id,
            road_name=str(item.get("road", "")), directed=directed,
        )
    return access_status


def _validate_edge_fields(item: dict[str, Any], edge_id: str, index: int) -> None:
    weight = item["weight"]
    if isinstance(weight, bool) or not isinstance(weight, (int, float)):
        raise ValueError(f"Bobot edge {edge_id!r} harus angka, diterima: {weight!r}.")
    if not math.isfinite(float(weight)) or float(weight) < 0:
        raise ValueError(
            f"Bobot edge {edge_id!r} harus finite dan non-negatif, diterima: {weight!r}."
        )
    if "directed" in item and not isinstance(item["directed"], bool):
        raise ValueError(
            f"Field 'directed' edge {edge_id!r} harus boolean, diterima: {item['directed']!r}."
        )
    if "access_status" in item:
        status = item["access_status"]
        if not isinstance(status, str) or not status.strip():
            raise ValueError(
                f"Field 'access_status' edge {edge_id!r} harus teks tidak kosong."
            )
    if not isinstance(item["from"], (str, int)) or not isinstance(item["to"], (str, int)):
        raise ValueError(f"Node asal/tujuan edge {edge_id!r} harus berupa ID node.")


def _load_scenario_block(data: dict[str, Any], graph: Graph) -> dict[str, Any]:
    raw = data.get("simulation")
    if raw is not None and not isinstance(raw, dict):
        raise ValueError("Field 'simulation' harus berupa object/dictionary.")

    if isinstance(raw, dict):
        scenario = dict(raw)
        scenario.setdefault("events", [])
        scenario.setdefault("metadata", data.get("metadata", {}))
        scenario.setdefault("blocked_edges", [])
    else:
        plan = data.get("execution_plan")
        if plan is None:
            raise ValueError("YAML harus memiliki blok 'simulation' atau 'execution_plan'.")
        if not isinstance(plan, dict):
            raise ValueError("Field 'execution_plan' harus berupa object/dictionary.")
        # Dijkstra baseline hanya memerlukan kondisi awal. Event akan diuji
        # terpisah lewat fungsi reroute_after_closure, bukan D* Lite.
        scenario = {
            "title": data.get(
                "title", data.get("metadata", {}).get("title", "Tanpa judul")
            ),
            "start": str(plan.get("start_node", "")),
            "goal": str(plan.get("goal_node", "")),
            "blocked_edges": [],
            "events": plan.get("events", []),
            "metadata": data.get("metadata", {}),
        }

    _validate_scenario_references(scenario, graph)
    return scenario


def _validate_scenario_references(scenario: dict[str, Any], graph: Graph) -> None:
    """Pastikan titik awal/tujuan dan ruas acuan skenario benar-benar ada."""
    for key in ("start", "goal"):
        value = str(scenario.get(key, "") or "")
        if not value:
            raise ValueError(f"Skenario harus menetapkan {key}.")
        if not graph.has_node(value):
            raise ValueError(f"Node {key} tidak dikenal dalam graf: {value!r}.")

    closure = scenario.get("closure_edge")
    if closure:
        closure = str(closure)
        if closure not in graph.edge_ids:
            raise ValueError(f"closure_edge tidak dikenal dalam graf: {closure!r}.")

    blocked = scenario.get("blocked_edges") or []
    if not isinstance(blocked, list):
        raise ValueError("Field 'blocked_edges' harus berupa daftar.")
    for item in blocked:
        edge_id = str(item)
        if edge_id not in graph.edge_ids:
            raise ValueError(f"blocked_edges berisi ruas yang tidak dikenal: {edge_id!r}.")
