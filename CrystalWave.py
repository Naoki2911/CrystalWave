import colorsys
import io
import json
import os
import queue
import random
import re
import sys
import threading
import time
import tkinter as tk
import tkinter.font as tkfont
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from tkinter import filedialog, messagebox, ttk

import customtkinter as ctk

try:
    import vlc
except Exception:
    raise SystemExit("VLC not found. Install VLC media player (videolan.org), then: pip install python-vlc")

try:
    from PIL import Image, ImageDraw, ImageFilter, ImageTk
except Exception:
    raise SystemExit("Pillow not found. Run: pip install pillow")

import yt_dlp

try:
    import certifi
    os.environ.setdefault("SSL_CERT_FILE", certifi.where())
    os.environ.setdefault("REQUESTS_CA_BUNDLE", certifi.where())
except Exception:
    pass

HOME = os.path.expanduser("~")
APP_DIR = os.path.dirname(os.path.abspath(__file__))
LIB_FILE = os.path.join(HOME, ".musify_library.json")
PLAYLISTS_FILE = os.path.join(HOME, ".musify_playlists.json")
SETTINGS_FILE = os.path.join(HOME, ".musify_settings.json")
STATS_FILE = os.path.join(HOME, ".musify_stats.json")
def resource_path(relative_path):
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base_path = sys._MEIPASS
    else:
        base_path = APP_DIR
    return os.path.join(base_path, relative_path)


ICON_FILE = resource_path("icon.ico")
DEFAULT_PLAYLIST = "My Playlist"
FAV_NAME = "Favorites"
RECENT_NAME = "Recently Played"
RECENT_MAX = 100
SLEEP_CHOICES = (("Off", None), ("15 minutes", 15), ("30 minutes", 30), ("45 minutes", 45),
                 ("1 hour", 60), ("End of this song", "song"))
LRCLIB_API = "https://lrclib.net/api/search"
THUMB_SIZE = 44
THUMB_RADIUS = 9
FADE_MS = 220
FADE_STEPS = 11

QUALITY_ORDER = ["low", "medium", "high", "very_high", "lossless"]
QUALITY = {
    "low": {
        "label": "Low",
        "desc": "About 50 kbps. Uses the least data and starts fastest.",
        "format": "bestaudio[abr<=64]/worstaudio/worst",
    },
    "medium": {
        "label": "Medium",
        "desc": "About 70 kbps. A balance for slower connections.",
        "format": "bestaudio[abr<=96]/bestaudio[abr<=64]/worstaudio/worst",
    },
    "high": {
        "label": "High",
        "desc": "About 128 kbps AAC. Good for everyday listening.",
        "format": "bestaudio[ext=m4a][abr<=160]/bestaudio[abr<=160]/bestaudio/best",
    },
    "very_high": {
        "label": "Very High",
        "desc": "Best available stream, usually Opus at 130 to 160 kbps.",
        "format": "bestaudio/best",
    },
    "lossless": {
        "label": "Lossless",
        "desc": "Uses a lossless stream (FLAC / ALAC) when the source offers one. "
                "YouTube does not, so CrystalWave falls back to the best available stream and tells you.",
        "format": "bestaudio[acodec~='^(flac|alac|wav|pcm)']/bestaudio/best",
    },
}

CROSSFADE_OPTIONS = [
    ("off", "Off", "Tracks play back-to-back with no overlap."),
    ("3", "3 seconds", "A quick, subtle blend between songs."),
    ("5", "5 seconds", "A smooth, noticeable blend - good for similar-tempo playlists."),
    ("8", "8 seconds", "A long, DJ-style blend between songs."),
]
CROSSFADE_STEPS = 30

DEFAULT_SETTINGS = {"audio_quality": "high", "crossfade": "off", "show_explicit": False, "theme": "glass",
                    "media_keys": True}

EXPLICIT_PATTERN = re.compile(r"[\[\(]\s*explicit\s*[\]\)]|\bexplicit\s*version\b", re.IGNORECASE)


def looks_explicit(title):
    return bool(EXPLICIT_PATTERN.search(title or ""))

THEMES = {
    "glass": {
        "label": "Crystal Purple", "desc": "Deep purple blurred backdrop with frosted glass panels.",
        "backdrop_stops": [(58, 22, 92), (17, 12, 28), (38, 16, 66)], "backdrop_blur": 60,
        "BG": "#1A1326", "SIDEBAR": "#160F21", "PANEL": "#231A33", "INPUT": "#2C2140", "HOVER": "#352846",
        "GLASS_BORDER": "#55437A", "GLASS_BORDER_SOFT": "#362A4C",
        "ACCENT": "#A855F7", "ACCENT_HOVER": "#C084FC", "TEXT": "#FFFFFF", "MUTED": "#C3B6DB",
    },
    "contrast": {
        "label": "High Contrast", "desc": "Flat true-black panels, bright purple borders, minimal blur - easier to read.",
        "backdrop_stops": [(10, 7, 14), (4, 3, 6), (14, 8, 20)], "backdrop_blur": 20,
        "BG": "#000000", "SIDEBAR": "#000000", "PANEL": "#0C0A0F", "INPUT": "#161219", "HOVER": "#211B29",
        "GLASS_BORDER": "#6B5A94", "GLASS_BORDER_SOFT": "#3F3450",
        "ACCENT": "#B57BFA", "ACCENT_HOVER": "#CDA0FC", "TEXT": "#FFFFFF", "MUTED": "#D9D2E6",
    },
    "light": {
        "label": "Light", "desc": "Soft lavender-tinted panels over a pale blurred backdrop.",
        "backdrop_stops": [(226, 218, 241), (240, 236, 247), (218, 224, 243)], "backdrop_blur": 60,
        "BG": "#FFFFFF", "SIDEBAR": "#F5F2FA", "PANEL": "#F8F6FC", "INPUT": "#EFEBF6", "HOVER": "#E7E1F2",
        "GLASS_BORDER": "#D9D0EA", "GLASS_BORDER_SOFT": "#E6DFF2",
        "ACCENT": "#7C3AED", "ACCENT_HOVER": "#6D28D9", "TEXT": "#18132A", "MUTED": "#645C78",
    },
}


def _read_saved_theme():
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            key = json.load(f).get("theme", "glass")
    except Exception:
        key = "glass"
    return key if key in THEMES else "glass"


ACTIVE_THEME = _read_saved_theme()
_theme = THEMES[ACTIVE_THEME]

BACKDROP_STOPS = _theme["backdrop_stops"]
BACKDROP_BLUR = _theme["backdrop_blur"]
BG = _theme["BG"]
SIDEBAR = _theme["SIDEBAR"]
PANEL = _theme["PANEL"]
INPUT = _theme["INPUT"]
HOVER = _theme["HOVER"]
GLASS_BORDER = _theme["GLASS_BORDER"]
GLASS_BORDER_SOFT = _theme["GLASS_BORDER_SOFT"]
ACCENT = _theme["ACCENT"]
ACCENT_HOVER = _theme["ACCENT_HOVER"]
TEXT = _theme["TEXT"]
MUTED = _theme["MUTED"]
FONT = "Segoe UI"
FONT_CHOICES = ("Poppins", "Inter", "Montserrat", "Nunito", "Manrope", "Segoe UI Variable Display", "Segoe UI")
FONTS_DIR = resource_path("fonts")


def pick_font(root):
    if os.path.isdir(FONTS_DIR):
        for name in sorted(os.listdir(FONTS_DIR)):
            if name.lower().endswith((".ttf", ".otf")):
                try:
                    ctk.FontManager.load_font(os.path.join(FONTS_DIR, name))
                except Exception:
                    pass
    installed = set(tkfont.families(root))
    for family in FONT_CHOICES:
        if family in installed:
            return family
    return "Segoe UI"

PAGE_HUE_SHIFT = {"search": 0, "playlists": 16, "stats": -16, "settings": 30}


def shift_hue(rgb, degrees):
    r, g, b = (c / 255 for c in rgb)
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    h = (h + degrees / 360.0) % 1.0
    r2, g2, b2 = colorsys.hls_to_rgb(h, l, s)
    return (int(r2 * 255), int(g2 * 255), int(b2 * 255))


def backdrop_stops_for_page(page_key, base=None):
    base = base or BACKDROP_STOPS
    deg = PAGE_HUE_SHIFT.get(page_key, 0)
    if not deg:
        return base
    return [shift_hue(c, deg) for c in base]


def fmt(sec):
    sec = int(max(sec, 0))
    return f"{sec // 60}:{sec % 60:02d}"


def describe_stream(info):
    codec = (info.get("acodec") or "").lower()
    if codec in ("", "none"):
        codec = (info.get("ext") or "").lower()
    if codec.startswith("mp4a") or codec in ("aac", "m4a"):
        name = "AAC"
    elif codec.startswith("opus") or codec == "webm":
        name = "Opus"
    else:
        name = codec.split(".")[0].upper() or "Audio"
    abr = info.get("abr") or info.get("tbr")
    label = f"{name} · {round(abr)} kbps" if abr else name
    lossless = codec.startswith(("flac", "alac", "wav", "pcm", "aiff"))
    return label, lossless


def guess_artist(title, channel=""):
    t = (title or "").strip()
    for sep in (" - ", " – ", " — ", " | "):
        if sep in t:
            a = t.split(sep)[0].strip()
            if 0 < len(a) <= 40:
                return a
    c = (channel or "").strip()
    for suf in (" - Topic", "VEVO", " Official"):
        c = c.replace(suf, "")
    return c.strip() or "Unknown Artist"


def parse_lrc(text):
    out = []
    for raw in (text or "").splitlines():
        raw = raw.strip()
        tags = re.findall(r"\[(\d+):(\d+(?:\.\d+)?)\]", raw)
        if not tags:
            continue
        content = re.sub(r"\[\d+:\d+(?:\.\d+)?\]", "", raw).strip()
        for m, s in tags:
            out.append((int(m) * 60 + float(s), content))
    out.sort(key=lambda x: x[0])
    return out


def fmt_hm(sec):
    sec = int(max(sec, 0))
    if sec >= 3600:
        return f"{sec // 3600}h {(sec % 3600) // 60}m"
    if sec >= 60:
        return f"{sec // 60}m"
    return f"{sec}s"


def fmt_big(sec):
    return f"{sec / 3600:.1f} hrs" if sec >= 3600 else f"{int(sec // 60)} min"


def new_stats():
    return {
        "total_seconds": 0.0,
        "total_plays": 0,
        "tracks": {},
        "artists": {},
        "days": {},
        "hours": {str(h): 0.0 for h in range(24)},
        "quality": {},
    }


def pick_thumb_url(entry):
    thumbs = [t for t in (entry.get("thumbnails") or []) if t.get("url")]
    if thumbs:
        thumbs.sort(key=lambda t: abs((t.get("height") or 90) - 90))
        return thumbs[0]["url"]
    if entry.get("thumbnail"):
        return entry["thumbnail"]
    vid = entry.get("id")
    if vid:
        return f"https://i.ytimg.com/vi/{vid}/mqdefault.jpg"
    return None


def shorten(text, limit):
    return text if len(text) <= limit else text[:limit - 1] + "…"


def track_from_entry(e):
    url = e.get("url") or f"https://www.youtube.com/watch?v={e.get('id')}"
    title = e.get("title") or "Unknown"
    return {
        "title": title,
        "artist": guess_artist(title, e.get("channel") or e.get("uploader") or ""),
        "src": url,
        "online": True,
        "duration": e.get("duration") or 0,
        "thumb": pick_thumb_url(e),
        "explicit": looks_explicit(title),
    }


def rounded_mask(size, radius):
    return rounded_mask_wh(size, size, radius)


def rounded_mask_wh(w, h, radius):
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, w - 1, h - 1], radius=radius, fill=255)
    return mask


def build_backdrop_image(width, height, stops=None):
    return ImageTk.PhotoImage(build_backdrop_pil(width, height, stops))


def build_backdrop_pil(width, height, stops=None):
    full_w, full_h = max(width, 2), max(height, 2)
    scale = 4
    width, height = max(full_w // scale, 2), max(full_h // scale, 2)
    base = Image.new("RGB", (width, height))
    top, mid, bottom = stops or BACKDROP_STOPS
    for y in range(height):
        t = y / max(height - 1, 1)
        if t < 0.5:
            t2 = t / 0.5
            r = top[0] + (mid[0] - top[0]) * t2
            g = top[1] + (mid[1] - top[1]) * t2
            b = top[2] + (mid[2] - top[2]) * t2
        else:
            t2 = (t - 0.5) / 0.5
            r = mid[0] + (bottom[0] - mid[0]) * t2
            g = mid[1] + (bottom[1] - mid[1]) * t2
            b = mid[2] + (bottom[2] - mid[2]) * t2
        ImageDraw.Draw(base).line([(0, y), (width, y)], fill=(int(r), int(g), int(b)))
    base = base.filter(ImageFilter.GaussianBlur(max(BACKDROP_BLUR / scale, 1)))
    return base.resize((full_w, full_h), Image.BICUBIC)


def make_placeholder_thumb(size, radius):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=(36, 36, 36, 255))
    cx = cy = size // 2
    r = size // 7
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(90, 90, 90, 255))
    return ImageTk.PhotoImage(img)


