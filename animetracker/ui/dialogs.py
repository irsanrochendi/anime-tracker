import threading
import webbrowser
from collections import Counter
from tkinter import messagebox

import customtkinter as ctk

from .. import config, logic
from ..sources import SourceError, bilibili, tmdb
from . import theme as T
from .widgets import Stepper

LINK_FIELDS = ("bilibili_season_id", "tmdb_id", "tmdb_media", "poster_url")


class ModalDialog(ctk.CTkToplevel):
    def __init__(self, app, title, width, height):
        super().__init__(app, fg_color=T.BG)
        self.app = app
        self.title(title)
        self.minsize(width, height)
        x = app.winfo_rootx() + max(0, (app.winfo_width() - width) // 2)
        y = app.winfo_rooty() + max(0, (app.winfo_height() - height) // 3)
        self.geometry(f"{width}x{height}+{x}+{y}")
        self.transient(app)
        self.bind("<Escape>", lambda e: self.destroy())
        # CTkToplevel di Windows kadang muncul di belakang; grab baru bisa setelah window terlihat.
        self.after(120, self._activate)

    def _activate(self):
        try:
            self.lift()
            self.focus_force()
            self.grab_set()
        except Exception:
            pass


def _label(master, text):
    return ctk.CTkLabel(master, text=text, font=(T.FONT, 12, "bold"), text_color=T.MUTED, anchor="w")


class ShowFormDialog(ModalDialog):
    POSTER = (132, 194)

    def __init__(self, app, show, on_save):
        super().__init__(app, "Edit Show" if show else "Tambah Show", 720, 560)
        self.show = show or {}
        self.on_save = on_save
        self.link = {f: self.show.get(f) for f in LINK_FIELDS}

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=22, pady=(20, 10))
        body.grid_columnconfigure(1, weight=1)

        # ── Kiri: poster + sumber data ─────────────────────────────────────
        left = ctk.CTkFrame(body, fg_color=T.SURFACE, corner_radius=12)
        left.grid(row=0, column=0, sticky="ns", padx=(0, 18))
        self.poster = ctk.CTkLabel(left, text="", width=self.POSTER[0], height=self.POSTER[1])
        self.poster.pack(padx=16, pady=(16, 10))
        self.source_lbl = ctk.CTkLabel(left, text="", font=(T.FONT, 12), text_color=T.MUTED, wraplength=150)
        self.source_lbl.pack(padx=12)
        btn = dict(height=32, corner_radius=8, font=(T.FONT, 12, "bold"), width=150)
        ctk.CTkButton(left, text="🔍 Cari di Bilibili", command=lambda: self.search("bilibili"),
                      fg_color=T.BLUE, hover_color=T.BLUE_HOVER, **btn).pack(padx=12, pady=(12, 6))
        ctk.CTkButton(left, text="🔍 Cari di TMDB", command=lambda: self.search("tmdb"),
                      fg_color=T.BLUE, hover_color=T.BLUE_HOVER, **btn).pack(padx=12, pady=(0, 6))
        self.unlink_btn = ctk.CTkButton(left, text="✕ Lepas tautan", command=self.unlink, fg_color=T.NEUTRAL_BTN,
                                        hover_color=T.NEUTRAL_HOVER, text_color=T.TEXT, **btn)
        self.unlink_btn.pack(padx=12, pady=(0, 16))

        # ── Kanan: form ─────────────────────────────────────────────────────
        form = ctk.CTkFrame(body, fg_color="transparent")
        form.grid(row=0, column=1, sticky="nsew")
        form.grid_columnconfigure((0, 1), weight=1)

        _label(form, "Judul *").grid(row=0, column=0, columnspan=2, sticky="w")
        self.title_entry = ctk.CTkEntry(form, height=36, font=(T.FONT, 14), placeholder_text="Judul anime / film / series", **T.ENTRY)
        self.title_entry.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(2, 12))
        if self.show.get("title"):
            self.title_entry.insert(0, self.show["title"])

        _label(form, "Tipe").grid(row=2, column=0, columnspan=2, sticky="w")
        self.type_seg = ctk.CTkSegmentedButton(form, values=config.TYPES, height=32, font=(T.FONT, 12), **T.SEG)
        self.type_seg.set(self.show.get("type") or "Anime")
        self.type_seg.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(2, 12))

        _label(form, "Season").grid(row=4, column=0, sticky="w")
        _label(form, "Episode terakhir ditonton").grid(row=4, column=1, sticky="w")
        self.season = Stepper(form, self.show.get("season", 1) if self.show else 1)
        self.season.grid(row=5, column=0, sticky="w", pady=(2, 12))
        self.episode = Stepper(form, self.show.get("episode", 0) if self.show else 0)
        self.episode.grid(row=5, column=1, sticky="w", pady=(2, 12))

        _label(form, "Status").grid(row=6, column=0, columnspan=2, sticky="w")
        self.status = ctk.CTkSegmentedButton(form, values=config.STATUSES, height=32, font=(T.FONT, 12), **T.SEG_BLUE)
        self.status.set(self.show.get("status") or "Watching")
        self.status.grid(row=7, column=0, columnspan=2, sticky="ew", pady=(2, 12))

        _label(form, "Catatan").grid(row=8, column=0, columnspan=2, sticky="w")
        self.notes = ctk.CTkTextbox(form, height=90, font=(T.FONT, 13), border_width=2, corner_radius=8, **T.TEXTBOX)
        self.notes.grid(row=9, column=0, columnspan=2, sticky="nsew", pady=(2, 0))
        form.grid_rowconfigure(9, weight=1)
        if self.show.get("notes"):
            self.notes.insert("1.0", self.show["notes"])

        # ── Tombol ──────────────────────────────────────────────────────────
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x", padx=22, pady=(4, 18))
        ctk.CTkButton(bar, text="💾 Simpan", command=self.save, height=38, width=130, corner_radius=10,
                      font=(T.FONT, 13, "bold"), fg_color=T.GREEN, hover_color=T.GREEN_HOVER).pack(side="right")
        ctk.CTkButton(bar, text="Batal", command=self.destroy, height=38, width=100, corner_radius=10,
                      font=(T.FONT, 13), fg_color=T.NEUTRAL_BTN, hover_color=T.NEUTRAL_HOVER,
                      text_color=T.TEXT).pack(side="right", padx=(0, 10))
        hint = "Ctrl+Enter untuk simpan" if not self.show else f"ID #{self.show['id']}"
        ctk.CTkLabel(bar, text=hint, text_color=T.MUTED, font=(T.FONT, 11)).pack(side="left")

        self.bind("<Control-Return>", lambda e: self.save())
        self.refresh_link()
        self.after(200, self.title_entry.focus_set)

    def refresh_link(self):
        if self.link.get("bilibili_season_id"):
            text = f"Bilibili\nSeason ID {self.link['bilibili_season_id']}"
        elif self.link.get("tmdb_id"):
            media = "Film" if self.link.get("tmdb_media") == "movie" else "Series"
            text = f"TMDB · {media}\nID {self.link['tmdb_id']}"
        else:
            text = "Belum terhubung ke sumber data.\nTautkan agar update episode & poster otomatis."
        self.source_lbl.configure(text=text)
        self.unlink_btn.configure(state="normal" if (self.link.get("bilibili_season_id") or self.link.get("tmdb_id")) else "disabled")
        title = self.title_entry.get().strip() or "?"
        url = self.link.get("poster_url")

        def ready(img):
            if self.winfo_exists() and self.link.get("poster_url") == url:
                self.poster.configure(image=img)
        self.poster.configure(image=self.app.images.get(url, self.POSTER, title, ready))

    def unlink(self):
        self.link = {f: None for f in LINK_FIELDS}
        self.refresh_link()

    def search(self, source):
        SearchDialog(self.app, source, self.title_entry.get().strip(), self.pick, parent=self)

    def pick(self, result):
        self.link = {f: None for f in LINK_FIELDS}
        if result.source == "bilibili":
            self.link["bilibili_season_id"] = result.remote_id
        else:
            self.link["tmdb_id"] = result.remote_id
            self.link["tmdb_media"] = result.media
        self.link["poster_url"] = result.poster_url
        if not self.title_entry.get().strip() or not self.show:
            self.title_entry.delete(0, "end")
            self.title_entry.insert(0, result.title)
        if not self.show:
            self.type_seg.set(result.type_guess)
        self.refresh_link()
        self._activate()

    def save(self):
        title = self.title_entry.get().strip()
        season, episode = self.season.get(), self.episode.get()
        if not title:
            messagebox.showwarning("Data belum lengkap", "Judul tidak boleh kosong.", parent=self)
            return
        if season is None or episode is None:
            messagebox.showwarning("Data tidak valid", "Season dan Episode harus angka 0 atau lebih.", parent=self)
            return
        data = {
            "title": title,
            "type": self.type_seg.get(),
            "season": season,
            "episode": episode,
            "status": self.status.get(),
            "notes": self.notes.get("1.0", "end").strip(),
            **self.link,
        }
        self.destroy()
        self.on_save(self.show.get("id"), data)


