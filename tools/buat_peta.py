"""Buat peta HTML interaktif (Leaflet + tile OpenStreetMap) dari skenario YAML.

Isi peta:
- seluruh node dan ruas yang bisa dilalui mobil damkar (graf model);
- rute awal dan rute alternatif setelah ruas hambatan ditutup;
- warna node = lama tempuh dari pos damkar (Dijkstra), sehingga terlihat
  "ke mana saja" damkar bisa pergi dan berapa lama;
- fasilitas NYATA dari OSM (hydrant, kantor polisi, kantor damkar) sebagai
  lapisan terpisah, plus fasilitas model per node (hydrant asumsi, armada).

Pemakaian:
  python tools/buat_peta.py [skenario.yaml] [keluaran.html]
  python tools/buat_peta.py --tanpa-osm     # hanya isi YAML, tanpa internet

Keluaran default: docs/peta_rute_damkar.html (buka di peramban).
"""
from __future__ import annotations

import argparse
import html
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from pathfinding.dijkstra import dijkstra  # noqa: E402
from pathfinding.io import load_scenario  # noqa: E402

OVERPASS = "https://overpass-api.de/api/interpreter"
UA = "matdis-tubes-peta/0.1"


# ---------------------------------------------------------------- data OSM --


def overpass(query: str, attempts: int = 4) -> dict:
    last_error: Exception | None = None
    for attempt in range(attempts):
        request = urllib.request.Request(
            OVERPASS,
            data=urllib.parse.urlencode({"data": query}).encode(),
            headers={"User-Agent": UA},
        )
        try:
            with urllib.request.urlopen(request, timeout=90) as handle:
                return json.load(handle)
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code in (429, 500, 502, 503, 504) and attempt < attempts - 1:
                time.sleep(6 * (attempt + 1))
                continue
            raise
    raise last_error if last_error else RuntimeError("Overpass gagal.")


def _points(elements: list[dict]) -> list[dict]:
    out = []
    for element in elements:
        center = element.get("center") or {}
        lat = element.get("lat", center.get("lat"))
        lon = element.get("lon", center.get("lon"))
        if lat is None or lon is None:
            continue
        tags = element.get("tags", {})
        out.append(
            {
                "lat": float(lat),
                "lon": float(lon),
                "name": tags.get("name", ""),
                "operator": tags.get("operator", ""),
                "kind": tags.get("fire_hydrant:type", ""),
                "address": tags.get("addr:full", ""),
                "osm": f"{element['type']}/{element['id']}",
            }
        )
    return out


def osrm_geometry(lat1: float, lon1: float, lat2: float, lon2: float) -> list[list[float]] | None:
    """Geometri rute mengemudi (OSRM) antara dua titik, format [[lat, lon], ...].

    Dipakai agar garis abu-abu jaringan dan garis rute mengikuti jalan
    sungguhan, bukan garis lurus antar node. None bila OSRM tidak menjawab
    (pemanggil memakai garis lurus sebagai cadangan).
    """
    url = (
        f"https://router.project-osrm.org/route/v1/driving/"
        f"{lon1},{lat1};{lon2},{lat2}?overview=full&geometries=geojson"
    )
    try:
        with urllib.request.urlopen(
            urllib.request.Request(url, headers={"User-Agent": UA}), timeout=60
        ) as handle:
            data = json.load(handle)
    except Exception:  # noqa: BLE001 - jaringan/gagal rate-limit -> garis lurus
        return None
    routes = data.get("routes") or []
    if not routes:
        return None
    return [
        [round(lat, 6), round(lon, 6)]
        for lon, lat in routes[0]["geometry"]["coordinates"]
    ]


def fetch_osm_facilities(nodes: list[dict]) -> dict[str, list[dict]]:
    """Ambil hydrant, kantor polisi, dan kantor damkar dari OSM untuk peta."""
    lats = [node["lat"] for node in nodes]
    lons = [node["lon"] for node in nodes]
    pad = 0.012
    bbox = f"{min(lats) - pad},{min(lons) - pad},{max(lats) + pad},{max(lons) + pad}"
    wide_pad = 0.05
    wide = (
        f"{min(lats) - wide_pad},{min(lons) - wide_pad},"
        f"{max(lats) + wide_pad},{max(lons) + wide_pad}"
    )
    hydrants = _points(
        overpass(
            f'[out:json][timeout:90];(node["emergency"="fire_hydrant"]({bbox});'
            f'way["emergency"="fire_hydrant"]({bbox}););out tags center;'
        )["elements"]
    )
    time.sleep(1)
    police = _points(
        overpass(
            f'[out:json][timeout:90];(node["amenity"="police"]({bbox});'
            f'way["amenity"="police"]({bbox}););out tags center;'
        )["elements"]
    )
    time.sleep(1)
    stations = _points(
        overpass(
            f'[out:json][timeout:90];(node["amenity"="fire_station"]({wide});'
            f'way["amenity"="fire_station"]({wide}););out tags center;'
        )["elements"]
    )
    time.sleep(1)
    hospitals = _points(
        overpass(
            f'[out:json][timeout:90];(node["amenity"="hospital"]({bbox});'
            f'way["amenity"="hospital"]({bbox}););out tags center;'
        )["elements"]
    )
    return {"hydrants": hydrants, "police": police, "stations": stations,
            "hospitals": hospitals}


