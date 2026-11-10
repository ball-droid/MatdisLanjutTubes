# Bagian C — Engine Base Pathfinding (Dijkstra)

Kode Python untuk tanggung jawab C: mesin pencari rute baseline, pembacaan skenario YAML, `run_simulation()`, pengujian Pytest, dan benchmark. Struktur modularnya mengambil inspirasi dari [trisgelar/matdis-tubes-2026](https://github.com/trisgelar/matdis-tubes-2026), terutama pemisahan algoritma, model graf, konfigurasi kasus, test, dan runner. Implementasi ini dibuat ringkas untuk studi kasus Pasar Johar.

## Studi kasus yang dipakai

Pada 2 Februari 2022, kebakaran terjadi di Pasar Johar Relokasi di kawasan Masjid Agung Jawa Tengah (MAJT), Semarang. Berita melaporkan kerumunan warga yang menonton membuat jalan macet dan menghambat akses kendaraan damkar. Hal itu menjadi dasar event penutupan ruas dalam simulasi.

Sumber berita:
- Bisnis.com, *Relokasi Pasar Johar Terbakar, Ganjar Minta Pedagang Diprioritaskan*: https://semarang.bisnis.com/read/20220202/535/1496092/relokasi-pasar-johar-terbakar-ganjar-minta-pedagang-diprioritaskan
- ANTARA Jateng, *Kerumunan warga sulitkan pemadaman kebakaran Pasar Johar relokasi*: https://jateng.antaranews.com/berita/431073/kerumunan-warga-sulitkan-pemadaman-kebakaran-pasar-johar-relokasi

## Penyesuaian dengan gambar peta

File `data/pasar_johar_demo.yaml` sekarang menggunakan titik awal **Pos Pemadam Barito** dan tujuan **titik kebakaran utama Pasar Johar Relokasi, Blok F**, sesuai gambar yang diberikan. Graf berisi 10 node dan 10 ruas (edge): rute utama dibuat berjumlah sekitar 9 menit dan rute alternatif lewat jalan lingkungan sisi barat sekitar 10 menit, mengikuti angka durasi yang tampak pada screenshot. Event penutupan diarahkan ke ruas akses masuk yang diberi lingkaran pada anotasi, lalu algoritma mencari rute alternatif lewat ruas sisi barat.

**Batas validitas data:** berita mendukung fakta bahwa kerumunan menghambat akses, dan screenshot mendukung asal, tujuan, perkiraan durasi, serta sketsa hambatan/jalur alternatif. Namun, screenshot resolusinya terbatas. Konektivitas graf dan pembagian bobot ke tiap ruas adalah **model demonstrasi**, bukan pengukuran GIS atau waktu aktual setiap ruas. Nama Jl. Pelabuhan Ratu pada anotasi juga perlu dikonfirmasi dari peta yang lebih jelas. Untuk laporan final, tim B perlu memeriksa edge satu per satu pada peta sumber lalu memperbarui YAML bila diperlukan.

## Skenario utama: jaringan jalan asli di sekitar lokasi berita (31 node)

`data/pasar_johar_damkar.yaml` adalah skenario default. Node dan ruasnya diambil dari jaringan jalan **nyata** di sekitar lokasi kebakaran (OpenStreetMap lewat Overpass API, ekstraksi 2026-11-10), bukan dari garis screenshot:

- **Titik awal**: Dinas Pemadam Kebakaran Kota Semarang, Jl. Madukoro III, Krobokan, Semarang Barat (`-6.9786498, 110.4005843`).
- **Titik tujuan**: akses Relokasi Pasar Johar di pertigaan Jl. Barito × Jl. Tirtoyoso V, Sambirejo, Gayamsari (`-6.9787493, 110.4411586`).
- **31 node simpang asli** — tiap node menyimpan `lat`, `lon`, dan `osm_node` (ID OpenStreetMap) sebagai jejak peta.
- **33 ruas bernama jalan** — field `road` berisi nama jalan persis hasil ekstraksi (mis. `Jl. Pandanaran`, `Jl. Indraprasta`), sehingga output simulasi menyebut jalan mana saja yang dilalui damkar.
- **Bobot** = jarak peta dibagi kecepatan model (jalan utama 35, sekunder 30, permukiman 20 km/jam) → satuan **menit estimasi**, bukan waktu tempuh terukur.

Hasil Dijkstra pada jaringan ini:

| | Koridor | Bobot | Ruas |
|---|---|---|---|
| Rute awal | Jl. Madukoro → Cokrokembang → Jenderal Sudirman → MGR Soegiyopranoto → Dokter Sutomo → Pandanaran → Kyai Saleh → Pekunden → Batan Selatan → Mayjend D.I. Panjaitan → Kartini → **Barito** (utara) | 10,74 menit | 14 |
| Rute alternatif (setelah akses Jl. Barito, `e14`, ditutup kerumunan) | Jl. Madukoro → Jenderal Sudirman → Indraprasta → Kapten Piere Tendean → Pemuda → Depok → KH. Wahid Hasyim → Gang Warung → Pekojan → Petudungan → M.T. Haryono → Dargo → Dokter Cipto → Bugangan → Kanalsari → **Tirtoyoso** (selatan) | 11,93 menit | 17 |

Penutupan `e14` dimodelkan sebagai akses utara Jl. Barito yang terputus oleh kerumunan — sesuai berita bahwa akses jalan menuju pasar macet dan menghambat damkar. Selisih rute: **+1,19 menit estimasi**.

Sumber berita:
- Bisnis.com, *Relokasi Pasar Johar Terbakar, Ganjar Minta Pedagang Diprioritaskan*: https://semarang.bisnis.com/read/20220202/535/1496092/relokasi-pasar-johar-terbakar-ganjar-minta-pedagang-diprioritaskan
- ANTARA Jateng, *Kerumunan warga sulitkan pemadaman kebakaran Pasar Johar relokasi*: https://jateng.antaranews.com/berita/431073/kerumunan-warga-sulitkan-pemadaman-kebakaran-pasar-johar-relokasi

Skenario lama berbasis screenshot (`data/pasar_johar_demo.yaml`, 10 node) tetap tersedia lewat `--scenario data/pasar_johar_demo.yaml`.

## Struktur proyek

```text
pathfinding_c/
├── data/
│   ├── pasar_johar_damkar.yaml    # SKENARIO DEFAULT:31 node dari jaringan jalan asli (OSM)
│   └── pasar_johar_demo.yaml      # skenario lama berbasis screenshot (10 node)
├── src/pathfinding/
│   ├── graph.py                # adjacency list berbobot
│   ├── dijkstra.py             # Dijkstra baseline dan reroute setelah penutupan
│   ├── io.py                   # YAML loader
│   ├── simulation.py           # run_simulation dan CLI
│   └── benchmark.py            # pengukuran waktu eksekusi
├── tests/test_dijkstra.py      # unit test dan test khusus kasus Pasar Johar
├── pyproject.toml
├── requirements.txt
└── requirements-dev.txt
```

## Menjalankan di Windows

Dari root folder proyek:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python -m pip install -e .
python -m pathfinding.simulation                                  # skenario default:31 node jalan asli
python -m pathfinding.simulation --scenario data/pasar_johar_demo.yaml   # skenario demo lama
python -m pytest -v
python -m pathfinding.benchmark --repeats 1000
```

Jika PowerShell memblokir aktivasi, jalankan perintah memakai `.venv\Scripts\python.exe`.

## Menjalankan di Linux / WSL

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m pip install -e .
python -m pathfinding.simulation                                  # skenario default:31 node jalan asli
python -m pathfinding.simulation --scenario data/pasar_johar_demo.yaml   # skenario demo lama
python -m pytest -v
python -m pathfinding.benchmark --repeats 1000
```

## Tampilan output terminal

Output `python -m pathfinding.simulation` disusun menjadi beberapa bagian: informasi kasus, konfigurasi titik awal/tujuan, rute awal, event penutupan, rute alternatif, ringkasan perbandingan, dan catatan validitas data. Setiap langkah rute menampilkan label lokasi, ID ruas, **nama jalan**, dan bobot estimasinya; setiap rute ditutup blok **`JALUR DAMKAR`** yang merangkum urutan jalan yang dilalui kendaraan (contoh: `Jl. Madukoro V -> Jl. Cokrokembang -> Jl. Pandanaran -> ... -> Jl. Barito`). Tidak ada dependensi tambahan untuk pemformatan terminal.

Contoh ringkasan output (skenario demo `pasar_johar_demo.yaml`):

```text
PATHFINDING C  |  DIJKSTRA ENGINE BASE
Lokasi  : Relokasi Pasar Johar, kawasan MAJT, Semarang
Tanggal : 2 Februari 2022
Graf    : 10 node | 10 ruas

01  RUTE AWAL
  Total bobot : 9 menit estimasi
  Jumlah ruas : 6

EVENT: AKSES JALAN TERHAMBAT
  ID ruas : e05

02  RUTE ALTERNATIF
  Total bobot : 10 menit estimasi
  Jumlah ruas : 7

RINGKASAN HASIL
  Perubahan bobot total : +1 menit estimasi
  Status                : Rute alternatif berhasil ditemukan
```

## Cara kerja simulasi

Skenario default (`pasar_johar_damkar.yaml`):

1. Dijkstra menghitung rute awal dari Dinas Pemadam Kebakaran Kota Semarang (Jl. Madukoro III) ke akses Relokasi Pasar Johar — koridor utara lewat Jl. Pandanaran/Panjaitan/Kartini/Barito, 10,74 menit estimasi.
2. Simulasi menutup edge `e14` (Jl. Barito, ruas simpang Kartini → pasar) sebagai model akses utara yang terputus oleh kerumunan, sesuai berita.
3. Dijkstra dijalankan kembali dengan edge tersebut dikecualikan; rute alternatif lewat koridor selatan (Jl. Indraprasta → Pemuda → Petudungan → Dargo → Bugangan → Kanalsari → Tirtoyoso) dibandingkan dengan rute awal: 11,93 menit, selisih +1,19 menit.
4. Benchmark mengukur waktu eksekusi lokal untuk mencatat baseline.

Skenario demo (`pasar_johar_demo.yaml`, lewat `--scenario`) memakai pola yang sama: rute awal 9 menit, penutupan `e05`, rute alternatif sisi barat 10 menit.

Penutupan dikerjakan sebagai larangan melewati edge, bukan membuat bobotnya sekadar besar. Penghitungan ulang di sini adalah Dijkstra baseline, **bukan D* Lite**; hal itu memungkinkan anggota D membandingkan algoritma dinamis dengan baseline C.

## Kontrak data untuk anggota B dan D

- Node memuat `id` dan `label` (skenario damkar menambah `lat`, `lon`, `osm_node` sebagai referensi peta; field tambahan diabaikan loader).
- Edge memuat `id`, `from`, `to`, `weight`, dan opsional `road`/`directed` (skenario damkar menambah `distance_m`).
- `weight` harus non-negatif. Dalam YAML kasus ini, satuannya menit estimasi untuk keseluruhan rute, tetapi distribusi per ruas masih simulatif.
- Anggota B dapat mengganti node, ruas, arah, dan bobot tanpa mengubah fungsi Dijkstra.
- Anggota D dapat memakai model graf yang sama untuk implementasi D* Lite dan mengukur perbandingannya dengan baseline.
