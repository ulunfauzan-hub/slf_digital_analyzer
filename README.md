# SLF Digital Analyzer

Alat penilaian **aset penghidupan rumah tangga** berbasis *Sustainable Livelihoods Framework* (SLF). Alat ini membaca jawaban kuesioner (Excel/CSV dari Google Form atau sumber lain) dan sebuah **tabel kuesioner**, lalu menghitung skor 0,00–1,00 untuk lima modal (manusia, alam, sosial, fisik, finansial), menggambar **pentagon aset**, dan mengekspor hasilnya.

Kuesioner dibuat **modular**: satu paket utama (wajib, lima modal) dan sejumlah modul tematik pilihan yang disesuaikan dengan mata pencaharian setempat. Peneliti di wilayah lain cukup mengganti tabel kuesioner, tanpa mengubah kode.

> Contoh penerapan: analisis aset penghidupan rumah tangga untuk pengembangan usaha hutan desa di LPHD Murung Panggang, Kabupaten Hulu Sungai Utara (lahan basah/rawa), dengan modul Perikanan Rawa, HHBK Purun/Galam, Pertanian-Peternakan Rawa, dan Ekowisata.

## Fitur
- Pentagon aset desa (skala 0–1) dan pentagon tiap modul tematik.
- Skor per rumah tangga, per indikator, dan rata-rata desa. Jumlah responden terbaca otomatis dari data.
- Modul tematik: rumah tangga yang tidak menjalankan usaha tersebut dikosongkan (NaN), **bukan 0**.
- Pencocokan jawaban yang toleran terhadap variasi teks (huruf, spasi, tanda hubung) dan **pemeriksaan tegas**: jawaban yang tidak cocok ditampilkan, tidak ditebak.
- Ekspor Excel lengkap dan PNG 300 DPI. Nama responden tidak dipakai dan tidak diekspor.

## Struktur repositori
```
app.py                          antarmuka Streamlit
slf_engine.py                   mesin hitung (tidak memuat aturan wilayah apa pun)
requirements.txt
kuesioner/
  Kuesioner_SLF_HSU_v1.0.xlsx   tabel kuesioner contoh (HSU / Murung Panggang)
  Template_Kuesioner_SLF.xlsx   template kosong untuk wilayah lain
CITATION.cff
```

## Cara memakai
1. Di Google Form: **Respons → Tautkan ke Spreadsheet**, lalu **File → Unduh → Microsoft Excel**.
2. Buka aplikasi (`streamlit run app.py`, atau versi yang sudah di-*deploy*) dan unggah file itu di sidebar.
3. Lihat hasil di tab **Pentagon Desa**, **Modul Tematik**, **Per Rumah Tangga**, **Indikator**; unduh di tab **Unduh**.
4. Centang **Pakai data simulasi** bila ingin mencoba tanpa data.

Instalasi lokal: `pip install -r requirements.txt` lalu `streamlit run app.py`.

## Memakai untuk wilayah lain
1. Salin `Template_Kuesioner_SLF.xlsx` dan ganti baris contoh dengan pertanyaan penelitianmu (baca sheet *Petunjuk* di dalamnya).
2. Buat Google Form yang **judul pertanyaannya sama** dengan kolom `Pertanyaan_Form`.
3. Isi sheet *Wilayah* (nama wilayah dan konversi satuan luas lokal ke hektar).
4. Unggah tabel itu lewat sidebar (*Ganti tabel kuesioner*). Bila ada kesalahan di tabel, aplikasi menampilkannya.

### Struktur tabel kuesioner
Semua isi kuesioner ada di **satu sheet** (`Kuesioner`): satu baris per pertanyaan, dengan pilihan jawaban di satu sel (satu opsi per baris), sehingga bisa langsung disalin ke Google Form. Sheet `Pengaturan` hanya berisi nama wilayah dan konversi satuan luas.