# ------------------------------------------------------------- payload data --


def build_payload(scenario_path: Path, with_osm: bool) -> dict:
    graph, scenario = load_scenario(scenario_path)
    coordinates = scenario["coordinates"]
    node_facilities = scenario.get("node_facilities") or {}
    start, goal = scenario["start"], scenario["goal"]
    closure = str(scenario.get("closure_edge") or "")

    initial = dijkstra(graph, start, goal)
    if initial is None:
        raise SystemExit("Rute awal tidak ditemukan; peta tidak bisa dibuat.")

    # Rute alternatif per unit damkar (berbeda satu sama lain), dihitung dalam
    # kondisi ruas hambatan ditutup - sama seperti keluaran simulasi.
    from pathfinding.rute_alternatif import plan_alternatives

    search_blocked = {closure} if closure else set()
    plans = scenario.get("alternatives") or []
    if not plans and closure:
        plans = [{"id": "tercepat", "label": "Rute alternatif", "purpose": "", "waypoints": []}]
    alternatives = plan_alternatives(
        plans, start, goal, lambda a, b: dijkstra(graph, a, b, search_blocked)
    )
    found = [alt for alt in alternatives if alt["result"] is not None]
    alternate = found[0]["result"] if found else None

    # Waktu tempuh dari pos damkar ke tiap node (Dijkstra per node).
    minutes: dict[str, float] = {}
    for node_id in graph.nodes:
        result = dijkstra(graph, start, node_id)
        minutes[node_id] = round(result.cost, 2) if result else float("inf")

    initial_edges = set(initial.edges)
    alternative_edges: set[str] = set()
    alternative_nodes: set[str] = set()
    service_nodes: set[str] = set()
    for alt in found:
        if alt["result"] is None:
            continue
        alternative_edges |= set(alt["result"].edges)
        alternative_nodes |= set(alt["result"].nodes)
        service_nodes |= set(alt["waypoints"])

    nodes = []
    for node_id, label in graph.nodes.items():
        fields = node_facilities.get(node_id) or {}
        roles = []
        if node_id == start:
            roles.append("titik awal")
        if node_id == goal:
            roles.append("tujuan")
        if initial and node_id in initial.nodes:
            roles.append("rute awal")
        if node_id in alternative_nodes:
            roles.append("rute alternatif")
        if node_id in service_nodes:
            roles.append("titik layanan")
        nodes.append(
            {
                "id": node_id,
                "label": label,
                "lat": coordinates[node_id][0],
                "lon": coordinates[node_id][1],
                "roles": roles,
                "minutes": minutes[node_id],
                "hydrant": fields.get("hydrant"),
                "facility": fields.get("facility"),
            }
        )

    edges = []
    seen = set()
    straight_fallback = 0
    for source in graph.nodes:
        for edge in graph.neighbors(source):
            if edge.edge_id in seen:
                continue
            seen.add(edge.edge_id)
            geometry = None
            if with_osm and source in coordinates and edge.target in coordinates:
                src, dst = coordinates[source], coordinates[edge.target]
                geometry = osrm_geometry(src[0], src[1], dst[0], dst[1])
                if geometry is None:
                    straight_fallback += 1
                time.sleep(0.2)
            edges.append(
                {
                    "id": edge.edge_id,
                    "from": source,
                    "to": edge.target,
                    "weight": round(edge.weight, 2),
                    "road": edge.road_name,
                    "route": (
                        "initial" if edge.edge_id in initial_edges
                        else "alternate" if edge.edge_id in alternative_edges
                        else None
                    ),
                    "closed": edge.edge_id == closure,
                    "geometry": geometry,
                }
            )

    # Rute dari tiap kantor damkar tambahan ke pasar: node logistik yang
    # ditambahkan harus benar-benar dilewati damkar, bukan cabang menggantung.
    deploy_routes = []
    for node_id, fields in node_facilities.items():
        if (fields.get("facility") or {}).get("type") != "fire_station":
            continue
        result = dijkstra(graph, node_id, goal)
        if result is None:
            continue
        deploy_routes.append(
            {
                "from": node_id,
                "label": graph.nodes.get(node_id, node_id),
                "cost": round(result.cost, 2),
                "edges": len(result.edges),
                "nodes": result.nodes,
            }
        )
    deploy_routes.sort(key=lambda item: item["cost"])

    alternative_payload = [
        {
            "id": alt["id"],
            "label": alt["label"],
            "purpose": alt["purpose"],
            "waypoints": alt["waypoints"],
            "cost": None if alt["result"] is None else round(alt["result"].cost, 2),
            "edges": None if alt["result"] is None else len(alt["result"].edges),
            "nodes": None if alt["result"] is None else alt["result"].nodes,
        }
        for alt in alternatives
    ]

    metadata = scenario.get("metadata") or {}
    payload = {
        "title": str(metadata.get("title", "Peta rute damkar")),
        "location": str(metadata.get("location", "")),
        "generated": date.today().isoformat(),
        "scenario": scenario_path.name,
        "unit": str(metadata.get("display_weight_unit", "menit estimasi")),
        "start": start,
        "goal": goal,
        "closed_edge": closure,
        "closure_description": str(scenario.get("closure_description", "")),
        "nodes": nodes,
        "edges": edges,
        "routes": {
            "initial": {
                "cost": round(initial.cost, 2),
                "edges": len(initial.edges),
                "nodes": initial.nodes,
            },
            "alternate": (
                {
                    "cost": round(alternate.cost, 2),
                    "edges": len(alternate.edges),
                    "nodes": alternate.nodes,
                }
                if alternate else None
            ),
        },
        "deploy": deploy_routes,
        "alternatives": alternative_payload,
        "straight_fallback": straight_fallback,
        "osm": {"hydrants": [], "police": [], "stations": [], "hospitals": []},
        "with_osm": False,
        "fact_note": str(metadata.get("facility_note", "")),
        "source_articles": metadata.get("source_articles") or [],
    }
    if with_osm:
        payload["osm"] = fetch_osm_facilities(
            [{"lat": n["lat"], "lon": n["lon"]} for n in nodes]
        )
        payload["with_osm"] = True
    return payload


