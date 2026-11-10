# Analisis Studi Kasus — Akses Damkar ke Kebakaran Pasar Johar Relokasi

Dokumen ini adalah **COMMIT 1** pengembangan tugas: analisis sumber berita, batas
fakta, rancangan node/edge, dan keputusan jenis graf. Kode dan dataset belum
diubah pada tahap ini.

## 1. Peristiwa dan sumber berita

| Hal | Keterangan |
|---|---|
| Peristiwa | Kebakaran di tempat relokasi Pasar Johar, kawasan Masjid Agung Jawa Tengah (MAJT), Semarang |
| Tanggal | Rabu, 2 Februari 2022 (malam) |
| Sumber 1 | Bisnis.com — *Relokasi Pasar Johar Terbakar, Ganjar Minta Pedagang Diprioritaskan* — https://semarang.bisnis.com/read/20220202/535/1496092/relokasi-pasar-johar-terbakar-ganjar-minta-pedagang-diprioritaskan |
| Sumber 2 | ANTARA Jawa Tengah — *Kerumunan warga sulitkan pemadaman kebakaran Pasar Johar relokasi* — https://jateng.antaranews.com/berita/431073/kerumunan-warga-sulitkan-pemadaman-kebakaran-pasar-johar-relokasi |

Kedua artikel dibaca langsung saat penyusunan dokumen ini (bukan kutipan
ulang dari file lain).

## 2. Fakta yang dipakai dari berita

Dikutip atau diparafrase dari dua sumber di atas:

- Kebakaran melanda tempat relokasi Pasar Johar di kawasan MAJT pada Rabu
  (2/2/2022) malam; api membakar kios di **blok F** (Bisnis.com: "puluhan kios
  yang ada di blok F"; ANTARA: titik api pada bagian **F1 sampai F9** hingga
  pukul 21.30 WIB).
- **Kerumunan warga** yang menonton membuat jalanan macet, termasuk
  **akses jalan menuju Pasar Johar Relokasi**, sehingga pemadaman menyulitkan
  petugas dan akses kendaraan damkar terganggu (dua-duanya menyebut hal ini).
- Petugas **Dinas Pemadam Kebakaran Kota Semarang** bersama sukarelawan
  berteriak meminta warga tidak memadati jalan yang menjadi akses kendaraan
  damkar menuju titik kebakaran (ANTARA).
- Ganjar Pranowo menegur warga yang menutup akses jalan:
  *"Minggir mas, ini buat jalan pemadam kebakaran … ayo semua minggir"*
  (kedua sumber).
- Ganjar menyatakan pemadam kebakaran sudah dikerahkan bersama kepolisian
  (Bisnis.com). **Jumlah unit dan jumlah petugas tidak disebutkan.**

## 3. Batas fakta: apa yang TIDAK tersedia dalam sumber berita

Hal-hal berikut **tidak tersedia dalam sumber berita** dan karena itu tidak
boleh ditulis sebagai fakta maupun diam-diam dimasukkan ke dataset:

- jumlah unit mobil pemadam yang dikerahkan;
- jumlah petugas / personel;
- waktu kedatangan mobil pertama ke lokasi;
- waktu pemadaman selesai (selain fakta api masih menyala pukul 21.30 WIB);
- kapasitas air, jumlah hidran, kondisi pompa, isi hydrant box, selang, nozzle;
- lebar jalan, kapasitas lalu lintas, sinyal lampu lalu lintas;
- koordinat GPS titik pos pemadam, titik kebakaran, dan persimpangan;
- nama ruas jalan yang macet (berita hanya mengatakan "akses jalan menuju
  pasar"), waktu tempuh per ruas, dan aturan satu arah yang berlaku saat itu;
- penyebab kebakaran.

**Yang berasal dari peta/screenshot, bukan berita:** titik awal (Pos Pemadam
Barito / Dinas Pemadam Kebakaran Kota Semarang di Jl. Madukoro III), titik
tujuan (akses Pasar Johar), urutan ruas jalan, serta angka durasi rute. Berita
hanya mendukung fakta bahwa **kerumunan menghambat akses** — itu dasar event
penutupan ruas dalam simulasi.

## 4. Rancangan node dan edge

### 4.1 Node (vertex)

Node = titik jaringan yang dilalui, menjadi titik keputusan, atau titik tujuan
perjalanan damkar. Node **bukan** atribut fasilitas (kapasitas air, pompa,
selang, durasi pemadaman, spesifikasi kendaraan) dan bukan daftar fasilitas
pemadam.

Skenario default `data/pasar_johar_damkar.yaml` (31 node) memakai pola peran:

| Peran | Contoh node |
|---|---|
| Titik keberangkatan | `pos_damkar_madukoro` — Dinas Pemadam Kebakaran Kota Semarang, Jl. Madukoro III |
| Koridor keluar | `simpang_madukoro_v`, `simpang_madukoro_cokrokembang` |
| Persimpangan penghubung koridor | `simpang_cokrokembang_sudirman`, `simpang_sudirman_soegiyopranoto`, `simpang_panjaitan_haryono` |
| Persimpangan pendekat pasar | `simpang_kartini_barito`, `simpang_barito_tirtoyoso`, `simpang_kanalsari_tirtoyoso` |
| Titik akses yang terhambat | `simpang_kartini_barito` → ruas `e14` (Jl. Barito) ditutup kerumunan |
| Jalur alternatif sisi selatan | `simpang_indraprasta_tendean` … `simpang_bugangan_kanalsari` |
| Titik tujuan | `pasar_johar_relokasi` — akses Relokasi Pasar Johar |

Node disimpan dengan `id`, `label`, plus `lat`, `lon`, `osm_node` sebagai jejak
peta. Node skenario lama `data/pasar_johar_demo.yaml` (10 node, berbasis
screenshot) memakai nama deskriptif karena lokasinya belum terverifikasi.

### 4.2 Edge (sisi)

Edge = ruas jalan yang menghubungkan dua node dan dapat dilalui damkar, dengan
field: `id` unik, `from`, `to`, `weight`, `road` (nama ruas), dan opsional
`distance_m`. Skema kontrak untuk anggota tim lain (node `id`+`label`, edge
`id`+`from`+`to`+`weight`+opsional `road`/`directed`) **tidak diubah**.

### 4.3 Bobot

- Satuan tunggal: **menit estimasi** untuk seluruh skenario.
- Skenario damkar: `weight = distance_m / (kecepatan model) × 60`, kecepatan
  model 35 km/jam (jalan utama), 30 (sekunder), 20 (permukiman).
- Skenario demo: bobot dibagi agar total rute sejalan dengan label 9 menit dan
  10 menit pada screenshot.
- Angka ini **bukan** pengukuran lalu lintas aktual, bukan waktu tempuh pada
  2 Februari 2022, dan tidak boleh dilaporkan sebagai hasil pengukuran.
- Jarak (`distance_m`) dan waktu (menit) **tidak dicampur** dalam satu
  perhitungan shortest path; `distance_m` hanya disimpan sebagai referensi.

## 5. Keputusan jenis graf: TIDAK BERARAH (dua arah), dengan keterbatasan terdokumentasi

Prompt bagian C.4 menuntut keputusan yang mempertimbangkan aturan lalu lintas
dan melarang asumsi "semua jalan dua arah" tanpa verifikasi. Karena itu aturan
satu arah **diverifikasi sungguhan** terhadap OpenStreetMap memakai
`tools/validasi_peta.py` (Overpass API, ekstraksi 2026-11-10):

| Pemeriksaan | Hasil |
|---|---|
| Node ada di OSM + koordinat cocok | **31/31 node** |
| Nama ruas edge cocok dengan nama jalan OSM | **28/28 nama ruas** |
| Edge yang berada di ruas benar-benar dua arah | **14/33** |
| Edge di ruas satu arah, searah dengan orientasi penyimpanan `from`→`to` | **11/33** (e11, e12, e13, e19, e21, e22, e23, e24, e26, e28, e30) |
| Edge di ruas satu arah, **berlawanan** dengan orientasi penyimpanan | **6/33** (e05, e06, e07, e08, e27, e29) |
| Campuran antar segmen (perlu cek manual) | **2/33** (e20, e25) |

Jadi asumsi "semua jalan dua arah" memang **tidak benar**. Namun penerapan
lurus aturan satu arah ke graf tersederhanakan ini diuji lebih dulu lewat
`tools/eksperimen_arah.py` dan hasilnya:

> Dengan 19 edge diarahkan mengikuti OSM, **tidak ada rute sama sekali** dari
> `pos_damkar_madukoro` ke `pasar_johar_relokasi` — baik rute awal maupun
> rute alternatif. Penyebabnya: kedua koridor putus pada choke point
`e08` (Jl. Pandanaran) dan `e27` (Jl. Gang Warung–Pekojan) yang di OSM
berlaku satu arah, sementara graf 31-node ini tidak memuat simpang-simpang
pemutar yang diperlukan untuk memutar balik secara legal.

**Keputusan:** graf tetap dimodelkan **tidak berarah (dua arah)** sebagai
penyederhanaan yang **ditandai eksplisit**, bukan sebagai klaim bahwa jalan
tersebut dua arah. Alasan:

1. Menerapkan aturan satu arah apa adanya membuat jaringan **putus**, sehingga
   skenario rute damkar tidak dapat dijalankan sama sekali.
2. Data OSM yang dipakai adalah kondisi **2026-11-10**, bukan aturan lalu lintas
   pada 2 Februari 2022; berita tidak menyebut arah lalu lintas apa pun.
3. Perbaikan yang benar memerlukan jaringan tingkat persimpangan yang jauh
   lebih lengkap (semua simpang pemutar) plus verifikasi peta/observasi —
   yang tercatat sebagai pekerjaan verifikasi, bukan sesuatu yang boleh
   dikarang.

Loader (`src/pathfinding/io.py`) **sudah mendukung** `directed: true` per edge,
sehingga koreksi arah dapat diterapkan per ruas tanpa mengubah kontrak kode
setelah verifikasi selesai. Pilihan ini didokumentasikan di sini sesuai
tuntutan bagian C.4: keputusannya dijelaskan, bukan dianggap remeh.

## 6. Lokasi, validasi, dan apa yang masih perlu diverifikasi

Terverifikasi (dapat diulang dengan `python tools/validasi_peta.py`):

- Seluruh `osm_node` dan koordinat pada skenario damkar cocok dengan OSM.
- Seluruh nama ruas pada edge cocok dengan nama jalan di OSM.

Belum terverifikasi / perlu pemeriksaan manual (Google Maps, peta resmi, atau
observasi lapangan):

- aturan satu arah per segmen yang berlaku pada 2 Februari 2022;
- apakah 31 simpang sudah mewakili seluruh simpang yang diperlukan damkar
  (termasuk simpang pemutar untuk jalan satu arah);
- posisi persimpangan persis untuk laporan final (koordinat sudah ada, tapi
  belum dicek satu per satu pada peta resmi);
- nama "Jl. Pelabuhan Ratu" pada skenario demo (anotasi screenshot, resolusi
  terbatas);
- topologi dan pembagian bobot skenario demo (10 node) yang masih model
  demonstrasi berbasis screenshot.

Graf ini **bukan** representasi GIS presisi dan tidak boleh dipresentasikan
sebagai hasil survei lapangan.

## 7. Rencana tahapan commit

Pengembangan dilakukan bertahap, tiap tahap di-commit terpisah sesuai prompt:

1. `docs:` analisis studi kasus — dokumen ini, plus alat validasi.
2. `data:` penyesuaian node/edge dataset (catatan sumber, kelas jalan, status akses).
3. `feat:` validasi struktur graf (duplikasi ID, bobot, referensi node, start/goal).
4. `feat:` algoritma dan skenario rute (rincian edge per rute, skenario tanpa alternatif).
5. `feat:` penyempurnaan tampilan simulasi (daftar node/edge, sumber berita).
6. `test:` + `docs:` pengujian dan dokumentasi akhir.
