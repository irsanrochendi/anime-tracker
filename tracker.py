import os
import sys
import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import requests
import threading
import time
import webbrowser

try:
    from win11toast import notify
    HAS_TOAST = True
except ImportError:
    HAS_TOAST = False

# When bundled by PyInstaller, __file__ resolves inside the temp _MEI extraction
# folder (wiped after the app closes), so the DB must live next to the .exe instead.
if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DB_FILE = os.path.join(BASE_DIR, "tracker_db.sqlite")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
CHECK_INTERVAL_SEC = 30 * 60  # cek update episode ke bilibili.tv tiap 30 menit

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    # Create tables
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS shows (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            type TEXT DEFAULT 'Anime',
            season INTEGER DEFAULT 1,
            episode INTEGER DEFAULT 1,
            status TEXT DEFAULT 'Watching',
            notes TEXT,
            bilibili_season_id TEXT DEFAULT NULL,
            latest_episode_str TEXT DEFAULT NULL
        )
    """)
    # Migration checklist if columns don't exist
    cursor.execute("PRAGMA table_info(shows)")
    columns = [col[1] for col in cursor.fetchall()]
    if "bilibili_season_id" not in columns:
        cursor.execute("ALTER TABLE shows ADD COLUMN bilibili_season_id TEXT DEFAULT NULL")
    if "latest_episode_str" not in columns:
        cursor.execute("ALTER TABLE shows ADD COLUMN latest_episode_str TEXT DEFAULT NULL")
    conn.commit()
    conn.close()

# Helper function to parse episode numbers from bilibili string (e.g. "Update to EP 1174", "EP 12", "Full")
def parse_ep_num(ep_str):
    if not ep_str:
        return 0
    import re
    match = re.search(r'(?:EP|Ep|E)\s*(\d+)', ep_str)
    if match:
        return int(match.group(1))
    # Try finding any integer
    match = re.search(r'(\d+)', ep_str)
    if match:
        return int(match.group(1))
    return 0

def fetch_latest_ep_str(season_id, title):
    """
    Ambil status episode terbaru dari Bilibili untuk sebuah season_id.
    Endpoint /ogv/play/series sering mengembalikan cards:null (tidak reliable),
    jadi strategi utama pakai search API (yang selalu ngasih index_show) dan
    cocokkan hasilnya dengan season_id. Endpoint /ogv/play/series dipakai
    sebagai fallback kedua kalau search gagal.
    """
    headers = {"User-Agent": UA, "Referer": "https://www.bilibili.tv/"}

    # Strategi 1: Search API (paling reliable, dipakai juga oleh dialog "Cari Anime")
    try:
        url = "https://api.bilibili.tv/intl/gateway/web/v2/search_v2"
        params = {"s_locale": "en_US", "platform": "web", "keyword": title, "pn": 1, "ps": 15}
        res = requests.get(url, headers=headers, params=params, timeout=10)
        if res.status_code == 200:
            data = res.json()
            modules = data.get("data", {}).get("modules", [])
            for mod in modules:
                if mod.get("type") not in ("ogv", "all"):
                    continue
                for it in mod.get("items", []):
                    candidates = it.get("seasons", [it]) if "seasons" in it else [it]
                    for s in candidates:
                        if str(s.get("season_id", "")) == str(season_id):
                            ep_str = s.get("index_show")
                            if ep_str:
                                return ep_str
    except Exception:
        pass

    # Strategi 2 (fallback): endpoint series/cards langsung berdasarkan season_id
    try:
        url = "https://api.bilibili.tv/intl/gateway/web/v2/ogv/play/series"
        params = {"s_locale": "en_US", "platform": "web", "season_id": season_id}
        headers2 = {"User-Agent": UA, "Referer": f"https://www.bilibili.tv/play/{season_id}"}
        res = requests.get(url, headers=headers2, params=params, timeout=10)
        if res.status_code == 200:
            d = res.json()
            cards = d.get("data", {}).get("cards") or []
            for c in cards:
                if str(c.get("season_id")) == str(season_id):
                    ep_str = c.get("index_show")
                    if ep_str:
                        return ep_str
    except Exception:
        pass

    return None

def get_episode_watch_url(season_id, episode_num):
    """
    Ambil link nonton langsung (Bilibili) untuk nomor episode tertentu dari sebuah season_id.
    Return None jika episode tidak ditemukan / gagal fetch.
    """
    if not season_id or not episode_num:
        return None
    try:
        headers = {"User-Agent": UA, "Referer": f"https://www.bilibili.tv/play/{season_id}"}
        url = "https://api.bilibili.tv/intl/gateway/web/v2/ogv/play/episodes"
        params = {"s_locale": "en_US", "platform": "web", "season_id": season_id}
        res = requests.get(url, headers=headers, params=params, timeout=10)
        if res.status_code == 200:
            data = res.json()
            for sec in data.get("data", {}).get("sections", []):
                for ep in sec.get("episodes", []):
                    short = ep.get("short_title_display", "")
                    import re
                    m = re.search(r'(\d+)', short)
                    if m and int(m.group(1)) == int(episode_num):
                        ep_id = ep.get("episode_id")
                        if ep_id:
                            return f"https://www.bilibili.tv/en/play/{season_id}/{ep_id}"
    except Exception:
        pass
    return None

class BilibiliSearchDialog(tk.Toplevel):
    def __init__(self, parent, default_keyword=""):
        super().__init__(parent)
        self.parent = parent
        self.title("Cari Anime di Bilibili (Bstation)")
        self.geometry("680x450")
        self.minsize(680, 450)
        self.transient(parent)
        self.grab_set()
        
        self.selected_season_id = None
        self.selected_title = None
        
        self.setup_ui(default_keyword)
        if default_keyword:
            self.do_search()

    def setup_ui(self, default_keyword):
        # Search Bar
        top_frame = ttk.Frame(self, padding=10)
        top_frame.pack(fill=tk.X, side=tk.TOP)
        
        ttk.Label(top_frame, text="Keyword: ", font=("Segoe UI", 10)).pack(side=tk.LEFT)
        self.keyword_entry = ttk.Entry(top_frame, width=40, font=("Segoe UI", 10))
        self.keyword_entry.insert(0, default_keyword)
        self.keyword_entry.pack(side=tk.LEFT, padx=5)
        self.keyword_entry.bind("<Return>", lambda e: self.do_search())
        
        btn_search = ttk.Button(top_frame, text="Cari Anime", command=self.do_search)
        btn_search.pack(side=tk.LEFT, padx=5)
        
        # Bottom Action Bar (Pack this first to guarantee visibility at the bottom)
        bot_frame = ttk.Frame(self, padding=15)
        bot_frame.pack(fill=tk.X, side=tk.BOTTOM)
        
        self.status_label = ttk.Label(bot_frame, text="Masukkan kata kunci pencarian...", foreground="gray", font=("Segoe UI", 9))
        self.status_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Define styles for the buttons inside the dialog
        style = ttk.Style(self)
        style.configure("BiliConfirm.TButton", font=("Segoe UI", 10, "bold"))
        style.map("BiliConfirm.TButton",
            foreground=[('pressed', '#ffffff'), ('active', '#ffffff'), ('', '#ffffff')],
            background=[('pressed', '!disabled', '#2ecc71'), ('active', '#2ecc71'), ('', '#2ecc71')]
        )
        
        style.configure("BiliCancel.TButton", font=("Segoe UI", 10, "bold"))
        style.map("BiliCancel.TButton",
            foreground=[('pressed', '#ffffff'), ('active', '#ffffff'), ('', '#ffffff')],
            background=[('pressed', '!disabled', '#95a5a6'), ('active', '#95a5a6'), ('', '#95a5a6')]
        )
        
        btn_cancel = ttk.Button(bot_frame, text="Cancel / Batal", style="BiliCancel.TButton", command=self.destroy)
        btn_cancel.pack(side=tk.RIGHT, padx=5)
        
        btn_select = ttk.Button(bot_frame, text="Confirm / Pilih Anime", style="BiliConfirm.TButton", command=self.on_select)
        btn_select.pack(side=tk.RIGHT, padx=5)

        # Results Table Container Frame (Fills the remaining middle space)
        table_frame = ttk.Frame(self, padding=10)
        table_frame.pack(fill=tk.BOTH, expand=True)
        
        self.tree = ttk.Treeview(table_frame, columns=("title", "season_id", "latest_ep", "type"), show="headings")
        self.tree.heading("title", text="Judul Anime")
        self.tree.heading("season_id", text="Season ID")
        self.tree.heading("latest_ep", text="Episode Terbaru")
        self.tree.heading("type", text="Tipe")
        
        self.tree.column("title", width=280, minwidth=150, anchor=tk.W, stretch=True)
        self.tree.column("season_id", width=90, minwidth=80, anchor=tk.CENTER, stretch=False)
        self.tree.column("latest_ep", width=110, minwidth=100, anchor=tk.CENTER, stretch=False)
        self.tree.column("type", width=60, minwidth=55, anchor=tk.CENTER, stretch=False)
        
        scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        # Pack scrollbar first to the right, then tree to fill the rest
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
    def do_search(self):
        kw = self.keyword_entry.get().strip()
        if not kw:
            return
            
        self.status_label.config(text="Searching...", foreground="blue")
        # Clear list
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        def thread_run():
            try:
                headers = {"User-Agent": UA, "Referer": "https://www.bilibili.tv/"}
                url = "https://api.bilibili.tv/intl/gateway/web/v2/search_v2"
                params = {
                    "s_locale": "en_US",
                    "platform": "web",
                    "keyword": kw,
                    "pn": 1,
                    "ps": 15
                }
                res = requests.get(url, headers=headers, params=params, timeout=10)
                if res.status_code == 200:
                    data = res.json()
                    modules = data.get("data", {}).get("modules", [])
                    found = False
                    for mod in modules:
                        if mod.get("type") == "ogv" or mod.get("type") == "all":
                            items = mod.get("items", [])
                            for it in items:
                                # Standard Anime series usually contain lists of seasons or season_id directly
                                if "seasons" in it:
                                    for s in it["seasons"]:
                                        self.tree.insert("", tk.END, values=(
                                            s.get("title", ""),
                                            s.get("season_id", ""),
                                            s.get("index_show", "N/A"),
                                            s.get("season_type", "Anime")
                                        ))
                                        found = True
                                elif "season_id" in it:
                                    self.tree.insert("", tk.END, values=(
                                        it.get("title", ""),
                                        it.get("season_id", ""),
                                        it.get("index_show", "N/A"),
                                        "Anime"
                                    ))
                                    found = True
                    
                    if found:
                        self.status_label.config(text="Pencarian selesai.", foreground="green")
                    else:
                        self.status_label.config(text="Anime tidak ditemukan.", foreground="red")
                else:
                    self.status_label.config(text=f"Error Bilibili API: {res.status_code}", foreground="red")
            except Exception as e:
                self.status_label.config(text=f"Error pencarian: {str(e)}", foreground="red")
                
        threading.Thread(target=thread_run, daemon=True).start()

    def on_select(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Pilih salah satu anime di list!")
            return
            
        values = self.tree.item(selected[0])["values"]
        self.selected_title = values[0]
        self.selected_season_id = values[1]
        self.destroy()

class AnimeTrackerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Anime & Show Tracker")
        self.geometry("950x580")
        self.minsize(760, 420)
        self.resizable(True, True)
        
        # Style Configuration
        self.style = ttk.Style()
        self.style.theme_use("clam")
        
        # Configure look and feel
        self.configure_colors()
        
        # Variables
        self.search_var = tk.StringVar()
        self.id_var = tk.StringVar()
        self.title_var = tk.StringVar()
        self.type_var = tk.StringVar(value="Anime")
        self.season_var = tk.IntVar(value=1)
        self.episode_var = tk.IntVar(value=1)
        self.status_var = tk.StringVar(value="Watching")
        self.notes_var = tk.StringVar()
        self.bili_id_var = tk.StringVar()
        self.bili_latest_var = tk.StringVar()
        self.last_check_var = tk.StringVar(value="Belum pernah cek update")
        
        self.notifier = HAS_TOAST
        
        self.setup_ui()
        self.load_data()
        
        # Auto check updates in background on startup, then repeat every CHECK_INTERVAL_SEC
        threading.Thread(target=self.periodic_check_loop, daemon=True).start()

    def configure_colors(self):
        self.style.configure(".", background="#f5f6f8", foreground="#2c3e50", font=("Segoe UI", 10))
        self.style.configure("TLabel", background="#f5f6f8", font=("Segoe UI", 10))
        self.style.configure("TFrame", background="#f5f6f8")
        
        self.style.configure("Header.TLabel", font=("Segoe UI", 14, "bold"), background="#f5f6f8", foreground="#2c3e50")
        
        self.style.configure("TButton", font=("Segoe UI", 9, "bold"), borderwidth=1, focuscolor="none")
        self.style.map("TButton",
            foreground=[('pressed', '#ffffff'), ('active', '#ffffff')],
            background=[('pressed', '!disabled', '#2980b9'), ('active', '#3498db'), ('', '#3498db')]
        )
        
        self.style.configure("Danger.TButton", font=("Segoe UI", 9, "bold"))
        self.style.map("Danger.TButton",
            foreground=[('pressed', '#ffffff'), ('active', '#ffffff')],
            background=[('pressed', '!disabled', '#c0392b'), ('active', '#e74c3c'), ('', '#e74c3c')]
        )
        
        self.style.configure("IncDec.TButton", font=("Segoe UI", 11, "bold"), width=3)
        self.style.map("IncDec.TButton",
            foreground=[('pressed', '#ffffff'), ('active', '#ffffff')],
            background=[('pressed', '!disabled', '#16a085'), ('active', '#1abc9c'), ('', '#1abc9c')]
        )

        self.style.configure("Save.TButton", font=("Segoe UI", 10, "bold"))
        self.style.map("Save.TButton",
            foreground=[('pressed', '#ffffff'), ('active', '#ffffff'), ('', '#ffffff')],
            background=[('pressed', '!disabled', '#2ecc71'), ('active', '#2ecc71'), ('', '#2ecc71')]
        )

        self.style.configure("Clear.TButton", font=("Segoe UI", 9))
        self.style.map("Clear.TButton",
            foreground=[('pressed', '#4f5d75'), ('active', '#4f5d75')],
            background=[('pressed', '!disabled', '#d1d5db'), ('active', '#e5e7eb'), ('', '#e5e7eb')]
        )

        self.style.configure("Treeview",
            background="#ffffff",
            fieldbackground="#ffffff",
            rowheight=28,
            font=("Segoe UI", 9)
        )
        self.style.map("Treeview",
            background=[("selected", "#3498db")],
            foreground=[("selected", "#ffffff")]
        )

    def setup_ui(self):
        # 1. Main Header
        header_frame = ttk.Frame(self, padding=(10, 10, 10, 5))
        header_frame.pack(fill=tk.X)
        
        app_title = ttk.Label(header_frame, text="🎬 Tracker Anime / Movie / Series", style="Header.TLabel")
        app_title.pack(side=tk.LEFT)
        
        # Search area
        search_frame = ttk.Frame(header_frame)
        search_frame.pack(side=tk.RIGHT)
        
        ttk.Label(search_frame, text="Cari: ").pack(side=tk.LEFT)
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=20)
        search_entry.pack(side=tk.LEFT, padx=5)
        self.search_var.trace_add("write", lambda *args: self.load_data())
        
        # 2. Main Content Split Panel
        content_frame = ttk.Frame(self, padding=10)
        content_frame.pack(fill=tk.BOTH, expand=True)
        
        # Left Panel (Editor / Creator Form)
        left_panel = ttk.LabelFrame(content_frame, text=" Data Entry ", padding=10)
        left_panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        left_panel.columnconfigure(0, weight=1)
        left_panel.columnconfigure(1, weight=1)
        
        # Form Fields
        ttk.Label(left_panel, text="Judul *").grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=3)
        self.title_entry = ttk.Entry(left_panel, textvariable=self.title_var, width=32)
        self.title_entry.grid(row=1, column=0, columnspan=2, sticky=tk.EW, pady=(0, 8))
        
        ttk.Label(left_panel, text="Tipe").grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=3)
        self.type_combo = ttk.Combobox(left_panel, textvariable=self.type_var, values=["Anime", "Movie", "Series", "Lainnya"], width=30, state="readonly")
        self.type_combo.grid(row=3, column=0, columnspan=2, sticky=tk.EW, pady=(0, 8))
        
        # Season Control
        ttk.Label(left_panel, text="Season").grid(row=4, column=0, sticky=tk.W, pady=3)
        season_frame = ttk.Frame(left_panel)
        season_frame.grid(row=5, column=0, columnspan=2, sticky=tk.W, pady=(0, 8))
        
        btn_dec_s = ttk.Button(season_frame, text="-", style="IncDec.TButton", command=lambda: self.change_val(self.season_var, -1))
        btn_dec_s.pack(side=tk.LEFT)
        self.season_entry = ttk.Entry(season_frame, textvariable=self.season_var, width=8, justify="center")
        self.season_entry.pack(side=tk.LEFT, padx=5)
        btn_inc_s = ttk.Button(season_frame, text="+", style="IncDec.TButton", command=lambda: self.change_val(self.season_var, 1))
        btn_inc_s.pack(side=tk.LEFT)
        
        # Episode Control
        ttk.Label(left_panel, text="Episode terakhir ditonton").grid(row=6, column=0, sticky=tk.W, pady=3)
        ep_frame = ttk.Frame(left_panel)
        ep_frame.grid(row=7, column=0, columnspan=2, sticky=tk.W, pady=(0, 8))
        
        btn_dec_e = ttk.Button(ep_frame, text="-", style="IncDec.TButton", command=lambda: self.change_val(self.episode_var, -1))
        btn_dec_e.pack(side=tk.LEFT)
        self.episode_entry = ttk.Entry(ep_frame, textvariable=self.episode_var, width=8, justify="center")
        self.episode_entry.pack(side=tk.LEFT, padx=5)
        btn_inc_e = ttk.Button(ep_frame, text="+", style="IncDec.TButton", command=lambda: self.change_val(self.episode_var, 1))
        btn_inc_e.pack(side=tk.LEFT)
        
        # Status
        ttk.Label(left_panel, text="Status").grid(row=8, column=0, columnspan=2, sticky=tk.W, pady=3)
        self.status_combo = ttk.Combobox(left_panel, textvariable=self.status_var, values=["Watching", "Completed", "Plan to Watch", "Dropped"], width=30, state="readonly")
        self.status_combo.grid(row=9, column=0, columnspan=2, sticky=tk.EW, pady=(0, 8))
        
        # Bilibili Season Link
        ttk.Label(left_panel, text="Bilibili Season ID").grid(row=10, column=0, columnspan=2, sticky=tk.W, pady=3)
        bili_frame = ttk.Frame(left_panel)
        bili_frame.grid(row=11, column=0, columnspan=2, sticky=tk.EW, pady=(0, 8))
        bili_frame.columnconfigure(0, weight=1)
        self.bili_entry = ttk.Entry(bili_frame, textvariable=self.bili_id_var, width=18)
        self.bili_entry.grid(row=0, column=0, sticky=tk.EW)
        btn_bili_search = ttk.Button(bili_frame, text="Cari Anime", command=self.search_bilibili_id, width=12)
        btn_bili_search.grid(row=0, column=1, sticky=tk.E, padx=(5,0))
        
        # Notes
        ttk.Label(left_panel, text="Catatan / Keterangan").grid(row=12, column=0, columnspan=2, sticky=tk.W, pady=3)
        self.notes_entry = ttk.Entry(left_panel, textvariable=self.notes_var, width=32)
        self.notes_entry.grid(row=13, column=0, columnspan=2, sticky=tk.EW, pady=(0, 12))
        
        # Form buttons
        btn_save = ttk.Button(left_panel, text="Simpan / Tambah Data", style="Save.TButton", command=self.save_item)
        btn_save.grid(row=14, column=0, columnspan=2, sticky=tk.EW, pady=8)
        
        btn_clear = ttk.Button(left_panel, text="Reset Form", style="Clear.TButton", command=self.clear_form)
        btn_clear.grid(row=15, column=0, columnspan=2, sticky=tk.EW, pady=4)
        
        # Right Panel
        right_panel = ttk.Frame(content_frame)
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # Treeview (Table)
        self.tree = ttk.Treeview(right_panel, columns=("id", "title", "type", "season", "episode", "status", "bili_id", "bili_latest", "notes"), show="headings")
        self.tree.heading("id", text="ID")
        self.tree.heading("title", text="Judul")
        self.tree.heading("type", text="Tipe")
        self.tree.heading("season", text="Sqn")
        self.tree.heading("episode", text="Ep")
        self.tree.heading("status", text="Status")
        self.tree.heading("bili_id", text="Bili ID")
        self.tree.heading("bili_latest", text="Update Bilibili")
        self.tree.heading("notes", text="Catatan")
        
        self.tree.column("id", width=35, minwidth=35, anchor=tk.CENTER, stretch=False)
        self.tree.column("title", width=180, minwidth=120, anchor=tk.W, stretch=True)
        self.tree.column("type", width=65, minwidth=60, anchor=tk.CENTER, stretch=False)
        self.tree.column("season", width=45, minwidth=40, anchor=tk.CENTER, stretch=False)
        self.tree.column("episode", width=45, minwidth=40, anchor=tk.CENTER, stretch=False)
        self.tree.column("status", width=95, minwidth=80, anchor=tk.CENTER, stretch=False)
        self.tree.column("bili_id", width=65, minwidth=65, anchor=tk.CENTER, stretch=False)
        self.tree.column("bili_latest", width=140, minwidth=110, anchor=tk.W, stretch=True)
        self.tree.column("notes", width=100, minwidth=80, anchor=tk.W, stretch=True)
        
        scrollbar = ttk.Scrollbar(right_panel, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, after=self.tree)
        
        # Color tag rows if there is update!
        self.tree.tag_configure("has_update", background="#e8f8f5", foreground="#117864")
        
        self.tree.bind("<<TreeviewSelect>>", self.on_select_row)
        
        # Action Toolbar
        toolbar = ttk.Frame(right_panel, padding=(0, 10, 0, 0))
        toolbar.pack(side=tk.BOTTOM, fill=tk.X)
        
        shortcut_frame = ttk.LabelFrame(toolbar, text=" Quick Update (Pilih Baris) ", padding=5)
        shortcut_frame.pack(side=tk.LEFT, fill=tk.Y)
        
        ttk.Label(shortcut_frame, text="Ep: ").pack(side=tk.LEFT, padx=2)
        ttk.Button(shortcut_frame, text="-1", style="IncDec.TButton", command=lambda: self.quick_adjust_ep(-1)).pack(side=tk.LEFT, padx=2)
        ttk.Button(shortcut_frame, text="+1", style="IncDec.TButton", command=lambda: self.quick_adjust_ep(1)).pack(side=tk.LEFT, padx=2)
        
        ttk.Label(shortcut_frame, text="  Seq: ").pack(side=tk.LEFT, padx=2)
        ttk.Button(shortcut_frame, text="-1", style="IncDec.TButton", command=lambda: self.quick_adjust_seq(-1)).pack(side=tk.LEFT, padx=2)
        ttk.Button(shortcut_frame, text="+1", style="IncDec.TButton", command=lambda: self.quick_adjust_seq(1)).pack(side=tk.LEFT, padx=2)
        
        btn_watch_next = ttk.Button(shortcut_frame, text="▶️ Nonton Ep Selanjutnya", command=self.open_next_episode)
        btn_watch_next.pack(side=tk.LEFT, padx=(10, 2))
        
        # Bilibili Action Panel
        bili_act_frame = ttk.Frame(toolbar)
        bili_act_frame.pack(side=tk.LEFT, padx=20)
        
        btn_check_now = ttk.Button(bili_act_frame, text="🔄 Cek Update Episode", command=self.trigger_manual_check)
        btn_check_now.pack(side=tk.LEFT)
        
        ttk.Label(bili_act_frame, textvariable=self.last_check_var, foreground="gray", font=("Segoe UI", 8)).pack(side=tk.LEFT, padx=8)
        
        btn_delete = ttk.Button(toolbar, text="Hapus Data", style="Danger.TButton", command=self.delete_item)
        btn_delete.pack(side=tk.RIGHT, padx=5)

    def open_next_episode(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Pilih Data", "Pilih dulu baris anime di tabel.")
            return
        
        bili_id = self.bili_id_var.get().strip()
        if not bili_id:
            messagebox.showwarning("Tidak Ada Bilibili ID", "Anime ini belum terhubung dengan Bilibili Season ID.\nGunakan 'Cari Anime' untuk menghubungkan.")
            return
        
        try:
            current_ep = int(self.episode_var.get())
        except ValueError:
            current_ep = 0
        next_ep = current_ep + 1
        
        title = self.title_var.get()
        
        def thread_run():
            url = get_episode_watch_url(bili_id, next_ep)
            if url:
                webbrowser.open(url)
            else:
                self.after(0, lambda: messagebox.showinfo(
                    "Episode Tidak Ditemukan",
                    f"Episode {next_ep} untuk '{title}' belum tersedia di Bilibili, atau data episode tidak ditemukan."
                ))
        
        threading.Thread(target=thread_run, daemon=True).start()

    def change_val(self, var, delta):
        try:
            val = int(var.get())
        except ValueError:
            val = 0
        new_val = val + delta
        if new_val < 0:
            new_val = 0
        var.set(new_val)

    def search_bilibili_id(self):
        default_kw = self.title_var.get().strip()
        dialog = BilibiliSearchDialog(self, default_kw)
        self.wait_window(dialog)
        if dialog.selected_season_id:
            self.bili_id_var.set(dialog.selected_season_id)
            if not self.title_var.get().strip():
                self.title_var.set(dialog.selected_title)

    def load_data(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        search_query = self.search_var.get().strip()
        
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        if search_query:
            cursor.execute("""
                SELECT id, title, type, season, episode, status, bilibili_season_id, latest_episode_str, notes 
                FROM shows 
                WHERE title LIKE ? OR notes LIKE ? OR status LIKE ? OR type LIKE ?
                ORDER BY id DESC
            """, (f"%{search_query}%", f"%{search_query}%", f"%{search_query}%", f"%{search_query}%"))
        else:
            cursor.execute("SELECT id, title, type, season, episode, status, bilibili_season_id, latest_episode_str, notes FROM shows ORDER BY id DESC")
            
        for row in cursor.fetchall():
            row_id, title, show_type, season, episode, status, bili_id, bili_latest, notes = row
            
            # Show update indicators
            tags = ()
            display_latest = bili_latest if bili_latest else "-"
            
            if bili_id and bili_latest:
                bili_ep_num = parse_ep_num(bili_latest)
                if bili_ep_num > episode:
                    tags = ("has_update",)
                    display_latest = f"🔴 Baru (EP {bili_ep_num})"
                else:
                    display_latest = f"✅ Up-to-date ({bili_latest})"
            
            self.tree.insert("", tk.END, values=(
                row_id, title, show_type, season, episode, status, bili_id if bili_id else "-", display_latest, notes if notes else ""
            ), tags=tags)
            
        conn.close()

    def on_select_row(self, event):
        selected = self.tree.selection()
        if not selected:
            return
            
        item = self.tree.item(selected[0])
        values = item["values"]
        
        if values:
            self.id_var.set(values[0])
            self.title_var.set(values[1])
            self.type_var.set(values[2])
            self.season_var.set(values[3])
            self.episode_var.set(values[4])
            self.status_var.set(values[5])
            
            bili_id = values[6]
            self.bili_id_var.set(bili_id if bili_id != "-" else "")
            
            self.notes_var.set(values[8])

    def save_item(self):
        title = self.title_var.get().strip()
        if not title:
            messagebox.showwarning("Validation Error", "Judul tidak boleh kosong!")
            return
            
        show_type = self.type_var.get()
        try:
            season = int(self.season_var.get())
            episode = int(self.episode_var.get())
        except ValueError:
            messagebox.showwarning("Validation Error", "Season dan Episode harus berupa angka!")
            return
            
        status = self.status_var.get()
        notes = self.notes_var.get().strip()
        bili_id = self.bili_id_var.get().strip()
        bili_id = bili_id if bili_id else None
        
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        selected_id = self.id_var.get()
        if selected_id:
            # Update existing
            cursor.execute("""
                UPDATE shows 
                SET title=?, type=?, season=?, episode=?, status=?, notes=?, bilibili_season_id=?
                WHERE id=?
            """, (title, show_type, season, episode, status, notes, bili_id, selected_id))
            conn.commit()
            
            # Fetch updates for this item if Bili ID changed/added
            if bili_id:
                threading.Thread(target=self.check_single_show_update, args=(selected_id, bili_id, title, episode), daemon=True).start()
        else:
            # Insert new
            cursor.execute("""
                INSERT INTO shows (title, type, season, episode, status, notes, bilibili_season_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (title, show_type, season, episode, status, notes, bili_id))
            conn.commit()
            
            inserted_id = cursor.lastrowid
            if bili_id:
                threading.Thread(target=self.check_single_show_update, args=(inserted_id, bili_id, title, episode), daemon=True).start()
            
        conn.close()
        
        self.clear_form()
        self.load_data()
        
    def delete_item(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Selection Warning", "Pilih data di tabel terlebih dahulu untuk menghapus!")
            return
            
        item = self.tree.item(selected[0])
        show_id = item["values"][0]
        show_title = item["values"][1]
        
        confirm = messagebox.askyesno("Hapus Data", f"Apakah Anda yakin ingin menghapus '{show_title}'?")
        if confirm:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM shows WHERE id=?", (show_id,))
            conn.commit()
            conn.close()
            
            self.clear_form()
            self.load_data()

    def clear_form(self):
        self.id_var.set("")
        self.title_var.set("")
        self.type_var.set("Anime")
        self.season_var.set(1)
        self.episode_var.set(1)
        self.status_var.set("Watching")
        self.bili_id_var.set("")
        self.notes_var.set("")
        self.tree.selection_remove(self.tree.selection())

    def quick_adjust_ep(self, delta):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Selection Warning", "Pilih data di tabel terlebih dahulu!")
            return
            
        item = self.tree.item(selected[0])
        show_id = item["values"][0]
        curr_ep = int(item["values"][4])
        
        new_ep = curr_ep + delta
        if new_ep < 0:
            new_ep = 0
            
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("UPDATE shows SET episode=? WHERE id=?", (new_ep, show_id))
        conn.commit()
        conn.close()
        
        self.load_data()
        
        # Select the item again to keep view active
        for item_id in self.tree.get_children():
            if self.tree.item(item_id)["values"][0] == show_id:
                self.tree.selection_set(item_id)
                self.tree.focus(item_id)
                break

    def quick_adjust_seq(self, delta):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Selection Warning", "Pilih data di tabel terlebih dahulu!")
            return
            
        item = self.tree.item(selected[0])
        show_id = item["values"][0]
        curr_seq = int(item["values"][3])
        
        new_seq = curr_seq + delta
        if new_seq < 0:
            new_seq = 0
            
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("UPDATE shows SET season=? WHERE id=?", (new_seq, show_id))
        conn.commit()
        conn.close()
        
        self.load_data()
        
        for item_id in self.tree.get_children():
            if self.tree.item(item_id)["values"][0] == show_id:
                self.tree.selection_set(item_id)
                self.tree.focus(item_id)
                break

    # === Bilibili Checks and Reminders ===
    def periodic_check_loop(self):
        """Jalan terus selama app hidup: cek update episode ke bilibili.tv tiap CHECK_INTERVAL_SEC."""
        while True:
            self.auto_check_updates(manual=False)
            time.sleep(CHECK_INTERVAL_SEC)

    def trigger_manual_check(self):
        threading.Thread(target=self.auto_check_updates, args=(True,), daemon=True).start()

    def check_single_show_update(self, show_id, season_id, title, user_ep):
        try:
            latest_ep_str = fetch_latest_ep_str(season_id, title)

            if latest_ep_str:
                # Read old value first to detect real changes (avoid re-notifying every check)
                conn = sqlite3.connect(DB_FILE)
                cursor = conn.cursor()
                cursor.execute("SELECT latest_episode_str FROM shows WHERE id=?", (show_id,))
                row = cursor.fetchone()
                old_ep_str = row[0] if row else None

                # Save to DB
                cursor.execute("UPDATE shows SET latest_episode_str=? WHERE id=?", (latest_ep_str, show_id))
                conn.commit()
                conn.close()
                
                # Refresh UI
                self.parent_refresh_callback()
                
                # Notify only if the latest known episode actually went UP since last check
                # AND it's still newer than what the user has watched.
                old_ep_num = parse_ep_num(old_ep_str)
                bili_ep_num = parse_ep_num(latest_ep_str)
                if bili_ep_num > old_ep_num and bili_ep_num > user_ep and self.notifier:
                    notify(
                        "Anime Update!",
                        f"Episode terbaru untuk '{title}' sudah rilis di Bilibili: {latest_ep_str}\n(Episode Anda saat ini: EP {user_ep})"
                    )
        except Exception:
            pass

    def auto_check_updates(self, manual=False):
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT id, title, episode, bilibili_season_id, latest_episode_str FROM shows WHERE bilibili_season_id IS NOT NULL AND status='Watching'")
        shows_to_check = cursor.fetchall()
        conn.close()
        
        if not shows_to_check:
            if manual:
                messagebox.showinfo("Cek Update", "Tidak ada anime berstatus 'Watching' yang terhubung dengan Bilibili ID.")
            return
            
        has_new_releases = False
        
        for show in shows_to_check:
            show_id, title, user_ep, season_id, old_ep_str = show
            try:
                latest_ep_str = fetch_latest_ep_str(season_id, title)

                if latest_ep_str:
                    conn = sqlite3.connect(DB_FILE)
                    cursor = conn.cursor()
                    cursor.execute("UPDATE shows SET latest_episode_str=? WHERE id=?", (latest_ep_str, show_id))
                    conn.commit()
                    conn.close()
                    
                    # Notify only if the latest known episode actually went UP since last check
                    # AND it's still newer than what the user has watched.
                    old_ep_num = parse_ep_num(old_ep_str)
                    bili_ep_num = parse_ep_num(latest_ep_str)
                    if bili_ep_num > user_ep:
                        has_new_releases = True
                        if bili_ep_num > old_ep_num and self.notifier:
                            notify(
                                "Anime Update!",
                                f"Episode terbaru untuk '{title}' sudah rilis di Bilibili: {latest_ep_str}\n(Episode Anda saat ini: EP {user_ep})"
                            )
            except Exception:
                pass
                
        self.parent_refresh_callback()
        self.after(0, lambda: self.last_check_var.set(f"Cek terakhir: {time.strftime('%H:%M:%S')}"))
        
        if manual:
            if has_new_releases:
                messagebox.showinfo("Cek Update Selesai", "Ada update episode baru! Detail rilis ditandai warna hijau di tabel.")
            else:
                messagebox.showinfo("Cek Update Selesai", "Semua anime Anda sudah up-to-date!")

    def parent_refresh_callback(self):
        # Tkinter handles UI thread safely
        self.after(0, self.load_data)

if __name__ == "__main__":
    init_db()
    app = AnimeTrackerApp()
    app.mainloop()
