"""Validasi fasilitas skenario terhadap OpenStreetMap (Overpass + Nominatim + OSRM).

Menjawab tiga pertanyaan yang dipakai pengembangan fasilitas node:

  1. Node mana yang berada di kantor polisi? (radius POLICE_RADIUS_M)
     -> node tersebut TIDAK diberi hydrant.
  2. Node mana yang dekat hydrant sungguhan di OSM? (radius HYDRANT_RADIUS_M)
     -> hydrant terverifikasi; sisanya hydrant asumsi model.
  3. Kantor pemadam tambahan mana di sekitar skenario yang layak dijadikan
     node logistik? (radius STATION_RADIUS_KM dari node jaringan terdekat)
     -> untuk tiap kantor dicari jalan terdekat (Nominatim) dan jarak rute
     jalan ke node jaringan (OSRM), dengan fallback jarak lurus bila OSRM
     tidak menjawab.

Hasil dicetak sebagai laporan; `--emit` menambahkan cuplikan YAML node/edge
yang bisa ditempel ke file skenario. Tidak ada file yang diubah otomatis.

Pemakaian:
  python tools/validasi_fasilitas.py [path/ke/skenario.yaml] [--emit]

Catatan: skenario tanpa lat/lon (mis. demo) dilewati dengan pesan, karena
pemeriksaan ini murni berbasis koordinat.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import yaml

OVERPASS = "https://overpass-api.de/api/interpreter"
NOMINATIM = "https://nominatim.openstreetmap.org/reverse"
OSRM = "https://router.project-osrm.org/route/v1/driving"
UA = "matdis-tubes-fasilitas/0.1"

POLICE_RADIUS_M = 100.0     # node dianggap "berada di kantor polisi" bila lebih dekat dari ini
HYDRANT_RADIUS_M = 300.0    # hydrant OSM dianggap melayani node bila lebih dekat dari ini
STATION_RADIUS_KM = 5.0     # kantor damkar kandidat node logistik
EARTH_RADIUS_M = 6_371_000.0
MODEL_ACCESS_SPEED_KMH = 20.0  # kecepatan model permukiman untuk koneksi kantor -> jaringan


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


def fetch_json(url: str, attempts: int = 3) -> dict:
    """GET JSON dengan beberapa percobaan (Nominatim/OSRM kadang sibuk)."""
    last_error: Exception | None = None
    for attempt in range(attempts):
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=60) as handle:
                return json.load(handle)
        except Exception as exc:  # noqa: BLE001 - semua kegagalan jaringan diperlakukan sama
            last_error = exc
            if attempt < attempts - 1:
                time.sleep(3 * (attempt + 1))
                continue
    raise last_error if last_error else RuntimeError("Permintaan gagal tanpa keterangan.")


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def _points(elements: list[dict]) -> list[tuple[str, int, float, float, dict]]:
    """Normalisasi elemen OSM (node/way) menjadi (type, id, lat, lon, tags)."""
    out = []
    for element in elements:
        center = element.get("center") or {}
        lat = element.get("lat", center.get("lat"))
        lon = element.get("lon", center.get("lon"))
        if lat is None or lon is None:
            continue
        out.append((element["type"], element["id"], float(lat), float(lon), element.get("tags", {})))
    return out


def load_nodes(path: Path) -> list[dict]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("nodes"), list):
        raise ValueError("YAML harus memiliki daftar 'nodes'.")
    for node in data["nodes"]:
        if not {"lat", "lon"} <= set(node):
            raise ValueError(
                f"Skenario tanpa lat/lon pada node {node.get('id')!r}: "
                "validasi fasilitas hanya bisa untuk skenario berbasis peta."
            )
    return data["nodes"]


def fetch_facilities(nodes: list[dict]) -> tuple[list, list, list]:
    """Ambil hydrant, kantor polisi, dan kantor damkar dari OSM."""
    lats = [node["lat"] for node in nodes]
    lons = [node["lon"] for node in nodes]
    pad = 0.012
    bbox = f"{min(lats) - pad},{min(lons) - pad},{max(lats) + pad},{max(lons) + pad}"
    wide_pad = 0.05
    wide = f"{min(lats) - wide_pad},{min(lons) - wide_pad},{max(lats) + wide_pad},{max(lons) + wide_pad}"

    hydrants = _points(
        overpass(
            f'[out:json][timeout:90];(node["emergency"="fire_hydrant"]({bbox});'
            f'way["emergency"="fire_hydrant"]({bbox}););out tags center;'
        )["elements"]
    )
    police = _points(
        overpass(
            f'[out:json][timeout:90];(node["amenity"="police"]({bbox});'
            f'way["amenity"="police"]({bbox}););out tags center;'
        )["elements"]
    )
    stations = _points(
        overpass(
            f'[out:json][timeout:90];(node["amenity"="fire_station"]({wide});'
            f'way["amenity"="fire_station"]({wide}););out tags center;'
        )["elements"]
    )
    return hydrants, police, stations


def nearest(target: tuple[float, float], candidates: list) -> tuple[float, tuple] | None:
    if not candidates:
        return None
    lat, lon = target
    best = min(candidates, key=lambda c: haversine_m(lat, lon, c[2], c[3]))
    return haversine_m(lat, lon, best[2], best[3]), best


def nearest_street_name(lat: float, lon: float) -> str | None:
    """Nama jalan terdekat lewat Nominatim reverse (1 permintaan per titik)."""
    url = NOMINATIM + "?" + urllib.parse.urlencode(
        {"lat": lat, "lon": lon, "format": "json", "zoom": 17, "accept-language": "id"}
    )
    try:
        address = fetch_json(url).get("address", {})
    except Exception:  # noqa: BLE001 - nama jalan bersifat pelengkap
        return None
    for key in ("road", "pedestrian", "footway", "neighbourhood"):
        if address.get(key):
            return str(address[key])
    return None


def osrm_road_distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float | None:
    """Jarak rute mengemudi (meter) via OSRM; None bila layanan tidak menjawab."""
    url = f"{OSRM}/{lon1},{lat1};{lon2},{lat2}?overview=false"
    try:
        routes = fetch_json(url).get("routes") or []
    except Exception:  # noqa: BLE001 - fallback ke jarak lurus
        return None
    return float(routes[0]["distance"]) if routes else None


def classify(nodes: list[dict], hydrants: list, police: list) -> dict[str, dict]:
    """Kelaskan tiap node: kantor polisi, hydrant terverifikasi, atau model."""
    result: dict[str, dict] = {}
    for node in nodes:
        target = (node["lat"], node["lon"])
        info: dict = {}
        police_hit = nearest(target, police)
        hydrant_hit = nearest(target, hydrants)
        if police_hit and police_hit[0] <= POLICE_RADIUS_M:
            hit, dist = police_hit[1], police_hit[0]
            info["kind"] = "police_station"
            info["osm"] = f"{hit[0]}/{hit[1]}"
            info["distance_m"] = round(dist)
            info["name"] = hit[4].get("name", "")
        elif hydrant_hit and hydrant_hit[0] <= HYDRANT_RADIUS_M:
            hit, dist = hydrant_hit[1], hydrant_hit[0]
            info["kind"] = "hydrant_verified"
            info["osm"] = f"{hit[0]}/{hit[1]}"
            info["distance_m"] = round(dist)
            info["name"] = hit[4].get("name", "")
            info["type"] = hit[4].get("fire_hydrant:type", "")
            info["operator"] = hit[4].get("operator", "")
        else:
            info["kind"] = "hydrant_model"
            info["distance_m"] = 0
            info["nearest_osm_m"] = round(hydrant_hit[0]) if hydrant_hit else None
            info["nearest_osm"] = (
                f"{hydrant_hit[1][0]}/{hydrant_hit[1][1]}" if hydrant_hit else None
            )
        result[str(node["id"])] = info
    return result


def candidate_stations(nodes: list[dict], stations: list) -> list[dict]:
    """Kantor damkar di luar skenario yang cukup dekat untuk jadi node logistik."""
    used = []
    out = []
    for kind, ident, lat, lon, tags in stations:
        hit = nearest(
            (lat, lon),
            [("node", str(n["id"]), float(n["lat"]), float(n["lon"]), {"label": n.get("label", "")})
             for n in nodes],
        )
        if hit is None:
            continue
        dist, node = hit
        label = tags.get("name", "")
        # Kantor yang menempel pada node titik awal (Dinas Pemadam) bukan kandidat.
        if label.startswith("Dinas Pemadam Kebakaran Kota Semarang"):
            continue
        if dist > STATION_RADIUS_KM * 1000:
            continue
        road = nearest_street_name(lat, lon)
        road_dist = osrm_road_distance_m(lat, lon, node[2], node[3])
        used.append(
            {
                "osm": f"{kind}/{ident}",
                "name": label or "(tanpa nama di OSM)",
                "lat": lat,
                "lon": lon,
                "street": road,
                "nearest_node": str(node[1]),
                "straight_m": round(dist),
                "road_m": None if road_dist is None else round(road_dist),
                "capacity": tags.get("capacity:persons", ""),
                "addr": tags.get("addr:full", ""),
            }
        )
        time.sleep(1)  # sopan terhadap Nominatim: maksimal 1 permintaan/detik
    return sorted(used, key=lambda item: item["straight_m"])


def print_report(path: Path, nodes: list[dict], classification: dict,
                 hydrants: list, police: list, stations: list, extras: list) -> None:
    print(f"File: {path}  node={len(nodes)}")
    print(f"OSM: hydrant={len(hydrants)} kantor polisi={len(police)} kantor damkar={len(stations)}")
    print(f"Radius: polisi<={POLICE_RADIUS_M:.0f} m, hydrant<={HYDRANT_RADIUS_M:.0f} m, "
          f"kantor damkar<={STATION_RADIUS_KM:g} km\n")

    verified = model = police_nodes = 0
    print("KLASIFIKASI PER NODE")
    for node in nodes:
        info = classification[str(node["id"])]
        if info["kind"] == "police_station":
            police_nodes += 1
            print(f"  {node['id']:<34} KANTOR POLISI  {info['name']} ({info['osm']}, "
                  f"{info['distance_m']} m) -> tanpa hydrant")
        elif info["kind"] == "hydrant_verified":
            verified += 1
            print(f"  {node['id']:<34} HYDRANT OSM    {info['name'] or '-'} ({info['osm']}, "
                  f"{info['distance_m']} m, type={info['type'] or '-'})")
        else:
            model += 1
            nearest_note = (
                f"OSM terdekat {info['nearest_osm_m']} m ({info['nearest_osm']})"
                if info["nearest_osm_m"] is not None
                else "OSM tidak punya hydrant di bbox"
            )
            print(f"  {node['id']:<34} HYDRANT MODEL  asumsi model di simpang; {nearest_note}")
    print(f"\nRingkas: {verified} hydrant terverifikasi OSM, {model} hydrant asumsi model, "
          f"{police_nodes} node kantor polisi (tanpa hydrant).")

    print("\nKANTOR DAMKAR KANDIDAT NODE LOGISTIK")
    if not extras:
        print("  (tidak ada kantor damkar lain dalam radius)")
    for item in extras:
        print(f"  {item['osm']} {item['name']}")
        print(f"    alamat: {item['addr'] or '-'} | kapasitas OSM: {item['capacity'] or '-'}")
        print(f"    jarak ke node {item['nearest_node']}: {item['straight_m']} m lurus"
              + (f", {item['road_m']} m lewat jalan (OSRM)" if item["road_m"] else ", OSRM tidak menjawab"))
        print(f"    jalan terdekat: {item['street'] or '-'}")


def _street_label(street: str | None) -> str:
    """Format nama jalan hasil Nominatim menjadi awalan 'Jl. ' yang rapi."""
    if not street:
        return "koneksi model (nama jalan belum terverifikasi)"
    cleaned = street.strip()
    for prefix in ("Jalan ", "Jl. ", "Jl ", "Jln. "):
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix):].strip()
            break
    return f"Jl. {cleaned}" if cleaned else "koneksi model (nama jalan belum terverifikasi)"


def emit_yaml(extras: list[dict]) -> None:
    print("\n# --- cuplikan YAML (--emit): node kantor damkar tambahan ---")
    for index, item in enumerate(extras, start=1):
        node_id = f"pos_damkar_tambahan_{index}"
        print(f"  - id: {node_id}")
        print(f"    label: \"{item['name']}\"")
        print(f"    lat: {item['lat']}")
        print(f"    lon: {item['lon']}")
        print(f"    osm_node: {int(item['osm'].split('/')[1])}")
        print("    facility:")
        print("      type: fire_station")
        print("      verified: true")
        print("      trucks: 2          # asumsi model")
        print("      personnel: 8       # asumsi model")
    print("\n# --- cuplikan YAML (--emit): edge koneksi ke node jaringan terdekat ---")
    for index, item in enumerate(extras, start=1):
        node_id = f"pos_damkar_tambahan_{index}"
        distance = item["road_m"] or item["straight_m"]
        weight = round(distance * 60.0 / (MODEL_ACCESS_SPEED_KMH * 1000.0), 2)
        print(f"  - id: e_log{index:02d}")
        print(f"    from: {node_id}")
        print(f"    to: {item['nearest_node']}")
        print(f"    weight: {weight}")
        print(f"    road: \"{_street_label(item['street'])} (koneksi model)\"")
        print(f"    distance_m: {distance}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validasi fasilitas node terhadap OSM.")
    parser.add_argument("scenario", nargs="?", default="data/pasar_johar_damkar.yaml")
    parser.add_argument("--emit", action="store_true", help="Cetak cuplikan YAML node/edge baru.")
    args = parser.parse_args()

    path = Path(args.scenario)
    nodes = load_nodes(path)
    hydrants, police, stations = fetch_facilities(nodes)
    classification = classify(nodes, hydrants, police)
    extras = candidate_stations(nodes, stations)
    print_report(path, nodes, classification, hydrants, police, stations, extras)
    if args.emit:
        emit_yaml(extras)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
