"""Validasi data skenario terhadap OpenStreetMap (Overpass API).

Dipakai sebagai bahan verifikasi dokumentasi studi kasus (bagian D prompt tugas):
  1. Memastikan osm_node pada YAML benar-benar ada dan koordinatnya cocok.
  2. Mengecek nama ruas yang dipakai edge terhadap nama jalan di OSM.
  3. Mengaudit arah jalan (oneway) pada segmen yang benar-benar dilalui tiap edge.

Hasil dicetak sebagai laporan; tidak mengubah file apa pun.
Pemakaian:  python tools/validasi_peta.py [path/ke/skenario.yaml]

Catatan: skenario demo (pasar_johar_demo.yaml) tidak punya lat/lon/osm_node,
jadi validasi node dan arah hanya dijalankan untuk skenario berbasis OSM.
"""
from __future__ import annotations

import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import yaml

OVERPASS = "https://overpass-api.de/api/interpreter"
UA = "matdis-tubes-validation/0.1"


def overpass(query: str, attempts: int = 4) -> dict:
    """Kirim query ke Overpass; ulangi bila server sibuk (429/5xx)."""
    last_error: Exception | None = None
    for attempt in range(attempts):
        req = urllib.request.Request(
            OVERPASS,
            data=urllib.parse.urlencode({"data": query}).encode(),
            headers={"User-Agent": UA},
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as handle:
                return json.load(handle)
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code in (429, 500, 502, 503, 504) and attempt < attempts - 1:
                time.sleep(8 * (attempt + 1))
                continue
            raise
    raise last_error if last_error else RuntimeError("Overpass gagal tanpa keterangan.")


def normalize_name(name: str) -> str:
    """Samakan gaya penulisan OSM ('Jalan Barito') dengan YAML ('Jl. Barito')."""
    lowered = name.lower()
    lowered = re.sub(r"^(jalan|jl\.?|jln\.?)\s+", "", lowered)
    lowered = re.sub(r"[.\-/,()]", " ", lowered)
    return re.sub(r"\s+", " ", lowered).strip()


def validate_nodes(nodes: list[dict]) -> list[str]:
    """Pastikan osm_node ada dan koordinatnya cocok dengan OSM."""
    ids = [str(node["osm_node"]) for node in nodes]
    query = "[out:json][timeout:60];node(id:" + ",".join(ids) + ");out body;"
    data = overpass(query)
    found = {str(el["id"]): el for el in data.get("elements", [])}
    problems: list[str] = []
    print(f"NODE: {len(found)}/{len(ids)} ditemukan di OSM")
    for node in nodes:
        element = found.get(str(node["osm_node"]))
        if element is None:
            problems.append(f"{node['id']}: osm_node {node['osm_node']} tidak ada di OSM")
            continue
        if (
            abs(element["lat"] - node["lat"]) > 1e-6
            or abs(element["lon"] - node["lon"]) > 1e-6
        ):
            problems.append(
                f"{node['id']}: koordinat berbeda yaml=({node['lat']},{node['lon']}) "
                f"osm=({element['lat']},{element['lon']})"
            )
    return problems


def check_roads(edges: list[dict], ways: list[dict]) -> None:
    """Cocokkan nama ruas pada edge dengan nama jalan yang ada di OSM."""
    index: dict[str, list[dict]] = {}
    for way in ways:
        tags = way.get("tags", {})
        if "name" in tags:
            index.setdefault(normalize_name(tags["name"]), []).append(tags)

    roads = sorted({edge["road"] for edge in edges})
    print(f"\nCEK NAMA RUAS ({len(ways)} way bernama dipakai sebagai acuan)")
    unmatched: list[str] = []
    oneway_roads: list[str] = []
    for road in roads:
        hits: list[dict] = []
        for part in (piece.strip() for piece in road.split(" - ")):
            hits.extend(index.get(normalize_name(part), []))
        if not hits:
            unmatched.append(road)
            print(f"  [!] {road}: nama tidak ditemukan persis di bbox")
            continue
        oneways = sorted({tags.get("oneway", "no") for tags in hits})
        highways = sorted({tags.get("highway", "?") for tags in hits})
        flag = "" if oneways == ["no"] else "  <-- ADA ATURAN ARAH"
        if oneways != ["no"]:
            oneway_roads.append(f"{road}: oneway={oneways}")
        print(f"  {road}: oneway={oneways} highway={highways} (n={len(hits)}){flag}")

    print(f"\nRingkas nama: {len(roads) - len(unmatched)}/{len(roads)} nama ruas cocok dengan OSM.")
    if unmatched:
        print("Perlu verifikasi manual nama ruas:")
        for road in unmatched:
            print(f"  - {road}")
    if oneway_roads:
        print("Nama ruas dengan aturan arah di OSM:")
        for item in oneway_roads:
            print(f"  - {item}")


def _allows(policy: str, forward: bool) -> bool:
    """Apakah perjalanan pada arah tertentu diizinkan oleh tag oneway way itu."""
    policy = policy.lower()
    if policy in {"yes", "true", "1"}:
        return forward
    if policy in {"-1", "reverse"}:
        return not forward
    return True  # no / tanpa tag -> dianggap dua arah


def _path_hops(
    adjacency: dict[int, list[tuple[int, dict]]], source: int, target: int
) -> list[tuple[int, int, dict]] | None:
    """Cari jalur tanpa memperhatikan arah; kembalikan (asal, tujuan, way) tiap hop."""
    previous: dict[int, tuple[int, dict]] = {}
    seen = {source}
    queue = [source]
    while queue:
        current = queue.pop(0)
        if current == target:
            break
        for neighbor, way in adjacency.get(current, ()):
            if neighbor not in seen:
                seen.add(neighbor)
                previous[neighbor] = (current, way)
                queue.append(neighbor)
    if target != source and target not in previous:
        return None

    chain = [target]
    while chain[-1] != source:
        chain.append(previous[chain[-1]][0])
    chain.reverse()

    hops: list[tuple[int, int, dict]] = []
    for start, end in zip(chain, chain[1:]):
        hops.append((start, end, previous[end][1]))
    return hops


def audit_edge_directions(edges: list[dict], ways: list[dict]) -> list[str]:
    """Audit arah tiap edge berdasarkan segmen jalan yang benar-benar dilalui.

    Untuk tiap edge: cari jalur antara dua simpangnya pada subgraf jalan
    bernama, lalu cek apakah tiap way di jalur itu mengizinkan perjalanan
    searah edge (asal -> tujuan) maupun berlawanan.
    """
    print(f"\nAUDIT ARAH PER EDGE (segmen, dari {len(ways)} way bernama)")
    by_name: dict[str, list[dict]] = {}
    for way in ways:
        name = way.get("tags", {}).get("name")
        if name:
            by_name.setdefault(normalize_name(name), []).append(way)

    findings: list[str] = []
    for edge in edges:
        source = int(edge["_source_osm"])
        target = int(edge["_target_osm"])
        parts = [normalize_name(piece.strip()) for piece in edge["road"].split(" - ")]
        adjacency: dict[int, list[tuple[int, dict]]] = {}
        seen_ways: set[int] = set()
        for part in parts:
            for way in by_name.get(part, []):
                if way["id"] in seen_ways:
                    continue
                seen_ways.add(way["id"])
                nodes = way.get("nodes") or []
                for a, b in zip(nodes, nodes[1:]):
                    adjacency.setdefault(a, []).append((b, way))
                    adjacency.setdefault(b, []).append((a, way))
        if not adjacency:
            findings.append(f"{edge['id']} {edge['road']}: nama ruas tak cocok, audit dilewati")
            continue
        hops = _path_hops(adjacency, source, target)
        if hops is None:
            findings.append(
                f"{edge['id']} {edge['road']}: tidak terhubung lewat ruas bernama (cek manual)"
            )
            continue

        forward_ok = True
        backward_ok = True
        policies: set[str] = set()
        for start, end, way in hops:
            tags = way.get("tags", {})
            policy = str(tags.get("oneway", "no"))
            policies.add(policy)
            order = {node_id: i for i, node_id in enumerate(way.get("nodes") or [])}
            start_before_end = order.get(start, 0) < order.get(end, 0)
            if not _allows(policy, start_before_end):
                forward_ok = False
            if not _allows(policy, not start_before_end):
                backward_ok = False

        if forward_ok and backward_ok:
            status = "dua arah"
        elif forward_ok:
            status = "SEARAH asal->tujuan (sesuai orientasi edge)"
        elif backward_ok:
            status = "SEARAH tujuan->asal (berlawanan orientasi edge)"
        else:
            status = "campuran antar segmen (perlu cek manual)"
        line = (
            f"{edge['id']} {edge['road']}: {status} "
            f"[oneway di jalur: {', '.join(sorted(policies))}]"
        )
        findings.append(line)
        print("  " + line)

    flagged = [f for f in findings if "dua arah" not in f]
    print(
        f"\nRingkas audit arah: {len(findings) - len(flagged)}/{len(findings)} edge dua arah; "
        f"{len(flagged)} edge berada di ruas dengan aturan arah."
    )
    return findings


def main() -> int:
    path = Path(sys.argv[1] if len(sys.argv) > 1 else "data/pasar_johar_damkar.yaml")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    nodes, edges = data["nodes"], data["edges"]
    print(f"File: {path}  node={len(nodes)} edge={len(edges)}")

    if not all({"lat", "lon", "osm_node"} <= set(node) for node in nodes):
        print("Skenario tanpa lat/lon/osm_node: validasi peta hanya bisa untuk skenario OSM.")
        return 0

    node_osm = {node["id"]: int(node["osm_node"]) for node in nodes}
    for edge in edges:
        edge["_source_osm"] = node_osm[edge["from"]]
        edge["_target_osm"] = node_osm[edge["to"]]
    lats = [node["lat"] for node in nodes]
    lons = [node["lon"] for node in nodes]
    pad = 0.01
    bbox = f"{min(lats) - pad},{min(lons) - pad},{max(lats) + pad},{max(lons) + pad}"
    print(f"bbox: {bbox}\n")

    problems = validate_nodes(nodes)
    for line in problems:
        print("  MASALAH:", line)
    if not problems:
        print("  Semua osm_node & koordinat cocok dengan OSM.")

    try:
        ways = overpass(
            f'[out:json][timeout:120];way["highway"]["name"]({bbox});out body;'
        ).get("elements", [])
        check_roads(edges, ways)
        audit_edge_directions(edges, ways)
    except urllib.error.HTTPError as exc:
        print("Overpass HTTP", exc.code, "saat cek ruas:", exc.read()[:300])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
