import queue
import threading
import webbrowser
from tkinter import messagebox

import customtkinter as ctk

from .. import __version__, config, db, logic
from ..config import Settings
from ..sources import bilibili, tmdb
from ..updater import UpdateChecker
from . import theme as T
from .dialogs import SettingsDialog, ShowFormDialog, StatsDialog
from .widgets import ImageCache, NavButton, ShowCard, StatTile

ALL = "Semua"
SORTS = ["Update dulu", "Terbaru ditambah", "Terakhir diubah", "Judul A–Z", "Status"]
STATUS_ICONS = {ALL: "🗂", "Watching": "▶", "Completed": "✔", "Plan to Watch": "🕒", "Dropped": "✕"}


class App(ctk.CTk):
    def __init__(self):
        self.settings = Settings()
        ctk.set_appearance_mode(self.settings.get("appearance"))
        ctk.set_default_color_theme("blue")
        super().__init__(fg_color=T.BG)
        self.title(f"{config.APP_NAME}")
        self.geometry("1280x800")
        self.minsize(1000, 620)
        # CustomTkinter mengatur ukuran ulang saat start, jadi maximize harus setelah window tampil.
        self.after(0, self._maximize)

        # Thread worker tidak boleh menyentuh widget; semua update UI lewat antrean ini.
        self._ui_queue = queue.Queue()
        self.after(40, self._drain_ui_queue)

        self.images = ImageCache(self.call_ui)
        self.shows, self.states, self.cards = [], {}, {}
        self.filter_status, self.filter_type = ALL, ALL
        self.only_updates = ctk.BooleanVar(value=False)
        self._search_job = None
        self._checking = False

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._build_sidebar()
        self._build_main()

        self.bind("<Control-n>", lambda e: self.open_form(None))
        self.bind("<Control-f>", lambda e: self.search.focus_set())
        self.bind("<F5>", lambda e: self.manual_check())

        self.checker = UpdateChecker(self.settings, on_changed=lambda: self.call_ui(self.reload))
        self.reload()
        self.checker.start_periodic()
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def _maximize(self):
        try:
            self.state("zoomed")
        except Exception:
            pass

    # ── threading helper ─────────────────────────────────────────────────────
    def call_ui(self, fn, *args):
        self._ui_queue.put((fn, args))

    def _drain_ui_queue(self):
        try:
            while True:
                fn, args = self._ui_queue.get_nowait()
                try:
                    fn(*args)
                except Exception as e:  # jangan sampai satu callback mematikan loop antrean
                    print("UI callback error:", e)
        except queue.Empty:
            pass
        self.after(40, self._drain_ui_queue)

    # ── layout ───────────────────────────────────────────────────────────────
    def _build_sidebar(self):
        side = ctk.CTkFrame(self, fg_color=T.SIDEBAR, corner_radius=0, width=250)
        side.grid(row=0, column=0, rowspan=2, sticky="nsw")
        side.grid_propagate(False)
        side.pack_propagate(False)

        head = ctk.CTkFrame(side, fg_color="transparent")
        head.pack(fill="x", padx=18, pady=(20, 4))
        ctk.CTkLabel(head, text="🎬 Show Tracker", font=(T.FONT, 20, "bold"), text_color=T.TEXT).pack(anchor="w")
        ctk.CTkLabel(head, text=f"Anime · Movie · Series   v{__version__}", font=(T.FONT, 11),
                     text_color=T.MUTED).pack(anchor="w")
        ctk.CTkFrame(side, height=2, fg_color=T.ACCENT, corner_radius=1).pack(fill="x", padx=18, pady=(10, 6))

        self.status_nav = {}
        self._section(side, "STATUS")
        for name in [ALL] + config.STATUSES:
            btn = NavButton(side, f"{STATUS_ICONS[name]}   {name}", command=lambda n=name: self.set_filter(status=n))
            btn.pack(fill="x", padx=10, pady=1)
            self.status_nav[name] = btn

        bottom = ctk.CTkFrame(side, fg_color="transparent")
        # Dipack sebelum header supaya statistik & pengaturan tidak terpotong di layar pendek.
        bottom.pack(side="bottom", fill="x", padx=14, pady=14, before=head)
        tiles = ctk.CTkFrame(bottom, fg_color="transparent")
        tiles.pack(fill="x")
        tiles.grid_columnconfigure((0, 1), weight=1)
        self.tile_total = StatTile(tiles, "Judul")
        self.tile_eps = StatTile(tiles, "Episode ditonton", T.BLUE)
        self.tile_new = StatTile(tiles, "Episode baru", T.GREEN)
        self.tile_done = StatTile(tiles, "Selesai", T.MUTED)
        for i, tile in enumerate((self.tile_total, self.tile_eps, self.tile_new, self.tile_done)):
            tile.grid(row=i // 2, column=i % 2, sticky="ew", padx=3, pady=3)

        ctk.CTkButton(bottom, text="📊 Statistik lengkap", command=lambda: StatsDialog(self), height=34,
                      corner_radius=8, font=(T.FONT, 12, "bold"), fg_color=T.NEUTRAL_BTN,
                      hover_color=T.NEUTRAL_HOVER, text_color=T.TEXT).pack(fill="x", pady=(8, 8))

        row = ctk.CTkFrame(bottom, fg_color="transparent")
        row.pack(fill="x")
        self.appearance = ctk.CTkSegmentedButton(row, values=["Dark", "Light", "System"], height=28,
                                                 font=(T.FONT, 11), command=self.set_appearance, **T.SEG_BLUE)
        self.appearance.set(self.settings.get("appearance"))
        self.appearance.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(row, text="⚙", width=34, height=28, command=lambda: SettingsDialog(self),
                      fg_color=T.NEUTRAL_BTN, hover_color=T.NEUTRAL_HOVER, text_color=T.TEXT,
                      font=(T.FONT, 14)).pack(side="left", padx=(6, 0))

    def _section(self, master, text):
        ctk.CTkLabel(master, text=text, font=(T.FONT, 11, "bold"), text_color=T.MUTED).pack(
            anchor="w", padx=22, pady=(12, 2))

    def _build_main(self):
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.grid(row=0, column=1, sticky="nsew", padx=(20, 20), pady=(18, 0))
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(2, weight=1)

        top = ctk.CTkFrame(main, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        titles = ctk.CTkFrame(top, fg_color="transparent")
        titles.pack(side="left")
        self.heading = ctk.CTkLabel(titles, text="", font=(T.FONT, 24, "bold"), text_color=T.TEXT)
        self.heading.pack(anchor="w")
        self.subheading = ctk.CTkLabel(titles, text="", font=(T.FONT, 12), text_color=T.MUTED)
        self.subheading.pack(anchor="w")

        ctk.CTkButton(top, text="＋ Tambah", command=lambda: self.open_form(None), height=38, width=120,
                      corner_radius=10, font=(T.FONT, 13, "bold"), fg_color=T.ACCENT,
                      hover_color=T.ACCENT_HOVER).pack(side="right")
        check = ctk.CTkFrame(top, fg_color="transparent")
        check.pack(side="right", padx=(10, 10))
        self.check_btn = ctk.CTkButton(check, text="🔄 Cek Update", command=self.manual_check, height=38, width=130,
                                       corner_radius=10, font=(T.FONT, 13, "bold"), fg_color=T.BLUE,
                                       hover_color=T.BLUE_HOVER)
        self.check_btn.pack()
        self.search = ctk.CTkEntry(top, placeholder_text="🔍  Cari judul / catatan…  (Ctrl+F)", height=38,
                                   width=280, corner_radius=10, font=(T.FONT, 13), **T.ENTRY)
        self.search.pack(side="right")
        self.search.bind("<KeyRelease>", self._on_search_key)

        filters = ctk.CTkFrame(main, fg_color="transparent")
        filters.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        self.type_seg = ctk.CTkSegmentedButton(
            filters, values=[ALL] + [f"{T.TYPE_ICONS[t]} {t}" for t in config.TYPES], height=32,
            font=(T.FONT, 12), command=lambda v: self.set_filter(type_=v.split(" ", 1)[-1]), **T.SEG)
        self.type_seg.set(ALL)
        self.type_seg.pack(side="left")
        ctk.CTkSwitch(filters, text="Hanya yang perlu perhatian", variable=self.only_updates, font=(T.FONT, 12),
                      command=self.apply_filters, progress_color=T.GREEN, text_color=T.TEXT).pack(side="left", padx=18)
        self.last_check = ctk.CTkLabel(filters, text="Belum pernah cek update", font=(T.FONT, 11), text_color=T.MUTED)
        self.last_check.pack(side="right", padx=(10, 0))
        self.sort = ctk.CTkOptionMenu(filters, values=SORTS, command=self.on_sort, height=32, width=170,
                                      font=(T.FONT, 12), **T.OPTION)
        self.sort.set(self.settings.get("sort") if self.settings.get("sort") in SORTS else SORTS[0])
        self.sort.pack(side="right")
        ctk.CTkLabel(filters, text="Urutkan", font=(T.FONT, 12), text_color=T.MUTED).pack(side="right", padx=(0, 8))

        self.list = ctk.CTkScrollableFrame(main, fg_color="transparent", **T.SCROLL)
        self.list.grid(row=2, column=0, sticky="nsew")
        self.empty = ctk.CTkLabel(self.list, text="", font=(T.FONT, 14), text_color=T.MUTED, justify="center")

        self.statusbar = ctk.CTkLabel(self, text="", font=(T.FONT, 11), text_color=T.MUTED, anchor="w")
        self.statusbar.grid(row=1, column=1, sticky="ew", padx=22, pady=(4, 8))

    # ── data ─────────────────────────────────────────────────────────────────
    def reload(self):
        self.shows = db.list_shows()
        self.states = {s["id"]: logic.compute_state(s) for s in self.shows}
        self._update_sidebar()
        self.apply_filters()
        if self.checker.last_check:
            self.last_check.configure(text=f"Cek terakhir: {self.checker.last_check}")

    def _update_sidebar(self):
        for name, btn in self.status_nav.items():
            btn.set_count(len(self.shows) if name == ALL else sum(1 for s in self.shows if s.get("status") == name))
            btn.set_selected(name == self.filter_status)
        self.tile_total.set(len(self.shows))
        self.tile_eps.set(sum((s.get("episode") or 0) for s in self.shows if s.get("type") != "Movie"))
        self.tile_new.set(sum(1 for st in self.states.values() if st.kind == logic.NEW))
        self.tile_done.set(sum(1 for s in self.shows if s.get("status") == "Completed"))

    def set_filter(self, status=None, type_=None):
        if status is not None:
            self.filter_status = status
        if type_ is not None:
            self.filter_type = type_
        self._update_sidebar()
        self.apply_filters()

    def _on_search_key(self, _event):
        if self._search_job:
            self.after_cancel(self._search_job)
        self._search_job = self.after(180, self.apply_filters)

    def on_sort(self, value):
        self.settings.update(sort=value)
        self.apply_filters()

    def _sorted(self, shows):
        mode = self.sort.get()
        status_rank = {s: i for i, s in enumerate(config.STATUSES)}
        if mode == "Terbaru ditambah":
            return sorted(shows, key=lambda s: -s["id"])
        if mode == "Terakhir diubah":
            return sorted(shows, key=lambda s: (s.get("updated_at") or "", s["id"]), reverse=True)
        if mode == "Judul A–Z":
            return sorted(shows, key=lambda s: s["title"].lower())
        if mode == "Status":
            return sorted(shows, key=lambda s: (status_rank.get(s.get("status"), 9), s["title"].lower()))
        return sorted(shows, key=lambda s: (logic.PRIORITY[self.states[s["id"]].kind],
                                            status_rank.get(s.get("status"), 9), -s["id"]))

    def apply_filters(self):
        self._search_job = None
        query = self.search.get().strip().lower()
        visible = []
        for s in self.shows:
            if self.filter_status != ALL and s.get("status") != self.filter_status:
                continue
            if self.filter_type != ALL and s.get("type") != self.filter_type:
                continue
            if self.only_updates.get() and self.states[s["id"]].kind not in (logic.NEW, logic.FINISHED_NOT_DONE, logic.RELEASED):
                continue
            if query and query not in s["title"].lower() and query not in (s.get("notes") or "").lower():
                continue
            visible.append(s)
        visible = self._sorted(visible)

        # Kartu dibuat sekali per show lalu dipakai ulang; hanya urutan & isinya yang diperbarui.
        live_ids = {s["id"] for s in self.shows}
        for show_id in [i for i in self.cards if i not in live_ids]:
            self.cards.pop(show_id).destroy()
        for card in self.cards.values():
            card.pack_forget()
        self.empty.pack_forget()
        for s in visible:
            card = self.cards.get(s["id"])
            if card is None:
                card = self.cards[s["id"]] = ShowCard(self.list, self)
            card.set_show(s, self.states[s["id"]])
            card.pack(fill="x", pady=5, padx=(0, 8))

        if not visible:
            if not self.shows:
                self.empty.configure(text="Belum ada tontonan.\n\nKlik ＋ Tambah (Ctrl+N) untuk mulai mencatat.")
            else:
                self.empty.configure(text="Tidak ada yang cocok dengan filter / pencarian.")
            self.empty.pack(pady=80)

        heading = self.filter_status if self.filter_status != ALL else "Semua tontonan"
        if self.filter_type != ALL:
            heading += f" · {self.filter_type}"
        self.heading.configure(text=heading)
        n_new = sum(1 for s in visible if self.states[s["id"]].kind == logic.NEW)
        sub = f"{len(visible)} judul"
        if n_new:
            sub += f"  ·  {n_new} punya episode baru"
        self.subheading.configure(text=sub)

    # ── aksi ─────────────────────────────────────────────────────────────────
    def flash(self, text, ms=4000):
        self.statusbar.configure(text=text)
        self.after(ms, lambda: self.statusbar.cget("text") == text and self.statusbar.configure(text=""))

    def open_form(self, show):
        ShowFormDialog(self, show, self.save_show)

    def save_show(self, show_id, data):
        if show_id:
            old = db.get_show(show_id) or {}
            db.update_show(show_id, data)
            link_changed = any(old.get(f) != data.get(f) for f in ("bilibili_season_id", "tmdb_id", "tmdb_media"))
            if link_changed:
                db.clear_remote_state(show_id)
        else:
            show_id = db.insert_show(data)
            link_changed = True
        self.reload()
        self.flash(f"Tersimpan: {data['title']}")
        if link_changed and (data.get("bilibili_season_id") or data.get("tmdb_id")):
            self.flash(f"Tersimpan: {data['title']} — mengambil info episode…")
            self.checker.check_show_async(show_id)

    def quick_adjust(self, show_id, delta):
        db.adjust_number(show_id, "episode", delta)
        self.reload()
        show = next((s for s in self.shows if s["id"] == show_id), None)
        if show:
            self.flash(f"{show['title']}: sekarang EP {show.get('episode')}")

    def delete_show(self, show):
        if messagebox.askyesno("Hapus", f"Hapus '{show['title']}' dari daftar?", parent=self):
            db.delete_show(show["id"])
            self.reload()
            self.flash(f"Dihapus: {show['title']}")

    def open_watch(self, show):
        if show.get("tmdb_id"):
            webbrowser.open(tmdb.page_url(show["tmdb_media"], show["tmdb_id"]))
            return
        season_id = show.get("bilibili_season_id")
        if not season_id:
            return
        next_ep = (show.get("episode") or 0) + 1
        self.flash(f"Membuka EP {next_ep} di Bilibili…")

        def run():
            url = bilibili.episode_watch_url(season_id, next_ep)
            if url:
                webbrowser.open(url)
            else:
                self.call_ui(lambda: self.flash(f"EP {next_ep} belum tersedia — membuka halaman season."))
                webbrowser.open(bilibili.page_url(season_id))
        threading.Thread(target=run, daemon=True).start()

    def manual_check(self):
        if self._checking:
            return
        self._checking = True
        self.check_btn.configure(state="disabled", text="⏳ Mengecek…")

        def run():
            try:
                summary = self.checker.check_all()
            except Exception as e:
                summary = {"error": str(e)}
            self.call_ui(self._check_done, summary)
        threading.Thread(target=run, daemon=True).start()

    def _check_done(self, summary):
        self._checking = False
        self.check_btn.configure(state="normal", text="🔄 Cek Update")
        if "error" in summary:
            messagebox.showerror("Cek Update", f"Gagal cek update: {summary['error']}", parent=self)
            return
        if not summary["checked"]:
            messagebox.showinfo("Cek Update", "Belum ada tontonan berstatus Watching / Plan to Watch "
                                "yang terhubung ke Bilibili atau TMDB.", parent=self)
            return
        lines = []
        if summary["new"]:
            lines.append(f"🟢 {len(summary['new'])} judul punya episode baru:")
            lines += [f"   • {t}" for t in summary["new"][:8]]
        if summary["finished"]:
            lines.append(f"\n🟠 {len(summary['finished'])} judul sudah tamat tayang tapi belum selesai kamu tonton:")
            lines += [f"   • {t} (kamu di EP {e})" for t, e in summary["finished"][:8]]
        if not lines:
            lines = ["Semua tontonan kamu sudah up-to-date! ✅"]
        messagebox.showinfo("Cek Update Selesai", f"{summary['checked']} judul dicek.\n\n" + "\n".join(lines), parent=self)

    def set_appearance(self, mode):
        ctk.set_appearance_mode(mode)
        self.settings.update(appearance=mode)

    def on_close(self):
        self.checker.stop()
        self.destroy()


def main():
    db.init_db()
    App().mainloop()