# --------------------------------------------------------------- template ---

TEMPLATE = """<!DOCTYPE html>
<html lang="id">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<style>
  * { box-sizing: border-box; }
  html, body { margin: 0; height: 100%; font-family: system-ui, -apple-system, "Segoe UI", sans-serif; }
  #app { display: flex; height: 100%; }
  #panel { width: 330px; min-width: 330px; background: #0f172a; color: #e2e8f0;
           padding: 18px 18px 24px; overflow-y: auto; }
  #panel h1 { font-size: 17px; margin: 0 0 4px; color: #f8fafc; line-height: 1.3; }
  #panel .sub { font-size: 12px; color: #94a3b8; margin-bottom: 14px; line-height: 1.5; }
  .stats { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 16px; }
  .stat { background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 8px 10px; }
  .stat b { display: block; font-size: 16px; color: #f8fafc; }
  .stat span { font-size: 11px; color: #94a3b8; }
  h2 { font-size: 12px; text-transform: uppercase; letter-spacing: .06em;
       color: #64748b; margin: 18px 0 8px; }
  .legend-item { display: flex; align-items: center; gap: 9px; font-size: 12.5px;
                 margin: 7px 0; color: #cbd5e1; line-height: 1.35; }
  .swatch { width: 26px; height: 12px; border-radius: 3px; flex: none; border: 1px solid rgba(255,255,255,.35); }
  .dot { width: 13px; height: 13px; border-radius: 50%; flex: none; border: 2px solid #0f172a; }
  .note { font-size: 11.5px; color: #94a3b8; background: #1e293b; border-left: 3px solid #3b82f6;
          padding: 8px 10px; border-radius: 0 6px 6px 0; margin-top: 12px; line-height: 1.55; }
  .note.warn { border-left-color: #f59e0b; }
  .src { font-size: 11px; color: #64748b; margin-top: 14px; line-height: 1.6; word-break: break-all; }
  #map { flex: 1; height: 100%; }
  .popup { font-size: 12.5px; line-height: 1.5; max-width: 280px; }
  .popup b { font-size: 13px; }
  .popup .id { color: #64748b; font-family: ui-monospace, monospace; font-size: 11px; }
  .badge { display: inline-block; background: #e2e8f0; color: #0f172a; border-radius: 10px;
           font-size: 10.5px; padding: 1px 7px; margin: 2px 3px 0 0; font-weight: 600; }
  .badge.blue { background: #60a5fa; }
  .badge.orange { background: #fbbf24; }
  .badge.green { background: #34d399; }
  .badge.purple { background: #c084fc; }
  .badge.red { background: #f87171; }
  .muted { color: #64748b; font-size: 11.5px; }
  @media (max-width: 760px) { #app { flex-direction: column; } #panel { width: 100%; min-width: 0; max-height: 45%; } }
</style>
</head>
<body>
<div id="app">
  <aside id="panel">
    <h1>__TITLE__</h1>
    <div class="sub">__LOCATION__<br>Skenario: __SCENARIO__ · dibuat __GENERATED__</div>
    <div class="stats">
      <div class="stat"><b>__NODE_COUNT__</b><span>node (bisa dilalui damkar)</span></div>
      <div class="stat"><b>__EDGE_COUNT__</b><span>ruas jalan</span></div>
      <div class="stat"><b>__INITIAL_COST__</b><span>rute awal (menit)</span></div>
      <div class="stat"><b>__ALTERNATE_COST__</b><span>setelah __CLOSED__ ditutup</span></div>
    </div>

    <h2>Lapisan peta</h2>
    <div class="legend-item"><span class="swatch" style="background:#94a3b8"></span> Jaringan jalan yang bisa dilalui damkar</div>
    <div class="legend-item"><span class="swatch" style="background:#1d4ed8"></span> Rute awal (tercepat)</div>
    <div id="alt-legend"></div>
    <div class="legend-item"><span class="swatch" style="background:#7c3aed"></span> Rute dari kantor damkar tambahan → pasar (node logistik <b>dilewati</b> damkar)</div>
    <div class="legend-item"><span class="swatch" style="background:#dc2626"></span> Ruas tertutup kerumunan (event berita)</div>

    <h2>Warna node = waktu dari pos damkar</h2>
    <div class="legend-item"><span class="dot" style="background:#22c55e"></span> ≤ 3 menit</div>
    <div class="legend-item"><span class="dot" style="background:#eab308"></span> 3–6 menit</div>
    <div class="legend-item"><span class="dot" style="background:#f97316"></span> 6–9 menit</div>
    <div class="legend-item"><span class="dot" style="background:#ef4444"></span> &gt; 9 menit</div>
    <div class="legend-item"><span class="dot" style="background:#22c55e;border-color:#fff"></span> Hijau tebal = titik awal</div>
    <div class="legend-item"><span class="dot" style="background:#ef4444;border-color:#fff"></span> Merah = tujuan</div>

    <h2>Fasilitas</h2>
    <div class="legend-item"><span class="dot" style="background:#06b6d4"></span> Node ber-hydrant (bisa isi air)</div>
    <div class="legend-item"><span class="dot" style="background:#6366f1"></span> Node kantor polisi (tanpa hydrant)</div>
    <div class="legend-item"><span class="dot" style="background:#a855f7"></span> Kantor damkar (logistik: mobil/personel)</div>
    <div class="legend-item"><span class="swatch" style="background:#0ea5e9;height:13px;width:13px;border-radius:50%"></span> Hydrant asli di OSM (klik untuk detail)</div>
    <div class="legend-item"><span class="swatch" style="background:#1e3a8a;height:13px;width:13px;border-radius:50%"></span> Kantor polisi asli di OSM</div>
    <div class="legend-item"><span class="swatch" style="background:#be123c;height:13px;width:13px;border-radius:50%"></span> Rumah sakit di OSM (bantuan ambulance)</div>
    <div class="legend-item"><span class="swatch" style="background:#b91c1c;height:13px;width:13px;border-radius:50%"></span> Kantor damkar asli di OSM</div>

    <div class="note">Semua node dan ruas pada peta ini <b>bisa dilalui mobil damkar</b> menurut model
    (graf tidak berarah), dan seluruh garis mengikuti jalan sungguhan (geometri OSRM).
    Setiap unit damkar memakai <b>rute alternatif berbeda</b>: ada yang lewat kantor polisi
    (kawalan polisi) dan ada yang lewat IGD rumah sakit (bantuan ambulance) - ketiganya
    tercantum di legenda dengan biayanya. Setiap node kantor damkar yang ditambahkan
    <b>dilewati oleh rute ungu</b> dari kantor tersebut ke pasar. Klik node untuk melihat
    waktu tempuh dari pos, status hydrant, dan fasilitasnya; klik ruas untuk bobot dan
    nama jalan.</div>
    <div class="note warn">Hydrant di simpang selain yang bertanda "terverifikasi OSM" adalah
    <b>asumsi model</b>; kantor polisi, kantor damkar, rumah sakit, dan hydrant berwarna biru
    tua/merah berasal langsung dari OpenStreetMap (ekstraksi __GENERATED__).</div>
    <div class="src">Sumber data: OpenStreetMap contributors (ODbL) · tile dasar:
    Esri World Street Map (jalan) dan Esri World Imagery (citra satelit) ·
    rute: Dijkstra (pembanding A* sama hasilnya).<br>__SOURCES__</div>
  </aside>
  <div id="map"></div>
</div>

<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
const NODES = __NODES__;
const EDGES = __EDGES__;
const ROUTES = __ROUTES__;
const DEPLOY = __DEPLOY__;
const ALTS = __ALTS__;
const OSM = __OSM__;
const CLOSED_EDGE = "__CLOSED__";
const UNIT = "__UNIT__";

const byId = Object.fromEntries(NODES.map(n => [n.id, n]));
const esc = s => String(s ?? "").replace(/[&<>"']/g,
  c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));

// Geometri tiap ruas (mengikuti jalan sungguhan hasil OSRM); bila kosong
// (mode offline / OSRM gagal) dipakai garis lurus antar node.
const edgeGeo = {};
EDGES.forEach(e => {
  const a = byId[e.from], b = byId[e.to];
  const g = e.geometry && e.geometry.length >= 2
    ? e.geometry
    : [[a.lat, a.lon], [b.lat, b.lon]];
  edgeGeo[e.from + ">" + e.to] = g;
  edgeGeo[e.to + ">" + e.from] = g.slice().reverse();
});

// Gabungkan geometri sepanjang rute supaya garis rute ikut jalan, bukan
// memotong blok.
function routePoints(ids) {
  const pts = [];
  for (let i = 0; i < ids.length - 1; i++) {
    const g = edgeGeo[ids[i] + ">" + ids[i + 1]];
    if (!g) {
      const n = byId[ids[i]];
      pts.push([n.lat, n.lon]);
      continue;
    }
    if (!pts.length) pts.push(g[0]);
    for (const p of g) {
      const last = pts[pts.length - 1];
      if (p[0] !== last[0] || p[1] !== last[1]) pts.push(p);
    }
  }
  const lastNode = byId[ids[ids.length - 1]];
  const last = pts[pts.length - 1];
  if (!last || last[0] !== lastNode.lat || last[1] !== lastNode.lon) {
    pts.push([lastNode.lat, lastNode.lon]);
  }
  return pts;
}

const map = L.map("map", {zoomControl: true});
// Tile resmi tile.openstreetmap.org menolak permintaan dari halaman lokal
// (usage policy OSM) dan basemap CARTO kini butuh API key, jadi basemap jalan
// memakai Esri World Street Map yang gratis tanpa kunci dan mengizinkan
// pemakaian client-side. Data peta tetap OpenStreetMap (atribusi dicantumkan).
const streetTiles = L.tileLayer(
  "https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}",
  {maxZoom: 19,
   attribution: "Tiles &copy; Esri · data &copy; OpenStreetMap contributors"});
const satellite = L.tileLayer(
  "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
  {maxZoom: 18, attribution: "Tiles &copy; Esri"});
streetTiles.addTo(map);

// --- lapisan jaringan -------------------------------------------------------
const gNetwork = L.layerGroup();
EDGES.forEach(e => {
  const pts = edgeGeo[e.from + ">" + e.to];
  const line = L.polyline(pts,
    {color: "#94a3b8", weight: 3, opacity: .65, lineJoin: "round"});
  line.bindPopup(
    `<div class="popup"><b>${esc(e.road || e.id)}</b><br>
     <span class="id">${esc(e.id)} · ${esc(e.from)} → ${esc(e.to)}</span><br>
     ${e.weight} ${esc(UNIT)}${e.closed ? '<br><span class="badge red">ditutup kerumunan</span>' : ""}
     ${e.route === "initial" ? '<span class="badge blue">rute awal</span>' : ""}
     ${e.route === "alternate" ? '<span class="badge orange">rute alternatif</span>' : ""}</div>`);
  line.addTo(gNetwork);
});

// --- lapisan rute -----------------------------------------------------------
function routeLine(ids, opts, popupHtml) {
  const pts = routePoints(ids);
  // Casing putih agar garis rute tetap terbaca di atas peta jalan padat.
  const casing = L.polyline(pts,
    {color: "#ffffff", weight: opts.weight + 4, opacity: .8, lineJoin: "round"});
  const line = L.polyline(pts, opts);
  if (popupHtml) line.bindPopup(popupHtml);
  return L.layerGroup([casing, line]);
}
function routePopup(title, r) {
  return `<div class="popup"><b>${esc(title)}</b><br>
    <span class="id">${esc(r.from || "rute utama")} → ${esc("__GOAL__")}</span><br>
    ${esc(r.cost)} ${esc(UNIT)} · ${esc(r.edges)} ruas</div>`;
}
const gInitial = L.layerGroup().addLayer(routeLine(ROUTES.initial.nodes,
  {color: "#1d4ed8", weight: 6, opacity: .9},
  routePopup("Rute awal (tercepat)", {cost: ROUTES.initial.cost,
    edges: ROUTES.initial.edges, from: "__START__"})));
// --- rute alternatif tiap unit damkar (berbeda satu sama lain) -------------
// Tiap unit mendapat rutenya sendiri; ada yang lewat kantor polisi (kawalan)
// dan ada yang lewat IGD rumah sakit (bantuan ambulance).
const ALT_COLORS = ["#f59e0b", "#0d9488", "#db2777"];
const ALT_DASH = ["12, 9", "", "4, 6"];
const gAlts = L.layerGroup();
ALTS.forEach((r, i) => {
  if (!r.nodes) return;  // rencana gagal: tidak digambar
  const color = ALT_COLORS[i % ALT_COLORS.length];
  const popup = `<div class="popup"><b>Alternatif ${i + 1}: ${esc(r.label)}</b><br>
    ${esc(r.purpose)}<br>
    ${esc(r.cost)} ${esc(UNIT)} · ${esc(r.edges)} ruas · ${esc(r.nodes.length)} node` +
    (r.waypoints && r.waypoints.length
      ? `<br>Titik layanan (dilewati): ${esc(r.waypoints.join(", "))}` : "") + `</div>`;
  routeLine(r.nodes,
    {color: color, weight: 6, opacity: .9, dashArray: ALT_DASH[i % ALT_DASH.length]},
    popup).addTo(gAlts);
});
// Isi legenda rute alternatif dari data (label + biaya, bukan teks mati).
ALTS.forEach((r, i) => {
  const box = document.getElementById("alt-legend");
  if (!box || !r.nodes) return;
  const item = document.createElement("div");
  item.className = "legend-item";
  item.innerHTML = `<span class="swatch" style="background:${ALT_COLORS[i % ALT_COLORS.length]}"></span>` +
    ` Alternatif ${i + 1} - ${esc(r.label)} (${esc(r.cost)} menit)` +
    (r.waypoints && r.waypoints.length
      ? ` <span class="muted">lewat ${esc(r.waypoints.join(", "))}</span>` : "");
  box.appendChild(item);
});

// --- rute dari kantor damkar tambahan (node logistik dilewati damkar) -------
const gDeploy = L.layerGroup();
DEPLOY.forEach(r => {
  const layer = routeLine(r.nodes,
    {color: "#7c3aed", weight: 5, opacity: .9},
    `<div class="popup"><b>🚒 Rute dari kantor damkar</b><br>
     <span class="id">${esc(r.from)}</span><br>${esc(r.label)}<br>
     ${esc(r.cost)} ${esc(UNIT)} · ${esc(r.edges)} ruas ·
     node tambahan ini <b>dilewati</b> oleh rute ini</div>`);
  layer.addTo(gDeploy);
});

// --- ruas tertutup ----------------------------------------------------------
const gClosed = L.layerGroup();
EDGES.filter(e => e.closed).forEach(e => {
  const pts = edgeGeo[e.from + ">" + e.to];
  L.polyline(pts, {color: "#ffffff", weight: 11, opacity: .8}).addTo(gClosed);
  const line = L.polyline(pts,
    {color: "#dc2626", weight: 7, opacity: .95, dashArray: "6, 7"});
  line.bindPopup(`<div class="popup"><b>Ruas ditutup kerumunan</b><br>
     <span class="id">${esc(e.id)} · ${esc(e.road)}</span><br>
     ${esc(window.CLOSURE_NOTE || "")}</div>`);
  line.addTo(gClosed);
});

// --- node -------------------------------------------------------------------
function timeColor(m) {
  if (m === "start") return "#22c55e";
  if (m === "goal") return "#ef4444";
  if (m <= 3) return "#22c55e";
  if (m <= 6) return "#eab308";
  if (m <= 9) return "#f97316";
  return "#ef4444";
}
const gNodes = L.layerGroup();
NODES.forEach(n => {
  const isStart = n.id === "__START__", isGoal = n.id === "__GOAL__";
  const color = timeColor(isStart ? "start" : isGoal ? "goal" : n.minutes);
  const marker = L.circleMarker([n.lat, n.lon], {
    radius: isStart || isGoal ? 9 : 7,
    color: "#0f172a", weight: 2, fillColor: color, fillOpacity: .95
  });
  const badges = n.roles.map(r =>
    `<span class="badge ${r === "rute awal" ? "blue" : r === "rute alternatif" ? "orange"
      : r === "titik awal" ? "green" : r === "tujuan" ? "red" : "purple"}">${esc(r)}</span>`).join("");
  let facility = "";
  if (n.hydrant) {
    facility += n.hydrant.verified
      ? `<br>💧 Hydrant <b>terverifikasi OSM</b>: ${esc(n.hydrant.name || "-")}
         (${esc(n.hydrant.osm_node)}), ${esc(n.hydrant.distance_m)} m dari node`
      : `<br>💧 Hydrant <span class="muted">asumsi model</span>`
        + (n.hydrant.nearest_osm_m ? ` (OSM terdekat ${esc(n.hydrant.nearest_osm_m)} m)` : "");
  } else {
    facility += `<br>🚫 Tanpa hydrant (node kantor polisi)`;
  }
  if (n.facility) {
    if (n.facility.type === "police_station") {
      facility += `<br>🚔 ${esc(n.facility.name)} (${esc(n.facility.distance_m)} m, ${esc(n.facility.address || "")})`;
    } else if (n.facility.type === "hospital") {
      facility += `<br>🏥 ${esc(n.facility.ambulances)} ambulance <span class="muted">(asumsi model)</span>` +
        (n.facility.emergency ? " · IGD darurat terverifikasi di OSM" : "");
    } else {
      facility += `<br>🚒 Kantor damkar: ${esc(n.facility.trucks)} mobil, `
        + `${esc(n.facility.personnel)} personel <span class="muted">(asumsi model)</span>`;
    }
  }
  marker.bindPopup(`<div class="popup"><b>${esc(n.label)}</b><br>
    <span class="id">${esc(n.id)}</span><br>${badges}<br>
    ⏱ ${esc(n.minutes)} ${esc(UNIT)} dari pos damkar${facility}</div>`);
  marker.addTo(gNodes);
});

// --- fasilitas OSM ----------------------------------------------------------
const gOsm = L.layerGroup();
OSM.hydrants.forEach(h => {
  L.circleMarker([h.lat, h.lon], {radius: 5, color: "#0c4a6e", weight: 2,
      fillColor: "#0ea5e9", fillOpacity: .95})
    .bindPopup(`<div class="popup"><b>💧 ${esc(h.name || "Hydrant")}</b><br>
      <span class="id">${esc(h.osm)}</span><br>jenis: ${esc(h.kind || "-")} ·
      pengelola: ${esc(h.operator || "-")}</div>`)
    .addTo(gOsm);
});
OSM.police.forEach(p => {
  L.circleMarker([p.lat, p.lon], {radius: 6, color: "#0f172a", weight: 2,
      fillColor: "#1e3a8a", fillOpacity: .95})
    .bindPopup(`<div class="popup"><b>🚔 ${esc(p.name || "Kantor polisi")}</b><br>
      <span class="id">${esc(p.osm)}</span>${p.address ? "<br>" + esc(p.address) : ""}</div>`)
    .addTo(gOsm);
});
OSM.stations.forEach(s => {
  L.circleMarker([s.lat, s.lon], {radius: 6, color: "#0f172a", weight: 2,
      fillColor: "#b91c1c", fillOpacity: .95})
    .bindPopup(`<div class="popup"><b>🚒 ${esc(s.name || "Kantor damkar")}</b><br>
      <span class="id">${esc(s.osm)}</span>${s.address ? "<br>" + esc(s.address) : ""}</div>`)
    .addTo(gOsm);
});
OSM.hospitals.forEach(h => {
  L.circleMarker([h.lat, h.lon], {radius: 6, color: "#0f172a", weight: 2,
      fillColor: "#be123c", fillOpacity: .95})
    .bindPopup(`<div class="popup"><b>🏥 ${esc(h.name || "Rumah sakit")}</b><br>
      <span class="id">${esc(h.osm)}</span>${h.address ? "<br>" + esc(h.address) : ""}<br>
      <span class="muted">potensi bantuan ambulance (rute alternatif)</span></div>`)
    .addTo(gOsm);
});

// --- kontrol lapisan & tampilan awal ---------------------------------------
const overlays = {
  "Jaringan (bisa dilalui damkar)": gNetwork,
  "Rute awal": gInitial,
  "Rute alternatif (3 unit damkar)": gAlts,
  "Rute dari kantor damkar": gDeploy,
  "Ruas tertutup": gClosed,
  "Node & waktu tempuh": gNodes,
  "Fasilitas OSM": gOsm
};
L.control.layers({"Peta jalan": streetTiles, "Citra satelit": satellite}, overlays,
  {collapsed: false}).addTo(map);
[gNetwork, gInitial, gAlts, gDeploy, gClosed, gNodes].forEach(l => l.addTo(map));
if (OSM.hydrants.length || OSM.police.length || OSM.stations.length || OSM.hospitals.length) gOsm.addTo(map);

const bounds = L.latLngBounds(NODES.map(n => [n.lat, n.lon]));
map.fitBounds(bounds.pad(0.08));
L.control.scale({imperial: false}).addTo(map);
window.CLOSURE_NOTE = __CLOSURE_NOTE__;
</script>
</body>
</html>
"""


