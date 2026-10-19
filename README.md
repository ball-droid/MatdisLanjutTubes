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

## Struktur proyek

```text
pathfinding_c/
├── data/pasar_johar_demo.yaml  # graf dan skenario berbasis berita/peta
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
python -m pathfinding.simulation
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
python -m pathfinding.simulation
python -m pytest -v
python -m pathfinding.benchmark --repeats 1000
```

## Cara kerja simulasi

1. Dijkstra menghitung rute awal dari Pos Pemadam Barito ke titik kebakaran.
2. Simulasi menutup edge `e05`, yang dipilih sebagai pendekatan model terhadap akses masuk yang terhambat pada anotasi peta.
3. Dijkstra dijalankan kembali dengan edge tersebut dikecualikan, dan rute alternatif melalui sisi barat dibandingkan dengan rute awal.
4. Benchmark mengukur waktu eksekusi lokal untuk mencatat baseline.

Penutupan dikerjakan sebagai larangan melewati edge, bukan membuat bobotnya sekadar besar. Penghitungan ulang di sini adalah Dijkstra baseline, **bukan D* Lite**; hal itu memungkinkan anggota D membandingkan algoritma dinamis dengan baseline C.

## Kontrak data untuk anggota B dan D

- Node memuat `id` dan `label`.
- Edge memuat `id`, `from`, `to`, `weight`, dan opsional `road`/`directed`.
- `weight` harus non-negatif. Dalam YAML kasus ini, satuannya menit estimasi untuk keseluruhan rute, tetapi distribusi per ruas masih simulatif.
- Anggota B dapat mengganti node, ruas, arah, dan bobot tanpa mengubah fungsi Dijkstra.
- Anggota D dapat memakai model graf yang sama untuk implementasi D* Lite dan mengukur perbandingannya dengan baseline.