def process_thumbnail(raw_bytes, size, mask):
    img = Image.open(io.BytesIO(raw_bytes)).convert("RGB")
    w, h = img.size
    s = min(w, h)
    img = img.crop(((w - s) // 2, (h - s) // 2, (w + s) // 2, (h + s) // 2))
    avg_color = dominant_color(img)
    img = img.resize((size, size), Image.LANCZOS)
    img = img.convert("RGBA")
    img.putalpha(mask)
    return img, avg_color


def dominant_color(img):
    small = img.convert("RGB").resize((48, 48), Image.BILINEAR)
    data = small.tobytes()
    n = len(data) // 3
    tr = tg = tb = 0
    bins = {}
    colorful = 0
    for i in range(0, len(data), 3):
        r, g, b = data[i], data[i + 1], data[i + 2]
        tr += r
        tg += g
        tb += b
        h, l, s = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
        chroma = s * (1 - abs(2 * l - 1))
        if chroma < 0.12:
            continue
        colorful += 1
        w = chroma * chroma
        e = bins.setdefault(int(h * 18) % 18, [0.0, 0.0, 0.0, 0.0])
        e[0] += w
        e[1] += r * w
        e[2] += g * w
        e[3] += b * w
    if bins and colorful >= 0.04 * n:
        best = max(bins.values(), key=lambda e: e[0])
        if best[0] > 0:
            return (int(best[1] / best[0]), int(best[2] / best[0]), int(best[3] / best[0]))
    return (tr // n, tg // n, tb // n)


def _is_hex(s):
    return isinstance(s, str) and len(s) == 7 and s[0] == "#"


def _norm(color):
    return color.upper() if _is_hex(color) else color


def _hex_to_rgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def _rgb_to_hex(rgb):
    return "#%02X%02X%02X" % tuple(max(0, min(255, int(round(v)))) for v in rgb)


def _hls_hex(h, l, s):
    r, g, b = colorsys.hls_to_rgb(h % 1.0, max(0.0, min(1.0, l)), max(0.0, min(1.0, s)))
    return _rgb_to_hex((r * 255, g * 255, b * 255))


def _hls_rgb(h, l, s):
    return _hex_to_rgb(_hls_hex(h, l, s))


def mix_color(a, b, t):
    if a == b or not (_is_hex(a) and _is_hex(b)):
        return b if t >= 1 else a
    return _rgb_to_hex(tuple(x + (y - x) * t for x, y in zip(_hex_to_rgb(a), _hex_to_rgb(b))))


GREY_KEYS = ("#4D4D4D", "#535353", "#3A3A3A", "#555555", "#2A2A2A", "#7A7A7A", "#222222")
PALETTE_KEYS = frozenset(
    _norm(c) for c in (BG, SIDEBAR, PANEL, INPUT, HOVER, GLASS_BORDER, GLASS_BORDER_SOFT,
                       ACCENT, ACCENT_HOVER, TEXT, MUTED) + GREY_KEYS
)


def build_song_theme(rgb):
    if rgb is None:
        return {}, None, ACCENT
    h, l, s = colorsys.rgb_to_hls(*(v / 255 for v in rgb))
    neutral = s < 0.14
    ss = s * 0.5 if neutral else min(0.55, max(0.18, s * 0.65))
    sa = s if neutral else max(0.55, min(s, 0.9))

    def H(light, sat=None):
        return _hls_hex(h, light, ss if sat is None else sat)

    if ACTIVE_THEME == "light":
        al = min(max(l, 0.36), 0.46)
        roles = {
            BG: H(.985), SIDEBAR: H(.955), PANEL: H(.972), INPUT: H(.93), HOVER: H(.90),
            GLASS_BORDER: H(.82), GLASS_BORDER_SOFT: H(.90),
            ACCENT: H(al, sa), ACCENT_HOVER: H(al - .07, sa),
            TEXT: H(.12, ss * .8), MUTED: H(.40, min(ss, .25)),
            "#4D4D4D": H(.80), "#535353": H(.74), "#3A3A3A": H(.80), "#555555": H(.70),
            "#2A2A2A": H(.88), "#7A7A7A": H(.55, ss * .5), "#222222": H(.90),
        }
        stops = [_hls_rgb(h, .88, ss), _hls_rgb(h, .95, ss * .6), _hls_rgb(h, .86, ss)]
    elif ACTIVE_THEME == "contrast":
        al = min(max(l, 0.64), 0.76)
        roles = {
            BG: BG, SIDEBAR: BG, PANEL: H(.045, ss * .6), INPUT: H(.08, ss * .6), HOVER: H(.13, ss * .7),
            GLASS_BORDER: H(.52), GLASS_BORDER_SOFT: H(.30),
            ACCENT: H(al, sa), ACCENT_HOVER: H(al + .08, sa),
            TEXT: TEXT, MUTED: H(.86, min(ss, .3) * .5),
            "#4D4D4D": H(.30, ss * .7), "#535353": H(.34, ss * .8), "#3A3A3A": H(.26, ss * .7),
            "#555555": H(.34, ss * .8), "#2A2A2A": H(.20, ss * .7), "#7A7A7A": H(.52, ss * .5),
            "#222222": H(.17, ss * .7),
        }
        stops = [_hls_rgb(h, .05, ss * .8), _hls_rgb(h, .02, ss * .4), _hls_rgb(h, .07, ss * .8)]
    else:
        al = min(max(l, 0.58), 0.72)
        roles = {
            BG: H(.10), SIDEBAR: H(.075), PANEL: H(.14), INPUT: H(.185), HOVER: H(.23),
            GLASS_BORDER: H(.40), GLASS_BORDER_SOFT: H(.24),
            ACCENT: H(al, sa), ACCENT_HOVER: H(al + .08, sa),
            TEXT: TEXT, MUTED: H(.80, min(ss, .35)),
            "#4D4D4D": H(.30, ss * .7), "#535353": H(.34, ss * .8), "#3A3A3A": H(.26, ss * .7),
            "#555555": H(.34, ss * .8), "#2A2A2A": H(.20, ss * .7), "#7A7A7A": H(.52, ss * .5),
            "#222222": H(.17, ss * .7),
        }
        stops = [_hls_rgb(h, .27, min(.65, ss * 1.2)), _hls_rgb(h, .07, ss * .5),
                 _hls_rgb(h, .17, min(.65, ss * 1.1))]
    pal = {}
    for k, v in roles.items():
        pal.setdefault(_norm(k), _norm(v))
    return pal, stops, roles[ACCENT]


class MusicApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        global FONT
        FONT = pick_font(self)
        ctk.set_appearance_mode("dark")
        self.title("CrystalWave")
        self.geometry("1040x700")
        self.minsize(880, 580)
        self.configure(fg_color=BG)
        self.set_app_icon()

        self.instance = vlc.Instance("--no-video", "--quiet")
        self.player = self.instance.media_player_new()
        self.player2 = self.instance.media_player_new()
        self.crossfading = False
        self._crossfade_job = None
        self._crossfade_source = None
        self._crossfade_next_idx = None
        self._crossfade_next_track = None

        self.settings = self.load_settings()
        self.playlists = {}
        self.current_playlist = None
        self.view = []
        self.results = []
        self.last_search_results = []
        self.queue = []
        self.qpos = -1
        self.token = 0
        self.active = False
        self.loading = False
        self.paused = False
        self.started = 0.0
        self.length = 0.0
        self.shuffle = False
        self.repeat = False
        self.sleep_at = None
        self.sleep_after_song = False
        self.mini = None
        self._mini_state = None
        self._media_thread = None
        self._media_tid = None
        self.seeking = False
        self.stream_label = ""
        self.fade_job = None
        self.tasks = queue.Queue()
        self.stats = self.load_stats()
        self.stats_dirty = False
        self.last_save = time.time()
        self.last_tick = time.time()
        self.cur_track = None
        self.cur_seconds = 0.0
        self.cur_counted = False
        self.week_data = []

        self.thumb_mask = rounded_mask(THUMB_SIZE, THUMB_RADIUS)
        self.default_thumb = make_placeholder_thumb(THUMB_SIZE, THUMB_RADIUS)
        self.thumb_cache = {}
        self.thumb_pil_cache = {}
        self.thumb_colors = {}
        self.thumb_pending = set()
        self.thumb_targets = {}
        self.accent_color = ACCENT
        self._pal_cur = {}
        self._rev = {}
        self._pal_job = None
        self._bd_stops_cur = None
        self._backdrop_pil = None
        self._bar_art_cache = None
        self._bar_chips = []
        self._tk_bg = []
        self._menus = []
        self._bar_art_photo = None

        self.lyrics_cache = {}
        self.lyrics_token = 0
        self.lyrics_track = None
        self.lyrics_active_idx = -1
        self.lyrics_line_labels = []

        self.setup_style()
        self.build_ui()
        self.load_playlists()
        self.show_page("search")
        self.setup_shortcuts()
        self.apply_media_keys()
        self.after(50, self._redraw_backdrop)
        self.tick()
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def set_app_icon(self):
        if not os.path.isfile(ICON_FILE):
            return

        try:
            self.iconbitmap(ICON_FILE)
        except Exception:
            pass

        try:
            self._icon_image = ImageTk.PhotoImage(Image.open(ICON_FILE))
            self.iconphoto(True, self._icon_image)
        except Exception:
            pass

        if sys.platform != "win32":
            return

        try:
            import ctypes
            from ctypes import wintypes

            user32 = ctypes.WinDLL("user32", use_last_error=True)
            shell32 = ctypes.WinDLL("shell32", use_last_error=True)

            shell32.SetCurrentProcessExplicitAppUserModelID.argtypes = [wintypes.LPCWSTR]
            shell32.SetCurrentProcessExplicitAppUserModelID.restype = wintypes.HRESULT
            shell32.SetCurrentProcessExplicitAppUserModelID("CrystalWave.MusicApp")

            user32.LoadImageW.argtypes = [
                wintypes.HINSTANCE,
                wintypes.LPCWSTR,
                wintypes.UINT,
                ctypes.c_int,
                ctypes.c_int,
                wintypes.UINT,
            ]
            user32.LoadImageW.restype = wintypes.HANDLE

            user32.SendMessageW.argtypes = [
                wintypes.HWND,
                wintypes.UINT,
                wintypes.WPARAM,
                wintypes.LPARAM,
            ]
            user32.SendMessageW.restype = wintypes.LRESULT

            user32.SetClassLongPtrW.argtypes = [
                wintypes.HWND,
                ctypes.c_int,
                ctypes.c_ssize_t,
            ]
            user32.SetClassLongPtrW.restype = ctypes.c_ssize_t

            hwnd = wintypes.HWND(self.winfo_id())
            icon_path = os.path.abspath(ICON_FILE)

            IMAGE_ICON = 1
            LR_LOADFROMFILE = 0x00000010
            LR_DEFAULTSIZE = 0x00000040
            WM_SETICON = 0x0080
            ICON_SMALL = 0
            ICON_BIG = 1
            GCLP_HICON = -14
            GCLP_HICONSM = -34

            hicon_big = user32.LoadImageW(
                None, icon_path, IMAGE_ICON, 32, 32, LR_LOADFROMFILE
            )
            hicon_small = user32.LoadImageW(
                None, icon_path, IMAGE_ICON, 16, 16, LR_LOADFROMFILE
            )

            if not hicon_big:
                hicon_big = user32.LoadImageW(
                    None, icon_path, IMAGE_ICON, 0, 0,
                    LR_LOADFROMFILE | LR_DEFAULTSIZE
                )
            if not hicon_small:
                hicon_small = hicon_big

            big_value = getattr(hicon_big, "value", hicon_big) or 0
            small_value = getattr(hicon_small, "value", hicon_small) or big_value

            if big_value:
                user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, big_value)
                user32.SetClassLongPtrW(hwnd, GCLP_HICON, big_value)

            if small_value:
                user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, small_value)
                user32.SetClassLongPtrW(hwnd, GCLP_HICONSM, small_value)

            self._win32_hicon_big = big_value
            self._win32_hicon_small = small_value

        except Exception:
            pass

    def load_settings(self):
        s = dict(DEFAULT_SETTINGS)
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                s.update(json.load(f))
        except (OSError, ValueError):
            pass
        if s.get("audio_quality") not in QUALITY:
            s["audio_quality"] = DEFAULT_SETTINGS["audio_quality"]
        if s.get("crossfade") not in {k for k, _l, _d in CROSSFADE_OPTIONS}:
            s["crossfade"] = DEFAULT_SETTINGS["crossfade"]
        if s.get("theme") not in THEMES:
            s["theme"] = DEFAULT_SETTINGS["theme"]
        return s

    def crossfade_seconds(self):
        v = self.settings.get("crossfade", "off")
        return int(v) if v != "off" else 0

    def save_settings(self):
        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.settings, f)
        except OSError:
            pass

    def load_stats(self):
        s = new_stats()
        try:
            with open(STATS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            for k in ("total_seconds", "total_plays"):
                if isinstance(data.get(k), (int, float)):
                    s[k] = data[k]
            for k in ("tracks", "artists", "days", "hours", "quality"):
                if isinstance(data.get(k), dict):
                    s[k].update(data[k])
        except (OSError, ValueError, AttributeError):
            pass
        return s

    def save_stats(self):
        try:
            with open(STATS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.stats, f)
            self.stats_dirty = False
        except OSError:
            pass

    def begin_listen(self, track):
        self.record_history(track)
        self.cur_track = track
        self.cur_seconds = 0.0
        self.cur_counted = False

    def record_listen(self, dt):
        t = self.cur_track
        if not t:
            return
        s = self.stats
        artist = t.get("artist") or guess_artist(t.get("title", ""))
        tr = s["tracks"].setdefault(t["src"], {"title": t["title"], "artist": artist, "plays": 0, "seconds": 0.0})
        ar = s["artists"].setdefault(artist, {"plays": 0, "seconds": 0.0})
        tr["seconds"] += dt
        ar["seconds"] += dt
        s["total_seconds"] += dt
        now = datetime.now()
        day = now.date().isoformat()
        s["days"][day] = s["days"].get(day, 0.0) + dt
        h = str(now.hour)
        s["hours"][h] = s["hours"].get(h, 0.0) + dt
        q = self.quality_key()
        s["quality"][q] = s["quality"].get(q, 0.0) + dt
        self.cur_seconds += dt
        if not self.cur_counted and self.cur_seconds >= 30:
            self.cur_counted = True
            s["total_plays"] += 1
            tr["plays"] += 1
            ar["plays"] += 1
        self.stats_dirty = True

    def current_streak(self):
        days = self.stats["days"]
        d = date.today()
        if days.get(d.isoformat(), 0) < 60:
            d -= timedelta(days=1)
        n = 0
        while days.get(d.isoformat(), 0) >= 60:
            n += 1
            d -= timedelta(days=1)
        return n

    def reset_stats(self):
        if messagebox.askyesno("Reset stats", "Erase all listening stats? This can't be undone."):
            self.stats = new_stats()
            self.save_stats()
            self.refresh_stats()

    def themed(self, color):
        return self._pal_cur.get(_norm(color), color)

    def setup_style(self):
        s = ttk.Style(self)
        if s.theme_use() != "clam":
            s.theme_use("clam")
        panel, hover = self.themed(PANEL), self.themed(HOVER)
        text, muted = self.themed(TEXT), self.themed(MUTED)

        s.configure(
            "CrystalWave.Treeview",
            background=panel,
            fieldbackground=panel,
            foreground=text,
            rowheight=THUMB_SIZE + 14,
            borderwidth=0,
            relief="flat",
            font=(FONT, 11),
            indent=0,
        )
        s.configure(
            "CrystalWave.Treeview.Heading",
            background=panel,
            foreground=muted,
            relief="flat",
            borderwidth=0,
            font=(FONT, 10, "bold"),
            padding=(8, 10),
        )
        s.map(
            "CrystalWave.Treeview",
            background=[
                ("disabled", panel),
                ("selected", hover),
                ("!selected", panel),
            ],
            foreground=[
                ("disabled", muted),
                ("selected", text),
                ("!selected", text),
            ],
        )
        s.map(
            "CrystalWave.Treeview.Heading",
            background=[("active", hover), ("!active", panel)],
            foreground=[("active", text), ("!active", muted)],
        )
        s.layout("CrystalWave.Treeview", [("Treeview.treearea", {"sticky": "nswe"})])

        for tree in (getattr(self, "net_tree", None), getattr(self, "lib_tree", None)):
            if tree:
                try:
                    tree.configure(style="CrystalWave.Treeview")
                    tree.tag_configure("playing", foreground=self.accent_color)
                except Exception:
                    pass

    def build_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._backdrop_job = None
        self.backdrop_label = tk.Label(self, bd=0, highlightthickness=0, bg=BG)
        self.backdrop_label.place(x=0, y=0, relwidth=1, relheight=1)
        self._tk_bg.append((self.backdrop_label, BG))
        self.bind("<Configure>", self._on_resize_backdrop)

        sidebar = ctk.CTkFrame(self, width=226, corner_radius=22, fg_color=SIDEBAR,
                               border_width=1, border_color=GLASS_BORDER)
        sidebar.grid(row=0, column=0, sticky="nsw", padx=(16, 8), pady=(16, 10))
        self.sidebar_panel = sidebar
        sidebar.grid_propagate(False)
        ctk.CTkLabel(sidebar, text="♫  CrystalWave", font=(FONT, 26, "bold"), text_color=ACCENT).pack(
            anchor="w", padx=22, pady=(26, 22)
        )
        self.nav = {}

        def nav_btn(key, label, **pack):
            b = ctk.CTkButton(
                sidebar, text=label, anchor="w", height=42, corner_radius=14, fg_color="transparent",
                hover_color=HOVER, text_color=MUTED, font=(FONT, 14, "bold"),
                command=lambda: self.show_page(key),
            )
            b.pack(fill="x", padx=12, pady=2, **pack)
            self.nav[key] = b

        nav_btn("search", "Search")
        nav_btn("playlists", "Playlists")
        nav_btn("stats", "Your Stats")
        nav_btn("settings", "Settings", side="bottom")

        main = ctk.CTkFrame(self, corner_radius=22, fg_color=BG, border_width=1, border_color=GLASS_BORDER)
        main.grid(row=0, column=1, sticky="nsew", padx=(8, 16), pady=(16, 10))
        main.grid_rowconfigure(0, weight=1)
        main.grid_columnconfigure(0, weight=1)
        self.main_panel = main
        holder = ctk.CTkFrame(main, corner_radius=0, fg_color=BG)
        holder.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        self._nav_order = ["search", "playlists", "stats", "settings"]
        builders = {
            "search": self.build_search_page,
            "playlists": self.build_playlists_page,
            "stats": self.build_stats_page,
            "settings": self.build_settings_page,
        }
        self.pages = {}
        self.current_page = None
        for key in self._nav_order:
            outer = ctk.CTkFrame(holder, corner_radius=22, fg_color=BG)
            inner = ctk.CTkFrame(outer, corner_radius=0, fg_color=BG)
            inner.pack(fill="both", expand=True, padx=18, pady=(14, 2))
            self.pages[key] = outer
            builders[key](inner)

        self.build_player_bar()

    def _on_resize_backdrop(self, event):
        if event.widget is not self:
            return
        if self._backdrop_job is not None:
            self.after_cancel(self._backdrop_job)
        self._backdrop_job = self.after(120, self._redraw_backdrop)

    def _paint_backdrop(self):
        w, h = self.winfo_width(), self.winfo_height()
        if w < 2 or h < 2:
            return
        stops = backdrop_stops_for_page(self.current_page, self._bd_stops_cur)
        self._backdrop_pil = build_backdrop_pil(w, h, stops)
        self._backdrop_photo = ImageTk.PhotoImage(self._backdrop_pil)
        self.backdrop_label.configure(image=self._backdrop_photo)
        self._paint_corners()

    def _redraw_backdrop(self):
        self._backdrop_job = None
        self._paint_backdrop()

    def _paint_corner_image(self, widget, pil, x, y):
        if pil is None:
            return
        try:
            w, h = widget.winfo_width(), widget.winfo_height()
            if w < 4 or h < 4:
                return
            photo = ImageTk.PhotoImage(pil.crop((x, y, x + w, y + h)).convert("RGB"))
            cv = widget._canvas
            item = widget.__dict__.get("_cw_corner_item")
            try:
                if item is None:
                    raise KeyError
                cv.itemconfig(item, image=photo)
            except Exception:
                item = cv.create_image(0, 0, image=photo, anchor="nw")
                widget._cw_corner_item = item
            cv.tag_lower(item)
            widget._cw_corner_photo = photo
        except Exception:
            pass

    def _paint_corners(self):
        pil = self._backdrop_pil
        for panel in (getattr(self, "sidebar_panel", None), getattr(self, "main_panel", None)):
            if panel is not None:
                self._paint_corner_image(panel, pil, panel.winfo_x(), panel.winfo_y())
        for name in ("lyrics_overlay", "queue_panel"):
            ov = getattr(self, name, None)
            if ov is not None and ov.winfo_ismapped():
                self._paint_corner_image(ov, pil, ov.winfo_x(), ov.winfo_y())
        self.update_player_bar_art()

    def build_search_page(self, page):
        ctk.CTkLabel(page, text="Search", font=(FONT, 30, "bold"), text_color=TEXT).pack(anchor="w")
        ctk.CTkLabel(page, text="Find any song or artist and stream it instantly.", font=(FONT, 13),
                     text_color=MUTED).pack(anchor="w", pady=(0, 14))

        row = ctk.CTkFrame(page, fg_color="transparent")
        row.pack(fill="x")
        self.online_entry = ctk.CTkEntry(
            row, placeholder_text="What do you want to listen to?", height=44, corner_radius=22,
            fg_color=INPUT, border_width=0, font=(FONT, 13),
        )
        self.online_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.online_entry.bind("<Return>", lambda e: self.search_online())
        ctk.CTkButton(
            row, text="Search", width=110, height=44, corner_radius=22, fg_color=ACCENT,
            hover_color=ACCENT_HOVER, text_color="black", font=(FONT, 13, "bold"), command=self.search_online,
        ).pack(side="left")

        actions = ctk.CTkFrame(page, fg_color="transparent")
        actions.pack(side="bottom", fill="x", pady=(10, 0))
        self.add_to_playlist_btn = ctk.CTkButton(
            actions, text="＋  Add to Playlist", height=36, corner_radius=18, fg_color="transparent",
            border_width=1, border_color="#535353", hover_color=HOVER, text_color=TEXT,
            font=(FONT, 12, "bold"), command=self.add_result_to_playlist_menu,
        )
        self.add_to_playlist_btn.pack(side="right")

        self.net_tree = self.make_table(page)
        self.net_tree.bind("<Double-1>", lambda e: self.on_double(e, self.net_tree, "results"))
        self.net_tree.bind("<Return>", lambda e: self.play_selected("results"))
        menu = self.make_menu([("Play", lambda: self.play_selected("results")),
                               ("Play Next", lambda: self.queue_selected("results", True)),
                               ("Add to Queue", lambda: self.queue_selected("results", False)),
                               ("Add to Playlist", self.add_result_to_playlist_menu)])
        self.bind_menu(self.net_tree, menu)

    def build_playlists_page(self, page):
        ctk.CTkLabel(page, text="Playlists", font=(FONT, 30, "bold"), text_color=TEXT).pack(anchor="w")
        ctk.CTkLabel(page, text="Organize songs into playlists and play them anytime.", font=(FONT, 13),
                     text_color=MUTED).pack(anchor="w", pady=(0, 14))

        body = ctk.CTkFrame(page, fg_color="transparent")
        body.pack(fill="both", expand=True)
        body.grid_columnconfigure(0, weight=0)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        left = ctk.CTkFrame(body, width=220, fg_color=PANEL, corner_radius=16, border_width=1, border_color=GLASS_BORDER_SOFT)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        left.grid_propagate(False)
        head = ctk.CTkFrame(left, fg_color="transparent")
        head.pack(fill="x", padx=12, pady=(12, 6))
        ctk.CTkLabel(head, text="YOUR PLAYLISTS", font=(FONT, 11, "bold"), text_color=MUTED).pack(side="left")
        ctk.CTkButton(head, text="+", width=26, height=26, corner_radius=13, fg_color=ACCENT,
                      hover_color=ACCENT_HOVER, text_color="black", font=(FONT, 14, "bold"),
                      command=self.new_playlist).pack(side="right")
        self.playlist_scroll = ctk.CTkScrollableFrame(left, fg_color="transparent")
        self.playlist_scroll.pack(fill="both", expand=True, padx=6, pady=(0, 8))
        self.playlist_rows = {}

        right = ctk.CTkFrame(body, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew")

        row = ctk.CTkFrame(right, fg_color="transparent")
        row.pack(fill="x")
        pl_head = ctk.CTkFrame(row, fg_color="transparent")
        pl_head.pack(side="left", fill="x", expand=True)
        self.pl_title_l = ctk.CTkLabel(pl_head, text="No playlist selected", font=(FONT, 20, "bold"),
                                       text_color=TEXT)
        self.pl_title_l.pack(anchor="w")
        self.pl_sub_l = ctk.CTkLabel(pl_head, text="Create a playlist to get started", font=(FONT, 12),
                                     text_color=MUTED)
        self.pl_sub_l.pack(anchor="w")
        ctk.CTkButton(row, text="Delete", width=70, height=32, corner_radius=16, fg_color="transparent",
                      border_width=1, border_color="#535353", hover_color=HOVER, text_color=TEXT,
                      font=(FONT, 11, "bold"), command=self.delete_current_playlist).pack(side="right")
        ctk.CTkButton(row, text="Export", width=70, height=32, corner_radius=16, fg_color="transparent",
                      border_width=1, border_color="#535353", hover_color=HOVER, text_color=TEXT,
                      font=(FONT, 11, "bold"), command=self.export_playlist).pack(side="right", padx=(0, 8))
        self.import_btn = ctk.CTkButton(row, text="Import", width=70, height=32, corner_radius=16,
                                        fg_color="transparent", border_width=1, border_color="#535353",
                                        hover_color=HOVER, text_color=TEXT, font=(FONT, 11, "bold"),
                                        command=self.show_import_menu)
        self.import_btn.pack(side="right", padx=(0, 8))

        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self.refresh_list())
        self.pl_filter_entry = ctk.CTkEntry(
            right, textvariable=self.search_var, placeholder_text="Filter this playlist", height=40,
            corner_radius=20, fg_color=INPUT, border_width=0, font=(FONT, 13),
        )
        self.pl_filter_entry.pack(fill="x", pady=(10, 0))

        actions = ctk.CTkFrame(right, fg_color="transparent")
        actions.pack(side="bottom", fill="x", pady=(10, 0))
        ctk.CTkButton(
            actions, text="Remove from Playlist", height=36, corner_radius=18, fg_color="transparent",
            border_width=1, border_color="#535353", hover_color=HOVER, text_color=TEXT,
            font=(FONT, 12, "bold"), command=self.remove_selected,
        ).pack(side="right")

        self.lib_tree = self.make_table(right)
        self.lib_tree.bind("<Double-1>", lambda e: self.on_double(e, self.lib_tree, "playlist"))
        self.lib_tree.bind("<Delete>", lambda e: self.remove_selected())
        self.lib_tree.bind("<Return>", lambda e: self.play_selected("playlist"))
        self._enable_reorder(self.lib_tree)
        menu = self.make_menu([("Play", lambda: self.play_selected("playlist")),
                               ("Play Next", lambda: self.queue_selected("playlist", True)),
                               ("Add to Queue", lambda: self.queue_selected("playlist", False)),
                               ("Move Up", lambda: self.move_selected(-1)),
                               ("Move Down", lambda: self.move_selected(1)),
                               ("Remove from Playlist", self.remove_selected)])
        self.bind_menu(self.lib_tree, menu)

    def build_settings_page(self, page):
        ctk.CTkLabel(page, text="Settings", font=(FONT, 30, "bold"), text_color=TEXT).pack(anchor="w")
        ctk.CTkLabel(page, text="Customize how CrystalWave sounds.", font=(FONT, 13),
                     text_color=MUTED).pack(anchor="w", pady=(0, 14))

        scroll = ctk.CTkScrollableFrame(page, fg_color="transparent", corner_radius=0)
        scroll.pack(fill="both", expand=True)

        card = ctk.CTkFrame(scroll, fg_color=PANEL, corner_radius=16, border_width=1, border_color=GLASS_BORDER_SOFT)
        card.pack(fill="x", pady=(0, 16))
        ctk.CTkLabel(card, text="Media Quality", font=(FONT, 18, "bold"), text_color=TEXT).pack(
            anchor="w", padx=20, pady=(18, 0))
        ctk.CTkLabel(card, text="Audio quality for streaming. Applies immediately, including to the song "
                                "that is playing.", font=(FONT, 12), text_color=MUTED, wraplength=620,
                     justify="left").pack(anchor="w", padx=20, pady=(2, 8))

        self.quality_var = tk.StringVar(value=self.settings["audio_quality"])
        for key in QUALITY_ORDER:
            q = QUALITY[key]
            row = ctk.CTkFrame(card, fg_color="transparent")
            row.pack(fill="x", padx=20, pady=(8, 0))
            ctk.CTkRadioButton(
                row, text=q["label"], variable=self.quality_var, value=key, font=(FONT, 14, "bold"),
                text_color=TEXT, fg_color=ACCENT, hover_color=ACCENT_HOVER, border_color="#7A7A7A",
                command=self.on_quality_change,
            ).pack(anchor="w")
            ctk.CTkLabel(row, text=q["desc"], font=(FONT, 11), text_color=MUTED, wraplength=600,
                         justify="left").pack(anchor="w", padx=(30, 0), pady=(2, 0))

        sep = ctk.CTkFrame(card, height=1, fg_color="#2A2A2A")
        sep.pack(fill="x", padx=20, pady=(16, 10))
        self.stream_info = ctk.CTkLabel(card, text="", font=(FONT, 12), text_color=MUTED, wraplength=620,
                                        justify="left", anchor="w")
        self.stream_info.pack(anchor="w", padx=20, pady=(0, 18))
        self.update_stream_info()

        cf_card = ctk.CTkFrame(scroll, fg_color=PANEL, corner_radius=16, border_width=1,
                               border_color=GLASS_BORDER_SOFT)
        cf_card.pack(fill="x", pady=(0, 16))
        ctk.CTkLabel(cf_card, text="Crossfade", font=(FONT, 18, "bold"), text_color=TEXT).pack(
            anchor="w", padx=20, pady=(18, 0))
        ctk.CTkLabel(cf_card, text="Blend the end of one song into the start of the next instead of a hard "
                                   "cut. Only applies when a song ends naturally - skipping tracks manually "
                                   "still cuts straight away.", font=(FONT, 12), text_color=MUTED,
                     wraplength=620, justify="left").pack(anchor="w", padx=20, pady=(2, 8))

        self.crossfade_var = tk.StringVar(value=self.settings["crossfade"])
        for key, label, desc in CROSSFADE_OPTIONS:
            row = ctk.CTkFrame(cf_card, fg_color="transparent")
            row.pack(fill="x", padx=20, pady=(8, 0))
            ctk.CTkRadioButton(
                row, text=label, variable=self.crossfade_var, value=key, font=(FONT, 14, "bold"),
                text_color=TEXT, fg_color=ACCENT, hover_color=ACCENT_HOVER, border_color="#7A7A7A",
                command=self.on_crossfade_change,
            ).pack(anchor="w")
            ctk.CTkLabel(row, text=desc, font=(FONT, 11), text_color=MUTED, wraplength=600,
                        justify="left").pack(anchor="w", padx=(30, 0), pady=(2, 0))
        ctk.CTkFrame(cf_card, height=4, fg_color="transparent").pack(pady=(10, 0))

        ex_card = ctk.CTkFrame(scroll, fg_color=PANEL, corner_radius=16, border_width=1,
                               border_color=GLASS_BORDER_SOFT)
        ex_card.pack(fill="x", pady=(0, 16))
        ex_row = ctk.CTkFrame(ex_card, fg_color="transparent")
        ex_row.pack(fill="x", padx=20, pady=(18, 4))
        ex_text = ctk.CTkFrame(ex_row, fg_color="transparent")
        ex_text.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(ex_text, text="Explicit Content", font=(FONT, 18, "bold"), text_color=TEXT).pack(anchor="w")
        ctk.CTkLabel(ex_text, text="Off by default. When off, songs flagged [E] are hidden from search "
                                   "results and playlists. Detection is based on the song's title (e.g. "
                                   "\"(Explicit)\") since CrystalWave's YouTube search has no official content rating.",
                     font=(FONT, 12), text_color=MUTED, wraplength=560, justify="left").pack(anchor="w", pady=(2, 0))
        self.explicit_var = tk.BooleanVar(value=self.settings["show_explicit"])
        ctk.CTkSwitch(ex_row, text="", variable=self.explicit_var, onvalue=True, offvalue=False,
                     width=44, progress_color=ACCENT, button_color=TEXT, button_hover_color=TEXT,
                     command=self.on_explicit_change).pack(side="right", padx=(10, 0))
        ctk.CTkFrame(ex_card, height=8, fg_color="transparent").pack()

        mk_card = ctk.CTkFrame(scroll, fg_color=PANEL, corner_radius=16, border_width=1,
                               border_color=GLASS_BORDER_SOFT)
        mk_card.pack(fill="x", pady=(0, 16))
        mk_row = ctk.CTkFrame(mk_card, fg_color="transparent")
        mk_row.pack(fill="x", padx=20, pady=(18, 4))
        mk_text = ctk.CTkFrame(mk_row, fg_color="transparent")
        mk_text.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(mk_text, text="Media Keys", font=(FONT, 18, "bold"), text_color=TEXT).pack(anchor="w")
        mk_note = ("Use the play/pause, next and previous keys on your keyboard even when CrystalWave is in "
                   "the background. While on, CrystalWave takes those keys from other players.")
        if sys.platform != "win32":
            mk_note = "Media keys are only supported on Windows."
        ctk.CTkLabel(mk_text, text=mk_note, font=(FONT, 12), text_color=MUTED, wraplength=560,
                     justify="left").pack(anchor="w", pady=(2, 0))
        self.media_keys_var = tk.BooleanVar(value=self.settings.get("media_keys", True))
        ctk.CTkSwitch(mk_row, text="", variable=self.media_keys_var, onvalue=True, offvalue=False,
                      width=44, progress_color=ACCENT, button_color=TEXT, button_hover_color=TEXT,
                      command=self.on_media_keys_change).pack(side="right", padx=(10, 0))
        ctk.CTkFrame(mk_card, height=8, fg_color="transparent").pack()

        th_card = ctk.CTkFrame(scroll, fg_color=PANEL, corner_radius=16, border_width=1,
                               border_color=GLASS_BORDER_SOFT)
        th_card.pack(fill="x", pady=(0, 16))
        ctk.CTkLabel(th_card, text="Theme", font=(FONT, 18, "bold"), text_color=TEXT).pack(
            anchor="w", padx=20, pady=(18, 0))
        ctk.CTkLabel(th_card, text="Takes effect the next time CrystalWave starts.", font=(FONT, 12),
                     text_color=MUTED, wraplength=560, justify="left").pack(anchor="w", padx=20, pady=(2, 8))
        self.theme_var = tk.StringVar(value=ACTIVE_THEME)
        for key, info in THEMES.items():
            row = ctk.CTkFrame(th_card, fg_color="transparent")
            row.pack(fill="x", padx=20, pady=(8, 0))
            ctk.CTkRadioButton(
                row, text=info["label"], variable=self.theme_var, value=key, font=(FONT, 14, "bold"),
                text_color=TEXT, fg_color=ACCENT, hover_color=ACCENT_HOVER, border_color="#7A7A7A",
                command=self.on_theme_change,
            ).pack(anchor="w")
            ctk.CTkLabel(row, text=info["desc"], font=(FONT, 11), text_color=MUTED, wraplength=540,
                        justify="left").pack(anchor="w", padx=(30, 0), pady=(2, 0))
        self.theme_restart_note = ctk.CTkLabel(th_card, text="", font=(FONT, 11), text_color=ACCENT)
        self.theme_restart_note.pack(anchor="w", padx=20, pady=(8, 0))
        ctk.CTkFrame(th_card, height=8, fg_color="transparent").pack()

    def on_crossfade_change(self):
        self.settings["crossfade"] = self.crossfade_var.get()
        self.save_settings()

    def on_explicit_change(self):
        self.settings["show_explicit"] = bool(self.explicit_var.get())
        self.save_settings()
        self.refresh_list()
        if self.last_search_results:
            self.show_results(self.last_search_results)

    def on_theme_change(self):
        self.settings["theme"] = self.theme_var.get()
        self.save_settings()
        note = "Restart CrystalWave to use this theme." if self.theme_var.get() != ACTIVE_THEME else ""
        self.theme_restart_note.configure(text=note)

    def build_stats_page(self, page):
        head = ctk.CTkFrame(page, fg_color="transparent")
        head.pack(fill="x")
        for text, cmd in (("Reset", self.reset_stats), ("↻  Refresh", self.refresh_stats)):
            ctk.CTkButton(head, text=text, width=96, height=34, corner_radius=17, fg_color="transparent",
                          border_width=1, border_color="#535353", hover_color=HOVER, text_color=TEXT,
                          font=(FONT, 12, "bold"), command=cmd).pack(side="right", padx=(8, 0), anchor="n")
        titles = ctk.CTkFrame(head, fg_color="transparent")
        titles.pack(side="left")
        ctk.CTkLabel(titles, text="Your Stats", font=(FONT, 30, "bold"), text_color=TEXT).pack(anchor="w")
        ctk.CTkLabel(titles, text="A look at your listening habits.", font=(FONT, 13),
                     text_color=MUTED).pack(anchor="w", pady=(0, 6))
        self.stats_scroll = ctk.CTkScrollableFrame(page, fg_color="transparent", corner_radius=0)
        self.stats_scroll.pack(fill="both", expand=True, pady=(8, 0))

    def stat_card(self, parent, col, label, value, size=26, animate_to=None, formatter=None):
        c = ctk.CTkFrame(parent, fg_color=PANEL, corner_radius=16, border_width=1, border_color=GLASS_BORDER_SOFT)
        c.grid(row=0, column=col, sticky="nsew", padx=(0 if col == 0 else 6, 0 if col == 3 else 6))
        start_text = formatter(0) if animate_to is not None else value
        value_label = ctk.CTkLabel(c, text=start_text, font=(FONT, size, "bold"), text_color=TEXT)
        value_label.pack(anchor="w", padx=18, pady=(16, 0))
        ctk.CTkLabel(c, text=label, font=(FONT, 12), text_color=MUTED).pack(anchor="w", padx=18, pady=(0, 16))
        if animate_to is not None:
            self.animate_count(value_label, animate_to, formatter)

    def animate_count(self, label, target, formatter, steps=20, i=0):
        t = i / steps
        eased = 1 - (1 - t) ** 3
        try:
            label.configure(text=formatter(target * eased))
        except Exception:
            return
        if i < steps:
            self.after(16, lambda: self.animate_count(label, target, formatter, steps, i + 1))
        else:
            label.configure(text=formatter(target))

    def stat_section(self, parent, title):
        card = ctk.CTkFrame(parent, fg_color=PANEL, corner_radius=16, border_width=1, border_color=GLASS_BORDER_SOFT)
        card.pack(fill="x", pady=(12, 0))
        ctk.CTkLabel(card, text=title, font=(FONT, 16, "bold"), text_color=TEXT).pack(anchor="w", padx=20,
                                                                                       pady=(16, 6))
        return card

    def rank_row(self, parent, rank, name, sub, right, ratio):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=20, pady=6)
        ctk.CTkLabel(row, text=str(rank), width=24, font=(FONT, 14, "bold"), text_color=MUTED).pack(side="left")
        ctk.CTkLabel(row, text=right, font=(FONT, 12), text_color=MUTED, anchor="e").pack(side="right")
        mid = ctk.CTkFrame(row, fg_color="transparent")
        mid.pack(side="left", fill="x", expand=True, padx=(8, 14))
        shown = name if len(name) <= 55 else name[:52] + "…"
        ctk.CTkLabel(mid, text=shown, font=(FONT, 13, "bold"), text_color=TEXT, anchor="w").pack(anchor="w")
        if sub:
            ctk.CTkLabel(mid, text=sub, font=(FONT, 11), text_color=MUTED, anchor="w").pack(anchor="w")
        bar = ctk.CTkProgressBar(mid, height=6, corner_radius=3, fg_color="#2A2A2A", progress_color=ACCENT)
        bar.set(max(0.02, min(ratio, 1.0)))
        bar.pack(fill="x", pady=(4, 0))

    def refresh_stats(self):
        for w in self.stats_scroll.winfo_children():
            w.destroy()
        s = self.stats
        body = self.stats_scroll
        arts = sorted(((n, a) for n, a in s["artists"].items() if a.get("plays", 0) > 0),
                      key=lambda x: x[1]["seconds"], reverse=True)
        songs = sorted((t for t in s["tracks"].values() if t.get("plays", 0) > 0),
                       key=lambda t: (t["plays"], t["seconds"]), reverse=True)

        row = ctk.CTkFrame(body, fg_color="transparent")
        row.pack(fill="x")
        for c in range(4):
            row.grid_columnconfigure(c, weight=1, uniform="a")
        self.stat_card(row, 0, "Time listened", fmt_big(s["total_seconds"]),
                      animate_to=s["total_seconds"], formatter=fmt_big)
        self.stat_card(row, 1, "Songs played", f"{s['total_plays']:,}",
                      animate_to=s["total_plays"], formatter=lambda v: f"{int(v):,}")
        self.stat_card(row, 2, "Unique songs", f"{len(songs):,}",
                      animate_to=len(songs), formatter=lambda v: f"{int(v):,}")
        self.stat_card(row, 3, "Artists", f"{len(arts):,}",
                      animate_to=len(arts), formatter=lambda v: f"{int(v):,}")

        active = [v for v in s["days"].values() if v >= 60]
        avg = fmt_hm(sum(active) / len(active)) if active else "—"
        hrs = s["hours"]
        peak = max(hrs, key=lambda h: hrs[h]) if hrs else None
        peak_txt = "—" if peak is None or hrs[peak] < 1 else f"{int(peak) % 12 or 12} {'AM' if int(peak) < 12 else 'PM'}"
        qs = s["quality"]
        topq = max(qs, key=qs.get) if qs else None
        topq_txt = QUALITY[topq]["label"] if topq in QUALITY else "—"
        streak = self.current_streak()
        row2 = ctk.CTkFrame(body, fg_color="transparent")
        row2.pack(fill="x", pady=(12, 0))
        for c in range(4):
            row2.grid_columnconfigure(c, weight=1, uniform="b")
        self.stat_card(row2, 0, "Listening streak", f"{streak} day{'s' if streak != 1 else ''}", 20)
        self.stat_card(row2, 1, "Peak listening hour", peak_txt, 20)
        self.stat_card(row2, 2, "Average per active day", avg, 20)
        self.stat_card(row2, 3, "Most used quality", topq_txt, 20)

        today = date.today()
        self.week_data = []
        for i in range(6, -1, -1):
            d = today - timedelta(days=i)
            self.week_data.append(("Today" if i == 0 else d.strftime("%a"), s["days"].get(d.isoformat(), 0.0)))
        card = self.stat_section(body, "Last 7 days")
        cv = tk.Canvas(card, height=190, bg=self.themed(PANEL), highlightthickness=0)
        self._week_cv = cv
        self._tk_bg.append((cv, PANEL))
        cv.pack(fill="x", padx=14, pady=(0, 12))
        cv.bind("<Configure>", lambda e: self.draw_week(cv))

        card = self.stat_section(body, "Top artists")
        if not arts:
            ctk.CTkLabel(card, text="Nothing here yet. Listen to a song for 30 seconds or more.",
                         font=(FONT, 12), text_color=MUTED).pack(anchor="w", padx=20, pady=(0, 16))
        top = arts[:5]
        mx = top[0][1]["seconds"] if top else 1
        for i, (name, a) in enumerate(top, 1):
            plays = a["plays"]
            self.rank_row(card, i, name, "", f"{fmt_hm(a['seconds'])}  ·  {plays} play{'s' if plays != 1 else ''}",
                          a["seconds"] / mx if mx else 0)
        ctk.CTkFrame(card, height=8, fg_color="transparent").pack()

        card = self.stat_section(body, "Top songs")
        if not songs:
            ctk.CTkLabel(card, text="Nothing here yet. Your most played songs will show up here.",
                         font=(FONT, 12), text_color=MUTED).pack(anchor="w", padx=20, pady=(0, 16))
        top = songs[:5]
        mx = top[0]["plays"] if top else 1
        for i, t in enumerate(top, 1):
            plays = t["plays"]
            self.rank_row(card, i, t["title"], t.get("artist", ""),
                          f"{plays} play{'s' if plays != 1 else ''}  ·  {fmt_hm(t['seconds'])}",
                          plays / mx if mx else 0)
        ctk.CTkFrame(card, height=8, fg_color="transparent").pack()

        ctk.CTkLabel(body, text="A song counts as played after 30 seconds. Stats are stored on this computer.",
                     font=(FONT, 11), text_color="#7A7A7A").pack(anchor="w", pady=(14, 8))
        self._recolor(self.stats_scroll, only_visible=False)

    def draw_week(self, cv):
        cv.delete("all")
        w = cv.winfo_width()
        h = int(float(cv["height"]))
        if w < 60 or not self.week_data:
            return
        n = len(self.week_data)
        top, base, pad = 26, h - 28, 20
        mx = max(v for _, v in self.week_data)
        slot = (w - 2 * pad) / n
        bw = min(slot * 0.5, 48)
        for i, (lab, v) in enumerate(self.week_data):
            cx = pad + slot * (i + 0.5)
            cv.create_rectangle(cx - bw / 2, top, cx + bw / 2, base, fill=self.themed("#222222"), outline="")
            if v > 0 and mx > 0:
                y0 = base - max((v / mx) * (base - top), 4)
                cv.create_rectangle(cx - bw / 2, y0, cx + bw / 2, base, fill=self.themed(ACCENT), outline="")
                cv.create_text(cx, y0 - 10, text=fmt_hm(v), fill=self.themed(TEXT), font=(FONT, 9))
            cv.create_text(cx, base + 14, text=lab, fill=self.themed(MUTED), font=(FONT, 10))

    def make_table(self, parent):
        wrap = ctk.CTkFrame(parent, fg_color=PANEL, corner_radius=18,
                            border_width=1, border_color=GLASS_BORDER_SOFT)
        wrap.pack(fill="both", expand=True, pady=(14, 0))
        tree = ttk.Treeview(wrap, columns=("title", "time", "lyrics"), show="tree headings",
                            selectmode="browse", style="CrystalWave.Treeview")
        tree.heading("#0", text="")
        tree.heading("title", text="Title", anchor="w")
        tree.heading("time", text="Duration", anchor="e")
        tree.heading("lyrics", text="", anchor="center")
        tree.column("#0", width=THUMB_SIZE + 24, minwidth=THUMB_SIZE + 24, anchor="center", stretch=False)
        tree.column("title", anchor="w", stretch=True)
        tree.column("time", width=90, anchor="e", stretch=False)
        tree.column("lyrics", width=50, minwidth=50, anchor="center", stretch=False)
        tree.tag_configure("playing", foreground=ACCENT)
        sb = ctk.CTkScrollbar(wrap, command=tree.yview, fg_color=PANEL, button_color="#3A3A3A",
                              button_hover_color="#555555")
        tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y", padx=(0, 4), pady=8)
        tree.pack(fill="both", expand=True, padx=(8, 0), pady=8)
        tree.bind("<Button-1>", self.on_table_click, add="+")
        return tree

    def make_menu(self, items):
        m = tk.Menu(self, tearoff=0, bg=self.themed(HOVER), fg=self.themed(TEXT), activebackground=self.themed(ACCENT),
                    activeforeground="black", bd=0, font=(FONT, 10))
        for label, cmd in items:
            m.add_command(label=label, command=cmd)
        self._menus.append(m)
        return m

    def bind_menu(self, tree, menu):
        def popup(e):
            row = tree.identify_row(e.y)
            if row:
                tree.selection_set(row)
                menu.tk_popup(e.x_root, e.y_root)
        tree.bind("<Button-3>", popup)
        tree.bind("<Button-2>", popup)

    def build_player_bar(self):
        bar = ctk.CTkFrame(self, height=96, corner_radius=22, fg_color=PANEL,
                           border_width=1, border_color=GLASS_BORDER)
        bar.grid(row=1, column=0, columnspan=2, sticky="ew", padx=16, pady=(0, 16))
        bar.grid_propagate(False)
        bar.grid_columnconfigure(0, weight=1, uniform="p")
        bar.grid_columnconfigure(1, weight=2, uniform="p")
        bar.grid_columnconfigure(2, weight=1, uniform="p")
        bar.grid_rowconfigure(0, weight=1)
        self.player_bar = bar

        self.bar_art_label = tk.Label(bar, bd=0, highlightthickness=0, bg=PANEL)
        self.bar_art_label.place(relx=0, rely=0, relwidth=1, relheight=1)
        self._tk_bg.append((self.bar_art_label, PANEL))

        left = ctk.CTkFrame(bar, fg_color=PANEL, corner_radius=16)
        left.grid(row=0, column=0, sticky="w", padx=(22, 8))
        self._bar_chips.append(left)
        self.now_thumb = tk.Label(left, image=self.default_thumb, bd=0, bg=PANEL, highlightthickness=0)
        self.now_thumb.image = self.default_thumb
        self._tk_bg.append((self.now_thumb, PANEL))
        self.now_thumb.pack(side="left", padx=(8, 10), pady=8)
        now_text = ctk.CTkFrame(left, fg_color="transparent")
        now_text.pack(side="left", padx=(0, 14))
        self.now_label = ctk.CTkLabel(now_text, text="Nothing playing", font=(FONT, 13, "bold"), text_color=TEXT,
                                      anchor="w", justify="left", wraplength=180)
        self.now_label.pack(anchor="w")
        status_row = ctk.CTkFrame(now_text, fg_color="transparent")
        status_row.pack(anchor="w")
        self.wave_canvas = tk.Canvas(status_row, width=20, height=14, bg=PANEL, highlightthickness=0, bd=0)
        self._tk_bg.append((self.wave_canvas, PANEL))
        self.wave_canvas.pack(side="left", padx=(0, 6))
        self.wave_bars = [
            self.wave_canvas.create_rectangle(x, 14, x + 3, 14, fill=MUTED, outline="")
            for x in (0, 5, 10, 15)
        ]
        self.status_l = ctk.CTkLabel(status_row, text="Pick a song to start", font=(FONT, 11), text_color=MUTED,
                                     anchor="w", justify="left", wraplength=150)
        self.status_l.pack(side="left")

        center = ctk.CTkFrame(bar, fg_color=PANEL, corner_radius=16)
        center.grid(row=0, column=1, sticky="ew", padx=4)
        self._bar_chips.append(center)
        ctrl = ctk.CTkFrame(center, fg_color="transparent")
        ctrl.pack(pady=(8, 2))

        def icon_btn(text, cmd, size=17):
            return ctk.CTkButton(ctrl, text=text, width=34, height=34, corner_radius=17, fg_color="transparent",
                                 hover_color=HOVER, text_color=MUTED, font=(FONT, size), command=cmd)

        self.fav_btn = icon_btn("♡", self.toggle_favorite, 18)
        self.fav_btn.grid(row=0, column=0, padx=4)
        self.shuffle_btn = icon_btn("⇄", self.toggle_shuffle)
        self.shuffle_btn.grid(row=0, column=1, padx=4)
        icon_btn("⏮", self.prev_track).grid(row=0, column=2, padx=4)
        self.play_btn = ctk.CTkButton(ctrl, text="▶", width=42, height=42, corner_radius=21, fg_color=TEXT,
                                      hover_color="#DDDDDD", text_color="black", font=(FONT, 17),
                                      command=self.toggle_play)
        self.play_btn.grid(row=0, column=3, padx=8)
        icon_btn("⏭", self.next_track).grid(row=0, column=4, padx=4)
        self.repeat_btn = icon_btn("⟲", self.toggle_repeat)
        self.repeat_btn.grid(row=0, column=5, padx=4)
        self.sleep_btn = icon_btn("☾", self.show_sleep_menu, 18)
        self.sleep_btn.grid(row=0, column=6, padx=4)
        icon_btn("☰", self.toggle_queue_view, 17).grid(row=0, column=7, padx=4)
        icon_btn("⧉", self.toggle_mini_player, 17).grid(row=0, column=8, padx=4)

        seek_row = ctk.CTkFrame(center, fg_color="transparent")
        seek_row.pack(fill="x", padx=14, pady=(0, 8))
        self.time_l = ctk.CTkLabel(seek_row, text="0:00", width=42, font=(FONT, 11), text_color=MUTED)
        self.time_l.pack(side="left")
        self.seek = ctk.CTkSlider(seek_row, from_=0, to=1, height=14, fg_color="#4D4D4D",
                                  progress_color=self.accent_color, button_color=TEXT, button_hover_color=TEXT)
        self.seek.set(0)
        self.seek.pack(side="left", fill="x", expand=True, padx=8)
        self.seek.bind("<ButtonPress-1>", lambda e: setattr(self, "seeking", True), add="+")
        self.seek.bind("<ButtonRelease-1>", self.on_seek_release, add="+")
        self.total_l = ctk.CTkLabel(seek_row, text="0:00", width=42, font=(FONT, 11), text_color=MUTED)
        self.total_l.pack(side="left")

        right = ctk.CTkFrame(bar, fg_color=PANEL, corner_radius=16)
        right.grid(row=0, column=2, sticky="e", padx=(8, 26))
        self._bar_chips.append(right)
        self.lyrics_bar_btn = ctk.CTkButton(
            right, text="Aa", width=34, height=30, corner_radius=8, fg_color="transparent",
            hover_color=HOVER, text_color=MUTED, font=(FONT, 12, "bold"),
            command=self.open_lyrics_for_current,
        )
        self.lyrics_bar_btn.pack(side="left", padx=(10, 14), pady=10)
        ctk.CTkLabel(right, text="🔊", font=(FONT, 14), text_color=MUTED).pack(side="left", padx=(0, 8))
        self.vol = ctk.CTkSlider(right, from_=0, to=1, width=110, height=14, fg_color="#4D4D4D",
                                 progress_color=self.accent_color, button_color=TEXT, button_hover_color=TEXT,
                                 command=self.set_volume)
        self.vol.set(0.7)
        self.vol.pack(side="left", padx=(0, 16), pady=10)

        self.build_lyrics_overlay()
        self.build_queue_panel()
        self.animate_waveform()

    def apply_accent_color(self, avg_color):
        pal, stops, _accent = build_song_theme(avg_color)
        self._begin_palette_transition(pal, stops)

    def _begin_palette_transition(self, pal_target, stops_target, steps=7, delay=30):
        if self._pal_job is not None:
            self.after_cancel(self._pal_job)
            self._pal_job = None
        keys = list(PALETTE_KEYS)
        start = {k: self._pal_cur.get(k, k) for k in keys}
        end = {k: pal_target.get(k, k) for k in keys}
        s0 = self._bd_stops_cur or BACKDROP_STOPS
        s1 = stops_target or BACKDROP_STOPS
        if start == end and [tuple(x) for x in s0] == [tuple(x) for x in s1]:
            return

        def step(i):
            e = i / steps
            e = e * e * (3 - 2 * e)
            pal = {k: mix_color(start[k], end[k], e) for k in keys}
            stops = [tuple(int(round(a + (b - a) * e)) for a, b in zip(c0, c1))
                     for c0, c1 in zip(s0, s1)]
            self._set_palette(pal, stops)
            if i < steps:
                self._pal_job = self.after(delay, lambda: step(i + 1))
            else:
                self._pal_job = None

        step(1)

    @staticmethod
    def _reverse_palette(pal):
        rev = {}
        for k, v in pal.items():
            if v != k:
                rev.setdefault(v, k)
        return rev

    def _set_palette(self, pal, stops):
        old_rev = self._reverse_palette(self._pal_cur)
        self._pal_cur = pal
        self._bd_stops_cur = stops
        self.accent_color = self.themed(ACCENT)
        self._rev = old_rev
        try:
            self._recolor(self, only_visible=True)
            if self.mini is not None and self.mini.winfo_exists():
                self.mini.configure(fg_color=self.themed(BG))
                self._recolor(self.mini, only_visible=False)
            self._apply_non_ctk_colors()
            self._paint_backdrop()
        except Exception:
            pass
        self._rev = self._reverse_palette(pal)

    _COLOR_OPTS = ("fg_color", "hover_color", "border_color", "progress_color", "button_color",
                   "button_hover_color", "checkmark_color", "text_color", "placeholder_text_color",
                   "scrollbar_fg_color", "scrollbar_button_color", "scrollbar_button_hover_color")
    _CTK_TYPES = tuple(t for t in (getattr(ctk, "CTkBaseClass", None),
                                   getattr(ctk, "CTkScrollableFrame", None)) if t)

    def _recolor(self, widget, only_visible=True):
        try:
            if only_visible and widget is not self and not widget.winfo_ismapped():
                return
        except Exception:
            return
        if isinstance(widget, self._CTK_TYPES):
            rec = widget.__dict__.setdefault("_cw_colors", {})
            changes = {}
            for opt in self._COLOR_OPTS:
                try:
                    cur = widget.cget(opt)
                except Exception:
                    continue
                if not isinstance(cur, str):
                    continue
                key = _norm(cur)
                ent = rec.get(opt)
                if ent is None or ent[1] != key:
                    ent = [key if key in PALETTE_KEYS else self._rev.get(key, key), key]
                new = self._pal_cur.get(ent[0], ent[0])
                rec[opt] = ent
                if new != key:
                    changes[opt] = new
                    ent[1] = new
                else:
                    ent[1] = key
            if isinstance(widget, ctk.CTkBaseClass):
                try:
                    cb = widget.cget("bg_color")
                    eff = self._effective_bg(widget)
                    if isinstance(cb, str) and _norm(cb) != eff:
                        changes["bg_color"] = eff
                except Exception:
                    pass
            if changes:
                try:
                    widget.configure(**changes)
                except Exception:
                    for opt in changes:
                        rec.pop(opt, None)
            if isinstance(widget, getattr(ctk, "CTkScrollableFrame", ())):
                self._sync_scrollable_bg(widget)
        for child in widget.winfo_children():
            self._recolor(child, only_visible)

    def _effective_bg(self, widget):
        m = widget.master
        while m is not None:
            try:
                fg = m.cget("fg_color")
                if isinstance(fg, str) and fg != "transparent":
                    return _norm(fg)
            except Exception:
                pass
            m = getattr(m, "master", None)
        return self.themed(BG)

    def _sync_scrollable_bg(self, sf):
        color = None
        try:
            fg = sf.cget("fg_color")
            if isinstance(fg, str) and fg != "transparent":
                color = fg
        except Exception:
            pass
        if color is None:
            color = self._effective_bg(sf)
        color = color or self.themed(BG)
        for target, base in ((getattr(sf, "_parent_canvas", None), tk.Canvas), (sf, tk.Frame)):
            if target is not None:
                try:
                    base.configure(target, bg=color)
                except Exception:
                    pass

    def _apply_non_ctk_colors(self):
        self.configure(fg_color=self.themed(BG))
        self._tk_bg = [(w, r) for w, r in self._tk_bg if w.winfo_exists()]
        for w, role in self._tk_bg:
            try:
                w.configure(bg=self.themed(role))
            except Exception:
                pass
        for m in self._menus:
            try:
                m.configure(bg=self.themed(HOVER), fg=self.themed(TEXT), activebackground=self.themed(ACCENT))
            except Exception:
                pass
        cv = getattr(self, "_week_cv", None)
        if cv is not None and cv.winfo_exists() and cv.winfo_ismapped():
            self.draw_week(cv)
        self.setup_style()

    def update_player_bar_art(self):
        bar = self.player_bar
        w, h = bar.winfo_width(), bar.winfo_height()
        if w < 40 or h < 40:
            return
        if self._backdrop_pil is not None:
            x, y = bar.winfo_x(), bar.winfo_y()
            base = self._backdrop_pil.crop((x, y, x + w, y + h)).convert("RGB")
        else:
            base = Image.new("RGB", (w, h), self.themed(PANEL))
        layer = None
        if 0 <= self.qpos < len(self.queue):
            src = self.queue[self.qpos]["src"]
            pil_img = self.thumb_pil_cache.get(src)
            if pil_img is not None:
                key = (src, w, h)
                if self._bar_art_cache is None or self._bar_art_cache[0] != key:
                    try:
                        art = pil_img.convert("RGB").resize((w, h), Image.LANCZOS).filter(ImageFilter.GaussianBlur(30))
                        art = Image.blend(art, Image.new("RGB", (w, h), (0, 0, 0)), 0.5)
                        self._bar_art_cache = (key, art)
                    except Exception:
                        self._bar_art_cache = None
                if self._bar_art_cache is not None:
                    layer = self._bar_art_cache[1]
        if layer is None:
            layer = Image.new("RGB", (w, h), self.themed(PANEL))
        base.paste(layer, (0, 0), rounded_mask_wh(w, h, 22))
        try:
            self._bar_art_photo = ImageTk.PhotoImage(base)
            self.bar_art_label.configure(image=self._bar_art_photo)
        except Exception:
            return
        for chip in self._bar_chips:
            self._paint_corner_image(chip, base, chip.winfo_x(), chip.winfo_y())

    def animate_waveform(self):
        active = self.active and not self.paused
        for rid, x in zip(self.wave_bars, (0, 5, 10, 15)):
            h = random.randint(4, 13) if active else 3
            color = self.accent_color if active else self.themed(MUTED)
            self.wave_canvas.coords(rid, x, 14 - h, x + 3, 14)
            self.wave_canvas.itemconfig(rid, fill=color)
        self.after(220, self.animate_waveform)

    def build_lyrics_overlay(self):
        self.lyrics_overlay = ctk.CTkFrame(self, corner_radius=22, fg_color=PANEL,
                                           border_width=1, border_color=GLASS_BORDER)

        head = ctk.CTkFrame(self.lyrics_overlay, fg_color="transparent")
        head.pack(fill="x", padx=30, pady=(24, 4))
        info = ctk.CTkFrame(head, fg_color="transparent")
        info.pack(side="left", fill="x", expand=True)
        self.lyrics_title_l = ctk.CTkLabel(info, text="Lyrics", font=(FONT, 22, "bold"),
                                           text_color=TEXT, anchor="w")
        self.lyrics_title_l.pack(anchor="w")
        self.lyrics_sub_l = ctk.CTkLabel(info, text="", font=(FONT, 12), text_color=MUTED, anchor="w")
        self.lyrics_sub_l.pack(anchor="w")
        ctk.CTkButton(head, text="✕", width=34, height=34, corner_radius=17, fg_color="transparent",
                      hover_color=HOVER, text_color=MUTED, font=(FONT, 15, "bold"),
                      command=self.close_lyrics_overlay).pack(side="right")

        self.lyrics_scroll = ctk.CTkScrollableFrame(self.lyrics_overlay, fg_color="transparent")
        self.lyrics_scroll.pack(fill="both", expand=True, padx=20, pady=(6, 24))

    def open_lyrics_for_current(self):
        if 0 <= self.qpos < len(self.queue):
            self.open_lyrics_for(self.queue[self.qpos])
        else:
            self.status("Play a song first to see its lyrics")

    def open_lyrics_for(self, track):
        self.lyrics_track = track
        self.lyrics_title_l.configure(text=track.get("title", "Unknown"))
        self.lyrics_sub_l.configure(text=track.get("artist") or "")
        self.lyrics_overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.lyrics_overlay.lift()
        self._recolor(self.lyrics_overlay, only_visible=False)
        self.after(40, self._paint_corners)

        cached = self.lyrics_cache.get(track["src"])
        if cached is not None:
            self.render_lyrics(cached)
            return

        self.render_lyrics_loading()
        self.lyrics_token += 1
        token = self.lyrics_token
        threading.Thread(
            target=self._lyrics_worker,
            args=(track["src"], track.get("title", ""), track.get("artist", ""),
                  track.get("duration") or 0, token),
            daemon=True,
        ).start()

    def close_lyrics_overlay(self):
        self.lyrics_overlay.place_forget()
        self.lyrics_track = None

    def _lyrics_worker(self, src, title, artist, duration, token):
        try:
            params = urllib.parse.urlencode({"track_name": title, "artist_name": artist or ""})
            req = urllib.request.Request(f"{LRCLIB_API}?{params}",
                                         headers={"User-Agent": "CrystalWave/1.0 (personal use)"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                candidates = json.loads(resp.read().decode("utf-8"))
            best = None
            if candidates:
                if duration:
                    candidates.sort(key=lambda c: abs((c.get("duration") or 0) - duration))
                best = candidates[0]
            if best and best.get("syncedLyrics"):
                result = {"synced": True, "lines": parse_lrc(best["syncedLyrics"]), "error": False}
            elif best and best.get("plainLyrics"):
                lines = [(0.0, ln) for ln in best["plainLyrics"].splitlines() if ln.strip()]
                result = {"synced": False, "lines": lines, "error": False}
            else:
                result = {"synced": False, "lines": [], "error": False}
        except Exception:
            result = {"synced": False, "lines": [], "error": True}
        self.tasks.put(lambda: self._lyrics_ready(src, result, token))

    def _lyrics_ready(self, src, result, token):
        if token != self.lyrics_token:
            return
        self.lyrics_cache[src] = result
        if self.lyrics_track and self.lyrics_track["src"] == src:
            self.render_lyrics(result)

    def _clear_lyrics_scroll(self):
        for w in self.lyrics_scroll.winfo_children():
            w.destroy()
        self.lyrics_line_labels = []
        self.lyrics_active_idx = -1

    def render_lyrics_loading(self):
        self._clear_lyrics_scroll()
        ctk.CTkLabel(self.lyrics_scroll, text="Looking up lyrics...", font=(FONT, 13),
                    text_color=self.themed(MUTED)).pack(pady=24)

    def render_lyrics(self, result):
        self._clear_lyrics_scroll()
        lines = result.get("lines") or []
        if not lines:
            msg = "Couldn't reach the lyrics service - check your connection." if result.get("error") \
                else "No lyrics found for this song."
            ctk.CTkLabel(self.lyrics_scroll, text=msg, font=(FONT, 13), text_color=self.themed(MUTED)).pack(pady=24)
            return
        if not result.get("synced"):
            ctk.CTkLabel(self.lyrics_scroll, text="Unsynced lyrics (no timing data available)",
                        font=(FONT, 11), text_color=self.themed(MUTED)).pack(anchor="w", padx=10, pady=(0, 10))
        for _ts, text in lines:
            lbl = ctk.CTkLabel(self.lyrics_scroll, text=text or "♪", font=(FONT, 16, "bold"),
                               text_color=self.themed(MUTED), anchor="w", justify="left", wraplength=640)
            lbl.pack(fill="x", padx=10, pady=6, anchor="w")
            self.lyrics_line_labels.append(lbl)
        self._lyrics_lines = lines

    def update_lyrics_highlight(self):
        if not self.lyrics_line_labels or not getattr(self, "_lyrics_lines", None):
            return
        pos = max(self.player.get_time(), 0) / 1000 if self.active else 0
        idx = -1
        for i, (ts, _text) in enumerate(self._lyrics_lines):
            if ts <= pos:
                idx = i
            else:
                break
        if idx == self.lyrics_active_idx:
            return
        if 0 <= self.lyrics_active_idx < len(self.lyrics_line_labels):
            self.lyrics_line_labels[self.lyrics_active_idx].configure(text_color=self.themed(MUTED), font=(FONT, 16, "bold"))
        self.lyrics_active_idx = idx
        if 0 <= idx < len(self.lyrics_line_labels):
            lbl = self.lyrics_line_labels[idx]
            lbl.configure(text_color=self.themed(ACCENT), font=(FONT, 19, "bold"))
            try:
                total = max(len(self.lyrics_line_labels) - 1, 1)
                frac = min(max((idx - 2) / total, 0.0), 1.0)
                self.lyrics_scroll._parent_canvas.yview_moveto(frac)
            except Exception:
                pass

    def show_page(self, key):
        if key == self.current_page or key not in self.pages:
            return
        for k, b in self.nav.items():
            b.configure(fg_color=self.themed(HOVER) if k == key else "transparent",
                        text_color=self.themed(TEXT) if k == key else self.themed(MUTED))
        if key == "stats":
            self.refresh_stats()

        new = self.pages[key]
        self._recolor(new, only_visible=False)
        old_key = self.current_page
        old = self.pages.get(old_key) if old_key else None
        self.current_page = key
        self._redraw_backdrop()

        if old is None:
            new.place(relx=0, rely=0, relwidth=1, relheight=1)
            new.lift()
            return

        direction = 1 if self._nav_order.index(key) > self._nav_order.index(old_key) else -1
        new.place(relx=direction, rely=0, relwidth=1, relheight=1)
        new.lift()
        self._slide_pages(old, new, direction)

    def _slide_pages(self, old, new, direction, step=0, steps=15):
        t = step / steps
        eased = 1 - (1 - t) ** 3
        new.place_configure(relx=direction * (1 - eased))
        old.place_configure(relx=-direction * eased)
        if step < steps:
            self.after(12, lambda: self._slide_pages(old, new, direction, step + 1, steps))
        else:
            new.place_configure(relx=0)
            old.place_forget()

    def status(self, text):
        self.status_l.configure(text=text)

    def quality_key(self):
        return self.settings["audio_quality"]

    def on_quality_change(self):
        key = self.quality_var.get()
        if key == self.settings["audio_quality"]:
            return
        self.settings["audio_quality"] = key
        self.save_settings()
        self.stream_label = ""
        self.update_stream_info()
        if 0 <= self.qpos < len(self.queue):
            if self.active:
                pos = max(self.player.get_time(), 0) / 1000
                self.play_current(start=pos, keep_paused=self.paused)
            elif self.loading:
                self.play_current()

    def update_stream_info(self, note=""):
        req = QUALITY[self.quality_key()]["label"]
        if self.stream_label:
            text = f"Now streaming: {self.stream_label}   (requested: {req})"
            if note:
                text += f"\n{note}"
        else:
            text = f"Selected quality: {req}. Play a song to see the stream you get."
        self.stream_info.configure(text=text)

    def now_status(self):
        return "Now playing"

    def load_playlists(self):
        try:
            with open(PLAYLISTS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.playlists = {
                name: [t for t in tracks if t.get("online")]
                for name, tracks in data.items() if isinstance(tracks, list)
            }
        except (OSError, ValueError):
            self.playlists = {}

        if not self.playlists:
            migrated = []
            try:
                with open(LIB_FILE, "r", encoding="utf-8") as f:
                    migrated = [t for t in json.load(f) if t.get("online")]
            except (OSError, ValueError):
                pass
            self.playlists = {DEFAULT_PLAYLIST: migrated}

        self.current_playlist = self.first_playlist()
        self.refresh_playlist_sidebar()
        self.refresh_list()

    def first_playlist(self):
        for name in self.playlists:
            if name != RECENT_NAME:
                return name
        return RECENT_NAME if RECENT_NAME in self.playlists else None

    def save_playlists(self):
        try:
            with open(PLAYLISTS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.playlists, f)
        except OSError:
            pass

    def current_tracks(self):
        return self.playlists.get(self.current_playlist, [])

    def new_playlist(self):
        dialog = ctk.CTkInputDialog(text="Name this playlist:", title="New Playlist")
        name = (dialog.get_input() or "").strip()
        if not name:
            return
        if name in self.playlists or name == RECENT_NAME:
            self.status(f'A playlist called "{name}" already exists')
            return
        self.playlists[name] = []
        self.current_playlist = name
        self.save_playlists()
        self.refresh_playlist_sidebar()
        self.refresh_list()

    def delete_current_playlist(self):
        name = self.current_playlist
        if not name:
            return
        if not messagebox.askyesno("Delete playlist", f'Delete "{name}"? This can\'t be undone.'):
            return
        del self.playlists[name]
        self.current_playlist = self.first_playlist()
        self.save_playlists()
        self.refresh_playlist_sidebar()
        self.refresh_list()

    def select_playlist(self, name):
        self.current_playlist = name
        self.refresh_playlist_sidebar()
        self.refresh_list()

    def refresh_playlist_sidebar(self):
        for w in self.playlist_scroll.winfo_children():
            w.destroy()
        names = [n for n in self.playlists if n != RECENT_NAME]
        if RECENT_NAME in self.playlists:
            names.append(RECENT_NAME)
        for name in names:
            n = len(self.playlists[name])
            active = name == self.current_playlist
            row = ctk.CTkButton(
                self.playlist_scroll, text=f"{name}\n{n} song{'s' if n != 1 else ''}", anchor="w",
                height=46, corner_radius=8, fg_color=HOVER if active else "transparent",
                hover_color=HOVER, text_color=TEXT if active else MUTED, font=(FONT, 12, "bold"),
                command=lambda n=name: self.select_playlist(n),
            )
            row.pack(fill="x", pady=2)
        self._recolor(self.playlist_scroll, only_visible=False)
        self.update_heart()

    def build_queue_panel(self):
        self.queue_panel = ctk.CTkFrame(self, corner_radius=22, fg_color=PANEL,
                                        border_width=1, border_color=GLASS_BORDER)
        head = ctk.CTkFrame(self.queue_panel, fg_color="transparent")
        head.pack(fill="x", padx=20, pady=(18, 0))
        ctk.CTkLabel(head, text="Up Next", font=(FONT, 20, "bold"), text_color=TEXT).pack(side="left")
        ctk.CTkButton(head, text="✕", width=30, height=30, corner_radius=15, fg_color="transparent",
                      hover_color=HOVER, text_color=MUTED, font=(FONT, 13, "bold"),
                      command=self.toggle_queue_view).pack(side="right")
        ctk.CTkButton(head, text="Clear", width=56, height=28, corner_radius=14, fg_color="transparent",
                      border_width=1, border_color="#535353", hover_color=HOVER, text_color=TEXT,
                      font=(FONT, 11, "bold"), command=self.clear_queue).pack(side="right", padx=(0, 8))
        self.queue_count_l = ctk.CTkLabel(self.queue_panel, text="", font=(FONT, 12), text_color=MUTED)
        self.queue_count_l.pack(anchor="w", padx=22)
        self.queue_scroll = ctk.CTkScrollableFrame(self.queue_panel, fg_color="transparent")
        self.queue_scroll.pack(fill="both", expand=True, padx=10, pady=(6, 16))

    def toggle_queue_view(self):
        if self.queue_panel.winfo_ismapped():
            self.queue_panel.place_forget()
            return
        self.queue_panel.place(relx=1, rely=0, x=-24, y=24, anchor="ne", width=380, relheight=1, height=-150)
        self.queue_panel.lift()
        self.refresh_queue_view()
        self.after(40, self._paint_corners)

    def refresh_queue_view(self):
        panel = getattr(self, "queue_panel", None)
        if panel is None or not panel.winfo_ismapped():
            return
        for w in self.queue_scroll.winfo_children():
            w.destroy()
        n = len(self.queue)
        if not n:
            self.queue_count_l.configure(text="Nothing queued yet")
        else:
            limit = 60
            start = max(self.qpos, 0)
            upcoming = n - start - 1
            self.queue_count_l.configure(text=f"{upcoming} up next")
            for idx in range(start, min(n, start + limit + 1)):
                self._queue_row(idx)
            if n > start + limit + 1:
                ctk.CTkLabel(self.queue_scroll, text=f"+ {n - start - limit - 1} more", font=(FONT, 11),
                             text_color=MUTED).pack(pady=8)
        self._recolor(self.queue_scroll, only_visible=False)

    def _queue_row(self, idx):
        t = self.queue[idx]
        current = idx == self.qpos
        row = ctk.CTkFrame(self.queue_scroll, fg_color="transparent")
        row.pack(fill="x", pady=1)
        mark = "▶  " if current else f"{idx - self.qpos}.  "
        btn = ctk.CTkButton(row, text=mark + shorten(t["title"], 38), anchor="w", height=36, corner_radius=8,
                            fg_color="transparent", hover_color=HOVER, font=(FONT, 12, "bold" if current else "normal"),
                            text_color=ACCENT if current else TEXT, command=lambda i=idx: self.queue_jump(i))
        btn.pack(side="left", fill="x", expand=True)
        if not current:
            ctk.CTkButton(row, text="✕", width=30, height=30, corner_radius=15, fg_color="transparent",
                          hover_color=HOVER, text_color=MUTED, font=(FONT, 12, "bold"),
                          command=lambda i=idx: self.queue_remove(i)).pack(side="right")
            btn.bind("<Button-3>", lambda e, i=idx: self.queue_menu(e, i))

    def _queue_editable(self):
        if self.crossfading:
            self.status("Wait for the crossfade to finish")
            return False
        return True

    def queue_jump(self, idx):
        if self._queue_editable() and 0 <= idx < len(self.queue):
            self.qpos = idx
            self.play_current()

    def queue_remove(self, idx):
        if self._queue_editable() and idx > self.qpos:
            del self.queue[idx]
            self.refresh_queue_view()

    def queue_move(self, idx, delta):
        new = idx + delta
        if self._queue_editable() and self.qpos < new < len(self.queue) and idx > self.qpos:
            self.queue[idx], self.queue[new] = self.queue[new], self.queue[idx]
            self.refresh_queue_view()

    def queue_to_top(self, idx):
        if self._queue_editable() and idx > self.qpos + 1:
            self.queue.insert(self.qpos + 1, self.queue.pop(idx))
            self.refresh_queue_view()

    def clear_queue(self):
        if self._queue_editable() and len(self.queue) > self.qpos + 1:
            del self.queue[self.qpos + 1:]
            self.refresh_queue_view()
            self.status("Queue cleared")

    def queue_menu(self, event, idx):
        menu = tk.Menu(self, tearoff=0, bg=self.themed(HOVER), fg=self.themed(TEXT),
                       activebackground=self.themed(ACCENT), activeforeground="black", bd=0, font=(FONT, 10))
        menu.add_command(label="Play Next", command=lambda: self.queue_to_top(idx))
        menu.add_command(label="Move Up", command=lambda: self.queue_move(idx, -1))
        menu.add_command(label="Move Down", command=lambda: self.queue_move(idx, 1))
        menu.add_command(label="Remove", command=lambda: self.queue_remove(idx))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def record_history(self, track):
        songs = self.playlists.setdefault(RECENT_NAME, [])
        songs[:] = [dict(track)] + [t for t in songs if t["src"] != track["src"]]
        del songs[RECENT_MAX:]
        self.save_playlists()
        if self.current_playlist == RECENT_NAME:
            self.refresh_list()
        self.refresh_playlist_sidebar()

    def export_playlist(self):
        name = self.current_playlist
        if not name:
            return
        safe = re.sub(r'[\\/:*?"<>|]+', "_", name)
        path = filedialog.asksaveasfilename(title="Export playlist", defaultextension=".json",
                                            initialfile=f"{safe}.json",
                                            filetypes=[("CrystalWave playlist", "*.json")])
        if not path:
            return
        data = {"crystalwave_playlist": 1, "name": name, "songs": self.current_tracks()}
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            self.status(f'Exported "{name}"')
        except OSError as ex:
            self.status(f"Export failed: {ex}"[:120])

    def show_import_menu(self):
        menu = tk.Menu(self, tearoff=0, bg=self.themed(HOVER), fg=self.themed(TEXT),
                       activebackground=self.themed(ACCENT), activeforeground="black", bd=0, font=(FONT, 10))
        menu.add_command(label="From file...", command=self.import_playlist_file)
        menu.add_command(label="From YouTube link...", command=self.import_playlist_link)
        try:
            menu.tk_popup(self.import_btn.winfo_rootx(),
                          self.import_btn.winfo_rooty() + self.import_btn.winfo_height())
        finally:
            menu.grab_release()

    def clean_tracks(self, songs):
        out, seen = [], set()
        if not isinstance(songs, list):
            return out
        for s in songs[:1000]:
            if not isinstance(s, dict):
                continue
            src, title = s.get("src"), s.get("title")
            if not (isinstance(src, str) and src.startswith(("http://", "https://")) and src not in seen
                    and isinstance(title, str) and title.strip()):
                continue
            seen.add(src)
            dur = s.get("duration")
            track = {
                "title": title.strip()[:200],
                "artist": str(s.get("artist") or "")[:100],
                "src": src,
                "online": True,
                "duration": dur if isinstance(dur, (int, float)) else 0,
                "explicit": bool(s.get("explicit")),
            }
            thumb = s.get("thumb")
            if isinstance(thumb, str) and thumb.startswith(("http://", "https://")):
                track["thumb"] = thumb
            out.append(track)
        return out

    def add_imported_playlist(self, name, tracks):
        name = (name or "").strip()[:60] or "Imported"
        if name == RECENT_NAME:
            name = "Imported"
        base, n = name, 2
        while name in self.playlists:
            name = f"{base} ({n})"
            n += 1
        self.playlists[name] = tracks
        self.current_playlist = name
        self.save_playlists()
        self.refresh_playlist_sidebar()
        self.refresh_list()
        self.status(f'Imported "{name}" ({len(tracks)} songs)')

    def import_playlist_file(self):
        path = filedialog.askopenfilename(title="Import playlist",
                                          filetypes=[("CrystalWave playlist", "*.json"), ("All files", "*.*")])
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            name, songs = str(data["name"]), data["songs"]
        except (OSError, ValueError, KeyError, TypeError):
            self.status("That file isn't a CrystalWave playlist")
            return
        tracks = self.clean_tracks(songs)
        if not tracks:
            self.status("No songs found in that file")
            return
        self.add_imported_playlist(name, tracks)

    def import_playlist_link(self):
        dialog = ctk.CTkInputDialog(text="Paste a YouTube playlist link:", title="Import playlist")
        url = (dialog.get_input() or "").strip()
        if not url:
            return
        if not url.startswith(("http://", "https://")):
            self.status("That doesn't look like a link")
            return
        self.status("Importing playlist...")
        threading.Thread(target=self._import_worker, args=(url,), daemon=True).start()

    def _import_worker(self, url):
        opts = {"quiet": True, "no_warnings": True, "extract_flat": True, "skip_download": True,
                "playlistend": 300}
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
            tracks = [track_from_entry(e) for e in (info.get("entries") or []) if e]
            name = info.get("title") or "Imported playlist"
            self.tasks.put(lambda: self._import_done(name, tracks))
        except Exception as ex:
            msg = f"Import failed: {ex}"
            self.tasks.put(lambda: self.status(msg[:120]))

    def _import_done(self, name, tracks):
        tracks = self.clean_tracks(tracks)
        if not tracks:
            self.status("No songs found at that link")
            return
        self.add_imported_playlist(name, tracks)

    def toggle_mini_player(self):
        if self.mini is not None and self.mini.winfo_exists():
            self.close_mini_player(restore=True)
        else:
            self.open_mini_player()

    def open_mini_player(self):
        win = ctk.CTkToplevel(self)
        win.title("CrystalWave")
        win.geometry("380x128")
        win.resizable(False, False)
        win.attributes("-topmost", True)
        win.configure(fg_color=self.themed(BG))
        win.protocol("WM_DELETE_WINDOW", lambda: self.close_mini_player(restore=True))
        win.bind("<space>", lambda e: self.toggle_play())
        win.bind("<Escape>", lambda e: self.close_mini_player(restore=True))
        if os.path.exists(ICON_FILE):
            win.after(300, lambda: self._mini_icon(win))
        self.mini = win

        body = ctk.CTkFrame(win, fg_color=BG, corner_radius=0)
        body.pack(fill="both", expand=True)
        body.grid_columnconfigure(1, weight=1)
        self.mini_art = tk.Label(body, bd=0, highlightthickness=0, bg=self.themed(PANEL), image=self.default_thumb)
        self.mini_art.grid(row=0, column=0, rowspan=2, padx=(14, 12), pady=(14, 0))
        self._tk_bg.append((self.mini_art, PANEL))
        self.mini_title = ctk.CTkLabel(body, text="Nothing playing", font=(FONT, 14, "bold"),
                                       text_color=TEXT, anchor="w")
        self.mini_title.grid(row=0, column=1, sticky="ew", padx=(0, 14), pady=(14, 0))
        self.mini_artist = ctk.CTkLabel(body, text="", font=(FONT, 11), text_color=MUTED, anchor="w")
        self.mini_artist.grid(row=1, column=1, sticky="ew", padx=(0, 14))

        ctrl = ctk.CTkFrame(body, fg_color="transparent")
        ctrl.grid(row=2, column=0, columnspan=2, pady=(2, 0))

        def mini_btn(text, cmd, size=16):
            b = ctk.CTkButton(ctrl, text=text, width=34, height=34, corner_radius=17, fg_color="transparent",
                              hover_color=HOVER, text_color=MUTED, font=(FONT, size), command=cmd)
            b.pack(side="left", padx=4)
            return b

        mini_btn("⏮", self.prev_track)
        self.mini_play = ctk.CTkButton(ctrl, text="▶", width=38, height=38, corner_radius=19, fg_color=TEXT,
                                       hover_color="#DDDDDD", text_color="black", font=(FONT, 16),
                                       command=self.toggle_play)
        self.mini_play.pack(side="left", padx=8)
        mini_btn("⏭", self.next_track)
        mini_btn("⤢", lambda: self.close_mini_player(restore=True))
        self.mini_bar = ctk.CTkProgressBar(body, height=4, progress_color=ACCENT, fg_color="#4D4D4D")
        self.mini_bar.set(0)
        self.mini_bar.grid(row=3, column=0, columnspan=2, sticky="ew", padx=14, pady=(6, 0))

        self._mini_state = None
        self._recolor(win, only_visible=False)
        self.update_mini()
        self.iconify()

    def _mini_icon(self, win):
        try:
            if win.winfo_exists():
                win.iconbitmap(ICON_FILE)
        except Exception:
            pass

    def close_mini_player(self, restore=False):
        win, self.mini = self.mini, None
        if win is not None:
            try:
                win.destroy()
            except Exception:
                pass
        if restore:
            self.deiconify()
            self.lift()

    def update_mini(self):
        win = self.mini
        if win is None:
            return
        try:
            if not win.winfo_exists():
                self.mini = None
                return
        except Exception:
            self.mini = None
            return
        t = self.queue[self.qpos] if 0 <= self.qpos < len(self.queue) else None
        title = shorten(t["title"], 34) if t else "Nothing playing"
        artist = shorten(t.get("artist") or "", 40) if t else ""
        play = self.play_btn.cget("text")
        photo = self.thumb_cache.get(t["src"], self.default_thumb) if t else self.default_thumb
        state = (title, artist, play, id(photo))
        if state != self._mini_state:
            self._mini_state = state
            self.mini_title.configure(text=title)
            self.mini_artist.configure(text=artist)
            self.mini_play.configure(text=play)
            self.mini_art.configure(image=photo)
            self.mini_art.image = photo
        self.mini_bar.set(min(max(self.seek.get() / max(self.length, 1), 0), 1))

    def on_media_keys_change(self):
        self.settings["media_keys"] = bool(self.media_keys_var.get())
        self.save_settings()
        self.apply_media_keys()

    def apply_media_keys(self):
        on = bool(self.settings.get("media_keys", True)) and sys.platform == "win32"
        running = self._media_thread is not None and self._media_thread.is_alive()
        if on and not running:
            ready = threading.Event()
            self._media_thread = threading.Thread(target=self._media_key_loop, args=(ready,), daemon=True)
            self._media_thread.start()
            ready.wait(1.0)
        elif not on and running:
            self.stop_media_keys()

    def stop_media_keys(self):
        thread = self._media_thread
        if thread is None or not thread.is_alive() or sys.platform != "win32":
            return
        try:
            import ctypes
            ctypes.windll.user32.PostThreadMessageW(self._media_tid, 0x0012, 0, 0)
            thread.join(0.5)
        except Exception:
            pass
        self._media_thread = None

    def _media_key_loop(self, ready):
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
        user32.RegisterHotKey.restype = wintypes.BOOL
        user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
        user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
        user32.GetMessageW.restype = ctypes.c_int
        user32.PeekMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT,
                                        wintypes.UINT, wintypes.UINT]
        msg = wintypes.MSG()
        user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 0)
        self._media_tid = ctypes.windll.kernel32.GetCurrentThreadId()
        actions = {1: (0xB3, self.toggle_play), 2: (0xB0, self.next_track), 3: (0xB1, self.prev_track)}
        registered = [hid for hid, (vk, _fn) in actions.items() if user32.RegisterHotKey(None, hid, 0x4000, vk)]
        ready.set()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == 0x0312 and msg.wParam in actions:
                self.tasks.put(actions[msg.wParam][1])
        for hid in registered:
            user32.UnregisterHotKey(None, hid)

    def queue_selected(self, source, next_up):
        if source == "playlist":
            i = self.selected(self.lib_tree)
            track = self.current_tracks()[i] if i is not None else None
        else:
            i = self.selected(self.net_tree)
            track = self.results[i] if i is not None else None
        if track is None:
            return
        track = dict(track)
        if not self.queue:
            self.play_from([track], 0)
            return
        if next_up:
            at = (self._crossfade_next_idx if self.crossfading else self.qpos) + 1
            self.queue.insert(at, track)
            self.status(f'Playing next: {track["title"]}')
        else:
            self.queue.append(track)
            self.status(f'Added to queue: {track["title"]}')
        self.refresh_queue_view()

    def update_heart(self):
        btn = getattr(self, "fav_btn", None)
        if btn is None:
            return
        fav = False
        if 0 <= self.qpos < len(self.queue):
            src = self.queue[self.qpos]["src"]
            fav = any(t["src"] == src for t in self.playlists.get(FAV_NAME, []))
        btn.configure(text="♥" if fav else "♡",
                      text_color=self.themed(ACCENT) if fav else self.themed(MUTED))

    def toggle_favorite(self):
        if not 0 <= self.qpos < len(self.queue):
            self.status("Play a song first")
            return
        track = self.queue[self.qpos]
        songs = self.playlists.get(FAV_NAME, [])
        if any(t["src"] == track["src"] for t in songs):
            self.playlists[FAV_NAME] = [t for t in songs if t["src"] != track["src"]]
            self.save_playlists()
            if self.current_playlist == FAV_NAME:
                self.refresh_list()
            self.refresh_playlist_sidebar()
            self.status("Removed from Favorites")
        else:
            self.add_track_to_playlist(FAV_NAME, track)
        self.update_heart()

    def show_sleep_menu(self):
        menu = tk.Menu(self, tearoff=0, bg=self.themed(HOVER), fg=self.themed(TEXT),
                       activebackground=self.themed(ACCENT), activeforeground="black", bd=0, font=(FONT, 10))
        for label, value in SLEEP_CHOICES:
            menu.add_command(label=label, command=lambda v=value: self.set_sleep(v, announce=True))
        try:
            menu.tk_popup(self.sleep_btn.winfo_rootx(),
                          self.sleep_btn.winfo_rooty() + self.sleep_btn.winfo_height())
        finally:
            menu.grab_release()

    def set_sleep(self, value, announce=False):
        self.sleep_at = None
        self.sleep_after_song = False
        if value == "song":
            self.sleep_after_song = True
        elif value:
            self.sleep_at = time.time() + value * 60
        on = value is not None
        self.sleep_btn.configure(text_color=self.themed(ACCENT) if on else self.themed(MUTED))
        if announce:
            if value == "song":
                self.status("Sleep timer: stops after this song")
            elif value:
                self.status(f"Sleep timer: pausing in {value} min")
            else:
                self.status("Sleep timer off")

    def add_result_to_playlist_menu(self):
        i = self.selected(self.net_tree)
        if i is None:
            self.status("Select a song in the results first")
            return
        track = self.results[i]
        menu = tk.Menu(self, tearoff=0, bg=self.themed(HOVER), fg=self.themed(TEXT), activebackground=self.themed(ACCENT),
                       activeforeground="black", bd=0, font=(FONT, 10))
        names = [n for n in self.playlists if n != RECENT_NAME]
        for name in names:
            menu.add_command(label=name, command=lambda n=name, t=track: self.add_track_to_playlist(n, t))
        if names:
            menu.add_separator()
        menu.add_command(label="New Playlist...", command=lambda t=track: self.add_to_new_playlist(t))
        try:
            x = self.add_to_playlist_btn.winfo_rootx()
            y = self.add_to_playlist_btn.winfo_rooty() + self.add_to_playlist_btn.winfo_height()
            menu.tk_popup(x, y)
        finally:
            menu.grab_release()

    def add_to_new_playlist(self, track):
        dialog = ctk.CTkInputDialog(text="Name this playlist:", title="New Playlist")
        name = (dialog.get_input() or "").strip()
        if not name:
            return
        if name not in self.playlists:
            self.playlists[name] = []
        self.add_track_to_playlist(name, track)

    def add_track_to_playlist(self, name, track):
        songs = self.playlists.setdefault(name, [])
        if any(t["src"] == track["src"] for t in songs):
            self.status(f'Already in "{name}"')
            return
        songs.append(dict(track))
        self.save_playlists()
        if name == self.current_playlist:
            self.refresh_list()
        self.refresh_playlist_sidebar()
        self.status(f'Added to "{name}"')

    def setup_shortcuts(self):
        self._premute_volume = None
        self.bind("<KeyPress>", self._on_key)

    def _focus_kind(self):
        try:
            w = self.focus_get()
            cls = w.winfo_class() if w is not None else ""
        except Exception:
            return "other"
        if cls in ("Entry", "Text", "TEntry", "Spinbox"):
            return "typing"
        if cls == "Treeview":
            return "tree"
        return "other"

    def _on_key(self, e):
        ks = e.keysym
        kind = self._focus_kind()
        typing = kind == "typing"
        if ks == "Escape":
            if self.lyrics_overlay.winfo_ismapped():
                self.close_lyrics_overlay()
            elif self.queue_panel.winfo_ismapped():
                self.toggle_queue_view()
            elif typing:
                self.focus_set()
            else:
                return None
            return "break"
        if e.state & 0x4:
            if ks in ("1", "2", "3", "4"):
                self.show_page(self._nav_order[int(ks) - 1])
            elif ks.lower() == "f":
                self.focus_search()
            elif ks.lower() == "m":
                self.toggle_mini_player()
            elif ks == "Right" and not typing:
                self.next_track()
            elif ks == "Left" and not typing:
                self.prev_track()
            elif ks in ("Up", "Down") and self.current_page == "playlists" and not typing:
                self.move_selected(-1 if ks == "Up" else 1)
            else:
                return None
            return "break"
        if typing:
            return None
        k = ks.lower()
        if ks == "space":
            self.toggle_play()
        elif ks == "Right":
            self.seek_by(5)
        elif ks == "Left":
            self.seek_by(-5)
        elif ks in ("Up", "Down") and kind != "tree":
            self.volume_by(0.05 if ks == "Up" else -0.05)
        elif k == "m":
            self.toggle_mute()
        elif k == "s":
            self.toggle_shuffle()
        elif k == "r":
            self.toggle_repeat()
        elif k == "f":
            self.toggle_favorite()
        elif k == "q":
            self.toggle_queue_view()
        elif k == "l":
            if self.lyrics_overlay.winfo_ismapped():
                self.close_lyrics_overlay()
            else:
                self.open_lyrics_for_current()
        else:
            return None
        return "break"

    def focus_search(self):
        if self.current_page == "playlists":
            entry = self.pl_filter_entry
        else:
            self.show_page("search")
            entry = self.online_entry
        entry.focus_set()
        try:
            entry.select_range(0, "end")
        except Exception:
            pass

    def seek_by(self, delta):
        if not self.active or self.loading or self.crossfading:
            return
        pos = max(self.player.get_time(), 0) / 1000
        top = max(self.length - 1, 0) if self.length else pos + delta
        t = min(max(pos + delta, 0), top)
        self.player.set_time(int(t * 1000))
        self.seek.set(t)
        self.time_l.configure(text=fmt(t))

    def volume_by(self, delta):
        v = min(max(self.vol.get() + delta, 0.0), 1.0)
        self.vol.set(v)
        self.set_volume(v)
        if v > 0:
            self._premute_volume = None

    def toggle_mute(self):
        v = self.vol.get()
        if v > 0.001:
            self._premute_volume = v
            target = 0.0
        else:
            target = self._premute_volume or 0.7
            self._premute_volume = None
        self.vol.set(target)
        self.set_volume(target)

    def _enable_reorder(self, tree):
        self._drag = None
        self._drop_line = tk.Frame(tree, height=2, bd=0, highlightthickness=0, bg=self.themed(ACCENT))
        self._tk_bg.append((self._drop_line, ACCENT))
        tree.bind("<ButtonPress-1>", self._drag_press, add="+")
        tree.bind("<B1-Motion>", self._drag_motion)
        tree.bind("<ButtonRelease-1>", self._drag_release)

    def _drag_press(self, e):
        tree = e.widget
        row = tree.identify_row(e.y)
        if not row or tree.identify_column(e.x) == "#3":
            self._drag = None
            return
        self._drag = {"row": row, "y0": e.y, "on": False, "target": None}

    def _drop_target(self, tree, y):
        vis = []
        for r in tree.get_children():
            bb = tree.bbox(r)
            if bb:
                vis.append((r, bb))
        if not vis:
            return None
        row = tree.identify_row(y)
        for r, bb in vis:
            if r == row:
                after = y > bb[1] + bb[3] / 2
                return (r, after, bb[1] + (bb[3] if after else 0))
        if y < vis[0][1][1]:
            return (vis[0][0], False, vis[0][1][1])
        r, bb = vis[-1]
        return (r, True, bb[1] + bb[3])

    def _drag_motion(self, e):
        d = self._drag
        if not d:
            return None
        tree = e.widget
        if not d["on"]:
            if abs(e.y - d["y0"]) < 7:
                return None
            d["on"] = True
            tree.configure(cursor="hand2")
        if e.y < 22:
            tree.yview_scroll(-1, "units")
        elif e.y > tree.winfo_height() - 22:
            tree.yview_scroll(1, "units")
        tgt = self._drop_target(tree, e.y)
        d["target"] = tgt
        if tgt:
            self._drop_line.place(x=0, y=max(tgt[2] - 1, 0), relwidth=1, height=2)
            self._drop_line.lift()
        return "break"

    def _drag_release(self, e):
        d, self._drag = self._drag, None
        if not d:
            return None
        e.widget.configure(cursor="")
        self._drop_line.place_forget()
        if not d["on"]:
            return None
        if d["target"]:
            row, after, _ = d["target"]
            self.move_track(int(d["row"]), int(row) + (1 if after else 0))
        return "break"

    def move_selected(self, delta):
        i = self.selected(self.lib_tree)
        if i is None or i not in self.view:
            return
        pos = self.view.index(i) + delta
        if not (0 <= pos < len(self.view)):
            return
        nb = self.view[pos]
        self.move_track(i, nb if delta < 0 else nb + 1)

    def move_track(self, src, p):
        lst = self.current_tracks()
        if self.current_playlist is None or not (0 <= src < len(lst)):
            return None
        p = max(0, min(p, len(lst)))
        if p in (src, src + 1):
            return None
        track = lst.pop(src)
        if src < p:
            p -= 1
        lst.insert(p, track)
        self._sync_queue_after_reorder(lst)
        self.refresh_queue_view()
        self.save_playlists()
        self.refresh_list()
        iid = str(p)
        if self.lib_tree.exists(iid):
            self.lib_tree.selection_set(iid)
            self.lib_tree.see(iid)
        return p

    def _sync_queue_after_reorder(self, lst):
        if self.crossfading or self._crossfade_source or not (0 <= self.qpos < len(self.queue)):
            return
        ids = {id(t) for t in self.queue}
        new_q = [t for t in lst if id(t) in ids]
        if len(new_q) != len(self.queue):
            return
        cur = self.queue[self.qpos]
        for i, t in enumerate(new_q):
            if t is cur:
                self.queue, self.qpos = new_q, i
                return

    def remove_selected(self):
        i = self.selected(self.lib_tree)
        if i is None or self.current_playlist is None:
            return
        del self.playlists[self.current_playlist][i]
        self.save_playlists()
        self.refresh_list()
        self.refresh_playlist_sidebar()

    def selected(self, tree):
        sel = tree.selection()
        return int(sel[0]) if sel else None

    def refresh_list(self):
        name = self.current_playlist
        tracks = self.current_tracks()
        show_explicit = self.settings.get("show_explicit")
        hidden = 0

        q = self.search_var.get().strip().lower()
        self.lib_tree.delete(*self.lib_tree.get_children())
        self.view = []
        for i, t in enumerate(tracks):
            if t.get("explicit") and not show_explicit:
                hidden += 1
                continue
            if q in t["title"].lower():
                self.view.append(i)
                self.insert_song_row(self.lib_tree, str(i), t)

        self.pl_title_l.configure(text=name or "No playlist selected")
        if name is None:
            self.pl_sub_l.configure(text="Create a playlist to get started")
        else:
            n = len(tracks) - hidden
            sub = f"{n} song{'s' if n != 1 else ''}"
            if hidden:
                sub += f" · {hidden} hidden (explicit)"
            self.pl_sub_l.configure(text=sub)
        self.tag_rows()

    def tag_rows(self):
        cur = self.queue[self.qpos]["src"] if 0 <= self.qpos < len(self.queue) else None
        for tree, data in ((self.lib_tree, self.current_tracks()), (self.net_tree, self.results)):
            for iid in tree.get_children():
                tree.item(iid, tags=("playing",) if data[int(iid)]["src"] == cur else ())

    def insert_song_row(self, tree, iid, track):
        d = fmt(track["duration"]) if track.get("duration") else ""
        photo = self.thumb_cache.get(track["src"], self.default_thumb)
        title = ("[E] " if track.get("explicit") else "") + track["title"]
        tree.insert("", "end", iid=iid, image=photo, values=("  " + title, d, "Aa"))
        if track["src"] not in self.thumb_cache:
            self.queue_thumb_fetch(track["src"], track.get("thumb"), tree, iid)

    def on_table_click(self, event):
        tree = event.widget
        if tree.identify_column(event.x) != "#3":
            return
        row = tree.identify_row(event.y)
        if not row:
            return
        if tree is self.lib_tree:
            tracks = self.current_tracks()
            if int(row) not in self.view:
                return
            track_list = [tracks[k] for k in self.view]
            pos = self.view.index(int(row))
        else:
            track_list = self.results
            pos = int(row)
        if pos >= len(track_list):
            return
        target = track_list[pos]
        already_playing = 0 <= self.qpos < len(self.queue) and self.queue[self.qpos]["src"] == target["src"]
        if not already_playing:
            tree.selection_set(row)
            self.play_from(track_list, pos)
        self.open_lyrics_for(target)

    def queue_thumb_fetch(self, src, url, tree, iid):
        if not url:
            return
        self.thumb_targets.setdefault(src, []).append((tree, iid))
        if src in self.thumb_pending:
            return
        self.thumb_pending.add(src)
        threading.Thread(target=self._thumb_worker, args=(src, url), daemon=True).start()

    def _thumb_worker(self, src, url):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                raw = resp.read()
            pil_img, avg_color = process_thumbnail(raw, THUMB_SIZE, self.thumb_mask)
            self.tasks.put(lambda: self._apply_thumb(src, pil_img, avg_color))
        except Exception:
            self.tasks.put(lambda: self._thumb_failed(src))

    def _apply_thumb(self, src, pil_img, avg_color):
        photo = ImageTk.PhotoImage(pil_img)
        self.thumb_cache[src] = photo
        self.thumb_pil_cache[src] = pil_img
        self.thumb_colors[src] = avg_color
        self.thumb_pending.discard(src)
        if 0 <= self.qpos < len(self.queue) and self.queue[self.qpos].get("src") == src:
            self.apply_accent_color(avg_color)
        for tree, iid in self.thumb_targets.pop(src, []):
            if iid is None:
                still_current = 0 <= self.qpos < len(self.queue) and self.queue[self.qpos]["src"] == src
                if still_current:
                    tree.configure(image=photo)
                    tree.image = photo
                    self.update_player_bar_art()
            elif tree.exists(iid):
                tree.item(iid, image=photo)

    def _thumb_failed(self, src):
        self.thumb_pending.discard(src)
        self.thumb_targets.pop(src, None)
        if 0 <= self.qpos < len(self.queue) and self.queue[self.qpos].get("src") == src:
            self.apply_accent_color(None)

    def search_online(self):
        q = self.online_entry.get().strip()
        if not q:
            return
        self.show_page("search")
        self.status(f"Searching for “{q}”...")
        threading.Thread(target=self._search_worker, args=(q,), daemon=True).start()

    def _search_worker(self, q):
        opts = {"quiet": True, "no_warnings": True, "extract_flat": True, "skip_download": True}
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(f"ytsearch20:{q}", download=False)
            results = []
            for e in info.get("entries") or []:
                if e:
                    results.append(track_from_entry(e))
            self.tasks.put(lambda: self.show_results(results))
        except Exception as ex:
            msg = f"Search failed: {ex}"
            self.tasks.put(lambda: self.status(msg[:120]))

    def show_results(self, results):
        self.last_search_results = results
        self.results = results if self.settings.get("show_explicit") else \
            [r for r in results if not r.get("explicit")]
        hidden = len(results) - len(self.results)
        self.net_tree.delete(*self.net_tree.get_children())
        for i, r in enumerate(self.results):
            self.insert_song_row(self.net_tree, str(i), r)
        if self.results:
            msg = f"{len(self.results)} results"
            if hidden:
                msg += f" · {hidden} hidden (explicit)"
        else:
            msg = "No results found" if not hidden else f"{hidden} results hidden (explicit)"
        self.status(msg)
        self.tag_rows()

    def on_double(self, event, tree, source):
        row = tree.identify_row(event.y)
        if row:
            tree.selection_set(row)
            self.play_selected(source)

    def play_selected(self, source):
        self.focus_set()
        if source == "playlist":
            i = self.selected(self.lib_tree)
            if i is not None:
                tracks = self.current_tracks()
                self.play_from([tracks[k] for k in self.view], self.view.index(i))
        else:
            i = self.selected(self.net_tree)
            if i is not None:
                self.play_from(self.results, i)

    def play_from(self, tracks, pos):
        self.queue = list(tracks)
        self.qpos = pos
        self.play_current()

    def play_current(self, start=0.0, keep_paused=False):
        t = self.queue[self.qpos]
        self.token += 1
        self.active = False
        self.loading = True
        self._cancel_fade()
        self._cancel_crossfade()
        self._crossfade_source = None
        self.player.stop()
        self.now_label.configure(text=t["title"])
        self.update_heart()
        self.status(f"Loading stream ({QUALITY[self.quality_key()]['label']})...")
        self.play_btn.configure(text="…")
        photo = self.thumb_cache.get(t["src"], self.default_thumb)
        self.now_thumb.configure(image=photo)
        self.now_thumb.image = photo
        if t["src"] in self.thumb_colors:
            self.apply_accent_color(self.thumb_colors[t["src"]])
            self.update_player_bar_art()
        else:
            self.queue_thumb_fetch(t["src"], t.get("thumb"), self.now_thumb, None)
        if start <= 0:
            self.begin_listen(t)
            self.seek.set(0)
            self.time_l.configure(text="0:00")
        self.set_length(t.get("duration") or 0)
        self.tag_rows()
        self.refresh_queue_view()
        threading.Thread(
            target=self._resolve_worker,
            args=(t, self.token, start, keep_paused, self.quality_key()),
            daemon=True,
        ).start()

    def _resolve_worker(self, track, token, start, keep_paused, quality):
        opts = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "format": QUALITY[quality]["format"],
        }
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(track["src"], download=False)
            stream = info.get("url")
            if not stream and info.get("requested_formats"):
                stream = info["requested_formats"][0]["url"]
            label, lossless = describe_stream(info)
            self.tasks.put(lambda: self.start_media(stream, token, start, keep_paused, quality, label, lossless))
        except Exception as ex:
            msg = f"Couldn't load stream: {ex}"
            self.tasks.put(lambda: self.load_failed(token, msg))

    def load_failed(self, token, msg):
        if token != self.token:
            return
        self.loading = False
        self.status(msg[:120])
        self.play_btn.configure(text="▶")

    def start_media(self, src, token, start, keep_paused, quality, label, lossless):
        if token != self.token:
            return
        options = [f":start-time={start:.2f}"] if start > 1 else []
        self.player.set_media(self.instance.media_new(src, *options))
        self.player.play()
        target_vol = 0 if keep_paused else int(self.vol.get() * 100)
        self.player.audio_set_volume(target_vol)
        for delay in (120, 300, 600, 1000):
            self.after(delay, lambda tok=token, v=target_vol: self._reapply_startup_volume(tok, v))
        self.loading = False
        self.active = True
        self.started = time.time()
        self.stream_label = label

        note = ""
        if quality == "lossless" and not lossless:
            note = "No lossless stream is available for this song, so the best available stream is used."
        self.update_stream_info(note)

        if keep_paused:
            self.paused = True
            self.play_btn.configure(text="▶")
            self.status("Paused")
            self.after(700, lambda: token == self.token and self.player.set_pause(1))
        else:
            self.paused = False
            self.play_btn.configure(text="⏸")
            self.status(self.now_status())

    def _reapply_startup_volume(self, token, target_vol):
        if token != self.token:
            return
        if not self.paused:
            self.player.audio_set_volume(target_vol)

    def toggle_play(self):
        if self.loading:
            return
        if self.crossfading:
            self._cancel_crossfade()
        if not self.queue:
            if self.view:
                tracks = self.current_tracks()
                self.play_from([tracks[i] for i in self.view], 0)
            return
        if not self.active:
            self.play_current()
            return

        if self.paused:
            self.paused = False
            self.player.set_pause(0)
            self.play_btn.configure(text="⏸")
            self.status(self.now_status())
            self.fade_to(int(self.vol.get() * 100))
        else:
            self.paused = True
            self.play_btn.configure(text="▶")
            self.status("Paused")
            self.fade_to(0, on_done=lambda: self.player.set_pause(1))

    def fade_to(self, target_volume, on_done=None, step=0):
        self._cancel_fade()
        start_volume = self.player.audio_get_volume()
        if start_volume < 0:
            start_volume = target_volume

        def step_fade(i):
            t = i / FADE_STEPS
            eased = 1 - (1 - t) ** 3
            vol = round(start_volume + (target_volume - start_volume) * eased)
            self.player.audio_set_volume(max(0, min(100, vol)))
            if i < FADE_STEPS:
                self.fade_job = self.after(FADE_MS // FADE_STEPS, lambda: step_fade(i + 1))
            else:
                self.fade_job = None
                if on_done:
                    on_done()

        step_fade(0)

    def _cancel_fade(self):
        if self.fade_job is not None:
            self.after_cancel(self.fade_job)
            self.fade_job = None

    def start_crossfade(self, duration):
        if not self.queue or len(self.queue) < 2:
            return
        if self.shuffle:
            candidates = [i for i in range(len(self.queue)) if i != self.qpos]
            idx = random.choice(candidates) if candidates else None
        else:
            idx = (self.qpos + 1) % len(self.queue)
        if idx is None:
            return
        next_track = self.queue[idx]
        self.crossfading = True
        threading.Thread(
            target=self._crossfade_resolve_worker,
            args=(idx, next_track, duration, self.token, self.quality_key()),
            daemon=True,
        ).start()

    def _crossfade_resolve_worker(self, idx, track, duration, token, quality):
        opts = {"quiet": True, "no_warnings": True, "noplaylist": True, "format": QUALITY[quality]["format"]}
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(track["src"], download=False)
            stream = info.get("url")
            if not stream and info.get("requested_formats"):
                stream = info["requested_formats"][0]["url"]
            if not stream:
                raise RuntimeError("no stream url")
            self.tasks.put(lambda: self._crossfade_begin(idx, track, stream, duration, token))
        except Exception:
            self.tasks.put(self._cancel_crossfade)

    def _crossfade_begin(self, idx, track, stream, duration, token):
        if token != self.token or not self.crossfading:
            return
        self.player2.set_media(self.instance.media_new(stream))
        self.player2.audio_set_volume(0)
        self.player2.play()
        self._crossfade_next_idx = idx
        self._crossfade_next_track = track
        self._crossfade_target_vol = int(self.vol.get() * 100)
        self._crossfade_duration_ms = max(duration, 1) * 1000
        self._crossfade_step(0)

    def _crossfade_step(self, i):
        if not self.crossfading:
            return
        t = i / CROSSFADE_STEPS
        eased = 1 - (1 - t) ** 3
        self.player.audio_set_volume(max(0, int(self._crossfade_target_vol * (1 - eased))))
        self.player2.audio_set_volume(min(100, int(self._crossfade_target_vol * eased)))
        if i < CROSSFADE_STEPS:
            self._crossfade_job = self.after(
                self._crossfade_duration_ms // CROSSFADE_STEPS, lambda: self._crossfade_step(i + 1)
            )
        else:
            self._crossfade_job = None
            self._crossfade_finish()

    def _crossfade_finish(self):
        outgoing = self.player
        outgoing.stop()
        self.player, self.player2 = self.player2, outgoing
        t = self._crossfade_next_track
        self.qpos = self._crossfade_next_idx
        self.token += 1
        self.crossfading = False
        self._crossfade_source = None

        self.now_label.configure(text=t["title"])
        self.update_heart()
        photo = self.thumb_cache.get(t["src"], self.default_thumb)
        self.now_thumb.configure(image=photo)
        self.now_thumb.image = photo
        if t["src"] in self.thumb_colors:
            self.apply_accent_color(self.thumb_colors[t["src"]])
            self.update_player_bar_art()
        else:
            self.queue_thumb_fetch(t["src"], t.get("thumb"), self.now_thumb, None)
        self.set_length(t.get("duration") or 0)
        self.started = time.time()
        self.active = True
        self.loading = False
        self.paused = False
        self.play_btn.configure(text="⏸")
        self.status(self.now_status())
        self.begin_listen(t)
        self.tag_rows()
        self.refresh_queue_view()

    def _cancel_crossfade(self):
        if self._crossfade_job is not None:
            self.after_cancel(self._crossfade_job)
            self._crossfade_job = None
        if self.crossfading:
            try:
                self.player2.stop()
            except Exception:
                pass
        self.crossfading = False

    def next_track(self):
        if not self.queue:
            return
        if self.shuffle and len(self.queue) > 1:
            self.qpos = random.choice([i for i in range(len(self.queue)) if i != self.qpos])
        else:
            self.qpos = (self.qpos + 1) % len(self.queue)
        self.play_current()

    def prev_track(self):
        if not self.queue:
            return
        if self.active and self.player.get_time() > 3000:
            self.player.set_time(0)
            return
        self.qpos = (self.qpos - 1) % len(self.queue)
        self.play_current()

    def toggle_shuffle(self):
        self.shuffle = not self.shuffle
        self.shuffle_btn.configure(text_color=self.themed(ACCENT) if self.shuffle else self.themed(MUTED))

    def toggle_repeat(self):
        self.repeat = not self.repeat
        self.repeat_btn.configure(text_color=self.themed(ACCENT) if self.repeat else self.themed(MUTED))

    def set_volume(self, v):
        self._cancel_fade()
        self.player.audio_set_volume(int(float(v) * 100))

    def set_length(self, s):
        self.length = s
        self.seek.configure(to=max(s, 1))
        self.total_l.configure(text=fmt(s))

    def on_seek_release(self, _):
        self.seeking = False
        if self.active:
            self.player.set_time(int(self.seek.get() * 1000))

    def tick(self):
        while True:
            try:
                task = self.tasks.get_nowait()
            except queue.Empty:
                break
            try:
                task()
            except Exception:
                pass

        now = time.time()
        dt = min(now - self.last_tick, 1.0)
        self.last_tick = now

        if self.active:
            state = self.player.get_state()
            if state == vlc.State.Playing and not self.paused:
                self.record_listen(dt)
            ln = self.player.get_length() / 1000
            if ln > 0 and abs(ln - self.length) > 1:
                self.set_length(ln)
            pos = max(self.player.get_time(), 0) / 1000
            if not self.seeking:
                self.seek.set(min(pos, max(self.length, 1)))
                self.time_l.configure(text=fmt(pos))

            if time.time() - self.started > 1.5 and not self.paused and not self.crossfading:
                if state == vlc.State.Ended:
                    self.active = False
                    if self.sleep_after_song:
                        self.set_sleep(None)
                        self.play_btn.configure(text="▶")
                        self.status("Sleep timer: stopped after the song")
                    elif self.repeat:
                        self.play_current()
                    else:
                        self.next_track()
                elif state == vlc.State.Error:
                    self.active = False
                    self.play_btn.configure(text="▶")
                    self.status("Playback error - try another track")
                else:
                    cf = self.crossfade_seconds()
                    if (cf and not self.repeat and not self.sleep_after_song and self.length > cf + 1
                            and len(self.queue) > 1
                            and self.length - pos <= cf
                            and self._crossfade_source != self.queue[self.qpos]["src"]):
                        self._crossfade_source = self.queue[self.qpos]["src"]
                        self.start_crossfade(cf)

        if self.sleep_at is not None and now >= self.sleep_at and not self.loading:
            self.set_sleep(None)
            if self.active and not self.paused:
                self.toggle_play()
                self.status("Sleep timer: paused")

        if self.stats_dirty and now - self.last_save > 10:
            self.last_save = now
            self.save_stats()

        if (self.lyrics_track is not None and self.lyrics_overlay.winfo_ismapped()
                and 0 <= self.qpos < len(self.queue) and self.queue[self.qpos]["src"] == self.lyrics_track["src"]):
            self.update_lyrics_highlight()

        self.update_mini()
        self.after(300, self.tick)

    def on_close(self):
        self.stop_media_keys()
        self.save_stats()
        try:
            self.player.stop()
            self.player.release()
        except Exception:
            pass
        try:
            self.player2.stop()
            self.player2.release()
        except Exception:
            pass
        self.destroy()


if __name__ == "__main__":
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("CrystalWave.MusicApp")
        except Exception:
            pass
    MusicApp().mainloop()