def render(payload: dict) -> str:
    sources = "<br>".join(html.escape(str(url)) for url in payload["source_articles"])
    alternate = payload["routes"]["alternate"]
    page = (
        TEMPLATE
        .replace("__TITLE__", html.escape(payload["title"]))
        .replace("__LOCATION__", html.escape(payload["location"]))
        .replace("__SCENARIO__", html.escape(payload["scenario"]))
        .replace("__GENERATED__", html.escape(payload["generated"]))
        .replace("__NODE_COUNT__", str(len(payload["nodes"])))
        .replace("__EDGE_COUNT__", str(len(payload["edges"])))
        .replace("__INITIAL_COST__", f"{payload['routes']['initial']['cost']:.2f}")
        .replace(
            "__ALTERNATE_COST__",
            f"{alternate['cost']:.2f}" if alternate else "n/a",
        )
        .replace("__CLOSED__", html.escape(payload["closed_edge"] or "-"))
        .replace("__SOURCES__", sources or "-")
        .replace("__NODES__", json.dumps(payload["nodes"], ensure_ascii=False))
        .replace("__EDGES__", json.dumps(payload["edges"], ensure_ascii=False))
        .replace("__ROUTES__", json.dumps(payload["routes"], ensure_ascii=False))
        .replace("__DEPLOY__", json.dumps(payload["deploy"], ensure_ascii=False))
        .replace("__ALTS__", json.dumps(payload["alternatives"], ensure_ascii=False))
        .replace("__OSM__", json.dumps(payload["osm"], ensure_ascii=False))
        .replace("__UNIT__", html.escape(payload["unit"]))
        .replace("__START__", payload["start"])
        .replace("__GOAL__", payload["goal"])
        .replace("__CLOSURE_NOTE__", json.dumps(payload["closure_description"], ensure_ascii=False))
    )
    return page


