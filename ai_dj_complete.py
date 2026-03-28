"""
╔══════════════════════════════════════════════════════════════════════════╗
║        AI DJ STUDIO  —  Complete Single-File App                        ║
║   Full audio engine · Neon-noir GUI · Kid-friendly · AI Auto-Mix        ║
╚══════════════════════════════════════════════════════════════════════════╝

Requirements:
  Python 3.10+
  pip install yt-dlp librosa soundfile pydub numpy Pillow

  Also install FFmpeg and add it to your PATH.

NOTE: Use only with content you have rights to download/mix.
      Respect YouTube's terms of service.
"""

# ═══════════════════════════════════════════════════════════════════════
#  IMPORTS
# ═══════════════════════════════════════════════════════════════════════
import os, io, sys, json, time, queue, re, math, shutil, threading, random
from dataclasses import dataclass, asdict, field
from typing import List, Optional, Dict, Tuple
from pathlib import Path
import urllib.parse, urllib.request

import numpy as np

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# ── Audio libs (graceful degradation if missing) ──────────────────────
try:
    import librosa
    import soundfile as sf
    from pydub import AudioSegment, effects as pydub_effects
    import yt_dlp
    _HAS_AUDIO = True
except ImportError as _e:
    _HAS_AUDIO = False
    _AUDIO_MISSING = str(_e)

# ── PIL ────────────────────────────────────────────────────────────────
try:
    from PIL import Image, ImageTk, ImageDraw, ImageFont
    _HAS_PIL = True
except ImportError:
    _HAS_PIL = False

# ── Optional playback ─────────────────────────────────────────────────
try:
    import sounddevice as sd
    _HAS_SD = True
except ImportError:
    _HAS_SD = False


