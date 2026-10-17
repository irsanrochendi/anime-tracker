# Changelog

## 2.0.1 — 2026-10-17

### Perbaikan
- Tombol **▶ Nonton** membuka episode yang salah, misalnya sudah di EP 12 tapi yang terbuka EP 10, kalau episode berikutnya belum ada di Bilibili. Sekarang tombol ini hanya membuka episode berikutnya. Kalau episode itu tidak ada, muncul pemberitahuan:
  - **Sudah tamat dan semua episode ditonton**: ditawarkan untuk menandai *Completed*.
  - **Masih tayang**: diberi tahu bahwa episode berikutnya belum rilis, beserta nomor episode terbaru.
  - **Gagal mengambil data**: diminta mengecek koneksi.
- Label seperti `PV` / `PV 2` di Bilibili tidak lagi dianggap nomor episode.

### Lainnya
- Versi aplikasi kini tertanam di metadata `.exe` (Properties → Details).

## 2.0.0 — 2026-10-17

### Baru
- UI baru berbasis **CustomTkinter**: kartu dengan poster, mode Dark/Light/System, dan tampilan HiDPI.
- Sumber data **TMDB** untuk film dan series, termasuk deteksi episode baru per season dan tanggal rilis.
- **Poster otomatis** dari Bilibili/TMDB, disimpan di folder `posters/`.
- **Filter dan urutan**: status, tipe, "Hanya yang perlu perhatian", serta urutan Update dulu / Terbaru / Terakhir diubah / Judul / Status.
- **Statistik**: total judul, episode ditonton, perkiraan jam nonton, dan grafik per status, tipe, dan sumber.
- Halaman **Pengaturan**: API key TMDB, bahasa, interval cek update, dan notifikasi on/off.
- Shortcut `Ctrl+N`, `Ctrl+F`, `F5`, `Ctrl+Enter`.

### Perbaikan
- Pencarian Bilibili tidak menemukan judul yang hasilnya ada di modul `ogv_subject`, misalnya One Piece dan BLEACH.
- UI tidak lagi diubah langsung dari thread background, yang sebelumnya berpotensi crash atau freeze.
- Pesan "Cek Update" hanya menyebut judul yang benar-benar tamat tayang tapi belum selesai ditonton.
- Notifikasi tidak muncul lagi saat sumber data baru saja ditautkan.

### Teknis
- `tracker.py` dipecah menjadi paket `animetracker/` (db, logic, updater, sources, ui).
- Migrasi database otomatis dari 1.x, dengan **backup** `tracker_db.sqlite.bak-<tanggal>` dibuat lebih dulu.
- Unit test di folder `tests/`.

## 1.x

Versi Tkinter awal: pencatatan tontonan dan integrasi Bilibili.
