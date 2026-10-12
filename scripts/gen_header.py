#!/usr/bin/env python3
"""Decrypt-typing header for the Bisiaux-dev GitHub profile README (dark + light SVG).

Each line is typed left to right by a cursor. Every newly revealed character first
flickers through random glyphs, then locks onto the real letter with a short flash
("eclair") that fades to the settled colour. The line holds while the cursor blinks,
then the cursor backspaces it away, each character dissolving into one last ghost glyph.

Pure CSS @keyframes, no script, no external resource (no webfont): the SVG keeps
animating when shown through <img>/<picture> on GitHub (camo proxy) in Chrome, Firefox
and Safari. Every character is its own <text>, centred in a fixed-width cell, so the
layout does not depend on which monospace font the viewer has.

Animation model (keeps the CSS small): every timed element shares one keyframe set per
role and is put in phase with a negative animation-delay.
  - scramble glyph : `b`   visible BLIP seconds from its start
  - ghost glyph    : `gh`  visible GHOST seconds from the moment its char is erased
  - locked char    : `on`  (opacity, flash -> settle fill) opens the char at lock time,
                     `off` (fill-opacity) closes it at erase time. Two different
                     properties, so the char is visible only where both windows agree.
  - cursor         : `cm`  position (steps() while typing / erasing), `bk` blink.
The cursor never disappears: between two lines it waits, solid, at the start of the next
one. The whole timeline is phase-shifted (PHASE) so that 0 s falls inside the hold of the
name: the first frame, which is all that a non-animating renderer (thumbnail, preview,
headless screenshot) shows, reads "Hi, I'm Pierre" with its cursor, never an empty box.

Layout: the first line (the name) is centred; the other lines share one left edge
(centred on their mean width), so the cursor starts them from the same point.

Python 3 standard library only. Output is deterministic (fixed seed). Both SVGs are
built and checked first; nothing is written if a check fails.
    python gen_header.py --out DIR      -> DIR/header-dark.svg, DIR/header-light.svg
"""
import argparse
import os
import random
from xml.sax.saxutils import escape

# ---------------------------------------------------------------- content
LINES = [
    "Hi, I'm Pierre",
    "Python · JavaScript · TypeScript developer",
    "Building APIs with Node.js, Express & Next.js",
    "Automating with Notion API & GitHub Actions",
]
ACCENT = (0, "Pierre")          # (line, word) drawn in the accent colour
# prefers-reduced-motion: one static line that still carries the main facts
STATIC_LINE = "Hi, I'm Pierre · Python/JS/TS developer"
GLYPHS = "!<>-_\\/[]{}=+*^?#%01ABCDEF"
SEED = 0xB15A                   # fixed seed -> stable output between runs

TITLE = "Hi, I'm Pierre: Python, JavaScript and TypeScript developer"
DESC = ("Animated terminal-style header. Each line decrypts from random glyphs into: "
        + " / ".join(LINES) + ".")

# ---------------------------------------------------------------- geometry
W, H = 600, 60
BASELINE = 37
CW = 12.0                       # cell width (user units), 45 chars -> 540
FONT_SIZE = 20
# 'SF Mono' cannot be picked by name from web content on macOS: ui-monospace gets it there
FONT_STACK = ("'JetBrains Mono','Cascadia Code',Consolas,'SF Mono',ui-monospace,Menlo,"
              "'Liberation Mono',monospace")
# cursor, relative to the right boundary of the last typed cell (the gap keeps the bar
# off the last glyph even at phone width, where 1 unit is about 0.55 px)
CUR_X, CUR_W = 3.0, 2.5         # bar
HALO_X, HALO_W = 0.25, 8.0      # soft halo around the bar
EDGE = 8                        # minimum free margin on both sides of the viewBox

# ---------------------------------------------------------------- timing (s)
TYPE = 0.048                    # cursor advance per character
BLIP = 0.07                     # one scramble glyph (about 14 Hz: reads as decrypt, not strobe)
SCRAMBLE = (2, 3, 3, 4)         # glyphs shown before a character locks
FLASH = 0.34                    # flash colour -> settled colour fade
HOLD_FIRST = 3.4                # the name holds longer: it is the line people must read
HOLD = 2.0                      # other lines: HOLD + HOLD_PER_CHAR * n after the last lock
HOLD_PER_CHAR = 0.012
ERASE = 0.018                   # backspace per character
GHOST = 0.10                    # ghost glyph left by an erased character
PRE = 0.70                      # new line: the cursor waits (solid) before typing starts
POST = 0.15                     # cursor rests at the line start after erasing
BLINK = 0.53                    # half period of the cursor blink
FIRST_LEFT = 2.2                # first frame: name settled, this much of its hold left