| Kolom | Isi |
|---|---|
| `Kode` | Kode unik pertanyaan |
| `Paket` | `Wajib` untuk paket utama (nama persis); nama modul tematik bebas |
| `Modal` | Manusia, Alam, Sosial, Fisik, Finansial (`Identitas` untuk pertanyaan yang tidak diskor) |
| `Pertanyaan_Form` | Judul pertanyaan di Google Form |
| `Tipe` | `angka`, `likert`, `pilihan`, `centang_hitung`, `centang_tingkat`, `teks`, `penentu_modul` |
| `Arah` | `invers` bila angka tinggi berarti buruk (hanya `angka` dan `likert`) |
| `Pilihan` | Satu opsi per baris dalam sel, **urut dari skor terendah ke tertinggi** |
| `Kata_Kunci` | Opsional: hanya bila teks pilihan di Form berbeda dari kolom `Pilihan` |
| `Tidak_Dihitung` | Opsional (`centang_hitung`): nomor opsi yang tidak dihitung, mis. `6` |

Format lama (sheet `Pilihan` dan `Wilayah` terpisah) tetap bisa dibaca.

### Tipe pertanyaan dan rumus skor
| Tipe | Skor (0–1) |
|---|---|
| `angka` | Min-Max antar responden: (x − min) / (maks − min) |
| `likert` | (x − 1) / 4 untuk skala 1–5 |
| `pilihan` | Pilihan tunggal. Skor = urutan opsi: 0, 1/(n−1), …, 1 (opsi pertama = 0, terakhir = 1) |
| `centang_hitung` | Jumlah opsi dicentang ÷ jumlah opsi yang dihitung |
| `centang_tingkat` | Skor opsi tertinggi yang dicentang (skor opsi seperti `pilihan`) |
| `teks`, `penentu_modul` | Tidak diskor |

`Arah = invers` (untuk kerentanan, misalnya frekuensi banjir) membalik skor `angka` dan `likert` menjadi 1 − skor. Pada tipe `pilihan` dan centang, tulis opsi dari aset terendah ke tertinggi, jadi arah sudah tercermin di urutannya.

Skor modal = rata-rata skor indikator di modal itu. Skor total = rata-rata lima modal. Semua indikator berbobot sama.

### Kata kunci
Bila Form dibuat dari tabel (teks pilihan disalin persis), kolom `Kata_Kunci` **tidak perlu diisi**: mesin mencocokkan jawaban dengan teks pilihan (tidak peka huruf besar/kecil, spasi, titik, koma). Isi `Kata_Kunci` hanya bila teks di Form berbeda, satu baris per opsi sejajar dengan `Pilihan`: huruf kecil tanpa spasi/titik/koma, tanda `|` berarti "atau". Pada pilihan tunggal, opsi dengan kata kunci terpanjang yang cocok yang dipilih. Pada kotak centang, sebuah opsi dianggap dipilih bila kata kuncinya terkandung dalam jawaban, jadi hindari label yang menjadi bagian dari label lain.

## Batasan yang perlu diketahui
- Lima modal tetap; skala Likert hanya 1–5; bobot indikator sama.
- Skor numerik memakai Min-Max antar responden, sehingga **bersifat relatif terhadap sampel**. Membandingkan skor antar penelitian hanya adil bila instrumen dan cara normalisasinya sama.
- Urutan skor pada pertanyaan pilihan adalah keputusan peneliti dan perlu dijustifikasi di metodologi. Beberapa urutan pada tabel contoh HSU berupa asumsi yang belum divalidasi.
- Konversi satuan lokal ke hektar harus diverifikasi dengan sumber setempat.
- Alat ini menghasilkan indeks deskriptif, bukan uji inferensial.

## Cara mengutip
Gunakan tombol **Cite this repository** di GitHub (dari `CITATION.cff`). Setelah repositori dihubungkan ke Zenodo, sitasi sebaiknya memakai DOI versi yang kamu gunakan.

```
ISI-NAMA-BELAKANG, ISI-NAMA-DEPAN. (2026). SLF Digital Analyzer (versi 0.2.0) [Perangkat lunak]. https://doi.org/ISI-DOI
```

## Lisensi
*Belum ditetapkan.* Usulan: kode dengan MIT atau Apache-2.0, dan tabel kuesioner dengan CC BY 4.0 (mewajibkan atribusi). Pastikan pilihan ini sesuai aturan institusi tentang hak atas karya tesis.
