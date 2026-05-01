#!/usr/bin/env python3
"""
spotify-lyrics-vis — Big ASCII word-by-word lyrics synced to Spotify
Requires: playerctl, syncedlyrics
"""

import subprocess
import time
import re
import sys
import signal
import threading
import shutil

# ── ASCII block font (5 rows tall) ────────────────────────────────────────────
FONT = {
    'A': ['▄█▄','█▀█','███','█ █','█ █'],
    'B': ['██▄','█▀█','██▀','█ █','███'],
    'C': ['▄██','█  ','█  ','█  ','▀██'],
    'D': ['██▄','█ █','█ █','█ █','██▀'],
    'E': ['███','█  ','██▀','█  ','███'],
    'F': ['███','█  ','██▀','█  ','█  '],
    'G': ['▄██','█  ','█▄█','█ █','▀██'],
    'H': ['█ █','█ █','███','█ █','█ █'],
    'I': ['███',' █ ',' █ ',' █ ','███'],
    'J': ['███','  █','  █','█ █','▀█▀'],
    'K': ['█ █','█▄▀','██ ','█▄▀','█ █'],
    'L': ['█  ','█  ','█  ','█  ','███'],
    'M': ['█▄█','███','█ █','█ █','█ █'],
    'N': ['██▄','█▀█','█ █','█ █','█ █'],
    'O': ['▄█▄','█ █','█ █','█ █','▀█▀'],
    'P': ['██▄','█ █','██▀','█  ','█  '],
    'Q': ['▄█▄','█ █','█ █','█▄█','  █'],
    'R': ['██▄','█ █','██▀','█▄▀','█ █'],
    'S': ['▄██','█  ','▀█▄','  █','██▀'],
    'T': ['███',' █ ',' █ ',' █ ',' █ '],
    'U': ['█ █','█ █','█ █','█ █','▀█▀'],
    'V': ['█ █','█ █','█ █','▀█▀',' █ '],
    'W': ['█ █','█ █','█ █','███','█▄█'],
    'X': ['█ █','▀█▀',' █ ','▀█▀','█ █'],
    'Y': ['█ █','▀█▀',' █ ',' █ ',' █ '],
    'Z': ['███','  █',' █ ','█  ','███'],
    '0': ['▄█▄','█ █','█ █','█ █','▀█▀'],
    '1': [' █ ','▄█ ',' █ ',' █ ','███'],
    '2': ['▄█▄','  █','▄█▀','█  ','███'],
    '3': ['██▀','  █','▀█▄','  █','██▀'],
    '4': ['█ █','█ █','███','  █','  █'],
    '5': ['███','█  ','██▄','  █','██▀'],
    '6': ['▄██','█  ','███','█ █','▀█▀'],
    '7': ['███','  █',' █ ',' █ ',' █ '],
    '8': ['▄█▄','█ █','▀█▀','█ █','▀█▀'],
    '9': ['▄█▄','█ █','▀██','  █','██▀'],
    "'":[' █ ',' █ ','   ','   ','   '],
    '\u2019':['   ','   ','   ',' █ ',' █ '],
    '\u2018':[' █ ',' █ ','   ','   ','   '],
    ',': ['   ','   ','   ',' ▄ ',' █ '],
    '.': ['   ','   ','   ','   ',' █ '],
    '!': [' █ ',' █ ',' █ ','   ',' █ '],
    '?': ['▄█▄','  █',' █ ','   ',' █ '],
    '-': ['   ','   ','███','   ','   '],
    ' ': ['   ','   ','   ','   ','   '],
    '_': ['   ','   ','   ','   ','███'],
    '&': ['▄█ ','█ █','▀█ ','█ █','▀██'],
    ':': ['   ',' █ ','   ',' █ ','   '],
}