# ---------------------------------------------------------------- themes
# Tokens measured on the avatar (see README header comment). Dark = transparent on
# GitHub #0d1117 / dimmed #22272e; light = transparent on #ffffff.
# The lock flash is the "brightest" moment of each theme: towards eclair on dark, towards
# a deeper violet (never black) on white, so both themes show the same effect.
THEMES = {
    "dark": dict(
        bgs=("#0d1117", "#22272e"),
        settle="#e3b7e6",         # glow
        accent="#fbd4ff",         # eclair
        flash="#fbd4ff",          # eclair flash on lock ...
        accent_flash="#ffffff",   # ... white spark for the already-bright accent
        scr=("#a87fb0", "#8f6a99"),   # mauve, lilas: dimmer than the locked text
        ghost="#765082",          # violet
        cursor="#fbd4ff",
        halo="#a87fb0", halo_op=0.30,
    ),
    "light": dict(
        bgs=("#ffffff",),
        settle="#765082",         # violet
        accent="#533861",         # violet profond
        flash="#533861",          # violet profond flash, fades to violet
        accent_flash="#302040",   # aubergine flash for the already-deep accent
        scr=("#8f6a99", "#a87fb0"),   # lilas, mauve: lighter than the locked text
        ghost="#c39bc8",          # midpoint mauve/glow, decorative only
        cursor="#533861",
        halo="#e3b7e6", halo_op=0.55,
    ),
}


# ---------------------------------------------------------------- helpers
def check(ok, msg):
    """Validation that survives `python -O` (unlike assert)."""
    if not ok:
        raise SystemExit("gen_header: " + msg)


def luminance(hex_color):
    h = hex_color.lstrip("#")
    out = []
    for i in (0, 2, 4):
        c = int(h[i:i + 2], 16) / 255
        out.append(c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4)
    return 0.2126 * out[0] + 0.7152 * out[1] + 0.0722 * out[2]


def contrast(a, b):
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def num(v, nd=3):
    s = f"{v:.{nd}f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def centred_x0(n):
    return (W - n * CW) / 2


def line_x0s():
    """Line 0 centred; the others share one left edge centred on their mean width."""
    rest = [len(t) for t in LINES[1:]]
    xs = [centred_x0(len(LINES[0]))]
    if rest:
        x = centred_x0(sum(rest) / len(rest))
        x = min(x, W - EDGE - (HALO_X + HALO_W) - max(rest) * CW)   # cursor stays inside
        xs += [x] * len(rest)
    return xs


# ---------------------------------------------------------------- timeline
def build_timeline():
    rng = random.Random(SEED)
    t = 0.0
    lines = []
    for li, (text, x0) in enumerate(zip(LINES, line_x0s())):
        n = len(text)
        gs = t                                  # line slot start (cursor jumps here)
        ts = gs + PRE                           # typing starts
        accent_idx = set()
        if ACCENT[0] == li:
            p = text.index(ACCENT[1])
            accent_idx = set(range(p, p + len(ACCENT[1])))
        chars = []
        for i, ch in enumerate(text):
            typed = ts + i * TYPE
            c = dict(i=i, ch=ch, x=x0 + (i + 0.5) * CW, typed=typed,
                     accent=i in accent_idx, glyphs=[])
            if ch != " ":
                k = rng.choice(SCRAMBLE)
                prev = None
                for j in range(k):
                    pool = [g for g in GLYPHS if g != prev and g != ch]
                    g = rng.choice(pool)
                    prev = g
                    c["glyphs"].append((g, typed + j * BLIP, rng.random() < 0.28))
                c["lock"] = typed + k * BLIP
                c["ghost"] = rng.choice([g for g in GLYPHS if g != ch])
            chars.append(c)
        hold_start = max(c.get("lock", 0) for c in chars)
        te = hold_start + (HOLD_FIRST if li == 0 else HOLD + HOLD_PER_CHAR * n)
        for c in chars:
            c["erase"] = te + (n - 1 - c["i"]) * ERASE
        erase_end = te + n * ERASE
        line_end = erase_end + POST
        lines.append(dict(text=text, n=n, x0=x0, gs=gs, ts=ts, type_end=ts + n * TYPE,
                          hold_start=hold_start, te=te, erase_end=erase_end,
                          line_end=line_end, chars=chars))
        t = line_end
    return lines, t


def blink_keys(lines):
    """Cursor opacity keyframes (time, 0/1): solid from the start of each line slot through
    typing, blinking during the hold, solid again while erasing."""
    bk = []
    for L in lines:
        bk.append((L["gs"], 1))
        t, on = L["hold_start"] + BLINK, 0
        while t < L["te"] - 0.12:
            bk.append((t, on))
            t += BLINK
            on = 1 - on
        bk.append((L["te"], 1))
    return bk


def cursor_on(bk, t):
    state = 1
    for k, o in bk:
        if k <= t:
            state = o
    return state


