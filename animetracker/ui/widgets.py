import os

import customtkinter as ctk

from .. import logic, posters
from . import theme as T


class ImageCache:
    """CTkImage untuk poster: cache di memori + download async lewat posters.fetch_async."""

    def __init__(self, call_ui):
        self.call_ui = call_ui
        self._images = {}

    def _make(self, pil_img, size):
        return ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=size)

    def placeholder(self, title, size):
        key = ("ph", (title or "?")[:24], size)
        if key not in self._images:
            self._images[key] = self._make(posters.placeholder(title, (size[0] * 2, size[1] * 2)), size)
        return self._images[key]

    def _from_path(self, path, size):
        key = (path, size)
        if key not in self._images:
            try:
                self._images[key] = self._make(posters.load_cover(path, (size[0] * 2, size[1] * 2)), size)
            except OSError:
                return None
        return self._images[key]

    def get(self, url, size, title, on_ready):
        """Return gambar yang langsung bisa dipakai; kalau perlu download, on_ready(img) dipanggil nanti."""
        if not url:
            return self.placeholder(title, size)
        path = posters.cache_path(url)
        if os.path.exists(path):
            return self._from_path(path, size) or self.placeholder(title, size)

        def done(local):
            if local:
                self.call_ui(lambda: self._deliver(local, size, on_ready))
        posters.fetch_async(url, done)
        return self.placeholder(title, size)

    def _deliver(self, path, size, on_ready):
        img = self._from_path(path, size)
        if img:
            on_ready(img)


class Stepper(ctk.CTkFrame):
    """[−] angka [+] untuk season / episode."""

    def __init__(self, master, value=1, width=150):
        super().__init__(master, fg_color="transparent")
        self.var = ctk.StringVar(value=str(value))
        btn = dict(width=34, height=34, corner_radius=8, fg_color=T.NEUTRAL_BTN, hover_color=T.NEUTRAL_HOVER,
                   text_color=T.TEXT, font=(T.FONT, 16, "bold"))
        ctk.CTkButton(self, text="−", command=lambda: self.add(-1), **btn).pack(side="left")
        ctk.CTkEntry(self, textvariable=self.var, width=width - 80, height=34, justify="center",
                     font=(T.FONT, 14), **T.ENTRY).pack(side="left", padx=6)
        ctk.CTkButton(self, text="+", command=lambda: self.add(1), **btn).pack(side="left")

    def get(self):
        """Angka >= 0, atau None kalau input tidak valid."""
        try:
            value = int(self.var.get().strip())
        except ValueError:
            return None
        return value if value >= 0 else None

    def set(self, value):
        self.var.set(str(value))

    def add(self, delta):
        self.set(max(0, (self.get() or 0) + delta))


class NavButton(ctk.CTkButton):
    def __init__(self, master, text, command):
        super().__init__(master, text=text, command=command, anchor="w", height=34, corner_radius=8,
                         fg_color="transparent", hover_color=T.SURFACE_ALT, text_color=T.TEXT,
                         font=(T.FONT, 13))
        self.count = ctk.CTkLabel(self, text="", text_color=T.MUTED, font=(T.FONT, 12), fg_color="transparent")
        self.count.place(relx=1.0, rely=0.5, x=-12, anchor="e")
        self.count.bind("<Button-1>", lambda e: command())

    def set_count(self, n):
        self.count.configure(text=str(n))

    def set_selected(self, selected):
        self.configure(fg_color=T.SURFACE_ALT if selected else "transparent",
                       text_color=T.ACCENT if selected else T.TEXT,
                       font=(T.FONT, 13, "bold" if selected else "normal"))


class StatTile(ctk.CTkFrame):
    def __init__(self, master, label, color=T.TEXT):
        super().__init__(master, fg_color=T.SURFACE_ALT, corner_radius=10)
        self.value = ctk.CTkLabel(self, text="0", font=(T.FONT, 20, "bold"), text_color=color)
        self.value.pack(anchor="w", padx=10, pady=(6, 0))
        ctk.CTkLabel(self, text=label, font=(T.FONT, 11), text_color=T.MUTED).pack(anchor="w", padx=10, pady=(0, 6))

    def set(self, value):
        self.value.configure(text=str(value))


def pill(master, text="", color=T.BLUE):
    return ctk.CTkLabel(master, text=text, fg_color=color, text_color="#FFFFFF", corner_radius=8,
                        font=(T.FONT, 11, "bold"), height=22, padx=8)