ACCENT_MAP = {
    'Á':'A','À':'A','Â':'A','Ã':'A','Ä':'A','Å':'A',
    'á':'A','à':'A','â':'A','ã':'A','ä':'A','å':'A',
    'É':'E','È':'E','Ê':'E','Ë':'E',
    'é':'E','è':'E','ê':'E','ë':'E',
    'Í':'I','Ì':'I','Î':'I','Ï':'I',
    'í':'I','ì':'I','î':'I','ï':'I',
    'Ó':'O','Ò':'O','Ô':'O','Õ':'O','Ö':'O',
    'ó':'O','ò':'O','ô':'O','õ':'O','ö':'O',
    'Ú':'U','Ù':'U','Û':'U','Ü':'U',
    'ú':'U','ù':'U','û':'U','ü':'U',
    'Ç':'C','ç':'C',
    'Ñ':'N','ñ':'N',
}

# ANSI
C_CYAN  = '\033[96m'
C_GRAY  = '\033[90m'
C_RESET = '\033[0m'
C_BOLD  = '\033[1m'
C_DIM   = '\033[2m'

ANSI_RE = re.compile(r'\033\[[0-9;]*m')

# ── Config ─────────────────────────────────────────────────────────────────────
ACTIVE_COLOR  = C_CYAN
CHAR_SPACING  = 1
SYNC_INTERVAL = 0.6
OFFSET = 0.1

# ── Terminal control ───────────────────────────────────────────────────────────
def write(s):
    sys.stdout.write(s)


def flush():
    sys.stdout.flush()

def clear_screen_fast():
    write('\033[2J\033[H')

def hide_cursor():
    write('\033[?25l')
    flush()

def show_cursor():
    write('\033[?25h')
    flush()

def get_term():
    return shutil.get_terminal_size((120, 40))

# ── Font rendering ─────────────────────────────────────────────────────────────
def normalize(ch):
    return ACCENT_MAP.get(ch, ch.upper())

_render_cache = {}

def render_word(word):
    if word in _render_cache:
        return _render_cache[word]
    rows = [''] * 5
    for i, ch in enumerate(word):
        glyph = FONT.get(normalize(ch), FONT[' '])
        for r in range(5):
            rows[r] += glyph[r]
            if i < len(word) - 1:
                rows[r] += ' ' * CHAR_SPACING
    colored = [f"{C_BOLD}{ACTIVE_COLOR}{row}{C_RESET}" for row in rows]
    _render_cache[word] = colored
    return colored

def center_block(rows, term_w, term_h):
    visible_w = len(ANSI_RE.sub('', rows[0]))
    pad = max(0, (term_w - visible_w) // 2)
    top = max(0, (term_h - 5) // 2)
    return top, [' ' * pad + r for r in rows]

# ── LRC parsing ────────────────────────────────────────────────────────────────
_LRC_RE = re.compile(r'\[(\d+):(\d+(?:\.\d+)?)\](.*)')

def parse_lrc(lrc_text):
    lines = []
    for line in lrc_text.splitlines():
        m = _LRC_RE.match(line.strip())
        if m:
            ts = int(m.group(1)) * 60 + float(m.group(2))
            text = m.group(3).strip()
            if text:
                lines.append((ts, text))
    lines.sort(key=lambda x: x[0])
    return lines

# ── Playerctl ──────────────────────────────────────────────────────────────────
def _pctl(*args):
    try:
        return subprocess.check_output(
            ['playerctl', '--player=spotify'] + list(args),
            stderr=subprocess.DEVNULL, timeout=1
        ).decode().strip()
    except Exception:
        return ''

def get_track():
    artist = _pctl('metadata', 'artist')
    title  = _pctl('metadata', 'title')
    return artist, title

def get_pos():
    try:
        return float(_pctl('position'))
    except Exception:
        return 0.0

def get_status():
    return _pctl('status').lower()

# ── Position tracker ───────────────────────────────────────────────────────────
class Tracker:
    def __init__(self):
        self._pos     = 0.0
        self._ts      = time.monotonic()
        self._playing = False
        self._lock    = threading.Lock()
        self._stop    = False
        threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self):
        while not self._stop:
            status  = get_status()
            playing = status == 'playing'
            pos     = get_pos()
            with self._lock:
                self._pos     = pos
                self._ts      = time.monotonic()
                self._playing = playing
            time.sleep(SYNC_INTERVAL)

    def get(self):
        with self._lock:
            if self._playing:
                return self._pos + (time.monotonic() - self._ts)
            return self._pos

    def playing(self):
        with self._lock:
            return self._playing

    def stop(self):
        self._stop = True

# ── Track watcher ──────────────────────────────────────────────────────────────
class Watcher:
    def __init__(self):
        self._artist = ''
        self._title  = ''
        self._lock   = threading.Lock()
        self._stop   = False
        threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self):
        while not self._stop:
            a, t = get_track()
            with self._lock:
                self._artist = a
                self._title  = t
            time.sleep(2.5)

    def get(self):
        with self._lock:
            return self._artist, self._title

    def stop(self):
        self._stop = True