def first_frame(lines):
    """Cycle time shown at 0 s: inside the name's hold, after its last flash, cursor lit."""
    return lines[0]["te"] - FIRST_LEFT


# ---------------------------------------------------------------- svg
def build_svg(theme, lines, T, phase):
    th = THEMES[theme]
    pct = lambda s: num(100 * s / T, 3) + "%"

    def delay(s):
        """animation-delay that puts an event at cycle time s in phase: 0 s shows `phase`."""
        d = (phase - s) % T
        return "-" + num(d, 3) + "s" if d > 1e-9 else "0s"

    locked = [c for L in lines for c in L["chars"] if "lock" in c]
    # `on` window must reach the erase; `off` window must cover what is left of `on`
    D = max(c["erase"] - c["lock"] for c in locked) + 0.05
    Hf = max(c["lock"] + D - c["erase"] for c in locked) + 0.05
    for c in locked:
        check(c["erase"] + Hf < c["lock"] + T - 0.02, "off window overlaps the next lock")
    check(FLASH < D, "flash longer than the lock window")

    # ---- cursor position keyframes
    cm = []   # (time, x, timing)
    for L in lines:
        x0, n = L["x0"], L["n"]
        cm.append((L["gs"], x0, "step-end"))
        cm.append((L["ts"], x0, f"steps({n},start)"))
        cm.append((L["type_end"], x0 + n * CW, "step-end"))
        cm.append((L["te"], x0 + n * CW, f"steps({n},start)"))
        cm.append((L["erase_end"], x0, "step-end"))
    cm_css = []
    last = -1.0
    for t, x, tf in cm:
        check(t > last + 1e-6, "cursor keyframes must be strictly increasing")
        last = t
        cm_css.append(f"{pct(t)}{{transform:translateX({num(x, 2)}px);"
                      f"animation-timing-function:{tf}}}")
    cm_css.append(f"100%{{transform:translateX({num(lines[0]['x0'], 2)}px)}}")

    # ---- cursor blink keyframes (solid while typing / erasing)
    bk_css = "".join(f"{pct(t)}{{opacity:{o}}}" for t, o in blink_keys(lines))

    Ts = num(T, 3) + "s"
    css = f"""
text{{font-family:{FONT_STACK};font-size:{FONT_SIZE}px;font-weight:500;text-anchor:middle}}
.l text{{fill:{th['settle']};opacity:0;animation:on {Ts} step-end infinite,off {Ts} step-end infinite}}
.l .n{{fill:{th['accent']};font-weight:700;animation-name:onn,off}}
.s text{{fill:{th['scr'][0]};opacity:0;animation:b {Ts} step-end infinite}}
.s .t{{fill:{th['scr'][1]}}}
.g text{{fill:{th['ghost']};opacity:0;animation:gh {Ts} step-end infinite}}
.cx{{animation:cm {Ts} step-end {delay(0)} infinite}}
.cb{{animation:bk {Ts} step-end {delay(0)} infinite}}
.st{{display:none}}
@media (prefers-reduced-motion:reduce){{.a{{display:none}}.st{{display:inline}}}}
@keyframes b{{0%{{opacity:1}}{pct(BLIP)}{{opacity:0}}}}
@keyframes gh{{0%{{opacity:1}}{pct(GHOST)}{{opacity:0}}}}
@keyframes on{{0%{{opacity:1;fill:{th['flash']};animation-timing-function:ease-out}}{pct(FLASH)}{{opacity:1;fill:{th['settle']};animation-timing-function:step-end}}{pct(D)}{{opacity:0}}}}
@keyframes onn{{0%{{opacity:1;fill:{th['accent_flash']};animation-timing-function:ease-out}}{pct(FLASH)}{{opacity:1;fill:{th['accent']};animation-timing-function:step-end}}{pct(D)}{{opacity:0}}}}
@keyframes off{{0%{{fill-opacity:0}}{pct(Hf)}{{fill-opacity:1}}}}
@keyframes cm{{{''.join(cm_css)}}}
@keyframes bk{{{bk_css}}}
"""

    out = []
    a = out.append
    a(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
      f'viewBox="0 0 {W} {H}" role="img" aria-labelledby="t d">')
    a(f'<title id="t">{escape(TITLE)}</title>')
    a(f'<desc id="d">{escape(DESC)}</desc>')
    a("<style>" + "".join(l.strip() for l in css.strip().splitlines()) + "</style>")

    n_anim = 0
    a(f'<g class="a" transform="translate(0 {BASELINE})">')
    # scramble glyphs
    a('<g class="s">')
    for L in lines:
        for c in L["chars"]:
            for g, start, alt in c["glyphs"]:
                cls = ' class="t"' if alt else ""
                a(f'<text{cls} x="{num(c["x"], 1)}" style="animation-delay:{delay(start)}">'
                  f'{escape(g)}</text>')
                n_anim += 1
    a("</g>")
    # locked characters
    a('<g class="l">')
    for L in lines:
        for c in L["chars"]:
            if "lock" not in c:
                continue
            cls = ' class="n"' if c["accent"] else ""
            a(f'<text{cls} x="{num(c["x"], 1)}" style="animation-delay:'
              f'{delay(c["lock"])},{delay(c["erase"])}">{escape(c["ch"])}</text>')
            n_anim += 1
    a("</g>")
    # ghost glyphs left by the backspace
    a('<g class="g">')
    for L in lines:
        for c in L["chars"]:
            if "lock" not in c:
                continue
            a(f'<text x="{num(c["x"], 1)}" style="animation-delay:{delay(c["erase"])}">'
              f'{escape(c["ghost"])}</text>')
            n_anim += 1
    a("</g>")
    # cursor: halo + bar, drawn CUR_X units right of the cell boundary
    a('<g class="cx"><g class="cb">'
      f'<rect x="{num(HALO_X)}" y="-19" width="{num(HALO_W)}" height="25" rx="4" '
      f'fill="{th["halo"]}" opacity="{th["halo_op"]}"/>'
      f'<rect x="{num(CUR_X)}" y="-18" width="{num(CUR_W)}" height="23" rx="1" '
      f'fill="{th["cursor"]}"/>'
      "</g></g>")
    n_anim += 2
    a("</g>")

    # static fallback (prefers-reduced-motion): one settled line, cursor at rest
    n = len(STATIC_LINE)
    x0 = centred_x0(n)
    p = STATIC_LINE.index(ACCENT[1])
    a(f'<g class="st" transform="translate(0 {BASELINE})">')
    for i, ch in enumerate(STATIC_LINE):
        if ch == " ":
            continue
        acc = p <= i < p + len(ACCENT[1])
        fill = th["accent"] if acc else th["settle"]
        weight = ' font-weight="700"' if acc else ""
        a(f'<text x="{num(x0 + (i + 0.5) * CW, 1)}" fill="{fill}"{weight}>{escape(ch)}</text>')
    xe = x0 + n * CW
    a(f'<rect x="{num(xe + CUR_X, 2)}" y="-18" width="{num(CUR_W)}" height="23" rx="1" '
      f'fill="{th["cursor"]}"/>')
    a("</g>")
    a("</svg>")
    return "\n".join(out) + "\n", n_anim


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", default=os.path.join(
        os.path.dirname(os.path.abspath(__file__)), os.pardir, "assets"),
        help="output directory (default: ../assets next to this script)")
    args = ap.parse_args()

    lines, T = build_timeline()
    for L in lines:
        hold = L["te"] - L["hold_start"]
        check(hold >= 1.8, f"hold too short for {L['text']!r}: {hold:.2f}s")
        check(L["x0"] >= EDGE, f"line too wide: {L['text']!r}")
        check(L["x0"] + L["n"] * CW + HALO_X + HALO_W <= W - EDGE,
              f"cursor leaves the viewBox: {L['text']!r}")
    check(centred_x0(len(STATIC_LINE)) >= EDGE, "static line too wide")
    phase = first_frame(lines)
    check(phase >= lines[0]["hold_start"] + FLASH + 0.05,
          "first frame falls before the name has settled")
    check(cursor_on(blink_keys(lines), phase) == 1, "cursor off on the first frame")

    # build and check everything first, write only if every check passed
    built = {}
    for theme, th in THEMES.items():
        svg, n_anim = build_svg(theme, lines, T, phase)
        size = len(svg.encode("utf-8"))
        check(size <= 150 * 1024, f"header-{theme}.svg too big: {size} B")
        crs = []
        for bg in th["bgs"]:
            for role in ("settle", "accent"):
                cr = contrast(th[role], bg)
                check(cr >= 4.5, f"{theme} {role} on {bg}: {cr:.2f} < 4.5")
                crs.append(f"{role}/{bg} {cr:.2f}")
            crs.append(f"scramble/{bg} {contrast(th['scr'][0], bg):.2f}")
        built[theme] = (svg, size, n_anim, crs)

    os.makedirs(args.out, exist_ok=True)
    for theme, (svg, size, n_anim, crs) in built.items():
        path = os.path.join(args.out, f"header-{theme}.svg")
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            f.write(svg)
        os.replace(tmp, path)
        print(f"{os.path.normpath(path)}: {size} B, {n_anim} animated nodes, "
              f"cycle {T:.2f}s, first frame at {phase:.2f}s | " + ", ".join(crs))
    for L in lines:
        print(f"  {L['text']!r}: n={L['n']} x0={L['x0']:.1f} slot {L['gs']:.2f}-"
              f"{L['line_end']:.2f}s, hold {L['te'] - L['hold_start']:.2f}s")


if __name__ == "__main__":
    main()
