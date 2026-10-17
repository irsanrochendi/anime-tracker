"""Download & cache poster ke folder posters/ di sebelah database."""
import hashlib
import os
import threading
from concurrent.futures import ThreadPoolExecutor

import requests
from PIL import Image, ImageDraw, ImageFont, ImageOps

from . import config

_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="poster")
_locks = {}
_locks_guard = threading.Lock()


def cache_path(url):
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:20]
    return os.path.join(config.POSTER_DIR, f"{digest}.jpg")


def _lock_for(path):
    with _locks_guard:
        return _locks.setdefault(path, threading.Lock())


def ensure_local(url):
    """Blocking: download (sekali) lalu simpan sebagai JPEG kecil. Return path atau None."""
    if not url:
        return None
    path = cache_path(url)
    with _lock_for(path):
        if os.path.exists(path):
            return path
        try:
            res = requests.get(url, timeout=15, headers={"User-Agent": config.UA})
            if res.status_code != 200:
                return None
            os.makedirs(config.POSTER_DIR, exist_ok=True)
            from io import BytesIO
            img = Image.open(BytesIO(res.content)).convert("RGB")
            img.thumbnail((342, 513))
            tmp = path + ".tmp"
            img.save(tmp, "JPEG", quality=88)
            os.replace(tmp, path)
            return path
        except (requests.RequestException, OSError, ValueError):
            return None


def load_cover(path, size):
    """PIL image dipotong (cover-fit) ke ukuran size."""
    with Image.open(path) as img:
        return ImageOps.fit(img.convert("RGB"), size, Image.LANCZOS)


def placeholder(title, size, colors=("#312E81", "#E11D48")):
    """Poster pengganti: gradien + inisial judul."""
    w, h = size
    top, bottom = Image.new("RGB", (1, 1), colors[0]).getpixel((0, 0)), Image.new("RGB", (1, 1), colors[1]).getpixel((0, 0))
    img = Image.new("RGB", size)
    draw = ImageDraw.Draw(img)
    for y in range(h):
        t = y / max(h - 1, 1)
        draw.line([(0, y), (w, y)], fill=tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)))
    initials = "".join(word[0] for word in (title or "?").split()[:2] if word[:1].isalnum()).upper() or "?"
    try:
        font = ImageFont.truetype("segoeuib.ttf", int(h * 0.28))
    except OSError:
        font = ImageFont.load_default()
    box = draw.textbbox((0, 0), initials, font=font)
    draw.text(((w - (box[2] - box[0])) / 2 - box[0], (h - (box[3] - box[1])) / 2 - box[1]),
              initials, font=font, fill="#F8FAFC")
    return img


def fetch_async(url, callback):
    """Download di background; callback(path_or_None) dipanggil dari thread worker."""
    _executor.submit(lambda: callback(ensure_local(url)))
