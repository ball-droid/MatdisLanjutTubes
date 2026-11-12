"""Rute alternatif per unit damkar: rute BERBEDA lewat titik layanan berbeda.

Setelah akses utara terputus (ruas `e14`), tidak semua unit damkar harus
memakai rute yang sama. Satu unit boleh memakai rute tercepat, unit lain
memakai waypoint - misalnya mampir ke rumah sakit untuk koordinasi ambulance
atau ke kantor polisi untuk kawalan - sehingga rutenya berbeda dan jumlah
node yang dikunjungi seluruh armada menjadi lebih banyak.

Semua kaki perjalanan dihitung dengan algoritma yang sama dengan baseline
(Dijkstra) atau pembandingnya (A*), jadi biaya total rute = jumlah biaya tiap
kaki. Kontrak hasilnya `PathResult`, sama seperti pencarian biasa.
"""
from __future__ import annotations

from typing import Callable, Iterable, Sequence

from .dijkstra import PathResult

# leg_search(a, b) -> PathResult | None (dibungkus pemanggil: algoritma,
# himpunan ruas tertutup, koordinat heuristik sudah diatur di sana).
LegSearch = Callable[[str, str], "PathResult | None"]


def route_via(points: Sequence[str], leg_search: LegSearch) -> PathResult | None:
    """Gabungkan kaki-kaki rute `points[0] -> ... -> points[-1]`.

    Mengembalikan None bila ada satu kaki pun yang tidak terjangkau, sehingga
    rute alternatif yang gagal tidak pernah dilaporkan sebagian jadi.
    """
    if len(points) < 2:
        raise ValueError("Butuh minimal titik awal dan titik tujuan.")
    nodes: list[str] = []
    edges: list[str] = []
    cost = 0.0
    for source, target in zip(points, points[1:]):
        leg = leg_search(str(source), str(target))
        if leg is None:
            return None
        if not nodes:
            nodes = list(leg.nodes)
        else:
            # Kaki berikutnya bertitik di simpul akhir kaki sebelumnya.
            nodes.extend(leg.nodes[1:])
        edges.extend(leg.edges)
        cost += leg.cost
    return PathResult(nodes=nodes, cost=cost, edges=edges)


def plan_alternatives(
    plans: Iterable[dict],
    start: str,
    goal: str,
    leg_search: LegSearch,
) -> list[dict]:
    """Hitung tiap rencana alternatif menjadi rute konkret.

    Mengembalikan daftar dict {id, label, purpose, waypoints, result}; `result`
    berupa PathResult atau None bila rute tidak terjangkau. Rencana yang gagal
    tetap dikembalikan (dengan result None) supaya pelaporannya jujur.
    """
    computed: list[dict] = []
    for plan in plans:
        if not isinstance(plan, dict):
            raise ValueError("Setiap rencana alternatif harus berupa object.")
        waypoints = [str(item) for item in plan.get("waypoints") or []]
        computed.append(
            {
                "id": str(plan.get("id", "")),
                "label": str(plan.get("label", "")),
                "purpose": str(plan.get("purpose", "") or ""),
                "waypoints": waypoints,
                "result": route_via([start, *waypoints, goal], leg_search),
            }
        )
    return computed