class SearchDialog(ModalDialog):
    THUMB = (46, 68)

    def __init__(self, app, source, keyword, on_pick, parent=None):
        name = "Bilibili (Bstation)" if source == "bilibili" else "TMDB (film & series)"
        super().__init__(app, f"Cari di {name}", 640, 560)
        self._parent = parent
        if parent is not None:
            self.transient(parent)
        self.source = source
        self.on_pick = on_pick
        self._search_id = 0

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=18, pady=(18, 8))
        self.entry = ctk.CTkEntry(top, height=38, font=(T.FONT, 14), placeholder_text=f"Cari judul di {name}…", **T.ENTRY)
        self.entry.pack(side="left", fill="x", expand=True)
        self.entry.bind("<Return>", lambda e: self.do_search())
        ctk.CTkButton(top, text="🔍 Cari", width=90, height=38, corner_radius=10, font=(T.FONT, 13, "bold"),
                      fg_color=T.ACCENT, hover_color=T.ACCENT_HOVER, command=self.do_search).pack(side="left", padx=(8, 0))

        self.status = ctk.CTkLabel(self, text="", text_color=T.MUTED, font=(T.FONT, 12), anchor="w")
        self.status.pack(fill="x", padx=20)
        self.results = ctk.CTkScrollableFrame(self, fg_color="transparent", **T.SCROLL)
        self.results.pack(fill="both", expand=True, padx=12, pady=(4, 14))

        if keyword:
            self.entry.insert(0, keyword)
            self.after(150, self.do_search)
        else:
            self.after(200, self.entry.focus_set)

    def do_search(self):
        kw = self.entry.get().strip()
        if not kw:
            return
        for child in self.results.winfo_children():
            child.destroy()
        self._search_id += 1
        search_id = self._search_id
        self.status.configure(text="Mencari…", text_color=T.MUTED)
        settings = self.app.settings

        def run():
            try:
                if self.source == "bilibili":
                    items = bilibili.search(kw)
                else:
                    items = tmdb.search(kw, settings.get("tmdb_api_key"), settings.get("tmdb_language"))
                self.app.call_ui(self.show_results, search_id, items, None)
            except SourceError as e:
                self.app.call_ui(self.show_results, search_id, [], str(e))
            except Exception as e:
                self.app.call_ui(self.show_results, search_id, [], f"Gagal mencari: {e.__class__.__name__}")
        threading.Thread(target=run, daemon=True).start()

    def show_results(self, search_id, items, error):
        if not self.winfo_exists() or search_id != self._search_id:
            return
        if error:
            self.status.configure(text=error, text_color=T.ACCENT)
            if self.source == "tmdb" and "API key" in error:
                ctk.CTkButton(self.results, text="⚙ Buka Pengaturan", command=self.open_settings,
                              fg_color=T.BLUE, hover_color=T.BLUE_HOVER).pack(pady=20)
            return
        self.status.configure(text=f"{len(items)} hasil" if items else "Tidak ditemukan.",
                              text_color=T.MUTED if items else T.ACCENT)
        for item in items:
            self._row(item)

    def _row(self, item):
        row = ctk.CTkFrame(self.results, fg_color=T.SURFACE, corner_radius=10)
        row.pack(fill="x", pady=4, padx=4)
        thumb = ctk.CTkLabel(row, text="", width=self.THUMB[0], height=self.THUMB[1])
        thumb.pack(side="left", padx=10, pady=8)

        def ready(img):
            if thumb.winfo_exists():
                thumb.configure(image=img)
        thumb.configure(image=self.app.images.get(item.poster_url, self.THUMB, item.title, ready))

        ctk.CTkButton(row, text="Pilih", width=70, height=32, corner_radius=8, font=(T.FONT, 12, "bold"),
                      fg_color=T.GREEN, hover_color=T.GREEN_HOVER,
                      command=lambda: self.choose(item)).pack(side="right", padx=12)
        text = ctk.CTkFrame(row, fg_color="transparent")
        text.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(text, text=item.title, font=(T.FONT, 13, "bold"), anchor="w", justify="left",
                     wraplength=380).pack(anchor="w", fill="x")
        ctk.CTkLabel(text, text=item.subtitle, font=(T.FONT, 11), text_color=T.MUTED, anchor="w").pack(anchor="w")
        for w in (row, thumb, text):
            w.bind("<Double-Button-1>", lambda e: self.choose(item))

    def destroy(self):
        parent = getattr(self, "_parent", None)
        super().destroy()
        # Kembalikan modal grab ke form yang membuka dialog ini.
        if parent is not None and parent.winfo_exists():
            parent._activate()

    def choose(self, item):
        self.destroy()
        self.on_pick(item)

    def open_settings(self):
        self.destroy()
        SettingsDialog(self.app)