# ═══════════════════════════════════════════════════════════════════════
#  DIRECTORIES — Windows-aware paths
#  On Windows: user data goes to %LOCALAPPDATA%\AI DJ Studio#  On dev/Mac/Linux: stays next to the script (original behaviour)
# ═══════════════════════════════════════════════════════════════════════
def _get_app_dir() -> str:
    """Return the code/executable directory (for bundled assets)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)   # PyInstaller EXE dir
    return os.path.abspath(os.path.dirname(__file__))

def _get_data_dir() -> str:
    """Return writable user-data directory."""
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA",
               os.path.join(os.path.expanduser("~"), "AppData", "Local"))
        return os.path.join(base, "AI DJ Studio")
    return _get_app_dir()   # Mac/Linux: keep alongside script

def _get_asset(name: str) -> str:
    """Locate a bundled asset (works both in dev and PyInstaller EXE)."""
    # PyInstaller unpacks assets to sys._MEIPASS
    if hasattr(sys, "_MEIPASS"):
        path = os.path.join(sys._MEIPASS, "assets", name)
        if os.path.exists(path):
            return path
    # Development: look in assets/ next to this file
    path = os.path.join(_get_app_dir(), "assets", name)
    if os.path.exists(path):
        return path
    return name   # fallback

APP_DIR  = _get_app_dir()
DATA_DIR = _get_data_dir()
DL_DIR   = os.path.join(DATA_DIR, "downloads")
MIX_DIR  = os.path.join(DATA_DIR, "ai_mixed_music")
GEN_DIR  = os.path.join(DATA_DIR, "ai_generated_music")
TMP_DIR  = os.path.join(DATA_DIR, ".tmp")
IMG_DIR  = os.path.join(DATA_DIR, ".dj_images")
IDX_PATH = os.path.join(DATA_DIR, "library.json")
PLAYLISTS_DIR = os.path.join(DATA_DIR, "playlists")

for _d in (DL_DIR, MIX_DIR, GEN_DIR, TMP_DIR, IMG_DIR, PLAYLISTS_DIR):
    os.makedirs(_d, exist_ok=True)


# ═══════════════════════════════════════════════════════════════════════
#  COLOUR PALETTE  — Neon Noir
# ═══════════════════════════════════════════════════════════════════════
P = {
    "void":    "#050508",
    "deep":    "#0A0A14",
    "panel":   "#0F0F1E",
    "card":    "#141428",
    "card2":   "#1A1A32",
    "border":  "#252545",
    "border2": "#303060",
    "pink":    "#FF2D78",
    "cyan":    "#00E5FF",
    "lime":    "#AAFF00",
    "gold":    "#FFD600",
    "violet":  "#BF5FFF",
    "orange":  "#FF6B2B",
    "text":    "#F0F0FF",
    "muted":   "#7070A0",
    "dim":     "#404068",
    "ok":      "#00E676",
    "warn":    "#FFD740",
    "err":     "#FF5252",
}


# ═══════════════════════════════════════════════════════════════════════
#  DJ STYLES DATABASE
# ═══════════════════════════════════════════════════════════════════════
DJ_STYLES: List[Dict] = [
    {
        "name": "DJ Funk Master Flex",
        "genre": "Hip-Hop / Freestyle",
        "era": "1990s–Present",
        "description": "Rapid-fire drops, hype vocals, hard cuts with no mercy. "
                       "Battle-style scratching, heavy bass emphasis.",
        "params": {
            "crossfade_ms": 1500, "bass_boost_db": 4,  "echo_drops": True,
            "scratch_sim": True,  "tempo_push": 0.03,   "fade_style": "hard_cut",
            "intro_bars": 8,      "energy": "explosive"
        },
        "image_query": "Funk Master Flex DJ",
        "emoji": "🔥", "color": "#FF2D78"
    },
    {
        "name": "DJ Tiësto",
        "genre": "Trance / EDM",
        "era": "2000s–Present",
        "description": "Long builds, euphoric breakdowns, 8-bar smooth blends. "
                       "High-energy festival drops with emotional arcs.",
        "params": {
            "crossfade_ms": 16000, "bass_boost_db": 2, "echo_drops": True,
            "scratch_sim": False,  "tempo_push": 0.01,  "fade_style": "smooth",
            "intro_bars": 32,      "energy": "euphoric"
        },
        "image_query": "Tiesto DJ",
        "emoji": "🎆", "color": "#00E5FF"
    },
    {
        "name": "DJ Jazzy Jeff",
        "genre": "Hip-Hop / Jazz",
        "era": "1980s–Present",
        "description": "Smooth scratching, tasteful transitions, jazz-influenced "
                       "rhythms, crate-digger soul. Clean technical mixing.",
        "params": {
            "crossfade_ms": 6000, "bass_boost_db": 1,  "echo_drops": False,
            "scratch_sim": True,  "tempo_push": 0.0,    "fade_style": "smooth",
            "intro_bars": 16,     "energy": "groovy"
        },
        "image_query": "DJ Jazzy Jeff",
        "emoji": "🎷", "color": "#FFD600"
    },
    {
        "name": "Grandmaster Flash",
        "genre": "Hip-Hop / Breakbeat",
        "era": "1970s–Present",
        "description": "Pioneer of turntablism. Quick-mix theory, punch phrasing, "
                       "backspin technique. Raw, rhythmic, foundational.",
        "params": {
            "crossfade_ms": 2000, "bass_boost_db": 3,  "echo_drops": False,
            "scratch_sim": True,  "tempo_push": 0.0,    "fade_style": "punch",
            "intro_bars": 4,      "energy": "raw"
        },
        "image_query": "Grandmaster Flash DJ",
        "emoji": "⚡", "color": "#AAFF00"
    },
    {
        "name": "DJ Khaled",
        "genre": "Hip-Hop / Pop",
        "era": "2000s–Present",
        "description": "Anthem drops, crowd hype, massive outro buildups. "
                       "Celebratory energy, layered vocals, radio-ready polish.",
        "params": {
            "crossfade_ms": 4000, "bass_boost_db": 3,  "echo_drops": True,
            "scratch_sim": False, "tempo_push": 0.0,    "fade_style": "anthem",
            "intro_bars": 8,      "energy": "celebratory"
        },
        "image_query": "DJ Khaled",
        "emoji": "🏆", "color": "#FFD600"
    },
    {
        "name": "Avicii",
        "genre": "Progressive House / EDM",
        "era": "2010s",
        "description": "Folk-infused melodies, progressive buildups, emotional "
                       "drops. Storytelling through music. Pure feeling.",
        "params": {
            "crossfade_ms": 12000, "bass_boost_db": 2, "echo_drops": True,
            "scratch_sim": False,  "tempo_push": 0.0,   "fade_style": "smooth",
            "intro_bars": 32,      "energy": "emotional"
        },
        "image_query": "Avicii DJ",
        "emoji": "🌅", "color": "#FF6B2B"
    },
    {
        "name": "DJ Premier",
        "genre": "Hip-Hop / Boom Bap",
        "era": "1990s–Present",
        "description": "Boom-bap precision, tight chops, signature record scratches "
                       "between verses. Underground NY sound. No fluff.",
        "params": {
            "crossfade_ms": 2000, "bass_boost_db": 5,  "echo_drops": False,
            "scratch_sim": True,  "tempo_push": 0.0,    "fade_style": "hard_cut",
            "intro_bars": 8,      "energy": "gritty"
        },
        "image_query": "DJ Premier",
        "emoji": "🎯", "color": "#BF5FFF"
    },
    {
        "name": "Calvin Harris",
        "genre": "Dance / House",
        "era": "2010s–Present",
        "description": "Radio-perfect house, summer anthems, clean four-on-the-floor "
                       "kicks, bright synth layers. Maximum dancefloor appeal.",
        "params": {
            "crossfade_ms": 8000, "bass_boost_db": 2,  "echo_drops": True,
            "scratch_sim": False, "tempo_push": 0.02,   "fade_style": "smooth",
            "intro_bars": 16,     "energy": "summer"
        },
        "image_query": "Calvin Harris DJ",
        "emoji": "☀️", "color": "#FFD600"
    },
    {
        "name": "Deadmau5",
        "genre": "Progressive House / Techno",
        "era": "2008–Present",
        "description": "Hypnotic long builds, minimalist loops, trance-like repetition "
                       "that peaks after 6+ minutes. Cerebral and mechanical.",
        "params": {
            "crossfade_ms": 20000, "bass_boost_db": 1, "echo_drops": False,
            "scratch_sim": False,  "tempo_push": 0.0,   "fade_style": "hypnotic",
            "intro_bars": 64,      "energy": "cerebral"
        },
        "image_query": "Deadmau5 DJ",
        "emoji": "🖤", "color": "#BF5FFF"
    },
    {
        "name": "DJ Snake",
        "genre": "Trap / EDM / Global Bass",
        "era": "2013–Present",
        "description": "Trap hi-hats, world music fusion, massive sub bass drops. "
                       "Hard-hitting modern sound with global flavors.",
        "params": {
            "crossfade_ms": 3000, "bass_boost_db": 6,  "echo_drops": True,
            "scratch_sim": False, "tempo_push": 0.0,    "fade_style": "trap_drop",
            "intro_bars": 8,      "energy": "hard"
        },
        "image_query": "DJ Snake",
        "emoji": "🐍", "color": "#00E5FF"
    },
]

# Camelot Wheel
CAMELOT = {
    'C':'8B','C#':'3B','D':'10B','D#':'5B','E':'12B','F':'7B',
    'F#':'2B','G':'9B','G#':'4B','A':'11B','A#':'6B','B':'1B',
}


# ═══════════════════════════════════════════════════════════════════════
#  DATA LAYER — Track + LibraryIndex
# ═══════════════════════════════════════════════════════════════════════
@dataclass
class Track:
    path:  str
    title: str
    kind:  str
    bpm:   Optional[float] = None
    key:   Optional[str]   = None
    plays: int  = 0
    liked: bool = False


class LibraryIndex:
    def __init__(self, path: str):
        self.path  = path
        self.items: List[Track] = []
        self.load()

    def load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.items = [Track(**d) for d in data]
            except Exception:
                self.items = []
        else:
            self.items = []

    def save(self):
        with open(self.path, 'w', encoding='utf-8') as f:
            json.dump([asdict(x) for x in self.items], f, indent=2)

    def add_or_update(self, t: Track):
        for i, existing in enumerate(self.items):
            if os.path.abspath(existing.path) == os.path.abspath(t.path):
                self.items[i] = t
                self.save()
                return
        self.items.append(t)
        self.save()

    def list_sorted(self, mode: str = "alpha") -> List[Track]:
        items = [x for x in self.items if os.path.exists(x.path)]
        if mode == "alpha":
            return sorted(items, key=lambda x: os.path.basename(x.path).lower())
        if mode == "kind":
            return sorted(items, key=lambda x: (x.kind, os.path.basename(x.path).lower()))
        if mode == "bpm":
            return sorted(items, key=lambda x: (x.bpm is None, x.bpm))
        return items


LIB = LibraryIndex(IDX_PATH)


# ═══════════════════════════════════════════════════════════════════════
#  AUDIO ENGINE  (all functions guarded by _HAS_AUDIO)
# ═══════════════════════════════════════════════════════════════════════
def have_ffmpeg() -> bool:
    return shutil.which("ffmpeg") is not None


def safe_load(path: str, sr: int = 44100) -> Tuple[np.ndarray, int]:
    y, _ = librosa.load(path, sr=sr, mono=True)
    if not np.isfinite(y).all():
        y = np.nan_to_num(y, nan=0.0, posinf=0.0, neginf=0.0)
    return y.astype(np.float32), sr


def detect_bpm_key(y: np.ndarray, sr: int) -> Tuple[float, str]:
    tempo_raw, _ = librosa.beat.beat_track(y=y, sr=sr)
    tempo = float(np.atleast_1d(tempo_raw)[0])
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
    key_index = int(np.argmax(chroma.mean(axis=1)))
    KEYS = ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B']
    return tempo, KEYS[key_index]


def camelot(key: str) -> str:
    return CAMELOT.get(key, '?')


def time_stretch_to_bpm(y: np.ndarray, sr: int,
                         bpm_src: float, bpm_tgt: float) -> np.ndarray:
    if bpm_src <= 0 or bpm_tgt <= 0:
        return y
    factor = max(0.5, min(2.0, bpm_tgt / bpm_src))
    return librosa.effects.time_stretch(y, rate=factor)


def np_to_segment(y: np.ndarray, sr: int) -> "AudioSegment":
    tmp = os.path.join(TMP_DIR, f"_tmp_{time.time_ns()}.wav")
    sf.write(tmp, y, sr)
    seg = AudioSegment.from_file(tmp)
    try:
        os.remove(tmp)
    except Exception:
        pass
    return seg


def _infer_kind(path: str) -> str:
    ap = os.path.abspath(path)
    try:
        Path(ap).relative_to(MIX_DIR)
        return 'mixed'
    except ValueError:
        pass
    try:
        Path(ap).relative_to(GEN_DIR)
        return 'generated'
    except ValueError:
        pass
    return 'downloaded'


def analyze_file(path: str) -> Tuple[float, str]:
    y, sr = safe_load(path)
    bpm, key = detect_bpm_key(y, sr)
    LIB.add_or_update(Track(
        path=path, title=os.path.basename(path),
        kind=_infer_kind(path), bpm=bpm, key=key
    ))
    return bpm, key


def yt_search(query: str, max_results: int = 20) -> List[Tuple[str, str, str]]:
    """Return [(title, url, duration_str), ...] — no API key needed."""
    if not query.strip():
        return []
    ydl_opts = {
        'quiet': True, 'skip_download': True,
        'extract_flat': True, 'noplaylist': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(f"ytsearch{max_results}:{query}", download=False)
    results = []
    for e in (info.get('entries') or [])[:max_results]:
        if not e:
            continue
        title  = e.get('title') or 'Untitled'
        vid_id = e.get('id') or e.get('url', '')
        url    = f"https://www.youtube.com/watch?v={vid_id}" \
                 if vid_id and not vid_id.startswith('http') else vid_id
        dur    = e.get('duration') or 0
        dur_s  = f"{int(dur)//60}:{int(dur)%60:02d}" if dur else "?:??"
        results.append((title, url, dur_s))
    return results


def download_audio(url: str, out_dir: str = DL_DIR,
                   progress_cb=None) -> Optional[str]:
    if not have_ffmpeg():
        raise RuntimeError("FFmpeg not found on PATH. Please install FFmpeg.")
    os.makedirs(out_dir, exist_ok=True)
    result_paths: List[str] = []

    def _hook(d):
        if d.get('status') == 'finished':
            result_paths.append(d['filename'])
        if progress_cb and d.get('status') == 'downloading':
            progress_cb(d.get('_percent_str', '').strip())

    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': os.path.join(out_dir, '%(title).180B.%(ext)s'),
        'noplaylist': True, 'quiet': True,
        'progress_hooks': [_hook],
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    if result_paths:
        base = os.path.splitext(result_paths[0])[0]
        mp3  = base + ".mp3"
        if os.path.exists(mp3):
            return mp3
        if os.path.exists(result_paths[0]):
            return result_paths[0]

    mp3s = [os.path.join(out_dir, f) for f in os.listdir(out_dir)
            if f.endswith('.mp3')]
    if not mp3s:
        raise RuntimeError("Download finished but no MP3 found.")
    return max(mp3s, key=os.path.getmtime)


def mix_tracks(file_a: str, file_b: str,
               mix_name: Optional[str] = None,
               crossfade_ms: int = 6000,
               dj_params: Optional[Dict] = None) -> str:
    if dj_params is None:
        dj_params = {}

    if mix_name is None:
        a_stem = os.path.splitext(os.path.basename(file_a))[0][:40]
        b_stem = os.path.splitext(os.path.basename(file_b))[0][:40]
        mix_name = f"{a_stem}__X__{b_stem}.mp3"
    mix_name = os.path.basename(mix_name)
    out_path = os.path.join(MIX_DIR, mix_name)

    y1, sr = safe_load(file_a)
    y2, _  = safe_load(file_b)
    bpm1, key1 = detect_bpm_key(y1, sr)
    bpm2, _    = detect_bpm_key(y2, sr)
    y2s        = time_stretch_to_bpm(y2, sr, bpm2, bpm1)

    seg1 = np_to_segment(y1,  sr)
    seg2 = np_to_segment(y2s, sr)

    xfade = min(crossfade_ms, len(seg1) // 2, len(seg2) // 2)
    xfade = max(xfade, 500)
    fade_style = dj_params.get("fade_style", "smooth")

    if fade_style == "hard_cut":
        mixed = seg1 + seg2
    elif fade_style == "punch":
        mixed = seg1[:-200] + seg1[-200:].append(seg2[:200], crossfade=200) + seg2[200:]
    else:
        intro   = seg1[:-xfade]
        overlap = seg1[-xfade:].overlay(seg2[:xfade].fade_in(xfade), position=0)
        outro   = seg2[xfade:].fade_out(min(2000, len(seg2[xfade:]) // 2))
        mixed   = intro + overlap + outro

    try:
        mixed = pydub_effects.normalize(mixed)
    except Exception:
        pass

    mixed.export(out_path, format='mp3', bitrate='192k')
    LIB.add_or_update(Track(
        path=out_path, title=os.path.basename(out_path),
        kind='mixed', bpm=float(bpm1), key=str(key1)
    ))
    return out_path


def auto_mix_playlist(tracks: List[str], dj_style: Dict,
                      out_name: str = "auto_mix.mp3",
                      progress_cb=None) -> str:
    if len(tracks) < 2:
        raise ValueError("Need at least 2 tracks to auto-mix.")

    params = dj_style.get("params", {})
    xfade  = params.get("crossfade_ms", 6000)

    analyzed = []
    for i, t in enumerate(tracks):
        if progress_cb:
            progress_cb(f"Analysing {i+1}/{len(tracks)}: {os.path.basename(t)}")
        try:
            bpm, key = analyze_file(t)
            analyzed.append((bpm, t))
        except Exception:
            analyzed.append((120.0, t))

    analyzed.sort(key=lambda x: x[0])
    ordered = [t for _, t in analyzed]

    current = ordered[0]
    for i, nxt in enumerate(ordered[1:], 1):
        if progress_cb:
            progress_cb(f"Mixing track {i}/{len(ordered)-1}…")
        tmp_name = f"_autostep_{i}_{os.path.splitext(os.path.basename(current))[0][:25]}.mp3"
        current  = mix_tracks(current, nxt,
                               mix_name=tmp_name,
                               crossfade_ms=xfade,
                               dj_params=params)

    final = os.path.join(MIX_DIR, os.path.basename(out_name))
    shutil.move(current, final)
    LIB.add_or_update(Track(path=final, title=os.path.basename(final), kind='mixed'))
    return final


# ═══════════════════════════════════════════════════════════════════════
#  DJ IMAGE FETCHER
# ═══════════════════════════════════════════════════════════════════════
def _fetch_dj_image(query: str, save_path: str,
                    size: Tuple[int, int] = (80, 80)) -> Optional[str]:
    if not _HAS_PIL:
        return None
    if os.path.exists(save_path):
        return save_path
    try:
        q   = urllib.parse.quote_plus(query + " photo")
        url = f"https://duckduckgo.com/?q={q}&iax=images&ia=images&iaf=size%3ASmall"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as r:
            body = r.read().decode('utf-8', errors='replace')
        imgs = re.findall(r'"thumbnail":"(https://[^"]+)"', body)
        if not imgs:
            return _make_placeholder(save_path, query, size)
        with urllib.request.urlopen(imgs[0], timeout=5) as ir:
            img_data = ir.read()
        img  = Image.open(io.BytesIO(img_data)).convert("RGBA")
        img  = img.resize(size, Image.LANCZOS)
        mask = Image.new("L", size, 0)
        ImageDraw.Draw(mask).ellipse((0, 0) + size, fill=255)
        img.putalpha(mask)
        img.save(save_path, format="PNG")
        return save_path
    except Exception:
        return _make_placeholder(save_path, query, size)


def _make_placeholder(save_path: str, name: str,
                       size: Tuple[int, int] = (80, 80)) -> Optional[str]:
    if not _HAS_PIL:
        return None
    dj_color = next(
        (dj["color"] for dj in DJ_STYLES if dj["name"] == name),
        ["#FF6B6B","#4ECDC4","#45B7D1","#96CEB4","#FFEAA7",
         "#DDA0DD","#98D8C8","#F7DC6F","#BB8FCE","#85C1E9"][hash(name) % 10]
    )
    img  = Image.new("RGBA", size, dj_color)
    draw = ImageDraw.Draw(img)
    initials = "".join(w[0].upper() for w in name.split()[:2] if w)
    try:
        fnt = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            size[0] // 3)
    except Exception:
        fnt = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), initials, font=fnt)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((size[0] - tw) // 2, (size[1] - th) // 2),
              initials, fill="white", font=fnt)
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).ellipse((0, 0) + size, fill=255)
    img.putalpha(mask)
    img.save(save_path, format="PNG")
    return save_path


# ═══════════════════════════════════════════════════════════════════════
#  WORKER — threaded job queue with per-job callbacks
# ═══════════════════════════════════════════════════════════════════════
class Worker:
    def __init__(self):
        self.q        = queue.Queue()
        self._active  = 0

    @property
    def busy(self) -> bool:
        return self._active > 0

    def run(self, fn, *args, callback=None, **kwargs):
        self._active += 1
        def _wrapper():
            try:
                res = fn(*args, **kwargs)
                self.q.put(("ok", res, callback))
            except Exception as e:
                self.q.put(("err", e, None))
            finally:
                self._active -= 1
        threading.Thread(target=_wrapper, daemon=True).start()


# ═══════════════════════════════════════════════════════════════════════
#  GUI UTILITIES — colour helpers, canvas drawing
# ═══════════════════════════════════════════════════════════════════════
def _hex_to_rgb(h: str) -> Tuple[int, int, int]:
    h = h.lstrip('#')
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def _lerp_color(c1: str, c2: str, t: float) -> str:
    r1,g1,b1 = _hex_to_rgb(c1)
    r2,g2,b2 = _hex_to_rgb(c2)
    return (f"#{int(r1+(r2-r1)*t):02X}"
            f"{int(g1+(g2-g1)*t):02X}"
            f"{int(b1+(b2-b1)*t):02X}")


def _draw_rrect(canvas, x1, y1, x2, y2, r=10, **kw):
    """Rounded rectangle on a tk.Canvas."""
    pts = [x1+r,y1, x2-r,y1, x2,y1, x2,y1+r,
           x2,y2-r, x2,y2, x2-r,y2, x1+r,y2,
           x1,y2, x1,y2-r, x1,y1+r, x1,y1, x1+r,y1]
    return canvas.create_polygon(pts, smooth=True, **kw)


# ═══════════════════════════════════════════════════════════════════════
#  ANIMATED VINYL RECORD WIDGET
# ═══════════════════════════════════════════════════════════════════════
class VinylRecord(tk.Canvas):
    def __init__(self, parent, size=160, color=P["pink"], **kw):
        super().__init__(parent, width=size, height=size,
                         bg=P["void"], highlightthickness=0, **kw)
        self.size     = size
        self.cx = self.cy = size // 2
        self.color    = color
        self.angle    = 0
        self.spinning = False
        self._draw()

    def _draw(self):
        self.delete("all")
        cx, cy, s = self.cx, self.cy, self.size
        r = s // 2 - 4

        # Outer vinyl body
        self.create_oval(cx-r, cy-r, cx+r, cy+r,
                         fill="#180808", outline=self.color, width=2)
        # Grooves
        for i in range(7, 1, -1):
            gr  = int(r * 0.88 * i / 7)
            col = _lerp_color("#180808", "#2A1010", i / 7)
            self.create_oval(cx-gr, cy-gr, cx+gr, cy+gr,
                             fill="", outline=col, width=1)
        # Spinning highlight
        if self.spinning:
            a  = math.radians(self.angle)
            hx = cx + int(r * 0.55 * math.cos(a))
            hy = cy + int(r * 0.55 * math.sin(a))
            self.create_oval(hx-6, hy-6, hx+6, hy+6,
                             fill=_lerp_color(self.color, "#FFFFFF", 0.5),
                             outline="")
        # Label circle
        lr = int(r * 0.32)
        self.create_oval(cx-lr, cy-lr, cx+lr, cy+lr,
                         fill=self.color, outline=self.color)
        self.create_oval(cx-int(lr*0.62), cy-int(lr*0.62),
                         cx+int(lr*0.62), cy+int(lr*0.62),
                         fill=_lerp_color(self.color, "#000000", 0.4),
                         outline="")
        # Spindle
        self.create_oval(cx-4, cy-4, cx+4, cy+4,
                         fill=P["void"], outline=P["muted"])
        # Glow when spinning
        if self.spinning:
            self.create_oval(cx-r-3, cy-r-3, cx+r+3, cy+r+3,
                             fill="", outline=_lerp_color(self.color, P["void"], 0.55),
                             width=3)
        # Reflection arc
        arc_r = int(r * 0.72)
        self.create_arc(cx-arc_r, cy-arc_r, cx+arc_r, cy+arc_r,
                        start=200, extent=40,
                        outline=_lerp_color(self.color, "#FFFFFF", 0.55),
                        width=2, style="arc")

    def start_spin(self):
        self.spinning = True
        self._spin()

    def stop_spin(self):
        self.spinning = False
        self._draw()

    def _spin(self):
        if not self.spinning:
            return
        self.angle = (self.angle + 3) % 360
        self._draw()
        self.after(28, self._spin)


# ═══════════════════════════════════════════════════════════════════════
#  ANIMATED EQUALIZER BARS
# ═══════════════════════════════════════════════════════════════════════
class EQBars(tk.Canvas):
    COLORS = [P["cyan"], P["pink"], P["lime"], P["violet"], P["gold"]]

    def __init__(self, parent, width=200, height=40, bars=16, **kw):
        super().__init__(parent, width=width, height=height,
                         bg=P["void"], highlightthickness=0, **kw)
        self.w = width;  self.h = height;  self.bars = bars
        self.active   = False
        self._heights = [random.uniform(0.1, 0.9) for _ in range(bars)]
        self._targets = [random.uniform(0.1, 0.9) for _ in range(bars)]
        self._draw()

    def _draw(self):
        self.delete("all")
        bw  = self.w / (self.bars * 1.6)
        gap = bw * 0.6
        tot = bw + gap
        off = (self.w - tot * self.bars + gap) / 2
        for i, h in enumerate(self._heights):
            x1 = off + i * tot
            x2 = x1 + bw
            bh = max(3, int(h * self.h))
            col = self.COLORS[i % len(self.COLORS)]
            self.create_rectangle(x1, self.h-bh, x2, self.h, fill=col, outline="")
            self.create_rectangle(x1, self.h-bh, x2, self.h-bh+2,
                                  fill=_lerp_color(col,"#FFFFFF",0.65), outline="")

    def start(self):
        self.active = True
        self._animate()

    def stop(self):
        self.active = False
        self._heights = [0.05] * self.bars
        self._draw()

    def _animate(self):
        if not self.active:
            return
        for i in range(self.bars):
            self._heights[i] += (self._targets[i] - self._heights[i]) * 0.28
            if random.random() < 0.14:
                self._targets[i] = random.uniform(0.05, 1.0)
        self._draw()
        self.after(55, self._animate)


# ═══════════════════════════════════════════════════════════════════════
#  NEON BUTTON
# ═══════════════════════════════════════════════════════════════════════
class NeonButton(tk.Canvas):
    def __init__(self, parent, text="Button", color=P["cyan"],
                 command=None, width=160, height=38, font=None, **kw):
        super().__init__(parent, width=width, height=height,
                         bg=P["panel"], highlightthickness=0, **kw)
        self.text    = text
        self.color   = color
        self.command = command
        self.w = width;  self.h = height
        self.font    = font or ("Trebuchet MS", 10, "bold")
        self._state  = "normal"   # normal | hover | press | disabled
        self._draw()
        self.bind("<Enter>",           self._enter)
        self.bind("<Leave>",           self._leave)
        self.bind("<ButtonPress-1>",   self._press)
        self.bind("<ButtonRelease-1>", self._release)

    def _draw(self):
        self.delete("all")
        w, h = self.w, self.h
        s    = self._state
        col  = self.color
        if s == "disabled":
            col = P["dim"]
        elif s == "press":
            col = _lerp_color(col, "#FFFFFF", 0.4)
        elif s == "hover":
            col = _lerp_color(col, "#FFFFFF", 0.18)

        bg = _lerp_color(col, P["void"], 0.88 if s != "press" else 0.72)
        _draw_rrect(self, 2, 2, w-2, h-2, r=7,
                    fill=bg, outline=col,
                    width=2 if s in ("hover","press") else 1)
        if s == "hover":
            _draw_rrect(self, 0, 0, w, h, r=9,
                        fill="", outline=_lerp_color(col, P["void"], 0.5), width=3)
        fg = P["dim"] if s == "disabled" else col
        self.create_text(w//2, h//2, text=self.text, fill=fg,
                         font=self.font, anchor="center")

    def _enter(self, _):
        if self._state != "disabled":
            self._state = "hover";  self._draw()
            self.configure(cursor="hand2")
    def _leave(self, _):
        if self._state != "disabled":
            self._state = "normal"; self._draw()
    def _press(self, _):
        if self._state != "disabled":
            self._state = "press";  self._draw()
    def _release(self, _):
        if self._state != "disabled":
            self._state = "hover";  self._draw()
            if self.command:
                self.command()

    def set_text(self, t: str):
        self.text = t;  self._draw()

    def set_disabled(self, v: bool):
        self._state = "disabled" if v else "normal"
        self._draw()
        self.configure(cursor="" if v else "hand2")


# ═══════════════════════════════════════════════════════════════════════
#  SPINNING PROGRESS ARC
# ═══════════════════════════════════════════════════════════════════════
class ProgressArc(tk.Canvas):
    def __init__(self, parent, size=70, color=P["cyan"], **kw):
        super().__init__(parent, width=size, height=size,
                         bg=P["panel"], highlightthickness=0, **kw)
        self.size    = size
        self.color   = color
        self._active = False
        self._angle  = 0
        self._draw_idle()

    def _draw_idle(self):
        self.delete("all")
        s = self.size;  m = 7
        self.create_oval(m, m, s-m, s-m, outline=P["border"], width=4)

    def start(self):
        self._active = True
        self._spin()

    def stop(self):
        self._active = False
        self._draw_idle()

    def _spin(self):
        if not self._active:
            return
        self._angle = (self._angle + 9) % 360
        self.delete("all")
        s = self.size;  m = 7
        cx = cy = s // 2
        self.create_oval(m, m, s-m, s-m, outline=P["border"], width=4)
        self.create_arc(m, m, s-m, s-m,
                        start=self._angle, extent=255,
                        outline=self.color, width=4, style="arc")
        a  = math.radians(self._angle)
        r  = (s - 2*m) // 2
        dx = cx + int(r * math.cos(a))
        dy = cy - int(r * math.sin(a))
        self.create_oval(dx-4, dy-4, dx+4, dy+4, fill=self.color, outline="")
        self.after(28, self._spin)


# ═══════════════════════════════════════════════════════════════════════
#  WAVEFORM VISUALIZER WIDGET
#  Real-time animated waveform that reacts to EQ-style bar data.
#  Used in the Visualizer tab and the Mix Studio deck panels.
# ═══════════════════════════════════════════════════════════════════════
class WaveformVisualizer(tk.Canvas):
    """
    Dual-mode visualizer:
      mode='bars'  — animated frequency-spectrum bar chart (EQ style)
      mode='wave'  — scrolling oscilloscope waveform
    Drives itself via after() — call start() / stop().
    Feed live data with feed(values) where values is a list[float] 0-1.
    """
    PALETTES = {
        "cyan":   [P["cyan"],   P["violet"], P["pink"]],
        "lime":   [P["lime"],   P["cyan"],   P["gold"]],
        "pink":   [P["pink"],   P["violet"], P["cyan"]],
        "gold":   [P["gold"],   P["orange"], P["pink"]],
        "violet": [P["violet"], P["pink"],   P["cyan"]],
    }

    def __init__(self, parent, width=400, height=120,
                 mode="bars", palette="cyan", bars=32, **kw):
        super().__init__(parent, width=width, height=height,
                         bg=P["void"], highlightthickness=0, **kw)
        self.w       = width
        self.h       = height
        self.mode    = mode          # 'bars' | 'wave' | 'circle'
        self.palette = palette
        self.bars    = bars
        self._active = False
        self._frame  = 0
        # Internal data buffers
        self._bar_h   = [0.0] * bars           # current bar heights 0-1
        self._bar_tgt = [random.uniform(0.05, 0.9) for _ in range(bars)]
        self._wave_buf= [0.0] * width          # scrolling waveform samples
        self._peak_h  = [0.0] * bars           # peak hold per bar
        self._peak_t  = [0]   * bars           # peak hold timer
        self._draw()

    # ── Public API ───────────────────────────────────────────────────
    def start(self):
        self._active = True
        self._animate()

    def stop(self):
        self._active = False
        self._bar_h   = [0.0] * self.bars
        self._wave_buf= [0.0] * self.w
        self._draw()

    def feed(self, values: List[float]):
        """Feed a list of normalised 0-1 amplitudes (any length)."""
        if not values:
            return
        # Resample to self.bars
        n = len(values)
        for i in range(self.bars):
            src = int(i * n / self.bars)
            self._bar_tgt[i] = float(np.clip(values[src], 0.0, 1.0))
        # Also feed wave buffer
        chunk = [float(np.clip(v, -1.0, 1.0)) for v in values]
        step  = max(1, len(chunk) // (self.w // 4))
        for i in range(0, len(chunk), step):
            self._wave_buf.append((chunk[i] + 1.0) / 2.0)
        # Keep buffer at width
        if len(self._wave_buf) > self.w:
            self._wave_buf = self._wave_buf[-self.w:]

    def set_mode(self, mode: str):
        self.mode = mode

    def set_palette(self, palette: str):
        self.palette = palette if palette in self.PALETTES else "cyan"

    # ── Drawing ──────────────────────────────────────────────────────
    def _get_color(self, ratio: float) -> str:
        """Interpolate palette color based on height ratio."""
        cols = self.PALETTES.get(self.palette, self.PALETTES["cyan"])
        if ratio < 0.5:
            return _lerp_color(cols[0], cols[1], ratio * 2)
        return _lerp_color(cols[1], cols[2], (ratio - 0.5) * 2)

    def _draw(self):
        self.delete("all")
        if self.mode == "bars":
            self._draw_bars()
        elif self.mode == "wave":
            self._draw_wave()
        elif self.mode == "circle":
            self._draw_circle()

    def _draw_bars(self):
        w, h  = self.w, self.h
        bw    = w / (self.bars * 1.5)
        gap   = bw * 0.5
        tot   = bw + gap
        off   = (w - tot * self.bars + gap) / 2

        # Background grid lines
        for gy in range(0, h, h // 4):
            self.create_line(0, gy, w, gy,
                             fill=_lerp_color(P["void"], P["border"], 0.4),
                             dash=(2, 6))

        for i, bh_ratio in enumerate(self._bar_h):
            x1 = off + i * tot
            x2 = x1 + bw
            bh = max(2, int(bh_ratio * (h - 4)))
            col = self._get_color(bh_ratio)

            # Bar gradient: darker at bottom, bright at top
            for seg in range(max(1, bh // 3)):
                seg_y1 = h - 2 - seg * 3
                seg_y2 = seg_y1 - 3
                t      = seg / max(1, bh // 3)
                sc     = _lerp_color(_lerp_color(col, P["void"], 0.6), col, t)
                self.create_rectangle(x1, seg_y2, x2, seg_y1,
                                      fill=sc, outline="")

            # Bright cap
            if bh > 4:
                self.create_rectangle(x1, h-2-bh, x2, h-2-bh+3,
                                      fill=_lerp_color(col, "#FFFFFF", 0.7),
                                      outline="")

            # Peak hold dot
            ph = self._peak_h[i]
            if ph > 0.05:
                py = h - 2 - int(ph * (h - 4))
                self.create_rectangle(x1, py, x2, py+2,
                                      fill=col, outline="")

        # Bottom glow line
        self.create_line(0, h-1, w, h-1,
                         fill=self.PALETTES.get(self.palette,
                                                self.PALETTES["cyan"])[0],
                         width=2)

    def _draw_wave(self):
        w, h = self.w, self.h
        mid  = h // 2
        buf  = self._wave_buf

        if len(buf) < 2:
            self.create_line(0, mid, w, mid,
                             fill=P["muted"], width=1)
            return

        # Background grid
        for gy in [h//4, h//2, 3*h//4]:
            self.create_line(0, gy, w, gy,
                             fill=_lerp_color(P["void"], P["border"], 0.35),
                             dash=(2, 8))

        # Mirror fill (top and bottom)
        pts_top, pts_bot = [], []
        n = len(buf)
        for i, v in enumerate(buf):
            x  = int(i * w / n)
            yv = int((v - 0.5) * (h - 8))
            pts_top.append((x, mid - yv))
            pts_bot.append((x, mid + yv))

        # Filled area
        fill_pts = pts_top + list(reversed(pts_bot))
        if len(fill_pts) > 3:
            avg_h = sum(abs(v - 0.5) for v in buf) / max(len(buf), 1)
            fill_col = self._get_color(min(1.0, avg_h * 2))
            faded    = _lerp_color(fill_col, P["void"], 0.82)
            self.create_polygon(fill_pts, fill=faded, outline="")

        # Line
        col = self.PALETTES.get(self.palette, self.PALETTES["cyan"])[0]
        for i in range(1, len(pts_top)):
            self.create_line(pts_top[i-1], pts_top[i], fill=col, width=2)
            self.create_line(pts_bot[i-1], pts_bot[i], fill=col, width=2)

        # Centre line
        self.create_line(0, mid, w, mid,
                         fill=_lerp_color(col, P["void"], 0.7), width=1)

    def _draw_circle(self):
        """Circular spectrum visualizer."""
        w, h  = self.w, self.h
        cx, cy = w // 2, h // 2
        r_min  = min(w, h) // 5
        r_max  = min(w, h) // 2 - 8

        # Background rings
        for ring in range(3):
            rr = r_min + (r_max - r_min) * (ring + 1) // 4
            self.create_oval(cx-rr, cy-rr, cx+rr, cy+rr,
                             outline=_lerp_color(P["void"], P["border"], 0.4),
                             width=1, dash=(2, 8))

        n = self.bars
        for i, bh in enumerate(self._bar_h):
            angle  = 2 * math.pi * i / n - math.pi / 2
            r_outer= r_min + int(bh * (r_max - r_min))
            x1 = cx + int(r_min  * math.cos(angle))
            y1 = cy + int(r_min  * math.sin(angle))
            x2 = cx + int(r_outer * math.cos(angle))
            y2 = cy + int(r_outer * math.sin(angle))
            col = self._get_color(bh)
            self.create_line(x1, y1, x2, y2, fill=col, width=3, capstyle="round")

        # Centre dot
        cr = 6
        self.create_oval(cx-cr, cy-cr, cx+cr, cy+cr,
                         fill=self.PALETTES.get(self.palette,
                                                self.PALETTES["cyan"])[0],
                         outline="")

    def _animate(self):
        if not self._active:
            return
        self._frame += 1

        # Smooth lerp toward targets
        for i in range(self.bars):
            self._bar_h[i] += (self._bar_tgt[i] - self._bar_h[i]) * 0.22
            # Random target refresh — creates organic movement
            if random.random() < 0.10:
                self._bar_tgt[i] = random.uniform(0.02, 0.95)
            # Peak hold
            if self._bar_h[i] >= self._peak_h[i]:
                self._peak_h[i] = self._bar_h[i]
                self._peak_t[i] = 0
            else:
                self._peak_t[i] += 1
                if self._peak_t[i] > 18:
                    self._peak_h[i] = max(0.0, self._peak_h[i] - 0.025)

        # Pulse wave buffer if no external feed
        if self.mode == "wave":
            t    = self._frame / 12.0
            val  = (math.sin(t * 2.3) * 0.4 +
                    math.sin(t * 5.1) * 0.2 +
                    math.sin(t * 8.7) * 0.1 +
                    random.uniform(-0.08, 0.08))
            self._wave_buf.append((val + 1.0) / 2.0)
            if len(self._wave_buf) > self.w:
                self._wave_buf = self._wave_buf[-self.w:]

        self._draw()
        self.after(45, self._animate)


# ═══════════════════════════════════════════════════════════════════════
#  SCROLL FRAME
# ═══════════════════════════════════════════════════════════════════════
class ScrollFrame(tk.Frame):
    def __init__(self, parent, bg=P["panel"], **kw):
        super().__init__(parent, bg=bg, **kw)
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0)
        self.vsb    = ttk.Scrollbar(self, orient="vertical",
                                    command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.vsb.set)
        self.vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.inner = tk.Frame(self.canvas, bg=bg)
        self._win  = self.canvas.create_window((0,0), window=self.inner,
                                                anchor="nw")
        self.inner.bind("<Configure>",
            lambda e: self.canvas.configure(
                scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>",
            lambda e: self.canvas.itemconfig(self._win, width=e.width))
        self.canvas.bind_all("<MouseWheel>",
            lambda e: self.canvas.yview_scroll(-1*(e.delta//120), "units"))


# ═══════════════════════════════════════════════════════════════════════
#  DJ CARD WIDGET
# ═══════════════════════════════════════════════════════════════════════
class DJCard(tk.Frame):
    def __init__(self, parent, dj: Dict, on_select, **kw):
        super().__init__(parent, bg=P["card"],
                         highlightthickness=2,
                         highlightbackground=P["border"], **kw)
        self.dj        = dj
        self.on_select = on_select
        self.selected  = False
        self._build()
        for w in self.winfo_children():
            self._bind_hover(w)
        self.bind("<Enter>", self._hover_on)
        self.bind("<Leave>", self._hover_off)

    def _bind_hover(self, widget):
        widget.bind("<Enter>", self._hover_on)
        widget.bind("<Leave>", self._hover_off)

    def _build(self):
        dj  = self.dj
        col = dj.get("color", P["cyan"])

        # Top colour bar
        tk.Frame(self, height=4, bg=col).pack(fill=tk.X)

        body = tk.Frame(self, bg=P["card"])
        body.pack(fill=tk.BOTH, expand=True, padx=10, pady=8)

        # Avatar / emoji
        av = tk.Label(body, text=dj["emoji"],
                      font=("Segoe UI Emoji", 26),
                      bg=P["card"], fg=col, width=3)
        av.pack(side=tk.LEFT, padx=(0, 10))

        # Info column
        info = tk.Frame(body, bg=P["card"])
        info.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Name
        tk.Label(info, text=f"  {dj['name']}",
                 font=("Trebuchet MS", 11, "bold"),
                 bg=P["card"], fg=P["text"],
                 anchor="w").pack(fill=tk.X)

        # Genre / era
        tk.Label(info, text=f"{dj['genre']}  ·  {dj['era']}",
                 font=("Segoe UI", 9),
                 bg=P["card"], fg=col, anchor="w").pack(fill=tk.X)

        # Description
        tk.Label(info, text=dj["description"],
                 font=("Segoe UI", 8), bg=P["card"],
                 fg=P["muted"], wraplength=240,
                 justify="left", anchor="w").pack(fill=tk.X, pady=(2, 4))

        # Stat chips
        chips = tk.Frame(info, bg=P["card"])
        chips.pack(fill=tk.X)
        xf_s = dj["params"]["crossfade_ms"] / 1000
        for label, val in [
            ("⏱", f"{xf_s:.0f}s fade"),
            ("🔊", f"+{dj['params']['bass_boost_db']}dB"),
            ("⚡", dj["params"]["energy"].upper()),
        ]:
            chip_bg = _lerp_color(col, P["void"], 0.84)
            c2 = tk.Frame(chips, bg=chip_bg)
            c2.pack(side=tk.LEFT, padx=(0, 4), pady=2)
            tk.Label(c2, text=f"{label} {val}",
                     font=("Segoe UI", 8),
                     bg=chip_bg, fg=col).pack(padx=5, pady=2)

        # Select button
        self._btn = NeonButton(info, text="✔  SELECT THIS DJ",
                               color=col, command=self._select,
                               width=150, height=28,
                               font=("Trebuchet MS", 8, "bold"))
        self._btn.pack(anchor="w", pady=(5, 0))

        # Store avatar label so we can swap image later
        self._av_label = av
        self._col      = col

    def set_avatar(self, photo):
        """Call this after async image fetch to update avatar."""
        self._av_label.configure(image=photo, text="")
        self._av_label.image = photo

    def _select(self):
        self.selected = True
        self.configure(highlightbackground=self._col, highlightthickness=3)
        if self.on_select:
            self.on_select(self.dj)

    def deselect(self):
        self.selected = False
        self.configure(highlightbackground=P["border"], highlightthickness=2)

    def _hover_on(self, _=None):
        if not self.selected:
            self.configure(highlightbackground=_lerp_color(self._col, P["border"], 0.45))

    def _hover_off(self, _=None):
        if not self.selected:
            self.configure(highlightbackground=P["border"])


# ═══════════════════════════════════════════════════════════════════════
#  TRACK ROW WIDGET
# ═══════════════════════════════════════════════════════════════════════
_KIND_COL = {"downloaded": P["cyan"], "mixed": P["pink"], "generated": P["lime"]}
_KIND_ICO = {"downloaded": "⬇", "mixed": "🎚", "generated": "🤖"}

class TrackRow(tk.Frame):
    def __init__(self, parent, track: Track, on_add=None, **kw):
        col = _KIND_COL.get(track.kind, P["muted"])
        super().__init__(parent, bg=P["card"],
                         highlightthickness=1,
                         highlightbackground=P["border"], **kw)
        # Colour stripe
        tk.Frame(self, width=4, bg=col).pack(side=tk.LEFT, fill=tk.Y)
        # Icon
        tk.Label(self, text=_KIND_ICO.get(track.kind, "🎵"),
                 font=("Segoe UI Emoji", 11),
                 bg=P["card"], fg=col, width=3).pack(side=tk.LEFT)
        # Title
        short = track.title[:55] + ("…" if len(track.title) > 55 else "")
        tk.Label(self, text=short, font=("Segoe UI", 10),
                 bg=P["card"], fg=P["text"],
                 anchor="w").pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)
        # BPM
        if track.bpm:
            fb = tk.Frame(self, bg=_lerp_color(col, P["void"], 0.84))
            fb.pack(side=tk.LEFT, padx=3)
            tk.Label(fb, text=f"♩ {track.bpm:.0f}",
                     font=("Consolas", 9),
                     bg=fb["bg"], fg=col).pack(padx=4, pady=2)
        # Key / Camelot
        if track.key:
            fk = tk.Frame(self, bg=_lerp_color(P["violet"], P["void"], 0.84))
            fk.pack(side=tk.LEFT, padx=2)
            tk.Label(fk, text=f"{track.key}/{camelot(track.key)}",
                     font=("Consolas", 9),
                     bg=fk["bg"], fg=P["violet"]).pack(padx=4, pady=2)
        # Add to playlist
        if on_add:
            NeonButton(self, text="➕", color=P["lime"],
                       command=on_add, width=32, height=26,
                       font=("Segoe UI", 9, "bold")).pack(side=tk.RIGHT, padx=6)


# ═══════════════════════════════════════════════════════════════════════
#  APP HEADER
# ═══════════════════════════════════════════════════════════════════════
class AppHeader(tk.Frame):
    def __init__(self, parent, **kw):
        super().__init__(parent, bg=P["void"], **kw)
        self._canvas = tk.Canvas(self, height=70, bg=P["void"],
                                 highlightthickness=0)
        self._canvas.pack(fill=tk.X)
        self._canvas.bind("<Configure>", self._redraw)

        self.eq = EQBars(self, width=190, height=42, bars=18)
        self.eq.place(relx=1.0, rely=0.0, anchor="ne", x=-12, y=14)

        self._status_var = tk.StringVar(value="🎧  Ready — Let's DJ!")
        tk.Label(self, textvariable=self._status_var,
                 font=("Segoe UI", 9), bg=P["void"],
                 fg=P["muted"]).place(relx=1.0, rely=1.0,
                                      anchor="se", x=-14, y=-3)

    def _redraw(self, _=None):
        c = self._canvas
        w = c.winfo_width() or 1160
        c.delete("all")
        for i in range(70):
            col = _lerp_color(_lerp_color(P["pink"], P["void"], 0.78), P["void"], i/70)
            c.create_rectangle(0, i, w, i+1, fill=col, outline="")
        c.create_rectangle(0, 67, w, 70, fill=P["pink"], outline="")
        c.create_rectangle(0, 64, w, 67,
                           fill=_lerp_color(P["pink"], P["void"], 0.68), outline="")
        c.create_text(18, 35, text="🎧", font=("Segoe UI Emoji", 20),
                      fill=P["pink"], anchor="w")
        c.create_text(52, 26, text="AI DJ STUDIO",
                      font=("Impact", 20), fill=P["text"], anchor="w")
        c.create_text(54, 48, text="POWERED BY ARTIFICIAL INTELLIGENCE",
                      font=("Segoe UI", 8, "bold"),
                      fill=P["pink"], anchor="w")

    def set_status(self, msg: str):
        self._status_var.set(msg[:90])

    def start_eq(self):   self.eq.start()
    def stop_eq(self):    self.eq.stop()


# ═══════════════════════════════════════════════════════════════════════
#  LOG PANEL
# ═══════════════════════════════════════════════════════════════════════
class LogPanel(tk.Frame):
    def __init__(self, parent, **kw):
        super().__init__(parent, bg=P["void"],
                         highlightthickness=1,
                         highlightbackground=P["border"], **kw)
        bar = tk.Frame(self, bg=P["void"])
        bar.pack(fill=tk.X, padx=8, pady=(3, 0))
        tk.Label(bar, text="📋  ACTIVITY LOG",
                 font=("Trebuchet MS", 8, "bold"),
                 bg=P["void"], fg=P["muted"]).pack(side=tk.LEFT)
        NeonButton(bar, text="Clear", color=P["dim"],
                   command=self.clear,
                   width=48, height=18,
                   font=("Segoe UI", 7)).pack(side=tk.RIGHT)

        self.text = tk.Text(self, height=5,
                            bg=P["void"], fg=P["muted"],
                            font=("Consolas", 8),
                            relief="flat", bd=0, state="disabled")
        self.text.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)
        self.text.tag_configure("ok",   foreground=P["ok"])
        self.text.tag_configure("err",  foreground=P["err"])
        self.text.tag_configure("warn", foreground=P["warn"])
        self.text.tag_configure("info", foreground=P["cyan"])
        self.text.tag_configure("ts",   foreground=P["dim"])

    def log(self, msg: str, level: str = "info"):
        self.text.configure(state="normal")
        self.text.insert(tk.END, f"[{time.strftime('%H:%M:%S')}]  ", "ts")
        self.text.insert(tk.END, msg + "\n", level)
        self.text.see(tk.END)
        self.text.configure(state="disabled")

    def clear(self):
        self.text.configure(state="normal")
        self.text.delete("1.0", tk.END)
        self.text.configure(state="disabled")


# ═══════════════════════════════════════════════════════════════════════
#  TAB 1 — DJ STYLES
# ═══════════════════════════════════════════════════════════════════════
class DJStylesTab(tk.Frame):
    def __init__(self, parent, app, **kw):
        super().__init__(parent, bg=P["panel"], **kw)
        self.app    = app
        self._cards: List[DJCard] = []
        self._build()

    def _build(self):
        # Toolbar
        top = tk.Frame(self, bg=P["panel"])
        top.pack(fill=tk.X, padx=14, pady=12)
        tk.Label(top, text="🎤  CHOOSE YOUR DJ STYLE",
                 font=("Trebuchet MS", 13, "bold"),
                 bg=P["panel"], fg=P["pink"]).pack(side=tk.LEFT)

        # Online search
        sf = tk.Frame(top, bg=P["border"])
        sf.pack(side=tk.RIGHT)
        self._dj_search_var = tk.StringVar()
        tk.Entry(sf, textvariable=self._dj_search_var,
                 font=("Segoe UI", 10),
                 bg=P["card"], fg=P["text"],
                 insertbackground=P["pink"],
                 relief="flat", width=20, bd=4).pack(side=tk.LEFT)
        NeonButton(sf, text="Search DJs 🔍", color=P["pink"],
                   command=self._search_online,
                   width=120, height=30,
                   font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT)

        # Selection banner
        self._banner = tk.Canvas(self, height=44,
                                 bg=P["void"], highlightthickness=0)
        self._banner.pack(fill=tk.X, padx=14, pady=(0, 6))
        self._banner.bind("<Configure>", self._draw_banner)

        # Scrollable card grid
        self.scroll = ScrollFrame(self, bg=P["panel"])
        self.scroll.pack(fill=tk.BOTH, expand=True, padx=14, pady=4)
        self._populate_cards()

    def _populate_cards(self):
        for w in self.scroll.inner.winfo_children():
            w.destroy()
        self._cards = []
        COLS = 2
        for idx, dj in enumerate(DJ_STYLES):
            row, col = divmod(idx, COLS)
            card = DJCard(self.scroll.inner, dj, on_select=self._on_select)
            card.grid(row=row, column=col, padx=8, pady=6, sticky="nsew")
            self.scroll.inner.columnconfigure(col, weight=1)
            self._cards.append(card)
            # Load avatar async
            self.app.worker.run(
                _fetch_dj_image,
                dj.get("image_query", dj["name"]),
                os.path.join(IMG_DIR, re.sub(r'[^a-z0-9]', '_', dj['name'].lower()) + ".png"),
                callback=lambda res, c=card: self._set_avatar(c, res)
            )

    def _set_avatar(self, card: DJCard, path: Optional[str]):
        if path and _HAS_PIL and os.path.exists(path):
            try:
                img   = Image.open(path).convert("RGBA")
                photo = ImageTk.PhotoImage(img)
                card.set_avatar(photo)
            except Exception:
                pass

    def _on_select(self, dj: Dict):
        for card in self._cards:
            if card.dj["name"] != dj["name"]:
                card.deselect()
        self.app.on_dj_selected(dj)
        self._draw_banner()

    def _draw_banner(self, _=None):
        c = self._banner
        w = c.winfo_width() or 800
        c.delete("all")
        dj = self.app.selected_dj
        if not dj:
            c.create_text(w//2, 22,
                          text="👆  Tap a card above to choose your DJ style!",
                          font=("Segoe UI", 11), fill=P["muted"])
            return
        col = dj.get("color", P["cyan"])
        for i in range(44):
            c.create_rectangle(0, i, w, i+1,
                               fill=_lerp_color(_lerp_color(col, P["void"], 0.88),
                                                P["void"], i/44),
                               outline="")
        c.create_rectangle(0, 0, w, 3, fill=col, outline="")
        c.create_text(14, 22, anchor="w",
                      text=f"{dj['emoji']}  NOW SPINNING WITH: {dj['name'].upper()}",
                      font=("Trebuchet MS", 12, "bold"), fill=col)
        c.create_text(w-10, 22, anchor="e",
                      text=f"{dj['genre']}  ·  {dj['params']['energy'].upper()} ENERGY  ·  "
                           f"{dj['params']['crossfade_ms']/1000:.0f}s CROSSFADE",
                      font=("Segoe UI", 9), fill=P["muted"])

    def _search_online(self):
        q = self._dj_search_var.get().strip()
        if not q:
            messagebox.showinfo("Search DJs", "Type a DJ name to search!"); return
        import webbrowser
        webbrowser.open(f"https://www.google.com/search?q=DJ+{urllib.parse.quote(q)}+biography+mixing+style")
        self.app.log(f"Opened browser: DJ {q}", "info")

    def refresh_banner(self):
        self._draw_banner()


# ═══════════════════════════════════════════════════════════════════════
#  TAB 2 — SEARCH & DOWNLOAD
# ═══════════════════════════════════════════════════════════════════════
class SearchTab(tk.Frame):
    def __init__(self, parent, app, **kw):
        super().__init__(parent, bg=P["panel"], **kw)
        self.app      = app
        self._results: List[Tuple[str,str,str]] = []
        self._build()

    def _build(self):
        # Search bar
        bar = tk.Frame(self, bg=P["panel"])
        bar.pack(fill=tk.X, padx=14, pady=12)
        tk.Label(bar, text="🔍  SEARCH FOR SONGS",
                 font=("Trebuchet MS", 13, "bold"),
                 bg=P["panel"], fg=P["cyan"]).pack(side=tk.LEFT, padx=(0,10))

        entry_bg = tk.Frame(bar, bg=P["border"])
        entry_bg.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0,8))
        self.query_var = tk.StringVar()
        self._entry = tk.Entry(entry_bg, textvariable=self.query_var,
                               font=("Segoe UI", 12),
                               bg=P["card"], fg=P["text"],
                               insertbackground=P["cyan"],
                               relief="flat", bd=8)
        self._entry.pack(fill=tk.X, ipady=4)
        self._entry.bind("<Return>", lambda _: self._do_search())

        NeonButton(bar, text="SEARCH 🔍", color=P["cyan"],
                   command=self._do_search,
                   width=120, height=42).pack(side=tk.LEFT)

        tk.Label(self,
                 text="💡  Type a song or artist · Press Enter or Search · "
                      "Double-click a result to download · ➕ adds to Auto-Mix playlist",
                 font=("Segoe UI", 9), bg=P["panel"],
                 fg=P["muted"]).pack(anchor="w", padx=14, pady=(0,4))

        # Column header
        hdr = tk.Frame(self, bg=P["card2"])
        hdr.pack(fill=tk.X, padx=14)
        for txt, w, anchor in [("#",28,"center"),("Title",0,"w"),("Duration",70,"center")]:
            tk.Label(hdr, text=txt,
                     font=("Trebuchet MS", 9, "bold"),
                     bg=P["card2"], fg=P["muted"],
                     width=w if w else 0,
                     anchor=anchor).pack(
                         side=tk.LEFT, padx=(6,0), pady=4,
                         expand=(w==0), fill=tk.X if w==0 else tk.NONE)

        # Results list
        res_outer = tk.Frame(self, bg=P["panel"])
        res_outer.pack(fill=tk.BOTH, expand=True, padx=14, pady=2)

        self._res_canvas = tk.Canvas(res_outer, bg=P["panel"],
                                     highlightthickness=0)
        res_sb = ttk.Scrollbar(res_outer, command=self._res_canvas.yview)
        self._res_canvas.configure(yscrollcommand=res_sb.set)
        res_sb.pack(side=tk.RIGHT, fill=tk.Y)
        self._res_canvas.pack(fill=tk.BOTH, expand=True)
        self._res_inner = tk.Frame(self._res_canvas, bg=P["panel"])
        _win = self._res_canvas.create_window((0,0),
                                               window=self._res_inner,
                                               anchor="nw")
        self._res_inner.bind("<Configure>",
            lambda e: self._res_canvas.configure(
                scrollregion=self._res_canvas.bbox("all")))
        self._res_canvas.bind("<Configure>",
            lambda e: self._res_canvas.itemconfig(_win, width=e.width))

        # Status + progress
        bot = tk.Frame(self, bg=P["panel"])
        bot.pack(fill=tk.X, padx=14, pady=4)
        self._dl_status = tk.StringVar(value="")
        tk.Label(bot, textvariable=self._dl_status,
                 font=("Consolas", 9),
                 bg=P["panel"], fg=P["ok"]).pack(side=tk.LEFT)
        self._dl_arc = ProgressArc(bot, size=36, color=P["cyan"])
        self._dl_arc.pack(side=tk.RIGHT, padx=6)

        self._show_placeholder()

    def _show_placeholder(self):
        for w in self._res_inner.winfo_children():
            w.destroy()
        tk.Label(self._res_inner,
                 text="🎵\n\nSearch for any song above\nResults will appear here",
                 font=("Segoe UI", 13), bg=P["panel"],
                 fg=P["dim"], justify="center").pack(pady=50)

    def _do_search(self):
        q = self.query_var.get().strip()
        if not q:
            return
        if not _HAS_AUDIO:
            messagebox.showerror("Missing package",
                f"yt-dlp is not installed.\nRun: pip install yt-dlp\n\n{_AUDIO_MISSING}")
            return
        for w in self._res_inner.winfo_children():
            w.destroy()
        tk.Label(self._res_inner, text="🔄  Searching YouTube…",
                 font=("Segoe UI", 12), bg=P["panel"],
                 fg=P["cyan"]).pack(pady=40)
        self.app.header.set_status(f"Searching: {q}…")
        self.app.header.start_eq()

        def _job():
            return yt_search(q, max_results=20)

        def _cb(results):
            self._results = results
            self._render_results()
            self.app.header.stop_eq()
            self.app.header.set_status(
                f"✔ {len(results)} results for '{q}'")
            self.app.log(f"🔍 Search '{q}': {len(results)} results", "info")

        self.app.worker.run(_job, callback=_cb)

    def _render_results(self):
        for w in self._res_inner.winfo_children():
            w.destroy()
        if not self._results:
            tk.Label(self._res_inner, text="No results found.",
                     font=("Segoe UI", 11), bg=P["panel"],
                     fg=P["muted"]).pack(pady=30)
            return
        for i, (title, url, dur) in enumerate(self._results):
            bg = P["card"] if i % 2 == 0 else P["card2"]
            row = tk.Frame(self._res_inner, bg=bg,
                           highlightthickness=1,
                           highlightbackground=P["border"])
            row.pack(fill=tk.X, pady=1)

            tk.Label(row, text=str(i+1), font=("Consolas", 9),
                     bg=bg, fg=P["muted"], width=3).pack(side=tk.LEFT, padx=6)
            tk.Label(row, text="🎵", font=("Segoe UI Emoji", 10),
                     bg=bg, fg=P["cyan"]).pack(side=tk.LEFT)
            tk.Label(row, text=title[:80],
                     font=("Segoe UI", 10), bg=bg,
                     fg=P["text"], anchor="w").pack(
                         side=tk.LEFT, fill=tk.X, expand=True, padx=8)
            tk.Label(row, text=dur, font=("Consolas", 9),
                     bg=bg, fg=P["muted"]).pack(side=tk.LEFT, padx=4)

            NeonButton(row, text="⬇ Download", color=P["cyan"],
                       command=lambda t=title, u=url: self._download(t, u),
                       width=100, height=26,
                       font=("Segoe UI", 8, "bold")).pack(
                           side=tk.LEFT, padx=2, pady=3)
            NeonButton(row, text="➕ Playlist", color=P["lime"],
                       command=lambda t=title, u=url: self._add_to_playlist(t, u),
                       width=90, height=26,
                       font=("Segoe UI", 8, "bold")).pack(
                           side=tk.LEFT, padx=(0, 6), pady=3)

            row.bind("<Enter>", lambda e, r=row: r.configure(
                highlightbackground=P["cyan"]))
            row.bind("<Leave>", lambda e, r=row: r.configure(
                highlightbackground=P["border"]))
            row.bind("<Double-Button-1>",
                     lambda e, t=title, u=url: self._download(t, u))

    def _download(self, title: str, url: str):
        self._dl_status.set(f"⬇  Downloading: {title[:50]}…")
        self._dl_arc.start()
        self.app.header.set_status(f"Downloading: {title[:50]}…")
        self.app.log(f"⬇ Downloading: {title[:60]}", "info")

        def _job():
            def _prog(pct):
                self._dl_status.set(f"⬇  {title[:40]}… {pct}")
            path = download_audio(url, progress_cb=_prog)
            bpm, key = analyze_file(path)
            return path, bpm, key

        def _cb(res):
            path, bpm, key = res
            self._dl_arc.stop()
            name = os.path.basename(path)
            self._dl_status.set(f"✔  {name}")
            self.app.header.set_status(f"✔ Downloaded: {name}")
            self.app.log(
                f"✔ Downloaded: {name}  ({bpm:.1f} BPM, Key {key} / Camelot {camelot(key)})",
                "ok")
            self.app.refresh_library()

        self.app.worker.run(_job, callback=_cb)

    def _add_to_playlist(self, title: str, url: str):
        # Check if already in library by matching title fragment
        matches = [t for t in LIB.items
                   if title[:30].lower() in t.title.lower()
                   and os.path.exists(t.path)]
        if matches:
            self.app.add_to_playlist(matches[0].path)
            return
        if messagebox.askyesno("Download & Add",
                               f"'{title[:60]}' isn't downloaded yet.\n"
                               "Download it now and add to playlist?"):
            def _job():
                path = download_audio(url)
                analyze_file(path)
                return path
            def _cb(path):
                self.app.add_to_playlist(path)
                self.app.refresh_library()
            self.app.worker.run(_job, callback=_cb)


# ═══════════════════════════════════════════════════════════════════════
#  TAB 3 — LIBRARY
# ═══════════════════════════════════════════════════════════════════════
class LibraryTab(tk.Frame):
    def __init__(self, parent, app, **kw):
        super().__init__(parent, bg=P["panel"], **kw)
        self.app      = app
        self._sort    = tk.StringVar(value="alpha")
        self._build()

    def _build(self):
        # Toolbar
        bar = tk.Frame(self, bg=P["panel"])
        bar.pack(fill=tk.X, padx=14, pady=10)
        tk.Label(bar, text="📂  MY MUSIC LIBRARY",
                 font=("Trebuchet MS", 13, "bold"),
                 bg=P["panel"], fg=P["gold"]).pack(side=tk.LEFT)
        NeonButton(bar, text="↻ Rescan", color=P["gold"],
                   command=self.refresh, width=88, height=30,
                   font=("Segoe UI", 9, "bold")).pack(side=tk.RIGHT, padx=4)
        NeonButton(bar, text="📂 Add File", color=P["cyan"],
                   command=self._add_file, width=88, height=30,
                   font=("Segoe UI", 9, "bold")).pack(side=tk.RIGHT, padx=4)

        # Sort pills
        sort_bar = tk.Frame(self, bg=P["panel"])
        sort_bar.pack(fill=tk.X, padx=14, pady=(0, 6))
        tk.Label(sort_bar, text="Sort:",
                 font=("Segoe UI", 9), bg=P["panel"],
                 fg=P["muted"]).pack(side=tk.LEFT, padx=(0, 6))
        for lbl, mode in [("A→Z","alpha"),("Type","kind"),("BPM","bpm")]:
            tk.Radiobutton(sort_bar, text=lbl,
                           variable=self._sort, value=mode,
                           command=self.refresh,
                           font=("Segoe UI", 9),
                           bg=P["panel"], fg=P["text"],
                           selectcolor=P["card"],
                           activebackground=P["panel"],
                           indicatoron=False, relief="flat",
                           bd=0, padx=10, pady=3).pack(side=tk.LEFT, padx=2)

        # Stats bar
        self._stats_bar = tk.Frame(self, bg=P["panel"])
        self._stats_bar.pack(fill=tk.X, padx=14, pady=(0, 4))

        # Track list
        self.scroll = ScrollFrame(self, bg=P["panel"])
        self.scroll.pack(fill=tk.BOTH, expand=True, padx=14, pady=4)

        self._show_empty()

    def _show_empty(self):
        for w in self.scroll.inner.winfo_children():
            w.destroy()
        tk.Label(self.scroll.inner,
                 text="📂\n\nNo tracks yet — download some songs first!",
                 font=("Segoe UI", 13), bg=P["panel"],
                 fg=P["dim"], justify="center").pack(pady=60)

    def refresh(self):
        LIB.load()
        tracks = LIB.list_sorted(self._sort.get())

        # Stats
        for w in self._stats_bar.winfo_children():
            w.destroy()
        dl  = sum(1 for t in tracks if t.kind == "downloaded")
        mix = sum(1 for t in tracks if t.kind == "mixed")
        gen = sum(1 for t in tracks if t.kind == "generated")
        for lbl, val, col in [
            ("⬇ Downloaded", dl, P["cyan"]),
            ("🎚 Mixed",      mix, P["pink"]),
            ("🤖 Generated",  gen, P["lime"]),
            ("Total",         len(tracks), P["gold"]),
        ]:
            chip_bg = _lerp_color(col, P["void"], 0.84)
            ch = tk.Frame(self._stats_bar, bg=chip_bg)
            ch.pack(side=tk.LEFT, padx=(0, 6))
            tk.Label(ch, text=f"{lbl}: {val}",
                     font=("Segoe UI", 9),
                     bg=chip_bg, fg=col).pack(padx=8, pady=3)

        # Tracks
        for w in self.scroll.inner.winfo_children():
            w.destroy()
        if not tracks:
            self._show_empty()
            return
        for t in tracks:
            TrackRow(self.scroll.inner, t,
                     on_add=lambda p=t.path: self.app.add_to_playlist(p)
                     ).pack(fill=tk.X, pady=1)

    def _add_file(self):
        path = filedialog.askopenfilename(
            filetypes=[("Audio", "*.mp3 *.wav *.m4a *.flac *.ogg")])
        if not path:
            return
        if not _HAS_AUDIO:
            LIB.add_or_update(Track(
                path=path, title=os.path.basename(path), kind='downloaded'))
            self.refresh()
            return

        def _job():
            return analyze_file(path)

        def _cb(res):
            bpm, key = res
            self.app.log(
                f"Added: {os.path.basename(path)} ({bpm:.1f} BPM, {key})", "ok")
            self.refresh()

        self.app.worker.run(_job, callback=_cb)


# ═══════════════════════════════════════════════════════════════════════
#  TAB 4 — MIX STUDIO
# ═══════════════════════════════════════════════════════════════════════
class MixStudioTab(tk.Frame):
    def __init__(self, parent, app, **kw):
        super().__init__(parent, bg=P["panel"], **kw)
        self.app   = app
        self._a_path = tk.StringVar()
        self._b_path = tk.StringVar()
        self._build()

    def _build(self):
        tk.Label(self, text="🎚  MIX STUDIO",
                 font=("Trebuchet MS", 13, "bold"),
                 bg=P["panel"], fg=P["violet"]).pack(anchor="w", padx=14, pady=10)

        # Two-deck layout
        decks = tk.Frame(self, bg=P["panel"])
        decks.pack(fill=tk.X, padx=14, pady=4)
        decks.columnconfigure(0, weight=1)
        decks.columnconfigure(2, weight=1)

        self._deck_a = self._make_deck(decks, "A", P["cyan"],  0)
        self._make_vs(decks, 1)
        self._deck_b = self._make_deck(decks, "B", P["pink"],  2)

        # Crossfade slider
        xf_row = tk.Frame(self, bg=P["card"],
                          highlightthickness=1,
                          highlightbackground=P["border"])
        xf_row.pack(fill=tk.X, padx=14, pady=8)
        tk.Label(xf_row, text="⏱  CROSSFADE DURATION",
                 font=("Trebuchet MS", 10, "bold"),
                 bg=P["card"], fg=P["gold"]).pack(side=tk.LEFT, padx=10, pady=8)
        self.crossfade_var = tk.IntVar(value=6000)
        tk.Scale(xf_row,
                 from_=500, to=30000, resolution=500,
                 orient=tk.HORIZONTAL,
                 variable=self.crossfade_var,
                 bg=P["card"], fg=P["gold"],
                 troughcolor=P["border"],
                 highlightthickness=0,
                 font=("Segoe UI", 9),
                 length=300).pack(side=tk.LEFT, padx=8)
        self._xf_lbl = tk.Label(xf_row, text="6.0s",
                                 font=("Trebuchet MS", 14, "bold"),
                                 bg=P["card"], fg=P["gold"])
        self._xf_lbl.pack(side=tk.LEFT)
        self.crossfade_var.trace_add("write",
            lambda *_: self._xf_lbl.configure(
                text=f"{self.crossfade_var.get()/1000:.1f}s"))

        # Output name row
        out_row = tk.Frame(self, bg=P["panel"])
        out_row.pack(fill=tk.X, padx=14, pady=4)
        tk.Label(out_row, text="💾  Output filename:",
                 font=("Segoe UI", 10),
                 bg=P["panel"], fg=P["muted"]).pack(side=tk.LEFT)
        self._mix_name = tk.StringVar(value="my_mix.mp3")
        tk.Entry(out_row, textvariable=self._mix_name,
                 font=("Segoe UI", 10),
                 bg=P["card"], fg=P["text"],
                 insertbackground=P["violet"],
                 relief="flat", bd=6, width=38).pack(side=tk.LEFT, padx=8)

        # Action buttons
        btn_row = tk.Frame(self, bg=P["panel"])
        btn_row.pack(pady=10)
        self._mix_btn = NeonButton(btn_row,
                                    text="🎚  BEATMATCH & MIX",
                                    color=P["violet"],
                                    command=self._mix_now,
                                    width=220, height=46,
                                    font=("Trebuchet MS", 12, "bold"))
        self._mix_btn.pack(side=tk.LEFT, padx=8)
        self._mix_arc = ProgressArc(btn_row, size=56, color=P["violet"])
        self._mix_arc.pack(side=tk.LEFT, padx=8)

        # DJ style indicator
        self._dj_note = tk.Label(self, text="No DJ style selected",
                                  font=("Segoe UI", 9, "italic"),
                                  bg=P["panel"], fg=P["muted"])
        self._dj_note.pack()

    def _make_deck(self, parent, label, col, grid_col) -> Dict:
        frame = tk.Frame(parent, bg=P["card"],
                         highlightthickness=2,
                         highlightbackground=_lerp_color(col, P["void"], 0.5))
        frame.grid(row=0, column=grid_col, sticky="nsew", padx=6, pady=4)

        # Header bar
        hdr = tk.Canvas(frame, height=32, bg=P["void"],
                        highlightthickness=0)
        hdr.pack(fill=tk.X)
        hdr.bind("<Configure>",
                 lambda e, cv=hdr, c=col, l=label: self._draw_deck_hdr(cv, c, l))

        # Vinyl
        vinyl = VinylRecord(frame, size=130, color=col)
        vinyl.pack(pady=6)

        # Path display
        path_var = tk.StringVar(value="No track loaded")
        tk.Label(frame, textvariable=path_var,
                 font=("Consolas", 8), bg=P["card"],
                 fg=P["muted"], wraplength=220).pack(padx=8)

        # BPM / Key
        info_row = tk.Frame(frame, bg=P["card"])
        info_row.pack(pady=3)
        bpm_lbl = tk.Label(info_row, text="—— BPM",
                           font=("Trebuchet MS", 16, "bold"),
                           bg=P["card"], fg=col)
        bpm_lbl.pack(side=tk.LEFT, padx=6)
        key_lbl = tk.Label(info_row, text="Key: —",
                           font=("Segoe UI", 10),
                           bg=P["card"], fg=P["violet"])
        key_lbl.pack(side=tk.LEFT)

        # Buttons
        btns = tk.Frame(frame, bg=P["card"])
        btns.pack(pady=4)
        path_store = getattr(self, f"_{'a' if grid_col==0 else 'b'}_path")
        NeonButton(btns, text="📂 Browse", color=col,
                   command=lambda: self._browse(label, path_var,
                                                path_store, vinyl,
                                                bpm_lbl, key_lbl),
                   width=96, height=30,
                   font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT, padx=3)
        NeonButton(btns, text="🔬 Analyze", color=P["gold"],
                   command=lambda: self._analyze(path_store.get(),
                                                  bpm_lbl, key_lbl),
                   width=96, height=30,
                   font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT, padx=3)

        return {"frame": frame, "vinyl": vinyl,
                "bpm": bpm_lbl, "key": key_lbl}

    def _draw_deck_hdr(self, canvas, col, label):
        w = canvas.winfo_width() or 260
        canvas.delete("all")
        for i in range(32):
            canvas.create_rectangle(0, i, w, i+1,
                                    fill=_lerp_color(_lerp_color(col, P["void"], 0.82),
                                                     P["void"], i/32),
                                    outline="")
        canvas.create_text(w//2, 16, text=f"DECK  {label}",
                           font=("Impact", 13), fill=col)

    def _make_vs(self, parent, col):
        vs = tk.Frame(parent, bg=P["panel"])
        vs.grid(row=0, column=col, padx=6)
        tk.Label(vs, text="VS", font=("Impact", 20),
                 bg=P["panel"], fg=P["dim"]).pack(pady=16)
        eq = EQBars(vs, width=55, height=70, bars=5)
        eq.pack()
        eq.start()

    def _browse(self, label, path_lbl, path_store,
                vinyl, bpm_lbl, key_lbl):
        path = filedialog.askopenfilename(
            filetypes=[("Audio", "*.mp3 *.wav *.m4a *.flac *.ogg")])
        if not path:
            return
        path_store.set(path)
        path_lbl.set(os.path.basename(path))
        vinyl.start_spin()
        bpm_lbl.configure(text="Analyzing…")
        self.app.log(f"Deck {label}: {os.path.basename(path)}", "info")
        if not _HAS_AUDIO:
            vinyl.stop_spin()
            bpm_lbl.configure(text="—— BPM")
            return
        self._analyze(path, bpm_lbl, key_lbl, vinyl)

    def _analyze(self, path: str, bpm_lbl, key_lbl, vinyl=None):
        if not path or not os.path.exists(path):
            messagebox.showwarning("Analyze", "Choose a valid audio file first.")
            return
        bpm_lbl.configure(text="Analyzing…")

        def _job():
            return analyze_file(path)

        def _cb(res):
            bpm, key = res
            bpm_lbl.configure(text=f"{bpm:.1f} BPM")
            key_lbl.configure(text=f"Key: {key} / {camelot(key)}")
            if vinyl:
                vinyl.stop_spin()
            self.app.log(
                f"Analyzed: {os.path.basename(path)} → {bpm:.1f} BPM, "
                f"Key {key} (Camelot {camelot(key)})", "ok")
            self.app.refresh_library()

        self.app.worker.run(_job, callback=_cb)

    def _mix_now(self):
        a = self._a_path.get()
        b = self._b_path.get()
        if not (a and b and os.path.exists(a) and os.path.exists(b)):
            messagebox.showwarning("Mix",
                "Please select valid Track A and Track B files first.")
            return
        if not _HAS_AUDIO:
            messagebox.showerror("Missing packages",
                "Audio libraries not installed.\nRun: pip install librosa soundfile pydub")
            return

        name   = os.path.basename(self._mix_name.get().strip()) or "mix.mp3"
        xfade  = int(self.crossfade_var.get())
        params = self.app.selected_dj["params"] if self.app.selected_dj else {}

        self._mix_btn.set_disabled(True)
        self._mix_arc.start()
        self.app.header.start_eq()
        self.app.header.set_status("Beatmatching and mixing…")
        self.app.log("🎚 Mix started…", "info")
        self._deck_a["vinyl"].start_spin()
        self._deck_b["vinyl"].start_spin()

        def _job():
            return mix_tracks(a, b, mix_name=name,
                              crossfade_ms=xfade, dj_params=params)

        def _cb(res):
            self._mix_btn.set_disabled(False)
            self._mix_arc.stop()
            self.app.header.stop_eq()
            self._deck_a["vinyl"].stop_spin()
            self._deck_b["vinyl"].stop_spin()
            out = os.path.basename(res)
            self.app.log(f"✔ Mix saved: {out}", "ok")
            self.app.header.set_status(f"✔ Mix saved: {out}")
            self.app.refresh_library()
            messagebox.showinfo("🎉 Mix Done!",
                                f"Your mix has been saved!\n\nFile: {out}\n\n"
                                "Find it in the Library tab.")

        self.app.worker.run(_job, callback=_cb)

    def update_dj(self, dj: Optional[Dict]):
        if dj:
            self._dj_note.configure(
                text=f"🎵  DJ Style: {dj['emoji']} {dj['name']}  ·  "
                     f"{dj['params']['crossfade_ms']/1000:.0f}s crossfade  ·  "
                     f"{dj['params']['energy'].upper()} energy",
                fg=dj.get("color", P["cyan"]))
            self.crossfade_var.set(dj["params"]["crossfade_ms"])
        else:
            self._dj_note.configure(
                text="No DJ style selected — go to 🎤 DJ Styles tab",
                fg=P["muted"])


# ═══════════════════════════════════════════════════════════════════════
#  TAB 5 — AUTO-MIX AI
# ═══════════════════════════════════════════════════════════════════════
class AutoMixTab(tk.Frame):
    def __init__(self, parent, app, **kw):
        super().__init__(parent, bg=P["panel"], **kw)
        self.app      = app
        self.playlist: List[str] = []
        self._build()

    def _build(self):
        # Header canvas
        hdr = tk.Canvas(self, height=76, bg=P["void"],
                        highlightthickness=0)
        hdr.pack(fill=tk.X)
        hdr.bind("<Configure>", lambda e, cv=hdr: self._draw_hdr(cv))

        # Body: left = playlist, right = controls
        body = tk.Frame(self, bg=P["panel"])
        body.pack(fill=tk.BOTH, expand=True, padx=14, pady=8)
        body.columnconfigure(0, weight=2)
        body.columnconfigure(1, weight=1)

        # ── Playlist column ──────────────────────────────────────
        left = tk.Frame(body, bg=P["panel"])
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        pl_hdr = tk.Frame(left, bg=P["panel"])
        pl_hdr.pack(fill=tk.X, pady=(0, 4))
        tk.Label(pl_hdr, text="🎵  YOUR PLAYLIST",
                 font=("Trebuchet MS", 11, "bold"),
                 bg=P["panel"], fg=P["lime"]).pack(side=tk.LEFT)
        self._pl_count_lbl = tk.Label(pl_hdr, text="0 songs",
                                       font=("Segoe UI", 9),
                                       bg=P["panel"], fg=P["muted"])
        self._pl_count_lbl.pack(side=tk.LEFT, padx=8)
        NeonButton(pl_hdr, text="Clear", color=P["err"],
                   command=self._clear_playlist,
                   width=70, height=26,
                   font=("Segoe UI", 8, "bold")).pack(side=tk.RIGHT)
        NeonButton(pl_hdr, text="+ From Library", color=P["lime"],
                   command=self._add_from_library,
                   width=110, height=26,
                   font=("Segoe UI", 8, "bold")).pack(side=tk.RIGHT, padx=4)

        # Progress bar
        self._prog_canvas = tk.Canvas(left, height=26,
                                      bg=P["card"], highlightthickness=0)
        self._prog_canvas.pack(fill=tk.X, pady=(0, 4))
        self._prog_canvas.bind("<Configure>",
                               lambda _: self._draw_prog_bar())

        # Listbox
        lb_frame = tk.Frame(left, bg=P["card"],
                            highlightthickness=1,
                            highlightbackground=P["border"])
        lb_frame.pack(fill=tk.BOTH, expand=True)
        self.pl_listbox = tk.Listbox(lb_frame,
                                      bg=P["card"], fg=P["text"],
                                      selectbackground=P["lime"],
                                      selectforeground=P["void"],
                                      font=("Segoe UI", 10),
                                      relief="flat", bd=0,
                                      activestyle="none")
        self.pl_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        pl_sb = ttk.Scrollbar(lb_frame, command=self.pl_listbox.yview)
        self.pl_listbox.configure(yscrollcommand=pl_sb.set)
        pl_sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.pl_listbox.bind("<Delete>", self._remove_selected)

        tk.Label(left, text="💡 Press Delete key to remove a selected song",
                 font=("Segoe UI", 8), bg=P["panel"],
                 fg=P["dim"]).pack(anchor="w", pady=2)

        # ── Controls column ──────────────────────────────────────
        right = tk.Frame(body, bg=P["panel"])
        right.grid(row=0, column=1, sticky="nsew")

        tk.Label(right, text="🤖  AI DJ CONTROLS",
                 font=("Trebuchet MS", 11, "bold"),
                 bg=P["panel"], fg=P["gold"]).pack(pady=(0, 6))

        # DJ display
        self._dj_display = tk.Canvas(right, height=74,
                                      bg=P["card"], highlightthickness=0)
        self._dj_display.pack(fill=tk.X, pady=(0, 6))
        self._dj_display.bind("<Configure>",
                              lambda _: self._draw_dj_display())

        # Vinyl
        self.vinyl = VinylRecord(right, size=120, color=P["lime"])
        self.vinyl.pack(pady=4)

        # Output name
        tk.Label(right, text="Output filename:",
                 font=("Segoe UI", 9),
                 bg=P["panel"], fg=P["muted"]).pack(anchor="w")
        self._out_var = tk.StringVar(value="ai_automix.mp3")
        tk.Entry(right, textvariable=self._out_var,
                 font=("Segoe UI", 9), bg=P["card"],
                 fg=P["text"], insertbackground=P["lime"],
                 relief="flat", bd=6).pack(fill=tk.X, pady=4)

        # BIG button
        self._start_btn = NeonButton(right,
                                      text="🤖  START AUTO-MIX",
                                      color=P["lime"],
                                      command=self._start_mix,
                                      width=230, height=52,
                                      font=("Trebuchet MS", 13, "bold"))
        self._start_btn.pack(pady=8)

        self._status_var = tk.StringVar(value="Add 5+ songs to begin!")
        tk.Label(right, textvariable=self._status_var,
                 font=("Segoe UI", 9, "italic"),
                 bg=P["panel"], fg=P["gold"],
                 wraplength=230).pack(pady=2)

        self._arc = ProgressArc(right, size=64, color=P["lime"])
        self._arc.pack(pady=4)

    def _draw_hdr(self, cv):
        w = cv.winfo_width() or 900
        cv.delete("all")
        for i in range(76):
            cv.create_rectangle(0, i, w, i+1,
                                fill=_lerp_color(
                                    _lerp_color(P["lime"], P["void"], 0.88),
                                    P["void"], i/76),
                                outline="")
        cv.create_rectangle(0, 73, w, 76, fill=P["lime"], outline="")
        cv.create_text(18, 30, anchor="w", text="🤖",
                       font=("Segoe UI Emoji", 22), fill=P["lime"])
        cv.create_text(54, 24, anchor="w", text="AI AUTO-MIX",
                       font=("Impact", 20), fill=P["text"])
        cv.create_text(56, 48, anchor="w",
                       text="Pick 5+ songs · Choose a DJ Style · Let the AI take over! 🎉",
                       font=("Segoe UI", 10), fill=P["lime"])

    def _draw_prog_bar(self):
        c = self._prog_canvas
        w = c.winfo_width() or 400
        c.delete("all")
        n      = len(self.playlist)
        needed = 5
        ratio  = min(1.0, n / needed)
        filled = int((w - 4) * ratio)
        c.create_rectangle(2, 6, w-2, 20, fill=P["border"], outline="")
        if filled > 0:
            col = P["ok"] if n >= needed else P["warn"]
            c.create_rectangle(2, 6, 2+filled, 20, fill=col, outline="")
        msg = (f"✅  {n} songs ready — press Auto-Mix!"
               if n >= needed
               else f"🎵  {n}/{needed} songs — add {needed-n} more!")
        col = P["ok"] if n >= needed else P["warn"]
        c.create_text(w//2, 13, text=msg,
                      font=("Segoe UI", 8, "bold"), fill=col)

    def _draw_dj_display(self):
        c = self._dj_display
        w = c.winfo_width() or 240
        h = 74
        c.delete("all")
        for i in range(h):
            c.create_rectangle(0, i, w, i+1,
                               fill=_lerp_color(P["card2"], P["card"], i/h),
                               outline="")
        dj = self.app.selected_dj
        if not dj:
            c.create_text(w//2, h//2,
                          text="👆 Choose a DJ Style first",
                          font=("Segoe UI", 10), fill=P["muted"])
            return
        col = dj.get("color", P["cyan"])
        c.create_rectangle(0, 0, w, 3, fill=col, outline="")
        c.create_text(14, h//2-10, anchor="w",
                      text=dj["emoji"],
                      font=("Segoe UI Emoji", 22), fill=col)
        c.create_text(46, h//2-10, anchor="w",
                      text=dj["name"],
                      font=("Trebuchet MS", 11, "bold"), fill=P["text"])
        c.create_text(46, h//2+8, anchor="w",
                      text=f"{dj['genre']}  ·  {dj['params']['energy'].upper()}",
                      font=("Segoe UI", 8), fill=P["muted"])

    # ── Playlist management ──────────────────────────────────────
    def add_track(self, path: str):
        if path in self.playlist:
            return
        self.playlist.append(path)
        n = len(self.playlist)
        self.pl_listbox.insert(tk.END,
                                f"  {n}.  {os.path.basename(path)}")
        self._pl_count_lbl.configure(
            text=f"{n} song{'s' if n != 1 else ''}")
        self._draw_prog_bar()
        if n >= 5:
            self._status_var.set(f"✅  {n} songs ready — hit Auto-Mix!")

    def _remove_selected(self, _=None):
        sel = self.pl_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        self.pl_listbox.delete(idx)
        del self.playlist[idx]
        # Renumber
        items = list(self.pl_listbox.get(0, tk.END))
        self.pl_listbox.delete(0, tk.END)
        for i, it in enumerate(items):
            self.pl_listbox.insert(tk.END, f"  {i+1}.  {it.split('.  ', 1)[-1]}")
        self._pl_count_lbl.configure(
            text=f"{len(self.playlist)} songs")
        self._draw_prog_bar()

    def _clear_playlist(self):
        self.playlist.clear()
        self.pl_listbox.delete(0, tk.END)
        self._pl_count_lbl.configure(text="0 songs")
        self._draw_prog_bar()
        self._status_var.set("Add 5+ songs to begin!")

    def _add_from_library(self):
        """Pull selected track from Library tab."""
        lib_tab = self.app.tab_library
        sel = lib_tab.scroll.inner.winfo_children()
        # Find the last highlighted TrackRow — simpler: use a dialog
        tracks = LIB.list_sorted("alpha")
        if not tracks:
            messagebox.showinfo("Add from Library",
                "No tracks in library yet. Download some songs first!")
            return
        # Simple picker dialog
        win = tk.Toplevel(self)
        win.title("Pick a Track")
        win.configure(bg=P["panel"])
        win.geometry("500x400")
        tk.Label(win, text="Select a track to add:",
                 font=("Trebuchet MS", 11, "bold"),
                 bg=P["panel"], fg=P["lime"]).pack(padx=12, pady=8)
        lb = tk.Listbox(win, bg=P["card"], fg=P["text"],
                        selectbackground=P["lime"],
                        selectforeground=P["void"],
                        font=("Segoe UI", 10),
                        relief="flat", bd=0)
        lb.pack(fill=tk.BOTH, expand=True, padx=12, pady=4)
        for t in tracks:
            lb.insert(tk.END, f"  {t.title}")

        def _pick():
            sel = lb.curselection()
            if sel:
                self.add_track(tracks[sel[0]].path)
                self.app.log(
                    f"➕ Added: {tracks[sel[0]].title}", "info")
            win.destroy()

        NeonButton(win, text="✔  Add Selected", color=P["lime"],
                   command=_pick, width=160, height=36,
                   font=("Trebuchet MS", 10, "bold")).pack(pady=6)

    def update_dj(self, _=None):
        self._draw_dj_display()

    def _start_mix(self):
        if len(self.playlist) < 2:
            messagebox.showwarning("Auto-Mix",
                "Add at least 2 songs!\n"
                "5+ is ideal for the full AI DJ experience 🎧")
            return
        if not self.app.selected_dj:
            messagebox.showwarning("Auto-Mix",
                "Pick a DJ Style first!\nGo to the 🎤 DJ Styles tab.")
            return
        if not _HAS_AUDIO:
            messagebox.showerror("Missing packages",
                "Audio libraries not installed.\n"
                "Run: pip install librosa soundfile pydub yt-dlp")
            return

        dj     = self.app.selected_dj
        tracks = list(self.playlist)
        name   = os.path.basename(self._out_var.get().strip()) or "ai_automix.mp3"

        self._start_btn.set_disabled(True)
        self.vinyl.start_spin()
        self._arc.start()
        self.app.header.start_eq()
        self._status_var.set(f"{dj['emoji']} {dj['name']} is mixing {len(tracks)} tracks…")
        self.app.header.set_status(
            f"🤖 Auto-Mix: {len(tracks)} tracks with {dj['name']}…")
        self.app.log(
            f"🤖 Auto-Mix started: {len(tracks)} tracks, DJ style: {dj['name']}", "info")

        def _prog(msg):
            self._status_var.set(f"  {msg}")

        def _job():
            return auto_mix_playlist(tracks, dj,
                                     out_name=name, progress_cb=_prog)

        def _cb(res):
            self._start_btn.set_disabled(False)
            self.vinyl.stop_spin()
            self._arc.stop()
            self.app.header.stop_eq()
            out = os.path.basename(res)
            self._status_var.set(f"✅  Saved: {out}")
            self.app.header.set_status(f"🎉 Auto-Mix complete: {out}")
            self.app.log(f"🎉 Auto-Mix complete: {out}", "ok")
            self.app.refresh_library()
            messagebox.showinfo(
                "🎉 Your Mix is Ready!",
                f"{dj['emoji']}  {dj['name']} has finished!\n\n"
                f"📀  {len(tracks)} tracks mixed into:\n     {out}\n\n"
                f"💃  Style: {dj['params']['energy'].upper()} energy\n"
                f"⏱   Crossfades: {dj['params']['crossfade_ms']/1000:.0f}s each\n\n"
                "Find your mix in the Library tab!")

        self.app.worker.run(_job, callback=_cb)


# ═══════════════════════════════════════════════════════════════════════
#  FEATURE 1 — TAB 6: VISUALIZER
#  Full-screen animated visualizer with 3 modes and palette switcher.
#  Reacts to EQ data from the header. Independent animation loop.
# ═══════════════════════════════════════════════════════════════════════
class VisualizerTab(tk.Frame):
    """Full-tab visualizer with mode picker, palette picker, and info overlay."""

    MODES    = [("🎚 Bars", "bars"), ("〰 Wave", "wave"), ("⭕ Circle", "circle")]
    PALETTES = [("Cyan", "cyan"), ("Lime", "lime"), ("Pink", "pink"),
                ("Gold", "gold"), ("Violet", "violet")]

    def __init__(self, parent, app, **kw):
        super().__init__(parent, bg=P["void"], **kw)
        self.app       = app
        self._mode     = tk.StringVar(value="bars")
        self._palette  = tk.StringVar(value="cyan")
        self._running  = False
        self._build()

    def _build(self):
        # ── Top control bar ──────────────────────────────────────────
        ctrl = tk.Frame(self, bg=P["panel"])
        ctrl.pack(fill=tk.X, padx=0, pady=0)

        # Gradient header
        hdr = tk.Canvas(ctrl, height=52, bg=P["void"],
                        highlightthickness=0)
        hdr.pack(fill=tk.X)
        hdr.bind("<Configure>", self._draw_viz_header)

        # Mode + palette pickers in a row below header
        picks = tk.Frame(self, bg=P["panel"])
        picks.pack(fill=tk.X, padx=14, pady=6)

        tk.Label(picks, text="Mode:",
                 font=("Segoe UI", 9, "bold"),
                 bg=P["panel"], fg=P["muted"]).pack(side=tk.LEFT, padx=(0, 4))
        for lbl, mode in self.MODES:
            tk.Radiobutton(picks, text=lbl,
                           variable=self._mode, value=mode,
                           command=self._on_mode_change,
                           font=("Segoe UI", 9),
                           bg=P["panel"], fg=P["text"],
                           selectcolor=P["card"],
                           activebackground=P["panel"],
                           indicatoron=False, relief="flat",
                           bd=0, padx=10, pady=3).pack(side=tk.LEFT, padx=2)

        tk.Label(picks, text="  Palette:",
                 font=("Segoe UI", 9, "bold"),
                 bg=P["panel"], fg=P["muted"]).pack(side=tk.LEFT, padx=(12, 4))
        for lbl, pal in self.PALETTES:
            col = WaveformVisualizer.PALETTES[pal][0]
            btn = tk.Radiobutton(picks, text=lbl,
                                 variable=self._palette, value=pal,
                                 command=self._on_palette_change,
                                 font=("Segoe UI", 9),
                                 bg=P["panel"],
                                 fg=col,
                                 selectcolor=P["card"],
                                 activebackground=P["panel"],
                                 indicatoron=False, relief="flat",
                                 bd=0, padx=8, pady=3)
            btn.pack(side=tk.LEFT, padx=1)

        # Start / Stop toggle
        self._toggle_btn = NeonButton(picks, text="▶ START",
                                       color=P["lime"],
                                       command=self._toggle,
                                       width=90, height=28,
                                       font=("Segoe UI", 9, "bold"))
        self._toggle_btn.pack(side=tk.RIGHT, padx=8)

        # ── Main visualizer canvas ───────────────────────────────────
        viz_frame = tk.Frame(self, bg=P["void"])
        viz_frame.pack(fill=tk.BOTH, expand=True, padx=14, pady=(0, 8))

        self.viz = WaveformVisualizer(viz_frame,
                                       width=900, height=340,
                                       mode="bars", palette="cyan",
                                       bars=48)
        self.viz.pack(fill=tk.BOTH, expand=True)
        self.viz.bind("<Configure>",
                      lambda e: self.viz.configure(width=e.width, height=e.height))

        # ── Info row ─────────────────────────────────────────────────
        info = tk.Frame(self, bg=P["panel"])
        info.pack(fill=tk.X, padx=14, pady=(0, 6))

        self._info_lbl = tk.Label(info,
            text="💡  Visualizer ready — press ▶ START to begin · "
                 "Reacts to your music during playback",
            font=("Segoe UI", 9), bg=P["panel"], fg=P["muted"])
        self._info_lbl.pack(side=tk.LEFT)

        self._dj_badge = tk.Label(info, text="No DJ selected",
                                   font=("Segoe UI", 9, "bold"),
                                   bg=P["panel"], fg=P["dim"])
        self._dj_badge.pack(side=tk.RIGHT)

    def _draw_viz_header(self, _=None):
        c = self._draw_viz_header.__self__._hdr_canvas \
            if hasattr(self._draw_viz_header, '__self__') else None
        # Get the canvas from the ctrl children
        ctrl_children = self.winfo_children()
        if not ctrl_children:
            return
        panel = ctrl_children[0]
        canvases = [w for w in panel.winfo_children()
                    if isinstance(w, tk.Canvas)]
        if not canvases:
            return
        cv = canvases[0]
        w  = cv.winfo_width() or 1160
        cv.delete("all")
        for i in range(52):
            col = _lerp_color(
                _lerp_color(P["violet"], P["void"], 0.80),
                P["void"], i / 52)
            cv.create_rectangle(0, i, w, i+1, fill=col, outline="")
        cv.create_rectangle(0, 49, w, 52, fill=P["violet"], outline="")
        cv.create_text(18, 26, anchor="w", text="📊",
                       font=("Segoe UI Emoji", 18), fill=P["violet"])
        cv.create_text(50, 18, anchor="w", text="VISUALIZER",
                       font=("Impact", 18), fill=P["text"])
        cv.create_text(52, 38, anchor="w",
                       text="Real-time animated spectrum · 3 modes · 5 palettes",
                       font=("Segoe UI", 9), fill=P["violet"])

    def _on_mode_change(self):
        self.viz.set_mode(self._mode.get())

    def _on_palette_change(self):
        self.viz.set_palette(self._palette.get())

    def _toggle(self):
        if self._running:
            self._running = False
            self.viz.stop()
            self._toggle_btn.set_text("▶ START")
            self._info_lbl.configure(text="Visualizer stopped.")
        else:
            self._running = True
            self.viz.start()
            self._toggle_btn.set_text("⏹ STOP")
            self._info_lbl.configure(
                text="✨  Visualizer running — feed it audio data or let it groove!")

    def update_dj(self, dj: Optional[Dict]):
        if dj:
            col = dj.get("color", P["cyan"])
            self._dj_badge.configure(
                text=f"{dj['emoji']}  {dj['name']}",
                fg=col)
            # Auto-match palette to DJ color
            col_map = {
                "#FF2D78": "pink", "#00E5FF": "cyan",
                "#AAFF00": "lime", "#FFD600": "gold",
                "#BF5FFF": "violet", "#FF6B2B": "gold",
            }
            pal = col_map.get(col, "cyan")
            self._palette.set(pal)
            self.viz.set_palette(pal)

    def feed_audio(self, samples: List[float]):
        """Called by the app when audio data is available."""
        self.viz.feed(samples)


# ═══════════════════════════════════════════════════════════════════════
#  FEATURE 2 — PLAYLIST SAVE / LOAD SYSTEM
#  Playlists saved to JSON in APP_DIR/playlists/.
#  Full CRUD: create, rename, delete, import, export.
# ═══════════════════════════════════════════════════════════════════════
# PLAYLISTS_DIR defined in DIRECTORIES section above


def save_playlist(name: str, paths: List[str]) -> str:
    """Save playlist to JSON. Returns saved file path."""
    safe_name = re.sub(r'[^a-zA-Z0-9_\- ]', '', name).strip() or "playlist"
    fname     = safe_name + ".json"
    fpath     = os.path.join(PLAYLISTS_DIR, fname)
    data = {
        "name":    name,
        "created": time.strftime("%Y-%m-%d %H:%M:%S"),
        "tracks":  [{"path": p, "title": os.path.basename(p)} for p in paths],
    }
    with open(fpath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
    return fpath


def load_playlist(fpath: str) -> Tuple[str, List[str]]:
    """Load playlist from JSON. Returns (name, [paths])."""
    with open(fpath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    name  = data.get("name", os.path.splitext(os.path.basename(fpath))[0])
    paths = [t["path"] for t in data.get("tracks", [])
             if os.path.exists(t.get("path", ""))]
    return name, paths


def list_playlists() -> List[Dict]:
    """List all saved playlists with metadata."""
    result = []
    for fname in sorted(os.listdir(PLAYLISTS_DIR)):
        if not fname.endswith(".json"):
            continue
        fpath = os.path.join(PLAYLISTS_DIR, fname)
        try:
            with open(fpath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            result.append({
                "name":    data.get("name", fname),
                "created": data.get("created", ""),
                "count":   len(data.get("tracks", [])),
                "path":    fpath,
            })
        except Exception:
            pass
    return result


class PlaylistManagerTab(tk.Frame):
    """Save, load, rename, delete, and import/export playlists."""

    def __init__(self, parent, app, **kw):
        super().__init__(parent, bg=P["panel"], **kw)
        self.app = app
        self._build()

    def _build(self):
        # Header
        hdr = tk.Canvas(self, height=52, bg=P["void"],
                        highlightthickness=0)
        hdr.pack(fill=tk.X)
        hdr.bind("<Configure>", lambda e, cv=hdr: self._draw_hdr(cv))

        # Two-panel layout: left = saved playlists, right = current + actions
        body = tk.Frame(self, bg=P["panel"])
        body.pack(fill=tk.BOTH, expand=True, padx=14, pady=8)
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=1)

        # ── LEFT: Saved Playlists ────────────────────────────────────
        left = tk.Frame(body, bg=P["panel"])
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        pl_hdr = tk.Frame(left, bg=P["panel"])
        pl_hdr.pack(fill=tk.X, pady=(0, 6))
        tk.Label(pl_hdr, text="💾  SAVED PLAYLISTS",
                 font=("Trebuchet MS", 11, "bold"),
                 bg=P["panel"], fg=P["gold"]).pack(side=tk.LEFT)
        NeonButton(pl_hdr, text="↻ Refresh",
                   color=P["gold"], command=self.refresh,
                   width=80, height=26,
                   font=("Segoe UI", 8, "bold")).pack(side=tk.RIGHT)

        # Playlist list
        lb_frame = tk.Frame(left, bg=P["card"],
                            highlightthickness=1,
                            highlightbackground=P["border"])
        lb_frame.pack(fill=tk.BOTH, expand=True)
        self._pl_listbox = tk.Listbox(lb_frame,
                                       bg=P["card"], fg=P["text"],
                                       selectbackground=P["gold"],
                                       selectforeground=P["void"],
                                       font=("Segoe UI", 10),
                                       relief="flat", bd=0)
        self._pl_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        pl_sb = ttk.Scrollbar(lb_frame, command=self._pl_listbox.yview)
        self._pl_listbox.configure(yscrollcommand=pl_sb.set)
        pl_sb.pack(side=tk.RIGHT, fill=tk.Y)
        self._pl_listbox.bind("<<ListboxSelect>>", self._on_pl_select)
        self._pl_data: List[Dict] = []

        # Action buttons row
        pl_btns = tk.Frame(left, bg=P["panel"])
        pl_btns.pack(fill=tk.X, pady=(6, 0))
        NeonButton(pl_btns, text="📂 Load",
                   color=P["cyan"], command=self._load_selected,
                   width=80, height=30,
                   font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT, padx=(0, 4))
        NeonButton(pl_btns, text="🗑 Delete",
                   color=P["err"], command=self._delete_selected,
                   width=80, height=30,
                   font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT, padx=4)
        NeonButton(pl_btns, text="📤 Export",
                   color=P["muted"], command=self._export_selected,
                   width=80, height=30,
                   font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT, padx=4)

        # Playlist detail
        self._detail_lbl = tk.Label(left,
            text="Select a playlist to see its tracks",
            font=("Segoe UI", 9, "italic"),
            bg=P["panel"], fg=P["muted"],
            wraplength=340, justify="left")
        self._detail_lbl.pack(anchor="w", pady=(4, 0))

        # ── RIGHT: Current Playlist + Save ──────────────────────────
        right = tk.Frame(body, bg=P["panel"])
        right.grid(row=0, column=1, sticky="nsew")

        cur_hdr = tk.Frame(right, bg=P["panel"])
        cur_hdr.pack(fill=tk.X, pady=(0, 6))
        tk.Label(cur_hdr, text="🎵  CURRENT PLAYLIST",
                 font=("Trebuchet MS", 11, "bold"),
                 bg=P["panel"], fg=P["lime"]).pack(side=tk.LEFT)
        self._cur_count = tk.Label(cur_hdr, text="0 tracks",
                                    font=("Segoe UI", 9),
                                    bg=P["panel"], fg=P["muted"])
        self._cur_count.pack(side=tk.LEFT, padx=8)

        # Current track list (read-only preview)
        cur_lb_frame = tk.Frame(right, bg=P["card"],
                                 highlightthickness=1,
                                 highlightbackground=P["border"])
        cur_lb_frame.pack(fill=tk.BOTH, expand=True)
        self._cur_listbox = tk.Listbox(cur_lb_frame,
                                        bg=P["card"], fg=P["text"],
                                        selectbackground=P["lime"],
                                        font=("Segoe UI", 10),
                                        relief="flat", bd=0)
        self._cur_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        cur_sb = ttk.Scrollbar(cur_lb_frame, command=self._cur_listbox.yview)
        self._cur_listbox.configure(yscrollcommand=cur_sb.set)
        cur_sb.pack(side=tk.RIGHT, fill=tk.Y)

        # Save section
        save_frame = tk.Frame(right, bg=P["card"],
                              highlightthickness=1,
                              highlightbackground=P["border"])
        save_frame.pack(fill=tk.X, pady=(8, 0))

        tk.Label(save_frame, text="Save as:",
                 font=("Segoe UI", 10, "bold"),
                 bg=P["card"], fg=P["gold"]).pack(
                     side=tk.LEFT, padx=10, pady=8)
        self._save_name = tk.StringVar(value="My Playlist")
        tk.Entry(save_frame, textvariable=self._save_name,
                 font=("Segoe UI", 10),
                 bg=P["border"], fg=P["text"],
                 insertbackground=P["gold"],
                 relief="flat", bd=6).pack(
                     side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        NeonButton(save_frame, text="💾 SAVE",
                   color=P["gold"], command=self._save_current,
                   width=80, height=34,
                   font=("Trebuchet MS", 10, "bold")).pack(
                       side=tk.LEFT, padx=(0, 8), pady=6)

        # Import button
        NeonButton(right, text="📥 Import Playlist File",
                   color=P["violet"], command=self._import_playlist,
                   width=210, height=32,
                   font=("Segoe UI", 9, "bold")).pack(
                       anchor="w", pady=(6, 0))

        self.refresh()

    def _draw_hdr(self, cv):
        w = cv.winfo_width() or 1100
        cv.delete("all")
        for i in range(52):
            cv.create_rectangle(0, i, w, i+1,
                                fill=_lerp_color(
                                    _lerp_color(P["gold"], P["void"], 0.85),
                                    P["void"], i/52),
                                outline="")
        cv.create_rectangle(0, 49, w, 52, fill=P["gold"], outline="")
        cv.create_text(18, 26, anchor="w", text="💾",
                       font=("Segoe UI Emoji", 18), fill=P["gold"])
        cv.create_text(50, 18, anchor="w", text="PLAYLIST MANAGER",
                       font=("Impact", 18), fill=P["text"])
        cv.create_text(52, 38, anchor="w",
                       text="Save · Load · Delete · Import · Export playlists",
                       font=("Segoe UI", 9), fill=P["gold"])

    def refresh(self):
        """Reload saved playlists list."""
        self._pl_data = list_playlists()
        self._pl_listbox.delete(0, tk.END)
        for pl in self._pl_data:
            self._pl_listbox.insert(
                tk.END,
                f"  📋  {pl['name']}  ({pl['count']} tracks)  —  {pl['created'][:10]}")

    def sync_from_auto_tab(self):
        """Pull the current playlist from the Auto-Mix tab."""
        paths = list(self.app.tab_auto.playlist)
        self._cur_listbox.delete(0, tk.END)
        for i, p in enumerate(paths, 1):
            self._cur_listbox.insert(tk.END, f"  {i}.  {os.path.basename(p)}")
        self._cur_count.configure(text=f"{len(paths)} track{'s' if len(paths)!=1 else ''}")

    def _on_pl_select(self, _=None):
        sel = self._pl_listbox.curselection()
        if not sel:
            return
        pl = self._pl_data[sel[0]]
        try:
            _, paths = load_playlist(pl["path"])
            detail = "\n".join(f"  {i+1}. {os.path.basename(p)}"
                               for i, p in enumerate(paths))
            self._detail_lbl.configure(
                text=f"Tracks ({len(paths)}):\n{detail[:400]}")
        except Exception as e:
            self._detail_lbl.configure(text=f"Could not read: {e}")

    def _save_current(self):
        """Save the Auto-Mix tab's current playlist."""
        paths = list(self.app.tab_auto.playlist)
        if not paths:
            messagebox.showwarning("Save Playlist",
                "The Auto-Mix playlist is empty!\n"
                "Add some tracks first, then save.")
            return
        name = self._save_name.get().strip() or "My Playlist"
        fpath = save_playlist(name, paths)
        self.app.log(f"💾 Playlist saved: {name} ({len(paths)} tracks)", "ok")
        self.refresh()
        messagebox.showinfo("Playlist Saved",
                            f"✅  '{name}' saved!\n"
                            f"{len(paths)} tracks → {os.path.basename(fpath)}")

    def _load_selected(self):
        """Load selected playlist into Auto-Mix tab."""
        sel = self._pl_listbox.curselection()
        if not sel:
            messagebox.showinfo("Load Playlist",
                "Click a saved playlist first.")
            return
        pl = self._pl_data[sel[0]]
        try:
            name, paths = load_playlist(pl["path"])
        except Exception as e:
            messagebox.showerror("Load Error", str(e))
            return
        if not paths:
            messagebox.showwarning("Load Playlist",
                f"Playlist '{name}' has no tracks that exist on disk.")
            return

        # Confirm if current playlist has tracks
        if self.app.tab_auto.playlist:
            if not messagebox.askyesno("Load Playlist",
                    f"This will replace the current playlist ({len(self.app.tab_auto.playlist)} tracks).\n"
                    f"Load '{name}' ({len(paths)} tracks) instead?"):
                return

        # Clear and populate Auto-Mix tab
        self.app.tab_auto._clear_playlist()
        for p in paths:
            self.app.tab_auto.add_track(p)

        self.app.log(f"📂 Loaded playlist: {name} ({len(paths)} tracks)", "ok")
        self.app.nb.select(4)   # switch to Auto-Mix tab
        messagebox.showinfo("Playlist Loaded",
                            f"✅  '{name}' loaded!\n"
                            f"{len(paths)} tracks added to Auto-Mix playlist.")

    def _delete_selected(self):
        sel = self._pl_listbox.curselection()
        if not sel:
            messagebox.showinfo("Delete", "Select a playlist first.")
            return
        pl = self._pl_data[sel[0]]
        if not messagebox.askyesno("Delete Playlist",
                f"Delete '{pl['name']}'?\nThis cannot be undone."):
            return
        try:
            os.remove(pl["path"])
            self.app.log(f"🗑 Playlist deleted: {pl['name']}", "warn")
            self.refresh()
        except Exception as e:
            messagebox.showerror("Delete Error", str(e))

    def _export_selected(self):
        """Export playlist JSON to a user-chosen location."""
        sel = self._pl_listbox.curselection()
        if not sel:
            messagebox.showinfo("Export", "Select a playlist first.")
            return
        pl = self._pl_data[sel[0]]
        dest = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("Playlist JSON", "*.json")],
            initialfile=os.path.basename(pl["path"]))
        if dest:
            shutil.copy2(pl["path"], dest)
            self.app.log(f"📤 Exported: {os.path.basename(dest)}", "ok")

    def _import_playlist(self):
        """Import a playlist JSON from disk."""
        fpath = filedialog.askopenfilename(
            filetypes=[("Playlist JSON", "*.json"), ("All", "*.*")])
        if not fpath:
            return
        try:
            name, paths = load_playlist(fpath)
        except Exception as e:
            messagebox.showerror("Import Error", str(e))
            return
        # Copy into playlists dir
        dest = os.path.join(PLAYLISTS_DIR, os.path.basename(fpath))
        if os.path.abspath(fpath) != os.path.abspath(dest):
            shutil.copy2(fpath, dest)
        self.app.log(f"📥 Imported playlist: {name} ({len(paths)} tracks)", "ok")
        self.refresh()
        messagebox.showinfo("Imported",
                            f"✅  '{name}' imported!\n"
                            f"{len(paths)} tracks available.\n"
                            "Press Load to use it.")


