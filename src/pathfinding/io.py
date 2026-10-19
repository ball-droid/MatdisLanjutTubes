"""Pembaca YAML untuk skenario graf jalan."""
from __future__ import annotations
from pathlib import Path
from typing import Any
import yaml
from .graph import Graph


def load_scenario(path: str | Path) -> tuple[Graph, dict[str, Any]]:
    """Muat file YAML dengan skema nodes, edges, simulation.

    Mendukung juga skema referensi Matdis: metadata, nodes, edges, dan
    execution_plan. Keduanya dinormalisasi ke kontrak yang sama untuk C.
    """
    file_path = Path(path)
    with file_path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError("Isi YAML harus berupa object/dictionary.")
    if not isinstance(data.get("nodes"), list) or not isinstance(data.get("edges"), list):
        raise ValueError("YAML harus memiliki daftar 'nodes' dan 'edges'.")

    graph = Graph()
    for item in data["nodes"]:
        if not isinstance(item, dict) or "id" not in item:
            raise ValueError("Setiap node harus memiliki field 'id'.")
        graph.add_node(str(item["id"]), str(item.get("label", item["id"])))

    for index, item in enumerate(data["edges"], start=1):
        if not isinstance(item, dict):
            raise ValueError("Setiap edge harus berupa object/dictionary.")
        missing = {"from", "to", "weight"}.difference(item)
        if missing:
            raise ValueError(f"Field edge belum lengkap: {', '.join(sorted(missing))}.")
        edge_id = str(item.get("id", f"e{index:02d}"))
        # Skema referensi memiliki edge searah secara default (NetworkX DiGraph).
        # Skema proyek C memakai dua arah secara default kecuali directed: true.
        reference_schema = "execution_plan" in data
        directed = bool(item.get("directed", reference_schema))
        graph.add_edge(
            source=str(item["from"]), target=str(item["to"]),
            weight=float(item["weight"]), edge_id=edge_id,
            road_name=str(item.get("road", "")), directed=directed,
        )

    scenario = data.get("simulation")
    if not isinstance(scenario, dict):
        plan = data.get("execution_plan", {})
        if not isinstance(plan, dict):
            raise ValueError("Field 'execution_plan' harus berupa object/dictionary.")
        events = plan.get("events", [])
        blocked_edges: list[str] = []
        # Dijkstra baseline hanya memerlukan kondisi awal. Event akan diuji
        # terpisah lewat fungsi reroute_after_closure, bukan D* Lite.
        scenario = {
            "title": data.get("title", data.get("metadata", {}).get("title", "Tanpa judul")),
            "start": str(plan.get("start_node", "")),
            "goal": str(plan.get("goal_node", "")),
            "blocked_edges": blocked_edges,
            "events": events,
            "metadata": data.get("metadata", {}),
        }
    else:
        scenario = dict(scenario)
        scenario.setdefault("events", [])
        scenario.setdefault("metadata", data.get("metadata", {}))
    return graph, scenario
