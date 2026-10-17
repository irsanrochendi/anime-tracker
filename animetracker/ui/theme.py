"""Palet warna (light, dark) — gaya streaming/OTT: gelap sinematik + aksen merah."""
from .. import logic

BG = ("#F3F4F9", "#0F0F23")
SURFACE = ("#FFFFFF", "#1B1B30")
SURFACE_ALT = ("#E9EBF3", "#25253F")
SIDEBAR = ("#FFFFFF", "#13132A")
BORDER = ("#DADDE8", "#2E2E52")
TEXT = ("#111827", "#F8FAFC")
MUTED = ("#6B7280", "#94A3B8")

ACCENT = ("#E11D48", "#E11D48")
ACCENT_HOVER = ("#BE123C", "#9F1239")
GREEN = ("#16A34A", "#22C55E")
GREEN_HOVER = ("#15803D", "#15803D")
ORANGE = ("#D97706", "#F59E0B")
BLUE = ("#4338CA", "#6366F1")
BLUE_HOVER = ("#3730A3", "#4F46E5")
NEUTRAL_BTN = ("#E5E7EB", "#2A2A48")
NEUTRAL_HOVER = ("#D1D5DB", "#34345A")

STATUS_COLORS = {
    "Watching": ("#4338CA", "#6366F1"),
    "Completed": ("#16A34A", "#16A34A"),
    "Plan to Watch": ("#7C3AED", "#7C3AED"),
    "Dropped": ("#6B7280", "#4B5563"),
}

TYPE_ICONS = {"Anime": "🌸", "Movie": "🎬", "Series": "📺", "Lainnya": "📁"}

STATE_COLORS = {
    logic.NEW: GREEN,
    logic.FINISHED_NOT_DONE: ORANGE,
    logic.RELEASED: BLUE,
    logic.UNRELEASED: MUTED,
    logic.UP_TO_DATE: TEXT,
    logic.DONE: MUTED,
    logic.NONE: MUTED,
}

# Garis aksen di kiri kartu; None = tanpa garis.
STATE_STRIPES = {
    logic.NEW: GREEN,
    logic.FINISHED_NOT_DONE: ORANGE,
    logic.RELEASED: BLUE,
}

FONT = "Segoe UI"

# Gaya bersama supaya widget bawaan CustomTkinter (default abu-abu) ikut palet ini.
ENTRY = dict(fg_color=SURFACE, border_color=BORDER, text_color=TEXT, placeholder_text_color=MUTED)
TEXTBOX = dict(fg_color=SURFACE, border_color=BORDER, text_color=TEXT)
SEG = dict(fg_color=SURFACE_ALT, unselected_color=SURFACE_ALT, unselected_hover_color=NEUTRAL_HOVER,
           selected_color=("#FECDD3", "#E11D48"), selected_hover_color=("#FDA4AF", "#BE123C"), text_color=TEXT)
SEG_BLUE = dict(SEG, selected_color=("#C7D2FE", "#4338CA"), selected_hover_color=("#A5B4FC", "#3730A3"))
OPTION = dict(fg_color=SURFACE_ALT, button_color=SURFACE_ALT, button_hover_color=NEUTRAL_HOVER, text_color=TEXT,
              dropdown_fg_color=SURFACE, dropdown_hover_color=SURFACE_ALT, dropdown_text_color=TEXT)
SCROLL = dict(scrollbar_button_color=BORDER, scrollbar_button_hover_color=NEUTRAL_HOVER)