class SettingsDialog(ModalDialog):
    INTERVALS = {"15 menit": 15, "30 menit": 30, "1 jam": 60, "2 jam": 120, "6 jam": 360}
    LANGUAGES = {"English (en-US)": "en-US", "Indonesia (id-ID)": "id-ID"}

    def __init__(self, app):
        super().__init__(app, "Pengaturan", 560, 540)
        s = app.settings
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=24, pady=20)

        ctk.CTkLabel(body, text="TMDB (sumber data film & series)", font=(T.FONT, 15, "bold"),
                     text_color=T.TEXT).pack(anchor="w")
        ctk.CTkLabel(body, text="API key gratis — isi 'API Key' atau 'API Read Access Token' dari akun TMDB kamu.",
                     font=(T.FONT, 11), text_color=T.MUTED, wraplength=500, justify="left").pack(anchor="w", pady=(2, 6))
        key_row = ctk.CTkFrame(body, fg_color="transparent")
        key_row.pack(fill="x")
        self.key = ctk.CTkEntry(key_row, height=36, show="•", font=(T.FONT, 13), placeholder_text="API key TMDB", **T.ENTRY)
        self.key.pack(side="left", fill="x", expand=True)
        if s.get("tmdb_api_key"):
            self.key.insert(0, s.get("tmdb_api_key"))
        ctk.CTkButton(key_row, text="👁", width=36, height=36, fg_color=T.NEUTRAL_BTN, hover_color=T.NEUTRAL_HOVER,
                      text_color=T.TEXT, command=self.toggle_key).pack(side="left", padx=(6, 0))
        ctk.CTkButton(key_row, text="Tes", width=56, height=36, fg_color=T.BLUE, hover_color=T.BLUE_HOVER,
                      command=self.test_key).pack(side="left", padx=(6, 0))
        link_row = ctk.CTkFrame(body, fg_color="transparent")
        link_row.pack(fill="x", pady=(4, 0))
        ctk.CTkButton(link_row, text="Cara dapat API key ↗", fg_color="transparent", hover_color=T.SURFACE_ALT,
                      text_color=T.BLUE, width=10, height=24, font=(T.FONT, 12, "underline"),
                      command=lambda: webbrowser.open(tmdb.KEY_URL)).pack(side="left")
        self.key_status = ctk.CTkLabel(link_row, text="", font=(T.FONT, 12))
        self.key_status.pack(side="left", padx=10)

        _label(body, "Bahasa data TMDB").pack(anchor="w", pady=(14, 2))
        lang_name = next((k for k, v in self.LANGUAGES.items() if v == s.get("tmdb_language")), "English (en-US)")
        self.lang = ctk.CTkOptionMenu(body, values=list(self.LANGUAGES), width=220, **T.OPTION)
        self.lang.set(lang_name)
        self.lang.pack(anchor="w")

        ctk.CTkLabel(body, text="Pengecekan update", font=(T.FONT, 15, "bold"),
                     text_color=T.TEXT).pack(anchor="w", pady=(20, 4))
        _label(body, "Cek otomatis setiap").pack(anchor="w")
        minutes = int(s.get("check_interval_min") or 30)
        interval_name = next((k for k, v in self.INTERVALS.items() if v == minutes), "30 menit")
        self.interval = ctk.CTkOptionMenu(body, values=list(self.INTERVALS), width=220, **T.OPTION)
        self.interval.set(interval_name)
        self.interval.pack(anchor="w", pady=(2, 10))
        self.notify = ctk.CTkSwitch(body, text="Notifikasi Windows saat ada episode baru", font=(T.FONT, 13))
        if s.get("notifications"):
            self.notify.select()
        self.notify.pack(anchor="w")

        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x", padx=24, pady=(0, 20))
        ctk.CTkButton(bar, text="💾 Simpan", command=self.save, height=38, width=130, corner_radius=10,
                      font=(T.FONT, 13, "bold"), fg_color=T.GREEN, hover_color=T.GREEN_HOVER).pack(side="right")
        ctk.CTkButton(bar, text="Batal", command=self.destroy, height=38, width=100, corner_radius=10,
                      fg_color=T.NEUTRAL_BTN, hover_color=T.NEUTRAL_HOVER, text_color=T.TEXT).pack(side="right", padx=10)
        ctk.CTkLabel(bar, text=f"Data: {config.DATA_DIR}", font=(T.FONT, 10), text_color=T.MUTED,
                     wraplength=280, justify="left").pack(side="left")

    def toggle_key(self):
        self.key.configure(show="" if self.key.cget("show") else "•")

    def test_key(self):
        key = self.key.get().strip()
        self.key_status.configure(text="Mengecek…", text_color=T.MUTED)

        def run():
            try:
                tmdb.validate_key(key)
                self.app.call_ui(lambda: self.winfo_exists() and self.key_status.configure(text="✔ Valid", text_color=T.GREEN))
            except SourceError as e:
                msg = str(e)
                self.app.call_ui(lambda: self.winfo_exists() and self.key_status.configure(text=f"✕ {msg}", text_color=T.ACCENT))
        threading.Thread(target=run, daemon=True).start()

    def save(self):
        old_interval = self.app.settings.get("check_interval_min")
        self.app.settings.update(
            tmdb_api_key=self.key.get().strip(),
            tmdb_language=self.LANGUAGES[self.lang.get()],
            check_interval_min=self.INTERVALS[self.interval.get()],
            notifications=bool(self.notify.get()),
        )
        if old_interval != self.app.settings.get("check_interval_min"):
            self.app.checker.reschedule()
        self.destroy()
        self.app.flash("Pengaturan disimpan.")