def main() -> int:
    parser = argparse.ArgumentParser(description="Buat peta HTML rute damkar.")
    parser.add_argument("scenario", nargs="?", default=str(REPO / "data" / "pasar_johar_damkar.yaml"))
    parser.add_argument("output", nargs="?", default=str(REPO / "docs" / "peta_rute_damkar.html"))
    parser.add_argument(
        "--tanpa-osm", action="store_true",
        help="Jangan ambil data OSM (hanya isi YAML; untuk tanpa internet).",
    )
    args = parser.parse_args()

    scenario_path = Path(args.scenario)
    output_path = Path(args.output)
    payload = build_payload(scenario_path, with_osm=not args.tanpa_osm)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render(payload), encoding="utf-8")

    osm = payload["osm"]
    print(f"Peta ditulis ke {output_path}")
    print(
        f"node={len(payload['nodes'])} ruas={len(payload['edges'])} | "
        f"rute awal {payload['routes']['initial']['cost']} "
        f"({payload['routes']['initial']['edges']} ruas)"
    )
    for route in payload["deploy"]:
        print(
            f"rute dari {route['from']}: {route['cost']} "
            f"({route['edges']} ruas) - node tambahan dilewati"
        )
    if payload["with_osm"]:
        print(
            f"OSM: hydrant={len(osm['hydrants'])} kantor polisi={len(osm['police'])} "
            f"kantor damkar={len(osm['stations'])} rumah sakit={len(osm['hospitals'])}"
        )
        print(
            f"geometri jalan: {len(payload['edges']) - payload['straight_fallback']}"
            f"/{len(payload['edges'])} ruas mengikuti rute OSRM"
            + (
                f", {payload['straight_fallback']} memakai garis lurus"
                if payload["straight_fallback"] else ""
            )
        )
    else:
        print("Mode --tanpa-osm: lapisan fasilitas OSM dan geometri jalan dilewati.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