class ShowCard(ctk.CTkFrame):
    POSTER = (64, 94)

    def __init__(self, master, app):
        super().__init__(master, fg_color=T.SURFACE, corner_radius=12, border_width=1, border_color=T.BORDER)
        self.app = app
        self.show = None
        self._poster_url = object()
        self.grid_columnconfigure(2, weight=1)

        self.stripe = ctk.CTkFrame(self, width=4, height=1, corner_radius=2, fg_color="transparent")
        self.stripe.grid(row=0, column=0, sticky="ns", padx=(6, 0), pady=12)

        self.poster = ctk.CTkLabel(self, text="", width=self.POSTER[0], height=self.POSTER[1])
        self.poster.grid(row=0, column=1, padx=(8, 14), pady=10)

        info = ctk.CTkFrame(self, fg_color="transparent")
        info.grid(row=0, column=2, sticky="nsew", pady=10)
        self.title = ctk.CTkLabel(info, text="", font=(T.FONT, 15, "bold"), text_color=T.TEXT,
                                  anchor="w", justify="left", wraplength=520)
        self.title.pack(anchor="w", fill="x")

        meta = ctk.CTkFrame(info, fg_color="transparent")
        meta.pack(anchor="w", pady=(4, 2))
        self.status = pill(meta)
        self.status.pack(side="left")
        self.meta = ctk.CTkLabel(meta, text="", font=(T.FONT, 12), text_color=T.MUTED)
        self.meta.pack(side="left", padx=(10, 0))

        self.state = ctk.CTkLabel(info, text="", font=(T.FONT, 12, "bold"), anchor="w")
        self.state.pack(anchor="w")
        self.notes = ctk.CTkLabel(info, text="", font=(T.FONT, 11), text_color=T.MUTED, anchor="w",
                                  justify="left", wraplength=520)

        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.grid(row=0, column=3, padx=(8, 14), pady=10, sticky="e")
        small = dict(height=30, corner_radius=8, font=(T.FONT, 12, "bold"))
        neutral = dict(fg_color=T.NEUTRAL_BTN, hover_color=T.NEUTRAL_HOVER, text_color=T.TEXT)

        stepper = ctk.CTkFrame(actions, fg_color="transparent")
        stepper.pack(anchor="e")
        ctk.CTkButton(stepper, text="−", width=32, command=lambda: self.app.quick_adjust(self.show["id"], -1),
                      **small, **neutral).pack(side="left")
        self.ep_label = ctk.CTkLabel(stepper, text="", width=70, font=(T.FONT, 13, "bold"), text_color=T.TEXT)
        self.ep_label.pack(side="left", padx=4)
        ctk.CTkButton(stepper, text="+1", width=40, command=lambda: self.app.quick_adjust(self.show["id"], 1),
                      fg_color=T.GREEN, hover_color=T.GREEN_HOVER, text_color="#FFFFFF", **small).pack(side="left")

        row2 = ctk.CTkFrame(actions, fg_color="transparent")
        row2.pack(anchor="e", pady=(8, 0))
        self.watch_btn = ctk.CTkButton(row2, text="▶ Nonton", width=92, command=lambda: self.app.open_watch(self.show),
                                       fg_color=T.ACCENT, hover_color=T.ACCENT_HOVER, text_color="#FFFFFF", **small)
        self.watch_btn.pack(side="left")
        ctk.CTkButton(row2, text="✎", width=34, command=lambda: self.app.open_form(self.show),
                      **small, **neutral).pack(side="left", padx=(6, 0))
        ctk.CTkButton(row2, text="🗑", width=34, command=lambda: self.app.delete_show(self.show),
                      **small, **neutral).pack(side="left", padx=(6, 0))

        for w in (self, info, meta, self.title, self.meta, self.state, self.notes, self.poster):
            w.bind("<Double-Button-1>", lambda e: self.app.open_form(self.show))

    def set_show(self, show, state):
        self.show = show
        self.title.configure(text=show["title"])
        status = show.get("status") or "Watching"
        self.status.configure(text=status, fg_color=T.STATUS_COLORS.get(status, T.BLUE))

        parts = [f"{T.TYPE_ICONS.get(show.get('type'), '📁')} {show.get('type') or 'Lainnya'}"]
        if show.get("type") != "Movie":
            parts.append(f"Season {show.get('season') or 0}")
        if show.get("bilibili_season_id"):
            parts.append("Bilibili")
        elif show.get("tmdb_id"):
            parts.append("TMDB")
        self.meta.configure(text="  ·  ".join(parts))

        self.state.configure(text=state.label, text_color=T.STATE_COLORS.get(state.kind, T.MUTED))
        stripe = T.STATE_STRIPES.get(state.kind)
        self.stripe.configure(fg_color=stripe or "transparent")
        self.ep_label.configure(text=f"EP {show.get('episode') or 0}")

        notes = (show.get("notes") or "").strip()
        if notes:
            self.notes.configure(text=notes if len(notes) <= 140 else notes[:137] + "…")
            self.notes.pack(anchor="w", pady=(2, 0))
        else:
            self.notes.pack_forget()

        linked = show.get("bilibili_season_id") or show.get("tmdb_id")
        self.watch_btn.configure(text="▶ Nonton" if show.get("bilibili_season_id") else "↗ Buka",
                                 state="normal" if linked else "disabled")

        key = show.get("poster_url") or ("placeholder", show["title"])
        if key != self._poster_url:
            self._poster_url = key
            url = show.get("poster_url")

            def ready(img):
                if self.winfo_exists() and self._poster_url == key:
                    self.poster.configure(image=img)
            self.poster.configure(image=self.app.images.get(url, self.POSTER, show["title"], ready))