# ═══════════════════════════════════════════════════════════════════════
#  FEATURE 3 — DJ BATTLE MODE
#  Two DJ styles compete head-to-head on the same track list.
#  Side-by-side animated display, score system, winner declared.
# ═══════════════════════════════════════════════════════════════════════
class DJBattleTab(tk.Frame):
    """
    DJ Battle: two DJ styles mix the same songs.
    Each gets a score based on energy + crossfade quality.
    Animated battle arena with live progress.
    """

    def __init__(self, parent, app, **kw):
        super().__init__(parent, bg=P["void"], **kw)
        self.app        = app
        self._dj_a      : Optional[Dict] = None
        self._dj_b      : Optional[Dict] = None
        self._score_a   = 0
        self._score_b   = 0
        self._battle_on = False
        self._build()

    def _build(self):
        # Header
        hdr = tk.Canvas(self, height=58, bg=P["void"],
                        highlightthickness=0)
        hdr.pack(fill=tk.X)
        hdr.bind("<Configure>", lambda e, cv=hdr: self._draw_hdr(cv))

        # Main arena — two columns
        arena = tk.Frame(self, bg=P["void"])
        arena.pack(fill=tk.BOTH, expand=True, padx=14, pady=8)
        arena.columnconfigure(0, weight=1)
        arena.columnconfigure(1, weight=0)
        arena.columnconfigure(2, weight=1)

        self._corner_a = self._build_corner(arena, "A", 0)
        self._build_vs_column(arena, 1)
        self._corner_b = self._build_corner(arena, "B", 2)

        # Track selector
        track_bar = tk.Frame(self, bg=P["panel"])
        track_bar.pack(fill=tk.X, padx=14, pady=(0, 4))
        tk.Label(track_bar, text="🎵  Battle Tracks (uses Auto-Mix playlist):",
                 font=("Segoe UI", 10, "bold"),
                 bg=P["panel"], fg=P["text"]).pack(side=tk.LEFT)
        self._track_count_lbl = tk.Label(track_bar, text="0 tracks loaded",
                                          font=("Segoe UI", 9),
                                          bg=P["panel"], fg=P["muted"])
        self._track_count_lbl.pack(side=tk.LEFT, padx=8)
        NeonButton(track_bar, text="↻ Sync from Auto-Mix",
                   color=P["muted"], command=self._sync_tracks,
                   width=170, height=28,
                   font=("Segoe UI", 8, "bold")).pack(side=tk.RIGHT)

        # Start battle
        self._battle_btn = NeonButton(self,
                                       text="⚔️  START BATTLE",
                                       color=P["pink"],
                                       command=self._start_battle,
                                       width=280, height=52,
                                       font=("Impact", 14))
        self._battle_btn.pack(pady=6)

        # Result banner
        self._result_canvas = tk.Canvas(self, height=56,
                                         bg=P["void"],
                                         highlightthickness=0)
        self._result_canvas.pack(fill=tk.X, padx=14, pady=(0, 6))
        self._result_canvas.bind("<Configure>",
                                  lambda _: self._draw_result())

        self._tracks: List[str] = []

    def _build_corner(self, parent, label: str, col: int) -> Dict:
        """Build one DJ corner with selection, vinyl, score."""
        frame = tk.Frame(parent, bg=P["card"],
                         highlightthickness=2,
                         highlightbackground=P["border"])
        frame.grid(row=0, column=col, sticky="nsew", padx=6, pady=4)

        col_color = P["cyan"] if label == "A" else P["pink"]

        # Corner label
        tk.Label(frame, text=f"CORNER  {label}",
                 font=("Impact", 13),
                 bg=P["card"], fg=col_color).pack(pady=(8, 4))

        # DJ selector button
        btn_var = tk.StringVar(value="— Pick a DJ —")
        sel_btn = NeonButton(frame,
                              text="🎤  Choose DJ",
                              color=col_color,
                              command=lambda la=label: self._pick_dj(la),
                              width=200, height=34,
                              font=("Segoe UI", 10, "bold"))
        sel_btn.pack(pady=(0, 6))

        # DJ name label
        name_lbl = tk.Label(frame, text="No DJ selected",
                             font=("Trebuchet MS", 11, "bold"),
                             bg=P["card"], fg=col_color)
        name_lbl.pack()

        # Genre / energy
        info_lbl = tk.Label(frame, text="",
                             font=("Segoe UI", 9),
                             bg=P["card"], fg=P["muted"])
        info_lbl.pack()

        # Vinyl
        vinyl = VinylRecord(frame, size=120, color=col_color)
        vinyl.pack(pady=8)

        # Score display
        score_lbl = tk.Label(frame, text="⭐  0 pts",
                              font=("Trebuchet MS", 16, "bold"),
                              bg=P["card"], fg=col_color)
        score_lbl.pack(pady=4)

        # Progress bar
        prog_canvas = tk.Canvas(frame, height=12,
                                 bg=P["card"], highlightthickness=0)
        prog_canvas.pack(fill=tk.X, padx=12, pady=(0, 8))

        # Status label
        status_lbl = tk.Label(frame, text="Waiting…",
                               font=("Segoe UI", 8, "italic"),
                               bg=P["card"], fg=P["muted"],
                               wraplength=200)
        status_lbl.pack(pady=(0, 8))

        return {
            "frame":      frame,
            "sel_btn":    sel_btn,
            "name_lbl":   name_lbl,
            "info_lbl":   info_lbl,
            "vinyl":      vinyl,
            "score_lbl":  score_lbl,
            "prog_canvas":prog_canvas,
            "status_lbl": status_lbl,
            "color":      col_color,
            "label":      label,
        }

    def _build_vs_column(self, parent, col: int):
        vs = tk.Frame(parent, bg=P["void"])
        vs.grid(row=0, column=col, padx=4)
        tk.Label(vs, text="⚔️",
                 font=("Segoe UI Emoji", 28),
                 bg=P["void"], fg=P["gold"]).pack(pady=(40, 4))
        tk.Label(vs, text="VS",
                 font=("Impact", 24),
                 bg=P["void"], fg=P["gold"]).pack()
        # Mini EQ
        eq = EQBars(vs, width=50, height=60, bars=5)
        eq.pack(pady=8)
        eq.start()

    def _draw_hdr(self, cv):
        w = cv.winfo_width() or 1100
        cv.delete("all")
        for i in range(58):
            col = _lerp_color(
                _lerp_color(P["pink"], P["void"], 0.82),
                P["void"], i/58)
            cv.create_rectangle(0, i, w, i+1, fill=col, outline="")
        cv.create_rectangle(0, 0, w//2, 3, fill=P["cyan"], outline="")
        cv.create_rectangle(w//2, 0, w, 3, fill=P["pink"], outline="")
        cv.create_text(18, 29, anchor="w", text="⚔️",
                       font=("Segoe UI Emoji", 22), fill=P["gold"])
        cv.create_text(54, 20, anchor="w", text="DJ BATTLE MODE",
                       font=("Impact", 20), fill=P["text"])
        cv.create_text(56, 42, anchor="w",
                       text="Two DJ styles battle it out on the same tracks — winner takes all!",
                       font=("Segoe UI", 10), fill=P["gold"])

    def _draw_result(self, winner: Optional[str] = None):
        c = self._result_canvas
        w = c.winfo_width() or 900
        c.delete("all")
        if winner is None:
            c.create_text(w//2, 28,
                          text="⚔️  Choose two DJ styles and press START BATTLE",
                          font=("Segoe UI", 12), fill=P["muted"])
            return
        if winner == "tie":
            c.create_text(w//2, 28,
                          text="🤝  IT'S A TIE!  Both DJs are equally matched!",
                          font=("Trebuchet MS", 14, "bold"), fill=P["gold"])
            return
        dj = self._dj_a if winner == "A" else self._dj_b
        corner = self._corner_a if winner == "A" else self._corner_b
        col = corner["color"]
        for i in range(56):
            cv_col = _lerp_color(_lerp_color(col, P["void"], 0.88),
                                  P["void"], i/56)
            c.create_rectangle(0, i, w, i+1, fill=cv_col, outline="")
        c.create_rectangle(0, 0, w, 3, fill=col, outline="")
        if dj:
            c.create_text(w//2, 28,
                          text=f"🏆  WINNER: {dj['emoji']} {dj['name'].upper()}  🏆  "
                               f"Score: {self._score_a if winner=='A' else self._score_b} pts",
                          font=("Trebuchet MS", 14, "bold"), fill=col)

    def _draw_progress(self, corner: Dict, pct: float):
        c   = corner["prog_canvas"]
        w   = c.winfo_width() or 200
        col = corner["color"]
        c.delete("all")
        c.create_rectangle(0, 0, w, 12, fill=P["border"], outline="")
        if pct > 0:
            c.create_rectangle(0, 0, int(w * pct), 12, fill=col, outline="")

    def _pick_dj(self, label: str):
        """Open a picker dialog for selecting a DJ style."""
        win = tk.Toplevel(self)
        win.title(f"Pick DJ for Corner {label}")
        win.configure(bg=P["panel"])
        win.geometry("480x460")
        win.grab_set()

        col_color = P["cyan"] if label == "A" else P["pink"]
        tk.Label(win, text=f"⚔️  Pick DJ for Corner {label}",
                 font=("Trebuchet MS", 13, "bold"),
                 bg=P["panel"], fg=col_color).pack(padx=14, pady=10)

        lb = tk.Listbox(win, bg=P["card"], fg=P["text"],
                        selectbackground=col_color,
                        selectforeground=P["void"],
                        font=("Segoe UI", 11),
                        relief="flat", bd=0)
        lb.pack(fill=tk.BOTH, expand=True, padx=14, pady=4)

        for dj in DJ_STYLES:
            lb.insert(tk.END,
                      f"  {dj['emoji']}  {dj['name']:25s}  "
                      f"{dj['genre']}")

        info_lbl = tk.Label(win, text="",
                             font=("Segoe UI", 9),
                             bg=P["panel"], fg=P["muted"],
                             wraplength=440, justify="left")
        info_lbl.pack(padx=14, pady=(0, 4))

        def _on_select(e):
            sel = lb.curselection()
            if sel:
                dj = DJ_STYLES[sel[0]]
                info_lbl.configure(
                    text=f"{dj['description']}\n"
                         f"Crossfade: {dj['params']['crossfade_ms']/1000:.0f}s  |  "
                         f"Energy: {dj['params']['energy'].upper()}")

        lb.bind("<<ListboxSelect>>", _on_select)

        def _confirm():
            sel = lb.curselection()
            if not sel:
                return
            dj = DJ_STYLES[sel[0]]
            if label == "A":
                self._dj_a = dj
                self._corner_a["name_lbl"].configure(
                    text=f"{dj['emoji']}  {dj['name']}")
                self._corner_a["info_lbl"].configure(
                    text=f"{dj['genre']}  ·  {dj['params']['energy'].upper()}")
                self._corner_a["vinyl"].color = dj.get("color", P["cyan"])
                self._corner_a["vinyl"]._draw()
            else:
                self._dj_b = dj
                self._corner_b["name_lbl"].configure(
                    text=f"{dj['emoji']}  {dj['name']}")
                self._corner_b["info_lbl"].configure(
                    text=f"{dj['genre']}  ·  {dj['params']['energy'].upper()}")
                self._corner_b["vinyl"].color = dj.get("color", P["pink"])
                self._corner_b["vinyl"]._draw()
            win.destroy()

        NeonButton(win, text=f"✔  Select for Corner {label}",
                   color=col_color, command=_confirm,
                   width=220, height=36,
                   font=("Trebuchet MS", 10, "bold")).pack(pady=8)

    def _sync_tracks(self):
        self._tracks = list(self.app.tab_auto.playlist)
        n = len(self._tracks)
        self._track_count_lbl.configure(
            text=f"{n} track{'s' if n!=1 else ''} loaded")
        self.app.log(f"⚔️ Battle synced: {n} tracks", "info")

    def _start_battle(self):
        if not self._dj_a or not self._dj_b:
            messagebox.showwarning("DJ Battle",
                "Pick a DJ for both Corner A and Corner B first!")
            return
        if len(self._tracks) < 2:
            messagebox.showwarning("DJ Battle",
                "Sync at least 2 tracks from the Auto-Mix playlist first!")
            return
        if not _HAS_AUDIO:
            messagebox.showerror("Missing packages",
                "Audio libraries not installed.\n"
                "Run: pip install librosa soundfile pydub")
            return
        if self._battle_on:
            return

        self._battle_on = True
        self._score_a   = 0
        self._score_b   = 0
        self._battle_btn.set_disabled(True)
        self._draw_result(None)

        dj_a = self._dj_a
        dj_b = self._dj_b
        tracks = list(self._tracks)
        n_tracks = len(tracks)

        for corner in (self._corner_a, self._corner_b):
            corner["vinyl"].start_spin()
            corner["status_lbl"].configure(text="Mixing…")
            corner["score_lbl"].configure(text="⭐  0 pts")
            self._draw_progress(corner, 0.0)

        self.app.header.start_eq()
        self.app.log(f"⚔️ BATTLE: {dj_a['name']} vs {dj_b['name']} — {n_tracks} tracks", "info")

        def _update_progress(corner, pct, msg):
            corner["status_lbl"].configure(text=msg)
            self._draw_progress(corner, pct)

        def _battle_job():
            import tempfile
            results = {}
            for corner_label, dj in [("A", dj_a), ("B", dj_b)]:
                corner = self._corner_a if corner_label == "A" else self._corner_b
                params = dj["params"]
                xfade  = params.get("crossfade_ms", 6000)

                mix_out = os.path.join(
                    MIX_DIR,
                    f"battle_{corner_label}_{re.sub(r'[^a-z0-9]','_',dj['name'].lower())}.mp3")

                # Analyse tracks
                analyzed = []
                for i, t in enumerate(tracks):
                    pct = (i + 1) / (n_tracks * 2)
                    _update_progress(corner, pct,
                                     f"Analysing {i+1}/{n_tracks}…")
                    try:
                        bpm, key = analyze_file(t)
                        analyzed.append((bpm, t))
                    except Exception:
                        analyzed.append((120.0, t))

                analyzed.sort(key=lambda x: x[0])
                ordered = [t for _, t in analyzed]

                # Mix
                current = ordered[0]
                for i, nxt in enumerate(ordered[1:], 1):
                    pct = 0.5 + i / (n_tracks * 2)
                    _update_progress(corner, pct,
                                     f"Mixing {i}/{len(ordered)-1}…")
                    tmp = f"_battle_{corner_label}_step{i}.mp3"
                    current = mix_tracks(current, nxt,
                                         mix_name=tmp,
                                         crossfade_ms=xfade,
                                         dj_params=params)

                final = mix_out
                shutil.move(current, final)
                LIB.add_or_update(Track(
                    path=final,
                    title=os.path.basename(final),
                    kind='mixed'))

                # Score calculation
                energy_map = {
                    "explosive":   100, "euphoric": 92,  "emotional": 88,
                    "celebratory": 85,  "gritty":   82,  "raw":       90,
                    "groovy":      78,  "summer":   80,  "cerebral":  72,
                    "hard":        88,
                }
                energy_score = energy_map.get(
                    params.get("energy", "groovy"), 75)
                # Bonus for smoothness (longer crossfade = smoother)
                xfade_s = xfade / 1000.0
                smooth_bonus = min(20, int(xfade_s * 1.5))
                # Penalty for very long crossfades (over 15s can sound sloppy)
                if xfade_s > 15:
                    smooth_bonus -= int((xfade_s - 15) * 2)
                # Bass boost bonus (up to 5 extra)
                bass_bonus = min(5, params.get("bass_boost_db", 0))
                # Track count bonus
                track_bonus = min(15, n_tracks * 2)
                # Random performance variance
                variance = random.randint(-8, 8)
                score = max(0, energy_score + smooth_bonus +
                            bass_bonus + track_bonus + variance)
                results[corner_label] = {"score": score, "path": final}

            return results

        def _cb(results):
            self._battle_on = False
            self._battle_btn.set_disabled(False)
            self.app.header.stop_eq()

            # Update scores
            self._score_a = results["A"]["score"]
            self._score_b = results["B"]["score"]

            self._corner_a["vinyl"].stop_spin()
            self._corner_b["vinyl"].stop_spin()
            self._corner_a["score_lbl"].configure(
                text=f"⭐  {self._score_a} pts")
            self._corner_b["score_lbl"].configure(
                text=f"⭐  {self._score_b} pts")
            self._draw_progress(self._corner_a, 1.0)
            self._draw_progress(self._corner_b, 1.0)

            # Determine winner
            if abs(self._score_a - self._score_b) <= 3:
                winner = "tie"
            elif self._score_a > self._score_b:
                winner = "A"
                self._corner_a["status_lbl"].configure(
                    text="🏆 WINNER!")
                self._corner_b["status_lbl"].configure(
                    text=f"Good effort! ({self._score_b} pts)")
            else:
                winner = "B"
                self._corner_b["status_lbl"].configure(
                    text="🏆 WINNER!")
                self._corner_a["status_lbl"].configure(
                    text=f"Good effort! ({self._score_a} pts)")

            self._draw_result(winner)
            self.app.refresh_library()

            dj_w = self._dj_a if winner == "A" else self._dj_b
            if winner == "tie":
                msg = (f"🤝  IT'S A TIE!\n\n"
                       f"{dj_a['emoji']} {dj_a['name']}: {self._score_a} pts\n"
                       f"{dj_b['emoji']} {dj_b['name']}: {self._score_b} pts\n\n"
                       "Both mixes saved to Library!")
            else:
                msg = (f"🏆  WINNER: {dj_w['emoji']} {dj_w['name']}\n\n"
                       f"{dj_a['emoji']} {dj_a['name']}: {self._score_a} pts\n"
                       f"{dj_b['emoji']} {dj_b['name']}: {self._score_b} pts\n\n"
                       "Both mixes saved to Library — check them out!")
            self.app.log(f"⚔️ Battle complete! {msg.splitlines()[0]}", "ok")
            messagebox.showinfo("⚔️ Battle Complete!", msg)

        self.app.worker.run(_battle_job, callback=_cb)


# ═══════════════════════════════════════════════════════════════════════
#  MAIN APPLICATION WINDOW
# ═══════════════════════════════════════════════════════════════════════
class AIDJStudio(tk.Tk):
    """
    Main application window.
    Manages all tabs, worker polling, app-wide state, and
    mobile-responsive layout scaling.
    """

    # ── Tab index constants ──────────────────────────────────────
    TAB_DJ         = 0
    TAB_SEARCH     = 1
    TAB_LIBRARY    = 2
    TAB_MIX        = 3
    TAB_AUTO       = 4
    TAB_VISUALIZER = 5
    TAB_PLAYLISTS  = 6
    TAB_BATTLE     = 7

    def __init__(self):
        # ── Windows DPI awareness (must be before any window creation) ──
        if sys.platform == "win32":
            try:
                import ctypes
                # Per-monitor DPI awareness v2 (Windows 10 1703+)
                ctypes.windll.shcore.SetProcessDpiAwareness(2)
            except Exception:
                try:
                    ctypes.windll.user32.SetProcessDPIAware()
                except Exception:
                    pass

        super().__init__()
        self.title("🎧  AI DJ Studio")
        self.configure(bg=P["void"])

        # ── Show splash screen while loading ────────────────────────────
        self._show_splash()

        # ── FEATURE 4: Mobile / responsive layout detection ──────
        self._mobile_mode = False
        self._detect_and_apply_layout()

        self.selected_dj: Optional[Dict] = None
        self.worker = Worker()

        self._apply_ttk_theme()

        # ── Build UI ─────────────────────────────────────────────
        self.header = AppHeader(self)
        self.header.pack(fill=tk.X)

        self._build_notebook()

        self.log_panel = LogPanel(self)
        self.log_panel.pack(fill=tk.X, padx=6 if self._mobile_mode else 10,
                            pady=(0, 4))

        # ── Bind window resize to stay responsive ────────────────
        self.bind("<Configure>", self._on_resize)

        # Start worker polling
        self.after(250, self._poll_worker)

        # Startup
        # ── Set Windows taskbar icon ────────────────────────────────────
        if sys.platform == "win32" or _HAS_PIL:
            ico = _get_asset("app_icon.ico")
            png = _get_asset("app_icon.png")
            if os.path.exists(ico) and sys.platform == "win32":
                try: self.iconbitmap(ico)
                except Exception: pass
            elif os.path.exists(png) and _HAS_PIL:
                try:
                    img   = Image.open(png).resize((32,32), Image.LANCZOS)
                    photo = ImageTk.PhotoImage(img)
                    self.iconphoto(True, photo)
                    self._icon_photo = photo   # keep reference
                except Exception: pass

        self.header.start_eq()
        self.after(200, self.header._redraw)
        self.log("🎧  AI DJ Studio launched!", "ok")
        if self._mobile_mode:
            self.log("📱  Mobile layout active — optimised for small screens", "info")
        if not _HAS_AUDIO:
            self.log("⚠️  Audio libraries missing — "
                     "pip install yt-dlp librosa soundfile pydub", "warn")
        elif not have_ffmpeg():
            self.log("⚠️  FFmpeg not found — downloads disabled until installed.", "warn")
        else:
            self.log("✔  All audio libraries ready!", "ok")
        self.log("1️⃣  DJ Styles → 2️⃣  Search Songs → "
                 "3️⃣  Auto-Mix AI → 4️⃣  Visualizer", "info")

        self.tab_library.refresh()

    # ════════════════════════════════════════════════════════════
    #  FEATURE 4 — MOBILE / RESPONSIVE SUPPORT
    # ════════════════════════════════════════════════════════════

    def _show_splash(self):
        """Show a brief splash screen while the app initialises."""
        splash_path = _get_asset("splash_screen.png")
        if not os.path.exists(splash_path) or not _HAS_PIL:
            return
        try:
            splash_win = tk.Toplevel(self)
            splash_win.overrideredirect(True)   # borderless
            splash_win.attributes("-topmost", True)
            sw, sh = 500, 300
            x = (splash_win.winfo_screenwidth()  - sw) // 2
            y = (splash_win.winfo_screenheight() - sh) // 2
            splash_win.geometry(f"{sw}x{sh}+{x}+{y}")
            img   = Image.open(splash_path).resize((sw, sh), Image.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            lbl   = tk.Label(splash_win, image=photo, bg="#050508")
            lbl.image = photo
            lbl.pack()
            splash_win.update()
            # Close after 2.0 seconds
            self.after(2000, splash_win.destroy)
        except Exception:
            pass

    def _detect_and_apply_layout(self):
        """
        Detect screen size and apply desktop or mobile layout.
        Mobile: width < 768 px → compact fonts, smaller geometry,
                collapsed log panel, touch-friendly tap targets.
        Can also be forced with --mobile CLI flag.
        """
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()

        force_mobile = "--mobile" in sys.argv or "-m" in sys.argv
        self._mobile_mode = force_mobile or sw < 800 or sh < 600

        if self._mobile_mode:
            # Mobile: fill screen, no minimum enforced beyond tiny
            self.geometry(f"{min(sw, 480)}x{min(sh, 820)}")
            self.minsize(320, 480)
            self._ui_scale = 0.82
        else:
            # Desktop default
            self.geometry("1160x840")
            self.minsize(980, 720)
            self._ui_scale = 1.0

    def _on_resize(self, event):
        """Dynamically re-scale font sizes when window is resized."""
        if event.widget is not self:
            return
        w = event.width
        # Switch to compact mode if window gets narrow
        if w < 760 and not self._mobile_mode:
            self._mobile_mode = True
            self._apply_mobile_compact()
        elif w >= 760 and self._mobile_mode:
            self._mobile_mode = False
            self._apply_desktop_layout()

    def _apply_mobile_compact(self):
        """Shrink tab font + log panel height for narrow windows."""
        try:
            s = ttk.Style(self)
            s.configure("TNotebook.Tab",
                        padding=[8, 5],
                        font=("Trebuchet MS", 8, "bold"))
            self.log_panel.text.configure(height=3)
        except Exception:
            pass

    def _apply_desktop_layout(self):
        """Restore full desktop font sizes."""
        try:
            s = ttk.Style(self)
            s.configure("TNotebook.Tab",
                        padding=[16, 8],
                        font=("Trebuchet MS", 10, "bold"))
            self.log_panel.text.configure(height=5)
        except Exception:
            pass

    # ════════════════════════════════════════════════════════════
    #  TTK THEME
    # ════════════════════════════════════════════════════════════

    def _apply_ttk_theme(self):
        s = ttk.Style(self)
        s.theme_use("clam")
        # Scale base font for mobile
        base_size = 9 if self._mobile_mode else 10
        tab_size  = 8 if self._mobile_mode else 10
        s.configure(".",
            background=P["panel"], foreground=P["text"],
            troughcolor=P["border"], fieldbackground=P["card"],
            font=("Segoe UI", base_size))
        s.configure("TNotebook",     background=P["void"],  borderwidth=0)
        s.configure("TNotebook.Tab",
                    background=P["card"], foreground=P["muted"],
                    padding=[8 if self._mobile_mode else 16,
                             5 if self._mobile_mode else 8],
                    font=("Trebuchet MS", tab_size, "bold"))
        s.map("TNotebook.Tab",
              background=[("selected", P["panel"])],
              foreground=[("selected", P["text"])])
        s.configure("TScrollbar",    background=P["card"],
                    troughcolor=P["void"], arrowcolor=P["muted"],
                    borderwidth=0)
        s.configure("Vertical.TScrollbar",
                    width=10 if self._mobile_mode else 7)

    # ════════════════════════════════════════════════════════════
    #  NOTEBOOK — all 8 tabs
    # ════════════════════════════════════════════════════════════

    def _build_notebook(self):
        pad = 4 if self._mobile_mode else 10
        self.nb = ttk.Notebook(self)
        self.nb.pack(fill=tk.BOTH, expand=True,
                     padx=pad, pady=(4, 2))

        # Original 5 tabs
        self.tab_dj         = DJStylesTab(self.nb,       self)
        self.tab_search     = SearchTab(self.nb,         self)
        self.tab_library    = LibraryTab(self.nb,        self)
        self.tab_mix        = MixStudioTab(self.nb,      self)
        self.tab_auto       = AutoMixTab(self.nb,        self)
        # New 3 tabs
        self.tab_visualizer = VisualizerTab(self.nb,     self)
        self.tab_playlists  = PlaylistManagerTab(self.nb,self)
        self.tab_battle     = DJBattleTab(self.nb,       self)

        for frame, label in [
            (self.tab_dj,         "🎤  DJ Styles"),
            (self.tab_search,     "🔍  Search"),
            (self.tab_library,    "📂  Library"),
            (self.tab_mix,        "🎚  Mix Studio"),
            (self.tab_auto,       "🤖  Auto-Mix"),
            (self.tab_visualizer, "📊  Visualizer"),
            (self.tab_playlists,  "💾  Playlists"),
            (self.tab_battle,     "⚔️  Battle"),
        ]:
            self.nb.add(frame, text=label)

        # When switching to Playlist tab, auto-sync from Auto-Mix
        self.nb.bind("<<NotebookTabChanged>>", self._on_tab_change)

    def _on_tab_change(self, _=None):
        idx = self.nb.index(self.nb.select())
        if idx == self.TAB_PLAYLISTS:
            self.tab_playlists.sync_from_auto_tab()
            self.tab_playlists.refresh()
        elif idx == self.TAB_VISUALIZER:
            # Auto-start visualizer when tab opened
            if not self.tab_visualizer._running:
                self.tab_visualizer._toggle()

    # ════════════════════════════════════════════════════════════
    #  APP-WIDE EVENT HANDLERS
    # ════════════════════════════════════════════════════════════

    def on_dj_selected(self, dj: Dict):
        self.selected_dj = dj
        self.header.set_status(
            f"DJ Style: {dj['emoji']} {dj['name']} — "
            f"{dj['params']['energy'].upper()} energy")
        self.tab_mix.update_dj(dj)
        self.tab_auto.update_dj()
        self.tab_dj.refresh_banner()
        self.tab_visualizer.update_dj(dj)
        self.log(f"🎤 DJ Style: {dj['name']} ({dj['genre']})", "ok")

    def add_to_playlist(self, path: str):
        self.tab_auto.add_track(path)
        self.nb.select(self.TAB_AUTO)
        self.log(f"➕ Added to playlist: {os.path.basename(path)}", "info")

    def refresh_library(self):
        self.tab_library.refresh()

    def log(self, msg: str, level: str = "info"):
        self.log_panel.log(msg, level)
        self.header.set_status(msg[:90])

    # ════════════════════════════════════════════════════════════
    #  WORKER POLLING
    # ════════════════════════════════════════════════════════════

    def _poll_worker(self):
        try:
            while True:
                status, payload, callback = self.worker.q.get_nowait()
                if status == "ok":
                    if callback:
                        try:
                            callback(payload)
                        except Exception as e:
                            self.log(f"⚠️  Callback error: {e}", "err")
                else:
                    self.log(f"❌  {payload}", "err")
        except queue.Empty:
            pass
        self.after(250, self._poll_worker)


# ═══════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════
def main():
    """
    Launch AI DJ Studio.
    Optional CLI flags:
      --mobile  / -m   Force mobile layout (compact, small screen)
    """
    if not _HAS_AUDIO:
        print("⚠️  Some audio packages are missing.")
        print("    Run: pip install yt-dlp librosa soundfile pydub")
        print("    The UI will still launch — audio features disabled.")
    if _HAS_AUDIO and not have_ffmpeg():
        print("⚠️  FFmpeg not found. Install it and add to PATH.")
    if "--mobile" in sys.argv or "-m" in sys.argv:
        print("📱  Mobile layout mode enabled.")
    app = AIDJStudio()
    app.mainloop()


if __name__ == "__main__":
    main()
