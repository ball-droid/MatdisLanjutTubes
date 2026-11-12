"""Heuristik jarak udara (haversine) untuk algoritma A*.

A* tetap optimal hanya bila heuristiknya *admissible* (tidak pernah
memperkirakan biaya lebih besar dari biaya sebenarnya). Heuristik yang dipakai
di sini:

    h(node) = jarak lurus (haversine) node -> goal  /  kecepatan model terbesar

Dua alasan menjamin admissibility pada data proyek ini:

1. Jarak lurus selalu <= panjang jalur nyata antara dua titik (triangular
   inequality), sedangkan bobot tiap ruas dihitung dari ``distance_m`` panjang
   ruas pada peta (README bagian 8).
2. Pembagi memakai kecepatan model TERBESAR (35 km/jam), sementara seluruh
   bobot ruas memakai kecepatan <= 35 km/jam (utama 35, sekunder 30,
   permukiman 20; enam ruas outlier berkecepatan tersirat 14-31 km/jam).
   Membagi dengan pembagi terbesar membuat h lebih kecil, sehingga h <= biaya
   sebenarnya.

Konsekuensinya heuristik ini sengaja lemah (mudah dihitung, aman), bukan
heuristik terkuat; sudah cukup untuk membandingkan A* dengan Dijkstra pada
graf proyek ini.

Koordinat tidak disimpan pada objek ``Graph`` (graph hanya menyimpan id dan
label); loader mengekstrak ``lat``/``lon`` dari YAML ke
``scenario["coordinates"]``. Bila peta koordinat kosong - misalnya skenario
demo berbasis screenshot tanpa jejak peta - heuristik mengembalikan 0 sehingga
A* menyusut menjadi Dijkstra persis: tetap benar, hanya tanpa keuntungan
penelusuran.
"""
from __future__ import annotations

import math
from typing import Callable, Mapping

EARTH_RADIUS_M = 6_371_000.0
MODEL_MAX_SPEED_KMH = 35.0

Coordinate = tuple[float, float]
Coordinates = Mapping[str, Coordinate]


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Jarak lingkaran besar antara dua koordinat, dalam meter."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def estimate_minutes(distance_m: float, speed_kmh: float = MODEL_MAX_SPEED_KMH) -> float:
    """Ubah jarak meter menjadi menit estimasi dengan kecepatan tertentu."""
    return distance_m * 60.0 / (speed_kmh * 1000.0)


def build_heuristic(coordinates: Coordinates, goal: str) -> Callable[[str], float]:
    """Bangun fungsi ``h(node) -> perkiraan sisa biaya (menit)`` menuju goal.

    Heuristik identik-nol bila goal tidak punya koordinat (skenario tanpa
    jejak peta) sehingga pemakainya selalu aman tanpa pemeriksaan khusus.
    """
    goal_coord = coordinates.get(goal)
    if goal_coord is None:
        return lambda _node_id: 0.0
    goal_lat, goal_lon = goal_coord

    cache: dict[str, float] = {}

    def heuristic(node_id: str) -> float:
        cached = cache.get(node_id)
        if cached is not None:
            return cached
        coordinate = coordinates.get(node_id)
        value = (
            0.0
            if coordinate is None
            else estimate_minutes(haversine_m(coordinate[0], coordinate[1], goal_lat, goal_lon))
        )
        cache[node_id] = value
        return value

    return heuristic