# Perkiraan durasi per episode (menit) untuk estimasi total waktu nonton.
MINUTES_PER_EP = {"Anime": 24, "Series": 45, "Lainnya": 30}
MOVIE_MINUTES = 120


class StatsDialog(ModalDialog):
    def __init__(self, app):
        super().__init__(app, "Statistik", 620, 600)
        shows = app.shows
        frame = ctk.CTkScrollableFrame(self, fg_color="transparent", **T.SCROLL)
        frame.pack(fill="both", expand=True, padx=14, pady=14)

        total = len(shows)
        episodes = sum((s.get("episode") or 0) for s in shows if s.get("type") != "Movie")
        movies_done = sum(1 for s in shows if s.get("type") == "Movie" and s.get("status") == "Completed")
        minutes = sum((s.get("episode") or 0) * MINUTES_PER_EP.get(s.get("type"), 30)
                      for s in shows if s.get("type") != "Movie") + movies_done * MOVIE_MINUTES
        completed = sum(1 for s in shows if s.get("status") == "Completed")
        states = Counter(app.states[s["id"]].kind for s in shows)

        tiles = ctk.CTkFrame(frame, fg_color="transparent")
        tiles.pack(fill="x", padx=6)
        tiles.grid_columnconfigure((0, 1, 2), weight=1)
        for i, (label, value, color) in enumerate([
            ("Total judul", total, T.TEXT),
            ("Episode ditonton", episodes, T.BLUE),
            ("≈ Jam nonton", round(minutes / 60), T.ACCENT),
            ("Selesai", f"{round(completed * 100 / total) if total else 0}%", T.GREEN),
            ("Episode baru", states[logic.NEW], T.GREEN),
            ("Tamat, belum selesai", states[logic.FINISHED_NOT_DONE], T.ORANGE),
        ]):
            tile = ctk.CTkFrame(tiles, fg_color=T.SURFACE, corner_radius=12)
            tile.grid(row=i // 3, column=i % 3, sticky="ew", padx=5, pady=5)
            ctk.CTkLabel(tile, text=str(value), font=(T.FONT, 24, "bold"), text_color=color).pack(anchor="w", padx=14, pady=(10, 0))
            ctk.CTkLabel(tile, text=label, font=(T.FONT, 11), text_color=T.MUTED).pack(anchor="w", padx=14, pady=(0, 10))

        self._bars(frame, "Per status", Counter(s.get("status") for s in shows), config.STATUSES, total,
                   lambda k: T.STATUS_COLORS.get(k, T.BLUE))
        self._bars(frame, "Per tipe", Counter(s.get("type") for s in shows), config.TYPES, total,
                   lambda k: T.ACCENT, icons=T.TYPE_ICONS)
        linked = Counter("Bilibili" if s.get("bilibili_season_id") else "TMDB" if s.get("tmdb_id") else "Tidak terhubung"
                         for s in shows)
        self._bars(frame, "Sumber data", linked, ["Bilibili", "TMDB", "Tidak terhubung"], total, lambda k: T.BLUE)
        ctk.CTkLabel(frame, text="Jam nonton = perkiraan (Anime 24 mnt/ep, Series 45 mnt/ep, Film 2 jam).",
                     font=(T.FONT, 11), text_color=T.MUTED).pack(anchor="w", padx=12, pady=(12, 0))

    def _bars(self, master, title, counts, keys, total, color_for, icons=None):
        card = ctk.CTkFrame(master, fg_color=T.SURFACE, corner_radius=12)
        card.pack(fill="x", padx=11, pady=(12, 0))
        card.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(card, text=title, font=(T.FONT, 14, "bold"), text_color=T.TEXT).grid(
            row=0, column=0, columnspan=3, sticky="w", padx=14, pady=(10, 6))
        for i, key in enumerate(keys, start=1):
            n = counts.get(key, 0)
            label = f"{icons.get(key, '')} {key}".strip() if icons else key
            pady = (3, 14) if i == len(keys) else 3
            ctk.CTkLabel(card, text=label, font=(T.FONT, 12), text_color=T.TEXT, width=130, anchor="w").grid(
                row=i, column=0, sticky="w", padx=(14, 6), pady=pady)
            bar = ctk.CTkProgressBar(card, height=12, corner_radius=6, progress_color=color_for(key), fg_color=T.SURFACE_ALT)
            bar.set(n / total if total else 0)
            bar.grid(row=i, column=1, sticky="ew", pady=pady)
            ctk.CTkLabel(card, text=str(n), font=(T.FONT, 12, "bold"), text_color=T.TEXT, width=40).grid(
                row=i, column=2, padx=(6, 14), pady=pady)