# ── Lyrics fetch ───────────────────────────────────────────────────────────────
def fetch_lyrics(artist, title):
    try:
        import syncedlyrics
        return syncedlyrics.search(f"{title} {artist}") or None
    except Exception:
        return None

# ── Display ────────────────────────────────────────────────────────────────────
_last_word = None

def show_word(word, term_w, term_h):
    global _last_word
    if word == _last_word:
        return
    _last_word = word
    rows = render_word(word)
    top, centered = center_block(rows, term_w, term_h)
    clear_screen_fast()
    write('\n' * top)
    write('\n'.join(centered))
    write('\n')
    flush()

def show_status(msg, term_w, term_h):
    global _last_word
    _last_word = None
    clear_screen_fast()
    pad = max(0, (term_w - len(msg)) // 2)
    top = max(0, term_h // 2)
    write('\n' * top)
    write(' ' * pad + C_DIM + C_GRAY + msg + C_RESET + '\n')
    flush()

# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    hide_cursor()
    tracker = Tracker()
    watcher = Watcher()

    def cleanup(*_):
        show_cursor()
        clear_screen_fast()
        flush()
        tracker.stop()
        watcher.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT,  cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    cur_artist = ''
    cur_title  = ''
    lines      = []
    fetching   = False

    show_status('♪  Aguardando Spotify...', 80, 24)
    time.sleep(2.8)

    while True:
        term_w, term_h = get_term()
        artist, title  = watcher.get()

        if not artist and not title:
            show_status('⏸  Spotify não encontrado', term_w, term_h)
            time.sleep(1)
            continue

        if (artist != cur_artist or title != cur_title) and not fetching:
            cur_artist = artist
            cur_title  = title
            lines      = []
            _render_cache.clear()
            show_status(f'♪  {artist} — {title}', term_w, term_h)

            def _fetch(a=artist, t=title):
                nonlocal lines, fetching
                fetching = True
                lrc = fetch_lyrics(a, t)
                lines = parse_lrc(lrc) if lrc else []
                fetching = False

            threading.Thread(target=_fetch, daemon=True).start()
            time.sleep(0.2)
            continue

        if fetching:
            show_status(f'⟳  Buscando: {cur_title}', term_w, term_h)
            time.sleep(0.25)
            continue

        if not lines:
            show_status(f'✗  Sem letras — {cur_title}', term_w, term_h)
            time.sleep(2)
            continue

        if not tracker.playing():
            show_status('⏸  Pausado', term_w, term_h)
            time.sleep(0.5)
            continue

        pos = tracker.get() + OFFSET

        # Binary search for current line
        lo, hi, cur_idx = 0, len(lines) - 1, 0
        while lo <= hi:
            mid = (lo + hi) // 2
            if lines[mid][0] <= pos:
                cur_idx = mid
                lo = mid + 1
            else:
                hi = mid - 1

        ts_start, line_text = lines[cur_idx]
        ts_end = lines[cur_idx + 1][0] if cur_idx + 1 < len(lines) else ts_start + 4.0

        words = line_text.split()
        if not words:
            time.sleep(0.03)
            continue

        per_word = (ts_end - ts_start) / len(words)
        elapsed  = pos - ts_start
        word_idx = max(0, min(int(elapsed / per_word), len(words) - 1))
        current_word = words[word_idx]

        show_word(current_word, term_w, term_h)

        # Sleep precisely until next word boundary
        next_ts    = ts_start + (word_idx + 1) * per_word
        sleep_time = max(0.02, min(next_ts - tracker.get() - 0.005, 0.2))
        time.sleep(sleep_time)

if __name__ == '__main__':
    main()
