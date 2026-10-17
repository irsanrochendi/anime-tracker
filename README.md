# 🎬 Anime & Show Tracker

Aplikasi desktop (Windows) untuk mencatat tontonan **Anime, Movie, dan TV Series**. Info episode terbaru diambil otomatis dari **Bilibili (Bstation)** untuk anime dan dari **TMDB** untuk film & series. Ada poster, filter, statistik, dan notifikasi Windows saat episode baru rilis.

## ✨ Fitur

- **UI modern (CustomTkinter)**: daftar berbentuk kartu dengan poster, mode **Dark / Light / System**, dan sudah menyesuaikan layar HiDPI.
- **Dua sumber data**
  - **Bilibili**: cari anime dari dalam aplikasi, lacak episode terbaru, dan tombol **▶ Nonton** langsung membuka episode berikutnya.
  - **TMDB**: film dan series di luar Bilibili, dengan deteksi episode baru per season, tanggal tayang episode berikutnya, dan tanggal rilis film. Butuh API key gratis, lihat di bawah.
- **Poster otomatis** dari Bilibili/TMDB. Poster di-cache di folder `posters/`, dan judul tanpa poster mendapat gambar inisial.
- **Filter & urutan**: status (sidebar, beserta jumlahnya), tipe, pencarian live judul/catatan, "Hanya yang perlu perhatian", dan urutan *Update dulu / Terbaru ditambah / Terakhir diubah / Judul A–Z / Status*.
- **Statistik**: total judul, episode ditonton, perkiraan jam nonton, persentase selesai, serta grafik per status, per tipe, dan per sumber data.
- **Indikator status** di setiap kartu:
  - 🟢 **Baru**: ada episode yang belum kamu tonton
  - 🟠 **Tamat tayang, belum selesai**
  - 🔵 **Film sudah rilis**, belum ditonton
  - ✅ **Up-to-date**, plus tanggal episode berikutnya jika diketahui
- **Cek update otomatis** di background (interval bisa diatur: 15 menit sampai 6 jam) dan manual lewat tombol **🔄 Cek Update** / `F5`.
- **Notifikasi Windows** hanya muncul saat episode terbaru benar-benar naik sejak cek terakhir, jadi tidak spam setiap kali aplikasi dibuka. Klik notifikasinya untuk membuka halaman show.
- **Quick update**: tombol `−` / `+1` episode langsung di kartu. Double-click kartu untuk mengedit.
- **Shortcut**: `Ctrl+N` tambah, `Ctrl+F` cari, `F5` cek update, `Ctrl+Enter` simpan form.

## 🔑 Mengaktifkan TMDB (opsional)

1. Buat akun gratis di [themoviedb.org](https://www.themoviedb.org/), lalu buka **Settings → API** dan minta API key.
2. Di aplikasi, buka **⚙ Pengaturan**, tempel **API Key** (v3) atau **API Read Access Token** (v4), lalu klik **Tes**.
3. Di form tambah/edit, klik **🔍 Cari di TMDB** untuk menautkan film/series.

API key disimpan di `settings.json` di sebelah database dan tidak ikut di-commit ke git.

## 🛠️ Persyaratan

- Python **3.10+**
- Windows 10/11 (untuk notifikasi `win11toast`)

## ⚙️ Menjalankan (development)

```bash
git clone git@github.com:irsanrochendi/anime-tracker.git
cd anime-tracker
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
python tracker.py
```

Menjalankan test:

```bash
python -m unittest discover -s tests -t .
```

## 📦 Build `.exe`

```bash
pyinstaller AnimeTracker.spec --noconfirm
```

Hasilnya `dist/AnimeTracker.exe`. Database (`tracker_db.sqlite`), `settings.json`, dan folder `posters/` dibuat di sebelah `.exe`, jadi data tidak hilang saat aplikasi ditutup.

## 🔄 Upgrade dari versi 1.x

Database lama langsung terbaca, tidak ada yang perlu dilakukan. Saat pertama kali dibuka, versi 2 menambah kolom baru dan **otomatis membuat backup** `tracker_db.sqlite.bak-<tanggal>` sebelum mengubah apa pun. Poster untuk anime yang sudah terhubung ke Bilibili diunduh otomatis pada pengecekan update pertama.

## 🧩 Struktur kode

```
tracker.py                 entry point (dipakai juga oleh PyInstaller)
animetracker/
  config.py                path data, konstanta, settings.json
  db.py                    SQLite: migrasi + CRUD
  logic.py                 logika murni: parsing episode, status update, aturan notifikasi
  updater.py               cek update di background + notifikasi Windows
  posters.py               download & cache poster
  sources/bilibili.py      Bilibili Web API (search, episode terbaru, link nonton)
  sources/tmdb.py          TMDB API v3 (search, detail film/series)
  ui/app.py                jendela utama (sidebar, filter, daftar kartu)
  ui/widgets.py            kartu show, stepper, cache gambar
  ui/dialogs.py            form tambah/edit, pencarian, pengaturan, statistik
  ui/theme.py              palet warna light/dark
tests/                     unit test (logika, migrasi DB, parser API)
```
