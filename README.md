# Rute Mobil Damkar ke Kebakaran Pasar Johar Relokasi — Model Graf, Dijkstra & A\*

Kode Python untuk tanggung jawab C: mesin pencari rute baseline Dijkstra,
algoritma pembanding **A\***, pembacaan
skenario YAML, `run_simulation()`, pengujian Pytest, dan benchmark. Struktur
modularnya mengambil inspirasi dari
[trisgelar/matdis-tubes-2026](https://github.com/trisgelar/matdis-tubes-2026),
terutama pemisahan algoritma, model graf, konfigurasi kasus, test, dan runner.

Analisis lengkap sumber berita, batas fakta, rancangan node/edge, dan keputusan
jenis graf ada di [`docs/analisis_studi_kasus.md`](docs/analisis_studi_kasus.md).

## 1. Latar belakang studi kasus

Pada Rabu, 2 Februari 2022 malam, kebakaran melanda tempat relokasi Pasar
Johar di kawasan Masjid Agung Jawa Tengah (MAJT), Semarang. Bisnis.com
melaporkan api membakar kios di blok F; ANTARA Jawa Tengah mencatat titik api
masih terlihat pada bagian F1–F9 hingga pukul 21.30 WIB.

Fakta inti yang dipakai proyek ini (dari kedua sumber, bukan dari karangan):

- **Kerumunan warga** yang menonton membuat jalanan macet, termasuk
  **akses jalan menuju Pasar Johar Relokasi**, sehingga pemadaman menyulitkan
  petugas dan kendaraan damkar sulit menembus.
- Petugas Dinas Pemadam Kebakaran Kota Semarang bersama sukarelawan berteriak
  meminta warga tidak memadati jalan yang menjadi akses kendaraan damkar.
- Ganjar Pranowo menegur warga yang menutup akses jalan:
  *"Minggir mas, ini buat jalan pemadam kebakaran … ayo semua minggir."*

## 2. Mengapa studi kasus ini relevan dengan akses mobil Damkar

Kebakaran tidak berhenti pada fakta kebakaran; masalah operasionalnya adalah
**akses**. Berita menyebut hambatannya adalah kerumunan yang memadati jalan
akses, bukan kerusakan kendaraan atau kehabisan air. Karena itu permasalahan
yang tepat dimodelkan adalah **masalah rute pada graf jaringan jalan**: bila
satu ruas akses terputus, apakah masih ada jalur lain yang dapat dilalui
damkar, dan berapa selisih beban rutenya? Persis itu yang dihitung program ini.

## 3. Tujuan pemodelan graf

1. Memodelkan jaringan jalan yang dilalui mobil damkar dari **pos pemadam**
   menuju **titik kebakaran** sebagai graf berbobot `G = (V, E)`.
2. Menghitung rute terpendek dengan **Dijkstra** (baseline).
3. Mensimulasikan **hambatan akses akibat kerumunan** dengan menutup sebuah
   ruas, lalu menghitung ulang rute alternatif dan membandingkannya.
4. Menyajikan hasil yang dapat dipresentasikan, dengan status validitas data
   yang terbuka: mana fakta berita, mana model simulasi.

## 4. Konsep matematis yang dipakai

- **Graf berbobot `G = (V, E)`** — `V` himpunan vertex/node lokasi, `E`
  himpunan edge/ruas jalan.
- **Fungsi bobot `w(e) ≥ 0`** — estimasi waktu (menit) untuk menempuh ruas `e`.
- **Jalur `p = (v₀, v₁, …, v_k)`** — urutan vertex yang saling terhubung oleh
  edge; bobot jalur `W(p) = Σ w(vᵢ, vᵢ₊₁)`.
- **Shortest path** — jalur dengan `W(p)` minimum dari `start` ke `goal`.
- **Dijkstra** — dipakai karena seluruh bobot non-negatif; program menolak bobot
  negatif maupun `NaN`/`inf` sejak data dimuat.
- **A\*** (pembanding) — kunci prioritas `f(n) = g(n) + h(n)` dengan heuristik
  haversine `h(n) = jarak lurus / kecepatan model terbesar (35 km/jam)`,
  yang admissible sehingga biaya rute dijamin sama dengan Dijkstra. Rincian
  dan hasil perbandingannya ada di bagian 19.
- **Penutupan edge** — ruas dikeluarkan dari `E` untuk pencarian tertentu
  (`blocked_edges`), **bukan** bobotnya diganti angka besar. Ini mewakili
  akses yang tidak dapat dilalui.

Contoh konkret pada data yang dipakai (bukan definisi umum): dengan
`w(e12) = 2,65` menit (Jl. Mayjend. D.I. Panjaitan, 1545 m) dan
`w(e13) = 1,56` menit (Jl. Kartini, 911 m), rute awal
`pos_damkar_madukoro → … → simpang_batan_panjaitan → simpang_panjaitan_haryono
→ simpang_kartini_barito → simpang_barito_tirtoyoso → pasar_johar_relokasi`
memiliki `W(p) = 10,74` menit dari total 14 ruas.

## 5. Definisi node dan edge yang dipakai

**Node (vertex)** = titik jaringan yang dapat dilalui, menjadi titik keputusan,
atau titik tujuan perjalanan damkar: pos pemadam, koridor keluar pos,
persimpangan penghubung, persimpangan pendekat pasar, dan titik akses pasar.
Node tetap **bukan** tempat menyimpan hal operasional murni (kapasitas air,
tekanan pompa, jumlah selang, durasi pemadaman, spesifikasi kendaraan); yang
kini boleh menempel pada node adalah **fasilitas lokasi**: hydrant sebagai
sumber air isi ulang, identitas kantor polisi, dan kantor damkar beserta
armada/personelnya untuk logistik. Rinciannya di bagian 20.

Field node: `id`, `label`, dan pada skenario damkar juga `lat`, `lon`,
`osm_node`/`osm_way` (ID elemen OpenStreetMap) sebagai jejak peta, serta
opsional `hydrant` dan `facility` (bagian 20).

**Edge (sisi)** = ruas jalan yang menghubungkan dua node dan dapat dilalui
damkar. Field edge: `id` unik, `from`, `to`, `weight`, `road` (nama ruas),
opsional `directed`, `distance_m`, dan `access_status` (status akses/hambatan
untuk ruas yang menjadi objek penutupan).

## 6. Daftar node dan alasan pemilihannya

Skenario default `data/pasar_johar_damkar.yaml` — 34 node (31 simpang jalan
asli + 3 kantor pemadam tambahan sebagai node logistik; fasilitas node ada di
bagian 20). "Peran" di bawah
dihitung dari hasil Dijkstra pada skenario ini (rute awal dan rute alternatif).

| # | id | label | peran | osm_node |
|---|---|---|---|---|
| 1 | pos_damkar_madukoro | Dinas Pemadam Kebakaran Kota Semarang (Jl. Madukoro III) | **titik awal**, kedua rute | 1919923494 |
| 2 | simpang_madukoro_v | Simpang Jl. Madukoro V × Jl. Madukoro III | koridor keluar pos, kedua rute | 1919937330 |
| 3 | simpang_madukoro_cokrokembang | Simpang Jl. Madukoro III × Jl. Cokrokembang | cabang barat, rute awal | 5428067515 |
| 4 | simpang_madukoro_east | Simpang Jl. Madukoro III × Jl. Madukoro | cabang timur, rute alternatif | 4933637574 |
| 5 | simpang_cokrokembang_sudirman | Simpang Jl. Cokrokembang × Jl. Jenderal Sudirman | persimpangan koridor utara, rute awal | 1919937382 |
| 6 | simpang_sudirman_soegiyopranoto | Simpang Jl. Jenderal Sudirman × Jl. MGR Soegiyopranoto | rute awal | 79761962 |
| 7 | simpang_soegiyopranoto_sutomo | Simpang Jl. MGR Soegiyopranoto × Jl. Dokter Sutomo | rute awal | 79761957 |
| 8 | simpang_sutomo_pandanaran | Simpang Jl. Dokter Sutomo × Jl. Pandanaran | rute awal | 2436108658 |
| 9 | simpang_pandanaran_kyaisaleh | Simpang Jl. Pandanaran × Jl. Kyai Saleh | rute awal | 7119000260 |
| 10 | simpang_kyaisaleh_pekunden | Simpang Jl. Kyai Saleh × Jl. Pekunden | rute awal | 7119000261 |
| 11 | simpang_pekunden_batan | Simpang Jl. Pekunden × Jl. Batan Selatan | rute awal | 259668137 |
| 12 | simpang_batan_panjaitan | Simpang Jl. Batan Selatan × Jl. Mayjend D.I. Panjaitan | rute awal | 257094446 |
| 13 | simpang_panjaitan_haryono | Simpang Jl. Mayjend D.I. Panjaitan × Jl. Kartini × Jl. M.T. Haryono | percabangan ke koridor selatan, rute awal | 79428875 |
| 14 | simpang_kartini_barito | Simpang Jl. Kartini × Jl. Barito | pendekat pasar; **titik hambatan** (ruas `e14`) | 1280109874 |
| 15 | simpang_barito_tirtoyoso | Simpang Jl. Barito × Jl. Tirtoyoso XI | akses utara pasar, rute awal | 2087600727 |
| 16 | simpang_tirtoyoso_xi | Simpang Jl. Tirtoyoso XI × Jl. Tirtoyoso Batas | akses timur pasar (cadangan; tidak dilalui kedua rute pada skenario ini) | 3230310749 |
| 17 | simpang_tirtoyoso_batas | Simpang Jl. Tirtoyoso Batas × Jl. Tirtoyoso V | akses selatan pasar, rute alternatif | 3230310693 |
| 18 | simpang_madukoro_sudirman | Simpang Jl. Madukoro × Jl. Jenderal Sudirman | rute alternatif | 2436172328 |
| 19 | simpang_sudirman_soegiyopranoto2 | Simpang Jl. Jenderal Sudirman × Jl. MGR Soegiyopranoto (sisi timur) | rute alternatif | 257678727 |
| 20 | simpang_soegiyopranoto_indraprasta | Simpang Jl. MGR Soegiyopranoto × Jl. Indraprasta | mulai koridor selatan, rute alternatif | 257678730 |
| 21 | simpang_indraprasta_tendean | Simpang Jl. Indraprasta × Jl. Kapten Piere Tendean | rute alternatif | 257678742 |
| 22 | simpang_tendean_pemuda | Simpang Jl. Kapten Piere Tendean × Jl. Pemuda | rute alternatif | 257678747 |
| 23 | simpang_depok_wahidhasyim | Simpang Jl. Depok × Jl. KH. Wahid Hasyim | rute alternatif | 257677223 |
| 24 | simpang_wahidhasyim_warung | Simpang Jl. KH. Wahid Hasyim × Jl. Gang Warung | rute alternatif | 257677315 |
| 25 | simpang_pekojan_petudungan | Simpang Jl. Pekojan × Jl. Petudungan | rute alternatif | 266525253 |
| 26 | simpang_petudungan_haryono | Simpang Jl. Petudungan × Jl. M.T. Haryono | rute alternatif | 79428883 |
| 27 | simpang_haryono_dargo | Simpang Jl. M.T. Haryono × Jl. Dargo | percabangan, rute alternatif | 2354309967 |
| 28 | simpang_cipto_bugangan | Simpang Jl. Dokter Cipto × Jl. Bugangan | rute alternatif | 1315839987 |
| 29 | simpang_bugangan_kanalsari | Simpang Jl. Bugangan × Jl. Kanalsari Barat I | rute alternatif | 7284165786 |
| 30 | simpang_kanalsari_tirtoyoso | Simpang Jl. Kanalsari Raya × Jl. Tirtoyoso Batas | rute alternatif | 5430893265 |
| 31 | pasar_johar_relokasi | Akses Relokasi Pasar Johar (Jl. Barito × Jl. Tirtoyoso V) | **tujuan**, kedua rute | 2087600687 |
| 32 | pos_damkar_tambahan_barat | Pos Pemadam Kebakaran (OSM tanpa nama, way 1338307869) | node logistik; 2 mobil, 8 personel (asumsi model) | way 1338307869 |
| 33 | pos_damkar_tambahan_utara | Pos Pemadam Kebakaran (OSM tanpa nama, way 740895779) | node logistik; 2 mobil, 8 personel (asumsi model) | way 740895779 |
| 34 | pos_damkar_tambahan_walisongo | Kantor Pemadam Kebakaran (Jl. Walisongo) | node logistik; 3 mobil, 10 personel (asumsi model) | way 564500892 |

Alasan pemilihan: 31 simpang pertama adalah persimpangan nyata pada jalur yang
menghubungkan pos pemadam ke pasar (diverifikasi ada di OpenStreetMap dengan
koordinat cocok), sehingga seluruhnya berperan sebagai titik keputusan atau
titik lalulintas pada pencarian rute. Tiga node terakhir **bukan**
persimpangan: itu kantor pemadam sungguhan di OSM dalam radius 5 km dari
jaringan, dipakai sebagai simpul logistik (ambil mobil/personel) dan
dipasang sebagai cabang mati sehingga rute awal maupun alternatif tidak
berubah. Graf tetap **satu komponen**; setiap node terjangkau dari titik
awal dan dapat mencapai tujuan.

## 7. Daftar edge/ruas yang dimodelkan

36 ruas (33 ruas jalan + 3 koneksi kantor damkar, bagian 20). `w` = bobot (menit estimasi), `m` = panjang ruas menurut peta (meter).

| id | dari → ke | w | m | nama ruas |
|---|---|---|---|---|
| e01 | pos_damkar_madukoro → simpang_madukoro_v | 0,13 | 44 | Jl. Madukoro V |
| e02 | simpang_madukoro_v → simpang_madukoro_cokrokembang | 0,09 | 21 | Jl. Madukoro III |
| e03 | simpang_madukoro_v → simpang_madukoro_east | 0,40 | 99 | Jl. Madukoro III |
| e04 | simpang_madukoro_cokrokembang → simpang_cokrokembang_sudirman | 0,73 | 183 | Jl. Cokrokembang |
| e05 | simpang_cokrokembang_sudirman → simpang_sudirman_soegiyopranoto | 0,42 | 244 | Jl. Jendral Sudirman |
| e06 | simpang_sudirman_soegiyopranoto → simpang_soegiyopranoto_sutomo | 1,60 | 933 | Jl. MGR Soegiyopranoto – Jl. MGR. Sugiopranoto |
| e07 | simpang_soegiyopranoto_sutomo → simpang_sutomo_pandanaran | 0,07 | 40 | Jl. Dokter Sutomo |
| e08 | simpang_sutomo_pandanaran → simpang_pandanaran_kyaisaleh | 0,91 | 528 | Jl. Pandanaran |
| e09 | simpang_pandanaran_kyaisaleh → simpang_kyaisaleh_pekunden | 0,02 | 11 | Jl. Kyai Saleh |
| e10 | simpang_kyaisaleh_pekunden → simpang_pekunden_batan | 0,32 | 188 | Jl. Pekunden |
| e11 | simpang_pekunden_batan → simpang_batan_panjaitan | 0,66 | 388 | Jl. Batan Selatan |
| e12 | simpang_batan_panjaitan → simpang_panjaitan_haryono | 2,65 | 1545 | Jl. Mayjend. D.I. Panjaitan |
| e13 | simpang_panjaitan_haryono → simpang_kartini_barito | 1,56 | 911 | Jl. Kartini |
| e14 | simpang_kartini_barito → simpang_barito_tirtoyoso | 1,06 | 532 | Jl. Barito — **ruas hambatan kerumunan** |
| e15 | simpang_barito_tirtoyoso → simpang_tirtoyoso_xi | 0,29 | 96 | Jl. Tirtoyoso XI |
| e16 | simpang_tirtoyoso_xi → simpang_tirtoyoso_batas | 0,80 | 268 | Jl. Tirtoyoso Batas |
| e17 | simpang_tirtoyoso_batas → pasar_johar_relokasi | 0,62 | 208 | Jl. Tirtoyoso V |
| e18 | simpang_barito_tirtoyoso → pasar_johar_relokasi | 0,52 | 260 | Jl. Barito |
| e19 | simpang_panjaitan_haryono → simpang_haryono_dargo | 1,75 | 1021 | Jl. M.T. Haryono |
| e20 | simpang_madukoro_east → simpang_madukoro_sudirman | 0,48 | 234 | Jl. Madukoro – Jl. Madukoro I |
| e21 | simpang_madukoro_sudirman → simpang_sudirman_soegiyopranoto2 | 0,02 | 12 | Jl. Jendral Sudirman |
| e22 | simpang_sudirman_soegiyopranoto2 → simpang_soegiyopranoto_indraprasta | 0,23 | 132 | Jl. MGR Soegiyopranoto |
| e23 | simpang_soegiyopranoto_indraprasta → simpang_indraprasta_tendean | 1,83 | 1070 | Jl. Indraprasta |
| e24 | simpang_indraprasta_tendean → simpang_tendean_pemuda | 0,80 | 465 | Jl. Kapten Piere Tendean |
| e25 | simpang_tendean_pemuda → simpang_depok_wahidhasyim | 1,10 | 566 | Jl. Pemuda – Jl. MH. Thamrin – Jl. Depok |
| e26 | simpang_depok_wahidhasyim → simpang_wahidhasyim_warung | 1,07 | 535 | Jl. KH. Wahid Hasyim |
| e27 | simpang_wahidhasyim_warung → simpang_pekojan_petudungan | 0,85 | 416 | Jl. Gang Warung – Jl. Gang Pinggir – Jl. Pekojan |
| e28 | simpang_pekojan_petudungan → simpang_petudungan_haryono | 0,96 | 322 | Jl. Petudungan |
| e29 | simpang_petudungan_haryono → simpang_haryono_dargo | 0,33 | 193 | Jl. M.T. Haryono |
| e30 | simpang_haryono_dargo → simpang_cipto_bugangan | 0,99 | 466 | Jl. Dargo – Jl. Dokter Cipto |
| e31 | simpang_cipto_bugangan → simpang_bugangan_kanalsari | 0,60 | 298 | Jl. Bugangan |
| e32 | simpang_bugangan_kanalsari → simpang_kanalsari_tirtoyoso | 0,87 | 290 | Jl. Kanalsari Barat I – Jl. Kanalsari Raya |
| e33 | simpang_kanalsari_tirtoyoso → simpang_tirtoyoso_batas | 0,65 | 217 | Jl. Tirtoyoso Batas |
| e_log01 | pos_damkar_tambahan_barat → simpang_madukoro_cokrokembang | 11,57 | 3856 | koneksi model (nama jalan belum terverifikasi) |
| e_log02 | pos_damkar_tambahan_utara → pos_damkar_madukoro | 18,25 | 6084 | koneksi model (nama jalan belum terverifikasi) |
| e_log03 | pos_damkar_tambahan_walisongo → simpang_cokrokembang_sudirman | 14,32 | 4775 | Jl. Walisongo (koneksi model) |

Tiga edge `e_log*` adalah **koneksi model** kantor damkar ke node jaringan
terdekat: `m` diambil dari jarak rute mengemudi (OSRM, bukan jarak lurus),
bobotnya `m × 60 / (20 × 1000)` memakai kecepatan model permukiman, dan
keduanya dicatat apa adanya karena nama ruas penghubung belum terverifikasi.
Edge ini bertanda `connection: model` di YAML, tidak ikut pencocokan nama
ruas maupun audit arah, dan karena bercabang mati tidak memengaruhi rute.

Skenario demo lama (`data/pasar_johar_demo.yaml`, 10 node / 10 ruas) tetap
tersedia dan memakai penamaan deskriptif karena lokasinya belum terverifikasi.

## 8. Sumber dan satuan bobot

- **Satuan: menit estimasi** untuk seluruh skenario. Jarak (`distance_m`) dan
  waktu **tidak dicampur** dalam satu perhitungan; `distance_m` hanya referensi.
- **Rumus**: `menit = distance_m × 60 / (kecepatan_km_per_jam × 1000)`,
  dengan kecepatan model nominal **utama 35, sekunder 30, permukiman 20 km/jam**.
- Enam ruas (`e02`, `e03`, `e04`, `e25`, `e27`, `e30`) bobotnya menyimpang
  sedikit dari kecepatan nominal (kecepatan tersirat 14–31 km/jam, selisih
  maksimal 0,06 menit). Penyimpangan dicatat di metadata YAML agar dapat
  ditinjau — bukan dikoreksi diam-diam, karena tidak ada pengukuran waktu
  tempuh yang menjadi rujukan.
- Skenario demo memakai total rute 9 menit dan 10 menit sesuai angka pada
  screenshot; distribusi per ruas adalah pembagian simulatif.

## 9. Jenis graf: keputusan arah

Model memakai **graf tidak berarah (dua arah)** sebagai penyederhanaan yang
dokumentatif, bukan klaim bahwa seluruh jalan dua arah. Pemeriksaan nyata
terhadap OpenStreetMap (`tools/validasi_peta.py`, ekstraksi 2026-11-10)
menghasilkan:

| Pemeriksaan | Hasil |
|---|---|
| Node ada di OSM + koordinat cocok | 31/31 |
| Nama ruas cocok dengan nama jalan OSM | 28/28 |
| Edge di ruas yang benar-benar dua arah | 14/33 |
| Edge di ruas satu arah | 19/33 |

Penerapan aturan satu arah apa adanya diuji dengan `tools/eksperimen_arah.py`:
rute awal maupun alternatif **putus total** (kedua koridor terhambat pada
`e08` Jl. Pandanaran dan `e27` Jl. Gang Warung–Pekojan), karena graf 31-node
ini belum memuat seluruh simpang pemutar yang diperlukan. Karena itu arah
dipertahankan dua arah, keputusannya dicatat di metadata YAML dan di
[`docs/analisis_studi_kasus.md`](docs/analisis_studi_kasus.md), dan
`directed: true` per edge tetap didukung loader bila verifikasi arah selesai.

## 10. Batasan antara fakta berita dan asumsi simulasi

| Sumber | Isi |
|---|---|
| **Fakta berita** | kebakaran di Pasar Johar Relokasi blok F pada 2 Februari 2022; kerumunan warga membuat akses jalan menuju pasar macet dan menyulitkan damkar |
| **Model peta/simulasi** | titik awal, titik tujuan, topologi jaringan, nama ruas, koordinat, pembagian bobot, event penutupan `e14`, serta fasilitas node (hydrant, kantor polisi, kantor damkar tambahan beserta armada/personelnya) |
| **Tidak tersedia dalam sumber berita** | jumlah unit damkar, jumlah petugas, waktu kedatangan, kapasitas air, jumlah hidran, lebar jalan, koordinat presisi, waktu tempuh per ruas, jumlah hydrant nyata di tiap simpang, jumlah mobil/personel tiap kantor |

Konsekuensinya: angka `10,74` dan `11,93` menit adalah **hasil model**, bukan
waktu kedatangan aktual damkar pada 2 Februari 2022. Titik awal/tujuan berasal
dari peta (OSM/screenshot), bukan dari berita — berita tidak menyebut pos
pemadam maupun rute.

## 11. Cara kerja Dijkstra dan simulasi penutupan akses

Skenario default (`data/pasar_johar_damkar.yaml`):

1. Loader membaca YAML, memvalidasi ID, bobot, referensi node, `start`/`goal`,
   dan `closure_edge`, lalu membangun adjacency list berbobot.
2. Dijkstra menghitung **rute awal** dari Dinas Pemadam Kebakaran Kota Semarang
   (Jl. Madukoro III) ke akses Relokasi Pasar Johar — koridor utara
   (Jl. Pandanaran → Panjaitan → Kartini → Barito), **10,74 menit, 14 ruas**.
3. Simulasi **menutup** `e14` (Jl. Barito, ruas simpang Kartini → pasar) sebagai
   model akses utara yang terputus oleh kerumunan, sesuai berita. Penutupan
   berarti ruas dikeluarkan dari himpunan edge yang boleh dilalui.
4. Dijkstra dijalankan ulang dengan ruas tersebut dikecualikan; diperoleh rute
   alternatif lewat koridor selatan (Jl. Indraprasta → Pemuda → Petudungan →
   Dargo → Bugangan → Kanalsari → Tirtoyoso): **11,93 menit, 17 ruas**,
   selisih **+1,19 menit** dan **+3 ruas**.
5. Bila setelah penutupan tujuan menjadi tidak terjangkau, program melaporkan
   `Tidak ada rute alternatif …` dan keluar dengan kode 1 (bukan dianggap
   berhasil).

Hasil setiap rute kini menyimpan urutan **ID ruas** (`PathResult.edges`) sehingga
bobot total dapat diverifikasi terhadap jumlah bobot tiap ruas (ada pengujinya).
Penghitungan ulang adalah Dijkstra baseline, **bukan D\* Lite**; hal itu
memungkinkan anggota D membandingkan algoritma dinamis dengan baseline C.

## 12. Instalasi dan menjalankan program

### Linux / WSL

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m pip install -e .
python -m pathfinding.simulation                                  # skenario default: 34 node (31 simpang + 3 kantor damkar)
python -m pathfinding.simulation --algorithm astar                # rute sama, diprose A* (bandingkan node dieksplorasi)
python -m pathfinding.simulation --scenario data/pasar_johar_demo.yaml   # skenario demo lama (10 node)
python -m pytest -v
python -m pathfinding.benchmark --repeats 1000
python -m pathfinding.benchmark --compare --repeats 10000        # tabel perbandingan Dijkstra vs A*
```

### Windows

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python -m pip install -e .
python -m pathfinding.simulation
python -m pathfinding.simulation --algorithm astar
python -m pathfinding.simulation --scenario data/pasar_johar_demo.yaml
python -m pytest -v
python -m pathfinding.benchmark --repeats 1000
python -m pathfinding.benchmark --compare --repeats 10000
```

Jika PowerShell memblokir aktivasi, jalankan perintah memakai
`.venv\Scripts\python.exe`.

### Alat bantu verifikasi peta (butuh internet)

```bash
python tools/validasi_peta.py data/pasar_johar_damkar.yaml   # cek node, nama ruas, aturan arah di OSM
python tools/validasi_fasilitas.py data/pasar_johar_damkar.yaml   # cocokkan hydrant, kantor polisi, kantor damkar ke OSM
python tools/eksperimen_arah.py                              # uji penerapan aturan satu arah
```

## 13. Menjalankan pengujian

```bash
python -m pytest -v
```

Cakupan 69 pengujian: perhitungan Dijkstra pada graf kecil, penutupan ruas,
skenario tanpa rute, pembacaan YAML (termasuk skema referensi `execution_plan`),
validasi struktur (ID duplikat, bobot negatif/non-angka, node/ruas tak
dikenal, field peta separuh, tipe `directed`/`access_status`), konsistensi
jumlah bobot rute terhadap total, keluaran simulasi (daftar node, daftar ruas,
sumber berita, batas fakta), skenario tanpa rute alternatif, benchmark, serta
pengujian A* (`tests/test_astar.py`): kesetaraan biaya/urutan rute dengan
Dijkstra pada kedua skenario, admissibility heuristik untuk seluruh 34 node,
kontrak input yang sama, dan tabel perbandingan benchmark. Ditambah
`tests/test_facilities.py` (17 pengujian): aturan hydrant/kantor polisi,
validasi field fasilitas, inventaris skenario damkar, dan keluaran bagian
sumber air. Seluruh pengujian yang sudah ada sebelum pengembangan tetap
lulus.

## 14. Contoh output program

Output `python -m pathfinding.simulation` (≈444 baris) berurutan: header kasus,
`01 KONFIGURASI SIMULASI`, `02 SUMBER BERITA DAN BATAS DATA`,
`03 DAFTAR NODE (34 node)`, `04 DAFTAR RUAS JALAN (36 ruas)`,
`04B SUMBER AIR DAN FASILITAS`,
`05 RUTE AWAL`, `06 EVENT: AKSES JALAN TERHAMBAT`, `07 RUTE ALTERNATIF`,
`08 RINGKASAN HASIL`, `09 CATATAN VALIDITAS DATA`. Ringkasannya:

```text
╔════════════════════════════════════════════════════════════════════════════╗
║ PATHFINDING C  |  DIJKSTRA ENGINE BASE                                     ║
╠════════════════════════════════════════════════════════════════════════════╣
║ Rute Damkar ke Kebakaran Relokasi Pasar Johar (jaringan jalan asli)        ║
╟────────────────────────────────────────────────────────────────────────────╢
║ Lokasi  : Relokasi Pasar Johar, kawasan Masjid Agung Jawa Tengah (MAJT),   ║
║ Semarang                                                                   ║
║ Tanggal : 2 Februari 2022                                                  ║
║ Graf    : 34 node | 36 ruas                                                ║
╚════════════════════════════════════════════════════════════════════════════╝

01  KONFIGURASI SIMULASI
  Titik awal              : Dinas Pemadam Kebakaran Kota Semarang (Jl.
                            Madukoro III)
  Titik tujuan            : Akses Relokasi Pasar Johar (Jl. Barito × Jl.
                            Tirtoyoso V)
  Algoritma               : Dijkstra (baseline / pencarian ulang penuh)
  Model graf              : tidak berarah (dua arah) - semua edge boleh
                            dilalui dua arah pada model ini
  Satuan bobot            : menit estimasi
  Ruas tertutup sejak awal: Tidak ada

03  DAFTAR NODE (34 node)
  01. pos_damkar_madukoro · titik awal, dilalui rute awal, dilalui rute
       Dinas Pemadam Kebakaran Kota Semarang (Jl. Madukoro III)
  ...

04B  SUMBER AIR DAN FASILITAS
  Aturan model            : hydrant di setiap node kecuali node kantor polisi
  Hydrant terverifikasi OSM: 1 node - Hydrant BCA (251 m dari
                             simpang_depok_wahidhasyim)
  Hydrant asumsi model    : 32 node (jejak jarak ke hydrant OSM tercatat di
                            YAML per node)
  Kantor polisi (tanpa hydrant): simpang_cipto_bugangan
    Polsek Semarang Timur (32 m dari node) - tidak memiliki hydrant sesuai
    aturan model
  Kantor damkar logistik (armada/personel = asumsi model):
    pos_damkar_tambahan_barat - 2 mobil, 8 personel
    pos_damkar_tambahan_utara - 2 mobil, 8 personel
    pos_damkar_tambahan_walisongo - 3 mobil, 10 personel

05  RUTE AWAL
  01. Dinas Pemadam Kebakaran Kota Semarang (Jl. Madukoro III)
       [TITIK AWAL]
       │
       ▼
  02. Simpang Jl. Madukoro V × Jl. Madukoro III
       Lewat e01 · Jl. Madukoro V · 0.13 menit estimasi
  ...
  Total bobot : 10.74 menit estimasi
  Jumlah ruas : 14
  Node dieksplorasi : 30 (pembanding Dijkstra vs A*)
  Sumber air di rute:
    15/15 node rute ber-hydrant (isi air di node tersebut)
    tanpa hydrant terverifikasi OSM di rute ini

  JALUR DAMKAR (urutan jalan yang dilalui)
    Jl. Madukoro V  ->  Jl. Madukoro III  ->  Jl. Cokrokembang  ->  ...

06  EVENT: AKSES JALAN TERHAMBAT
  ID ruas                 : e14
  Status akses            : rawan terhambat kerumunan (event simulasi sesuai
                            berita 2 Februari 2022)
  Tindakan   : Ruas dikecualikan dari pencarian rute berikutnya.

08  RINGKASAN HASIL
  Rute awal               : 10.74 menit estimasi | 14 ruas
  Rute alternatif         : 11.93 menit estimasi | 17 ruas
  Perubahan bobot total   : +1.19 menit estimasi
  Selisih ruas            : +3 ruas
  Status                  : Rute alternatif berhasil ditemukan

09  CATATAN VALIDITAS DATA
  ... Terverifikasi: 34/34 elemen OSM (31 simpang + 3 way kantor damkar),
  28/28 nama ruas, graf satu komponen ...
  Belum diverifikasi: aturan satu arah 2022, posisi persimpangan pada peta
  resmi, waktu tempuh aktual, simpang pemutar ...
```

## 15. Keterbatasan data dan saran validasi lapangan

- **Waktu per ruas adalah model**, bukan pengukuran lalu lintas pada
  2 Februari 2022; tidak ada data waktu tempuh aktual dalam sumber berita.
- **Aturan satu arah belum diterapkan** ke model (lihat bagian 9); perlu
  verifikasi peta/observasi lapangan, termasuk aturan yang berlaku pada 2022.
- **Posisi persimpangan** sudah punya koordinat OSM, tetapi belum diperiksa
  satu per satu pada peta resmi; graf ini bukan representasi GIS presisi.
- **Skenario demo (10 node)** masih berbasis screenshot beresolusi terbatas;
  nama "Jl. Pelabuhan Ratu" pada anotasi perlu dikonfirmasi.
- **Enam ruas dengan bobot menyimpang** (bagian 8) perlu ditinjau ulang.
- Saran validasi: periksa tiap edge pada Google Maps/peta resmi, cocokkan
  simpang yang hilang (terutama simpang pemutar), lalu perbarui YAML; jalankan
  ulang `tools/validasi_peta.py` untuk memastikan node/nama ruas masih cocok.

## 16. Sumber berita

- Bisnis.com, *Relokasi Pasar Johar Terbakar, Ganjar Minta Pedagang
  Diprioritaskan*:
  https://semarang.bisnis.com/read/20220202/535/1496092/relokasi-pasar-johar-terbakar-ganjar-minta-pedagang-diprioritaskan
- ANTARA Jawa Tengah, *Kerumunan warga sulitkan pemadaman kebakaran Pasar
  Johar relokasi*:
  https://jateng.antaranews.com/berita/431073/kerumunan-warga-sulitkan-pemadaman-kebakaran-pasar-johar-relokasi

Peta jalan: OpenStreetMap contributors (ODbL).

## 17. Struktur proyek

```text
MatdisLanjutTubes/
├── data/
│   ├── pasar_johar_damkar.yaml    # SKENARIO DEFAULT: 34 node (31 simpang OSM + 3 kantor damkar)
│   └── pasar_johar_demo.yaml      # skenario lama berbasis screenshot (10 node)
├── docs/
│   ├── analisis_studi_kasus.md    # analisis berita, batas fakta, rancangan node/edge, keputusan arah
│   └── peta_rute_damkar.html      # peta interaktif (hasil tools/buat_peta.py)
├── src/pathfinding/
│   ├── graph.py                   # adjacency list berbobot + validasi ID/bobot/arah
│   ├── dijkstra.py                # Dijkstra baseline, rute ber-jejak ruas, reroute setelah penutupan
│   ├── astar.py                   # A* pembanding: f = g + h, kontrak identik dengan Dijkstra
│   ├── heuristic.py               # heuristik haversine admissible (jarak lurus / kecepatan terbesar)
│   ├── io.py                      # YAML loader + validasi struktur & referensi skenario
│   ├── simulation.py              # run_simulation dan CLI (--algorithm dijkstra|astar)
│   └── benchmark.py               # pengukuran waktu + perbandingan Dijkstra vs A*
├── tests/test_dijkstra.py         # 38 pengujian baseline
├── tests/test_astar.py            # 14 pengujian A* & heuristik
├── tests/test_facilities.py       # 17 pengujian fasilitas node (total 69)
├── tools/
│   ├── validasi_peta.py           # validasi node/nama ruas/aturan arah terhadap OSM
│   ├── validasi_fasilitas.py      # cocokkan hydrant, kantor polisi, kantor damkar ke OSM
│   ├── buat_peta.py               # generate peta HTML interaktif (Leaflet + tile OSM)
│   └── eksperimen_arah.py         # uji penerapan aturan satu arah pada graf
├── pyproject.toml
├── requirements.txt
└── requirements-dev.txt
```

## 18. Kontrak data untuk anggota B dan D

- Node memuat `id` dan `label` (skenario damkar menambah `lat`, `lon`,
  `osm_node` sebagai referensi peta; field tambahan diabaikan loader).
- Edge memuat `id`, `from`, `to`, `weight`, dan opsional `road`, `directed`,
  `access_status` (skenario damkar menambah `distance_m`).
- `weight` wajib angka, finite, dan non-negatif. Satuan pada kasus ini menit
  estimasi, tetapi distribusi per ruas masih simulatif.
- ID node dan edge wajib unik; `start`, `goal`, `closure_edge`, dan
  `blocked_edges` wajib merujuk data yang ada — semuanya divalidasi saat muat.
- Anggota B dapat mengganti node, ruas, arah, dan bobot tanpa mengubah fungsi
  Dijkstra; perbarui pengujian yang memang mengekspektasikan angka tersebut.
- Anggota D dapat memakai model graf yang sama untuk implementasi D\* Lite dan
  mengukur perbandingannya dengan baseline C. Pembanding A\* (bagian 19) sudah
  tersedia sebagai pembanding kedua; D\* Lite belum ada di repositori ini.

## 19. Perbandingan A\* dengan Dijkstra (hasil pengukuran)

A\* ditambahkan sebagai pembanding baseline dengan kontrak hasil yang sama:
biaya rute, urutan node, dan urutan ruas **identik** pada kedua skenario (diuji
`tests/test_astar.py`), jadi perbandingannya adil — yang berbeda hanya waktu
eksekusi dan jumlah node dieksplorasi.

Cara menjalankan:

```bash
python -m pathfinding.simulation --algorithm astar     # lihat "Node dieksplorasi" tiap rute
python -m pathfinding.benchmark --compare --repeats 10000
```

Hasil `--compare --repeats 50000` pada skenario default (34 node / 36 ruas,
Linux, Python 3.14, diulang tiga kali agar arah hasil stabil):

| algoritma | rata-rata | minimum | biaya rute | node rute | node dieksplorasi |
|---|---|---|---|---|---|
| Dijkstra | 0,016–0,017 ms | 0,014 ms | 10,74 menit | 15 | 30 |
| A\* | 0,034–0,036 ms | 0,028 ms | 10,74 menit | 15 | 27 |

Rasio kecepatan Dijkstra/A\* ≈ **0,47–0,48×** — pada mesin ini A\* **lebih
lambat** sekitar dua kali lipat walaupun memuat lebih sedikit node (hemat
eksplorasi 3/30 = 10%). Setelah ruas `e14` ditutup, keduanya mengeksplorasi
29 node sehingga selisihnya nol.

Interpretasi (jujur, sesuai data):

- **Yang dimenangkan A\*: efisiensi penelusuran.** Heuristik haversine
  admissible memangkas 10% eksplorasi pada rute awal — pada graf besar
  (ribuan node) penghematan semacam ini biasanya yang membuat A\* menang.
- **Yang dimenangkan Dijkstra: waktu pada graf kecil.** Biaya heuristik
  (haversine + cache dictionary + kunci antrian 3 elemen) lebih besar daripada
  penghematan 3 pop pada graf 34 node. Karena itu pada proyek ini Dijkstra
  tetap baseline yang wajar.
- Angka waktu sangat bergantung mesin/versi Python dan hanya berlaku untuk
  skenario ini; angka rute (10,74 / 11,93 menit) tidak bergantung algoritma.
- Heuristik sengaja lemah (pembagi kecepatan terbesar 35 km/jam) demi
  admissibility; heuristik lebih kuat tetap harus memenuhi syarat yang sama
  sebelum dipakai untuk mengklaim keunggulan apa pun.

## 20. Fasilitas node: hydrant, kantor polisi, kantor damkar (logistik)

Pengembangan ini menjawab kebutuhan operasional yang tidak ada dalam model
rute murni: dari mana mobil damkar mengambil **air**, di mana **logistik**
(armada/personel tambahan) diambil, dan node mana yang justru harus dilewati
tanpa mengambil air. Semua diperiksa dulu terhadap peta di sekitar Pasar
Johar memakai `tools/validasi_fasilitas.py` (Overpass + Nominatim + OSRM,
ekstraksi **2026-11-12**).

### 20.1 Hasil pemeriksaan peta (fakta OSM)

| Pemeriksaan | Hasil |
|---|---|
| Hydrant (`emergency=fire_hydrant`) di bbox skenario | **15** titik |
| Kantor polisi (`amenity=police`) di bbox skenario | **15** bangunan |
| Kantor damkar (`amenity=fire_station`) radius 5 km dari jaringan | **3** selain kantor di titik awal |
| Node yang berada di hydrant sungguhan (≤300 m) | **1** node: `simpang_depok_wahidhasyim` → Hydrant BCA, 251 m (node OSM 5466104936, operator PAM) |
| Node yang berada di kantor polisi (≤100 m) | **1** node: `simpang_cipto_bugangan` → Polsek Semarang Timur, Jl. Dr. Cipto no 66, 32 m (way 564915121) |
| Node lain (29 simpang + 3 kantor damkar) | hydrant **asumsi model**, dengan jejak `nearest_osm_m` (jarak ke hydrant OSM terdekat, 335–2076 m) dicatat per node |

### 20.2 Aturan model

1. **Hydrant di setiap node kecuali node kantor polisi.** Pada skenario ini
   `simpang_cipto_bugangan` adalah satu-satunya node kantor polisi sehingga
   menjadi satu-satunya node tanpa hydrant. Aturan ini *keputusan model*
   (berita tidak menyebut hidran), bukan klaim bahwa tiap simpang Semarang
   benar-benar punya hidran.
2. **Node kantor polisi dilarang memiliki hydrant** — loader menolaknya, jadi
   pelanggaran aturan tidak bisa lolos diam-diam.
3. **Kantor damkar tambahan = node logistik.** Tiga kantor pemadam sungguhan
   di OSM dijadikan node bercabang mati: `pos_damkar_tambahan_barat`,
   `pos_damkar_tambahan_utara`, `pos_damkar_tambahan_walisongo`. Fungsi modelnya
   tempat mengambil **mobil** dan **personel** tambahan; jumlahnya (2/2/3 mobil,
   8/8/10 personel) adalah **asumsi model** karena tidak ada di berita maupun OSM.
4. Koneksi kantor damkar ke jaringan memakai jarak rute OSRM (3856/6084/4775 m)
   dan kecepatan model permukiman; nama ruas penghubung belum terverifikasi,
   karena itu edge ditandai `connection: model`.

Contoh penulisan pada `data/pasar_johar_damkar.yaml`:

```yaml
  - id: simpang_depok_wahidhasyim
    hydrant:
      verified: true          # ada di OSM
      osm_node: 5466104936
      name: "Hydrant BCA"
      distance_m: 251
  - id: simpang_cipto_bugangan
    facility:
      type: police_station    # node ini TANPA hydrant
      name: "Polsek Semarang Timur"
      distance_m: 32
```

### 20.3 Dampak ke rute dan keluaran

- Rute awal dan alternatif **tidak berubah** (10,74 dan 11,93 menit) karena
  ketiga node logistik bercabang mati dan hydrant adalah atribut, bukan edge.
- Simulasi kini mencetak bagian **`04B SUMBER AIR DAN FASILITAS`** (aturan
  model, hydrant terverifikasi, jumlah hydrant model, node kantor polisi,
  armada/personel tiap kantor) serta laporan **`Sumber air di rute`** pada
  tiap rute, seolah-olah mobil damkar berhenti isi air di node yang dilalui:
  - rute awal: **15/15 node ber-hydrant** (tanpa hydrant terverifikasi OSM);
  - rute alternatif: **17/18 node ber-hydrant**, melewati **Hydrant BCA**
    (terverifikasi) dan **`simpang_cipto_bugangan`** yang justru tanpa hydrant
    karena berada di Polsek Semarang Timur.
- `python -m pytest` mencakup 17 pengujian fasilitas (aturan, validasi field,
  inventaris, keluaran); total 69 pengujian.

### 20.4 Batas fakta dan sisa verifikasi

| Sumber | Isi |
|---|---|
| **Fakta peta (OSM, 2026-11-12)** | keberadaan 15 hydrant, 15 kantor polisi, 3 kantor damkar tambahan, koordinat dan nama masing-masing |
| **Asumsi model** | hydrant di 29 simpang lain, ambang jarak layanan ≤300 m/≤100 m, jumlah mobil dan personel tiap kantor, jarak rute koneksi OSRM |
| **Belum diverifikasi** | keberadaan hidran fisik di simpang (perlu cek Google Maps/observasi lapangan), aturan hidran yang berlaku pada 2 Februari 2022, jumlah armada/personel sesungguhnya |

Periksa ulang kapan saja dengan
`python tools/validasi_fasilitas.py data/pasar_johar_damkar.yaml --emit`
(butuh internet) — laporannya identik dengan yang mendasari bagian ini.

## 21. Peta visual: jaringan, rute, dan fasilitas (Leaflet + OSM)

`tools/buat_peta.py` mengubah skenario YAML menjadi peta HTML interaktif
`docs/peta_rute_damkar.html` — cukup dobel-klik file itu di peramban
(internet diperlukan untuk tile peta dan pustaka Leaflet dari CDN):

```bash
python tools/buat_peta.py                      # ambil juga data fasilitas OSM
python tools/buat_peta.py --tanpa-osm          # hanya isi YAML, tanpa internet
```

Catatan tile: basemap jalan memakai **Esri World Street Map** dan alternatifnya
citra satelit Esri, karena tile resmi `tile.openstreetmap.org` menolak
permintaan dari halaman lokal/aplikasi (usage policy OSM) dan basemap CARTO
kini mewajibkan API key — keduanya membuat peta muncul "access blocked" atau
watermark saat file HTML dibuka langsung. **Data** peta (node, ruas, hydrant,
kantor polisi/damkar) tetap OpenStreetMap dan atribusinya tetap dicantumkan.

Isi peta (semua dihitung ulang dari YAML, jadi tidak pernah beda dengan
keluaran simulasi):

| Lapisan | Isi |
|---|---|
| Jaringan (bisa dilalui damkar) | 36 ruas + 34 node graf model, klik untuk bobot/nama jalan |
| Rute awal | pola biru tebal, 10,74 menit / 14 ruas |
| Ruas tertutup | merah putus-putus pada `e14` (Jl. Barito) — hambatan kerumunan |
| Rute alternatif | oranye putus-putus, 11,93 menit / 17 ruas (koridor selatan) |
| Node & waktu tempuh | warna node = lama dari pos damkar (≤3 hijau, 3–6 kuning, 6–9 oranye, >9 merah) — jawaban "ke mana saja damkar bisa pergi dan berapa lama" |
| Fasilitas OSM | 22 hydrant, 18 kantor polisi, 4 kantor damkar asli dari OpenStreetMap |

Klik sebuah node untuk melihat perannya (rute awal/alternatif/tujuan), waktu
tempuh dari pos, status hydrant (terverifikasi OSM atau asumsi model), dan
armada/personel kantor damkar. Basis peta bisa diganti ke **citra satelit**
(Esri) lewat kontrol lapisan di kanan atas.

Peta digenerate ulang setiap kali data berubah; file HTML ikut di-commit agar
bisa langsung dibuka tanpa menjalankan ulang tool.
