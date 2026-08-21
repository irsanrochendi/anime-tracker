# 🎬 Anime & Show Tracker

Aplikasi desktop berbasis **Python Tkinter** untuk mencatat riwayat tontonan Anime, Movie, atau TV Series lokal kamu secara praktis, terintegrasi langsung dengan data episode terbaru di **Bilibili (Bstation)**.

Aplikasi ini dapat mendeteksi episode terbaru secara otomatis dari Bilibili, mewarnai baris tabel yang memiliki konten baru, dan mengirimkan Windows Toast Notification (notifikasi melayang) agar kamu tahu kapan episode baru rilis.

## ✨ Fitur Utama

- **Pencatatan Anime & Series**: Kelola data tontonan meliputi: Judul, Tipe (Anime, Movie, Series, Lainnya), Nomor Season saat ini, Nomor Episode terakhir yang ditonton, Status (Watching, Completed, Plan to Watch, Dropped), dan Catatan khusus.
- **Pencarian Bilibili Season ID**: Cari anime langsung di database Bilibili dari dalam aplikasi. Kamu tinggal klik "Cari Anime", pilih dari list pencarian, dan tautkan ke show yang kamu tracking.
- **Auto & Manual Check Update**: 
  - Aplikasi melakukan auto-update secara berkala (tiap 30 menit) di background thread (tidak membuat UI freeze/macet).
  - Dilengkapi tombol manual checking *Cek Update Episode* untuk melakukan query langsung.
- **Indikator Visual Episode Baru (🔴 / ✅)**:
  - Jika episode terbaru di Bilibili lebih tinggi dari yang terakhir kamu tonton, baris tabel akan disorot warna hijau lembut dan ditandai ikon merah **🔴 Baru (EP XX)**.
  - Jika tontonan kamu sudah paling baru, status berubah menjadi ikon hijau **✅ Up-to-date (EP XX)**.
- **Windows Toast Notifications**: Memberikan notifikasi sistem melayang (balloon pop-up) di sudut kanan bawah Windows setiap kali episode baru dirilis di Bilibili (hanya untuk anime berstatus `Watching` yang terhubung Bilibili).
- **Aman Bebas Hambatan (DB Path Fix)**: Konfigurasi SQLite dirancang khusus agar saat dibangun menjadi executable (`.exe`), database disimpan permanen di sebelah file `.exe`, mencegah hilangnya data saat aplikasi ditutup.
- **Quick Update Toolbar**: Pintasan tombol `-1` dan `+1` langsung di toolbar bawah untuk menambah/mengurangi jumlah episode dan season tontonan tanpa membuka popup form edit.
- **Pencarian Live**: Input kata kunci pad kolum cari untuk filter instan di tabel utama.

---

## 🛠️ Persyaratan Sistem

- **Python**: Versi `3.10` atau lebih baru.
- **Windows OS**: (Dibutuhkan untuk notifikasi balon Windows `win10toast` / `pywin32`).

---

## ⚙️ Cara Instalasi & Menjalankan (Development Mode)

1. Clone repositori ke local drive:
   ```bash
   git clone git@github.com:irsanrochendi/anime-tracker.git
   cd anime-tracker
   ```

2. Buat Virtual Environment (Opsional tapi direkomendasikan):
   ```bash
   python -m venv venv
   source venv/Scripts/activate  # Untuk Windows (Bash)
   # atau
   .\venv\Scripts\activate      # Untuk Windows (PowerShell/CMD)
   ```

3. Install dependensi:
   ```bash
   pip install -r requirements.txt
   ```

4. Jalankan aplikasi:
   ```bash
   python tracker.py
   ```

---

## 📦 Membangun Standalone Executable (.exe)

Aplikasi dipaket menggunakan **PyInstaller** dengan spesifikasi (`AnimeTracker.spec`) agar berjalan mandiri tanpa instalasi Python di PC client visual.

Untuk me-rebuild file biner `.exe`:
```bash
pip install pyinstaller
pyinstaller AnimeTracker.spec --noconfirm
```

Hasil kompilasi visual berupa file tunggal **`AnimeTracker.exe`** akan muncul dalam direktori:
```
dist/AnimeTracker.exe
```

*Catatan: Saat pertama kali dijalankan dari direktori `dist/`, aplikasi otomatis memproduksi file databasenya sendiri (`tracker_db.sqlite`) di dalam folder yang sama agar data tersimpan permanen.*

---

## 🧩 Teknologi yang Digunakan

1. **GUI Framework**: Python Tkinter & ttk (Clam theme).
2. **Database Engine**: SQLite3.
3. **API Integration**: Bilibili Web API (Search & OGV Client API).
4. **Desktop Notifications**: `win10toast` (Windows 10/11 native API mapping).
5. **Packager**: PyInstaller.
