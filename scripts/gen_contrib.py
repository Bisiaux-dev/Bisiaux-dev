#!/usr/bin/env python3
"""Ciel nocturne : le graphe de contributions GitHub dessiné comme un ciel de nuit.

Chaque jour actif devient une étoile placée à (semaine, jour de la semaine) ; sa taille et son
éclat suivent le nombre de contributions (échelle log). Les jours vides sont une poussière
discrète. Une trace de lumière (la DA de l'avatar) traverse les étoiles dans l'ordre
chronologique, en reliant au plus une par semaine : une comète la parcourt, allume chaque
étoile au passage (reliée ou non), la trace reste allumée un instant puis s'éteint, et le
cycle recommence (14 s).
Le curseur clignotant de l'en-tête (même barre, même halo, même rythme) marque aujourd'hui.
Aucune grille, aucun texte, aucun total.

Sortie : contrib-dark.svg et contrib-light.svg (fond transparent, viewBox 900x180, sans JS ni
ressource externe : <style> + @keyframes pour le scintillement et le curseur, SMIL pour tout
ce qui doit rester synchronisé : comète, trace, éclats). prefers-reduced-motion : le CSS
s'arrête et les calques SMIL (.mo) sont masqués au profit d'une version fixe (.st) : trace
allumée, étoiles, curseur plein.

Cas limites :
  - 0 contribution  -> une étoile filante traverse un ciel de poussière (jamais de cadre vide)
  - 1 jour actif    -> une étoile filante se pose sur l'étoile
  - trace           -> au plus une étoile reliée par semaine (la plus brillante, en évitant
                        les zigzags : programmation dynamique) : la lumière avance toujours
                        vers la droite, même après une rafale de jours actifs. Elle ne dessine
                        que là où il y a eu de l'activité (rien avant la 1re ni après la
                        dernière) ; les autres étoiles s'allument quand la comète les longe
  - année dense     -> tailles réduites selon la densité ; semaines reliées plus espacées
  - jour record     -> échelle log + plancher : les petits jours restent visibles
  - réponse vide, illisible ou en erreur -> sortie en erreur, aucun fichier écrit

Bibliothèque standard uniquement. Sortie déterministe : même calendrier -> mêmes octets
(tout l'aléa vient d'un hachage SHA-256 de la date). Les deux SVG sont construits avant
d'écrire quoi que ce soit, puis remplacés (os.replace) : jamais de paire dépareillée.

Usage :
  GITHUB_TOKEN=... python gen_contrib.py --out dist [--user Bisiaux-dev]   (repli : GH_TOKEN)
  python gen_contrib.py --from-json calendar.json --out dist     # sans réseau (tests)
  python gen_contrib.py --save-json calendar.json ...            # garde la réponse brute
  python gen_contrib.py --self-test       # calendriers synthétiques, n'écrit rien
"""

import argparse
import datetime
import hashlib
import json
import math
import os
import urllib.error
import urllib.request
from xml.sax.saxutils import escape

QUERY = (
    "query($login:String!){user(login:$login){contributionsCollection{contributionCalendar{"
    "weeks{contributionDays{date contributionCount weekday}}}}}}"
)

# --------------------------------------------------------------------------------------------
# Palette (jetons mesurés sur l'avatar)
#   nuit #0b0910 · ombre #281838 · aubergine #302040 · violet profond #533861 · violet #765082
#   lilas #8f6a99 · mauve #a87fb0 · glow #e3b7e6 · éclair #fbd4ff · givre #f6ebf7
# Thème sombre : la lumière monte vers le givre. Thème clair : carte du ciel à l'encre de nuit,
# halos et nébuleuse en glow (lilas pâle) sur blanc. Pas de texte -> pas de contrainte 4,5:1 ;
# les cœurs d'étoiles restent quand même très contrastés (éclair sur nuit, aubergine sur blanc).
# Curseur : mêmes couleurs que celui de l'en-tête (scripts/gen_header.py).
# --------------------------------------------------------------------------------------------
THEMES = {
    "dark": {
        "dust": "#a87fb0", "dust_op": (0.26, 0.52),
        "twinkle": (0.5, 0.35),       # opacité au creux du scintillement (étoiles, poussière)
        "halo": "#e3b7e6", "halo_op": 0.8,
        "core": ("#e3b7e6", "#fbd4ff", "#f6ebf7"),
        "glint": "#fbd4ff",
        "neb": ("#765082", "#533861"), "neb_op": (0.40, 0.62),
        "ghost_under": "#533861", "ghost_under_op": 0.45,
        "ghost": "#8f6a99", "ghost_op": 0.6,
        "lit_wide": "#765082", "lit_wide_op": 0.5,
        "lit": "#e3b7e6", "lit_op": 0.95,
        "tail": ("#765082", "#a87fb0", "#e3b7e6", "#fbd4ff"),
        "head_glow": "#fbd4ff", "head": "#f6ebf7",
        "flare": "#fbd4ff",
        "cursor": "#fbd4ff", "cursor_halo": "#a87fb0", "cursor_halo_op": 0.30,
    },
    "light": {
        "dust": "#8f6a99", "dust_op": (0.24, 0.46),
        "twinkle": (0.72, 0.5),       # sur blanc, une étoile d'encre qui pâlit vire au gris
        "halo": "#a87fb0", "halo_op": 0.42,
        "core": ("#765082", "#533861", "#302040"),
        "glint": "#533861",
        "neb": ("#e3b7e6", "#f6ebf7"), "neb_op": (0.30, 0.48),
        "ghost_under": "#e3b7e6", "ghost_under_op": 0.45,
        "ghost": "#a87fb0", "ghost_op": 0.75,
        "lit_wide": "#e3b7e6", "lit_wide_op": 0.85,
        "lit": "#765082", "lit_op": 0.95,
        "tail": ("#e3b7e6", "#e3b7e6", "#a87fb0", "#533861"),
        "head_glow": "#a87fb0", "head": "#302040",
        "flare": "#a87fb0",
        "cursor": "#533861", "cursor_halo": "#e3b7e6", "cursor_halo_op": 0.55,
    },
}

# Géométrie (unités du viewBox ; proportions du graphe GitHub : 53 semaines x 7 jours)
W, H = 900, 180
MX = 30                      # marge horizontale jusqu'au centre de la 1re/dernière semaine
ROW0, PY = 36, 18            # centre du dimanche, pas vertical entre deux jours
MID_Y = ROW0 + 3 * PY        # mercredi = milieu du ciel
EDGE = 1.0                   # aucun dégradé ne touche le bord du viewBox (pas de couture)

# Animation (secondes)
T = 14.0                     # durée d'un cycle complet, en boucle
A = 0.9                      # départ de la comète
EASE = (0.42, 0.0, 0.58, 1.0)
BLINK = 0.53                 # demi-période du curseur (identique à l'en-tête)

# Traits (largeurs en unités du viewBox ; ~0,92 px à 830 px de large)
GHOST_W = (3.6, 1.0)         # trace fantôme : sous-couche large, fil fin
LIT_W = (4.6, 1.6)           # trace allumée : lueur large, cœur
TAIL_W = (3.2, 2.4, 1.7, 1.25)

MAX_TRACE = 18               # étoiles reliées au plus (une par semaine au plus)
ROW_COST = 0.12              # coût d'un jour d'écart vertical entre deux étoiles reliées
LINK_BONUS = 1.0             # prime par étoile reliée (> pire écart vertical : 6 x ROW_COST)
MAX_SIDE_FLARES = 40         # étoiles non reliées qui s'allument au passage (les plus brillantes)
MAX_GLINTS = 16              # étoiles à aigrettes (toutes en dessous de ce nombre)
MAX_PULSE = 5                # aigrettes qui respirent
GLINT_V = 0.55               # aigrette anamorphique : branche verticale / horizontale
# aigrette à 4 branches, longueur 1 (mise à l'échelle par étoile)
SPARK = "M0-1C.07-.07.07-.07 1 0C.07.07.07.07 0 1C-.07.07-.07.07-1 0C-.07-.07-.07-.07 0-1Z"

MAX_BYTES = 150 * 1024


# ------------------------------------------------------------------------------ données ----

def fetch_calendar(login, token):
    body = json.dumps({"query": QUERY, "variables": {"login": login}}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={
            "Authorization": "bearer " + token,
            "Content-Type": "application/json",
            "User-Agent": "gen-contrib-ciel",
        },
    )
    try:  # jamais le jeton dans les messages
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as exc:
        raise SystemExit("GitHub GraphQL: HTTP %s %s" % (exc.code, exc.reason))
    except urllib.error.URLError as exc:
        raise SystemExit("GitHub GraphQL: network error (%s)" % exc.reason)
    except (ValueError, OSError) as exc:  # corps non JSON, coupure, délai dépassé
        raise SystemExit("GitHub GraphQL: unreadable response (%s)" % exc.__class__.__name__)


def extract_weeks(payload):
    """Accepte la réponse GraphQL brute, {"weeks": [...]}, ou directement la liste des semaines.
    Tout le reste (erreurs GraphQL, forme inconnue, calendrier vide) arrête le script."""
    if isinstance(payload, dict) and payload.get("errors"):
        raise SystemExit("GitHub GraphQL: " + "; ".join(
            str(e.get("message", "?")) if isinstance(e, dict) else str(e)
            for e in payload["errors"]))
    node = payload
    if isinstance(node, dict) and "data" in node:
        user = (node["data"] or {}).get("user")
        if user is None:
            raise SystemExit("GitHub GraphQL: user not found")
        try:
            node = user["contributionsCollection"]["contributionCalendar"]
        except (KeyError, TypeError):
            raise SystemExit("GitHub GraphQL: unexpected response shape")
    if isinstance(node, dict):
        if "weeks" not in node:
            raise SystemExit("unrecognised calendar JSON (no 'weeks')")
        node = node["weeks"]
    if not isinstance(node, list):
        raise SystemExit("unrecognised calendar JSON")
    if not node:
        raise SystemExit("empty contribution calendar (no weeks): nothing written")
    return node


def to_days(weeks):
    days = []
    try:
        for wi, week in enumerate(weeks):
            for d in week["contributionDays"]:
                days.append({
                    "w": wi,
                    "wd": int(d["weekday"]) % 7,
                    "date": str(d["date"]),
                    "n": max(0, int(d["contributionCount"])),
                })
    except (KeyError, TypeError, ValueError):
        raise SystemExit("unrecognised calendar JSON (malformed week or day)")
    if not days:
        raise SystemExit("empty contribution calendar (no days): nothing written")
    days.sort(key=lambda d: d["date"])
    return days, len(weeks)


# ---------------------------------------------------------------------------- utilitaires ----

def h01(*parts):
    """Flottant déterministe dans [0, 1) dérivé de la date (+ sel)."""
    digest = hashlib.sha256("|".join(str(p) for p in parts).encode()).digest()
    return int.from_bytes(digest[:6], "big") / float(1 << 48)


def f1(v):
    s = "%.1f" % v
    if s.endswith(".0"):
        s = s[:-2]
    return "0" if s == "-0" else s


def f2(v):
    s = ("%.2f" % v).rstrip("0").rstrip(".")
    return "0" if s in ("", "-0") else s


def f4(v):
    s = ("%.4f" % v).rstrip("0").rstrip(".")
    return "0" if s in ("", "-0") else s


def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def edge_room(x, y):
    """Distance au bord du viewBox le plus proche (moins la marge EDGE)."""
    return min(x, W - x, y, H - y) - EDGE


def bezier_xy(u, p1x, p1y, p2x, p2y):
    """Courbe cubic-bezier(p1, p2) de (0,0) à (1,1) au paramètre u."""
    def c(a, b):
        return 3 * a * u * (1 - u) ** 2 + 3 * b * u * u * (1 - u) + u ** 3
    return c(p1x, p2x), c(p1y, p2y)


def ease_time_for_progress(progress, spline=EASE):
    """Fraction de temps à laquelle l'easing atteint `progress` (même calcul que keySplines)."""
    lo, hi = 0.0, 1.0
    for _ in range(60):
        mid = (lo + hi) / 2
        if bezier_xy(mid, *spline)[1] < progress:
            lo = mid
        else:
            hi = mid
    return bezier_xy((lo + hi) / 2, *spline)[0]


def cubic_len(p0, c1, c2, p3, steps=240):
    total, prev = 0.0, p0
    for i in range(1, steps + 1):
        u = i / steps
        v = 1 - u
        x = v ** 3 * p0[0] + 3 * v * v * u * c1[0] + 3 * v * u * u * c2[0] + u ** 3 * p3[0]
        y = v ** 3 * p0[1] + 3 * v * v * u * c1[1] + 3 * v * u * u * c2[1] + u ** 3 * p3[1]
        total += math.hypot(x - prev[0], y - prev[1])
        prev = (x, y)
    return total


def rounded(p):
    return (float(f1(p[0])), float(f1(p[1])))


def smooth_path(points, tension=0.82):
    """Catmull-Rom centripète -> Béziers cubiques (ni boucle ni rebroussement).
    Les longueurs sont mesurées sur les points arrondis, ceux que le navigateur lit : la tête
    de la comète (animateMotion) et les traits (dashoffset) restent calés.
    Renvoie (d, longueur totale, longueur cumulée à chaque point)."""
    pts = [rounded(p) for p in points]
    n = len(pts)
    ext = [(2 * pts[0][0] - pts[1][0], 2 * pts[0][1] - pts[1][1])] + pts + \
          [(2 * pts[-1][0] - pts[-2][0], 2 * pts[-1][1] - pts[-2][1])]
    d = ["M%s %s" % (f1(pts[0][0]), f1(pts[0][1]))]
    cum = [0.0]

    def knot(a, b):
        return max(math.hypot(b[0] - a[0], b[1] - a[1]) ** 0.5, 1e-4)

    for i in range(n - 1):
        p0, p1, p2, p3 = ext[i], ext[i + 1], ext[i + 2], ext[i + 3]
        t01, t12, t23 = knot(p0, p1), knot(p1, p2), knot(p2, p3)
        m1 = [(p2[k] - p1[k]) + t12 * ((p1[k] - p0[k]) / t01 - (p2[k] - p0[k]) / (t01 + t12))
              for k in (0, 1)]
        m2 = [(p2[k] - p1[k]) + t12 * ((p3[k] - p2[k]) / t23 - (p3[k] - p1[k]) / (t12 + t23))
              for k in (0, 1)]
        c1 = rounded((p1[0] + tension * m1[0] / 3, p1[1] + tension * m1[1] / 3))
        c2 = rounded((p2[0] - tension * m2[0] / 3, p2[1] - tension * m2[1] / 3))
        d.append("C%s %s %s %s %s %s" % (f1(c1[0]), f1(c1[1]), f1(c2[0]), f1(c2[1]),
                                         f1(p2[0]), f1(p2[1])))
        cum.append(cum[-1] + cubic_len(p1, c1, c2, p2))
    return "".join(d), cum[-1], cum


# ------------------------------------------------------------------------------- scène ----

def trace_gap(weeks):
    """Plus petit écart g (en semaines) tel que les semaines actives gardées à au moins g
    semaines l'une de l'autre soient au plus MAX_TRACE. Croît doucement avec la densité."""
    active = sorted(set(weeks))
    g = 1
    while True:
        kept, prev = 0, None
        for w in active:
            if prev is None or w - prev >= g:
                kept, prev = kept + 1, w
        if kept <= MAX_TRACE:
            return g
        g += 1


def pick_trace(stars):
    """Étoiles reliées par la trace, dans l'ordre chronologique.
    Une seule règle, quel que soit le nombre d'étoiles (pas de palier) : au plus une étoile
    par semaine (les jours d'une semaine sont empilés dans une colonne : en relier deux ferait
    descendre la trace le long de la colonne puis remonter à la suivante, en se croisant),
    semaines espacées d'au moins trace_gap(), au plus MAX_TRACE, la dernière étant la plus
    récente. Parmi ces chaînes, celle qui maximise l'éclat cumulé moins un coût par jour
    d'écart vertical -> une ligne de lumière qui avance toujours vers la droite et ondule
    doucement au lieu de zigzaguer."""
    n = len(stars)
    if n == 0:
        return []
    gap = trace_gap([s["w"] for s in stars])
    # prime de lien (relier une semaine de plus vaut mieux que la sauter, sauf pour éviter un
    # pic Dim -> Sam -> Dim) + éclat + un peu de hasard (départage les ex aequo) - un léger
    # rappel vers le milieu du ciel
    score = [LINK_BONUS + s["t"] + 0.1 * h01(s["date"], "dp") - 0.03 * abs(s["y"] - MID_Y) / PY
             for s in stars]
    weeks = [s["w"] for s in stars]
    # prédécesseurs possibles de j : écart >= gap, fenêtre de ~4*gap semaines (élargie à la
    # semaine active la plus proche si l'année a un trou)
    preds = []
    for j in range(n):
        hi = j
        while hi > 0 and weeks[j] - weeks[hi - 1] < gap:
            hi -= 1
        if hi == 0:
            preds.append(range(0))
            continue
        w_lo = min(weeks[j] - 4 * gap, weeks[hi - 1])
        lo = hi
        while lo > 0 and weeks[lo - 1] >= w_lo:
            lo -= 1
        preds.append(range(lo, hi))
    neg = float("-inf")
    best = [score[:]]
    back = [[-1] * n]
    for _ in range(2, MAX_TRACE + 1):
        prev, cur, arg = best[-1], [neg] * n, [-1] * n
        for j in range(n):
            yj = stars[j]["y"]
            for i in preds[j]:
                if prev[i] == neg:
                    continue
                v = prev[i] - ROW_COST * abs(yj - stars[i]["y"]) / PY
                if v > cur[j]:
                    cur[j], arg[j] = v, i
            if arg[j] >= 0:
                cur[j] += score[j]
        best.append(cur)
        back.append(arg)
    last = n - 1
    k = max(range(len(best)), key=lambda k: (best[k][last], -k))
    chain, j = [], last
    while j >= 0:
        chain.append(stars[j])
        j = back[k][j]
        k -= 1
    return chain[::-1]


def bowed_points(nodes, px):
    """Points de passage de la trace. Entre deux nœuds éloignés (> 3 semaines), un point
    intermédiaire courbe le trait en arc, du côté qui prolonge le mouvement d'arrivée et
    annonce le suivant : la lumière coule d'un amas à l'autre au lieu d'un fil tendu.
    Renvoie (points, index de chaque nœud dans la liste)."""
    ys = [s["y"] for s in nodes]
    pts, idx = [], []
    for i, s in enumerate(nodes):
        idx.append(len(pts))
        pts.append((s["x"], s["y"]))
        if i + 1 == len(nodes):
            break
        nxt = nodes[i + 1]
        dx = nxt["x"] - s["x"]
        if dx <= 3 * px:
            continue
        vote = 0
        if i > 0:
            vote += (ys[i] > ys[i - 1]) - (ys[i] < ys[i - 1])
        if i + 2 < len(nodes):
            vote -= (ys[i + 2] > ys[i + 1]) - (ys[i + 2] < ys[i + 1])
        my = (s["y"] + nxt["y"]) / 2
        if vote == 0:  # rien n'impose de sens : on s'écarte du bord le plus proche
            vote = 1 if my < MID_Y else -1
        sag = min(0.075 * dx, 24.0) * (1 if vote > 0 else -1)
        pts.append((s["x"] + dx / 2, clamp(my + sag, ROW0 - 12, ROW0 + 6 * PY + 12)))
    return pts, idx


def along(xs, cum, x):
    """Longueur parcourue par la comète quand elle passe à l'abscisse x (xs croissants :
    une étoile reliée par semaine au plus, la trace avance toujours vers la droite)."""
    if x <= xs[0]:
        return 0.0
    for k in range(len(xs) - 1):
        if x <= xs[k + 1]:
            return cum[k] + (cum[k + 1] - cum[k]) * (x - xs[k]) / (xs[k + 1] - xs[k])
    return cum[-1]


def build_scene(days, nweeks):
    px = (W - 2 * MX) / max(nweeks - 1, 1)
    counts = [d["n"] for d in days if d["n"] > 0]
    lmax = math.log1p(max(counts + [1]))
    # densité : plus il y a d'étoiles, plus elles sont petites (un ciel dense reste lisible)
    density = len(counts) / float(max(len(days), 1))
    size = 1.0 / (1.0 + 1.4 * density)

    stars, dust = [], []
    for d in days:
        bx = MX + d["w"] * px
        by = ROW0 + d["wd"] * PY
        if d["n"] > 0:
            # éclat 0..1 : log (un record n'écrase pas le reste), courbe qui fait ressortir les
            # plus brillantes, plancher pour que le plus petit jour reste une étoile
            t = 0.12 + 0.88 * (math.log1p(d["n"]) / lmax) ** 1.35
            stars.append({
                "date": d["date"], "n": d["n"], "t": t, "w": d["w"],
                "x": bx + (h01(d["date"], "sx") - 0.5) * 0.62 * px,
                "y": by + (h01(d["date"], "sy") - 0.5) * 0.5 * PY,
            })
        else:
            dust.append({
                "x": bx + (h01(d["date"], "dx") - 0.5) * 0.9 * px,
                "y": by + (h01(d["date"], "dy") - 0.5) * 0.9 * PY,
                "r": 0.55 + 0.5 * h01(d["date"], "dr"),
                "o": h01(d["date"], "do"),
                "g": int(h01(d["date"], "dg") * 3),
            })

    # La trace ne relie que des étoiles : pas de lumière avant la première ni après la dernière.
    trace = pick_trace(stars)

    # Aujourd'hui = dernier jour du calendrier : le curseur s'y pose, juste après sa case.
    today = days[-1]
    cursor = {"x": MX + today["w"] * px + 0.5 * px + 1.5, "y": ROW0 + today["wd"] * PY}

    # Aigrettes : toutes les étoiles en année clairsemée, sinon les MAX_GLINTS plus brillantes
    # (ex aequo départagés par hachage, pour ne pas les grouper en fin d'année) ;
    # les ~1/6 plus brillantes respirent en plus.
    ranked = sorted(stars, key=lambda s: (s["n"], h01(s["date"], "rk")), reverse=True)
    n_pulse = int(clamp(round(len(stars) / 6.0), 1, MAX_PULSE))
    glints = {s["date"]: i < n_pulse for i, s in enumerate(ranked[:MAX_GLINTS])}

    # Nébuleuse : densité d'activité lissée par semaine, maxima locaux (4 max, espacés)
    weekly = [0.0] * nweeks
    for s in stars:
        weekly[s["w"]] += math.log1p(s["n"])
    sigma = 2.6
    smooth = []
    for i in range(nweeks):
        acc = 0.0
        for j in range(max(0, i - 8), min(nweeks, i + 9)):
            acc += weekly[j] * math.exp(-((i - j) ** 2) / (2 * sigma * sigma))
        smooth.append(acc)
    peak = max(smooth) if smooth else 0.0
    nebula = []
    if peak > 0:
        cands = [i for i in range(nweeks)
                 if smooth[i] > 0.2 * peak
                 and smooth[i] >= (smooth[i - 1] if i > 0 else -1)
                 and smooth[i] >= (smooth[i + 1] if i + 1 < nweeks else -1)]
        cands.sort(key=lambda i: (-smooth[i], i))
        picked = []
        for i in cands:
            if all(abs(i - j) >= 7 for j in picked):
                picked.append(i)
            if len(picked) == 4:
                break
        for i in sorted(picked):
            near = [s for s in stars if abs(s["w"] - i) <= 3]
            wsum = sum(math.log1p(s["n"]) for s in near) or 1.0
            cy = sum(s["y"] * math.log1p(s["n"]) for s in near) / wsum if near else H / 2
            k = smooth[i] / peak
            rx, ry = 80 + 50 * k, 62 + 18 * k
            x = clamp(MX + i * px, rx * 0.8, W - rx * 0.8)
            y = clamp(cy * 0.5 + (H / 2) * 0.5, H * 0.42, H * 0.58)
            nebula.append({
                "x": x, "y": y, "k": k,
                # l'ellipse tient dans le viewBox : le dégradé s'éteint avant le bord
                "rx": min(rx, x - EDGE, W - x - EDGE),
                "ry": min(ry, y - EDGE, H - y - EDGE),
            })
    else:  # aucun jour actif : une brume discrète, pour que le ciel reste habité
        nebula.append({"x": W * 0.62, "y": H / 2, "rx": 150, "ry": 70, "k": 0.45})

    return {"stars": stars, "dust": dust, "trace": trace, "glints": glints,
            "nebula": nebula, "px": px, "size": size, "cursor": cursor}


# -------------------------------------------------------------------------------- SVG ----

def keytimes(times):
    return ";".join(f4(clamp(t / T, 0.0, 1.0)) for t in times)


def render(scene, theme_name, login):
    th = THEMES[theme_name]
    stars, nodes, size = scene["stars"], scene["trace"], scene["size"]
    out = []
    o = out.append

    # --- trajectoire de la comète -------------------------------------------------------
    flares = []  # (étoile, longueur parcourue jusqu'à elle, "node" | "last" | "side")
    if len(nodes) >= 2:
        pts, idx = bowed_points(nodes, scene["px"])
        path_d, plen, cum = smooth_path(pts)
        flares = [(s, cum[i], "last" if k == len(nodes) - 1 else "node")
                  for k, (s, i) in enumerate(zip(nodes, idx))]
        # les étoiles non reliées s'allument quand la comète passe à leur verticale
        # (la trace avance toujours vers la droite : x -> longueur parcourue est monotone)
        linked = set(s["date"] for s in nodes)
        side = sorted((s for s in stars if s["date"] not in linked),
                      key=lambda s: (s["n"], h01(s["date"], "sf")), reverse=True)
        xs = [rounded(p)[0] for p in pts]
        flares += [(s, along(xs, cum, s["x"]), "side") for s in side[:MAX_SIDE_FLARES]]
        mode = "constellation"
    elif len(nodes) == 1:  # une seule étoile : une étoile filante s'y pose
        s = nodes[0]
        p0 = (s["x"] - 220 if s["x"] > 260 else s["x"] + 220, 30 if s["y"] > H / 2 else H - 30)
        mid = ((p0[0] + s["x"]) / 2, (p0[1] + s["y"]) / 2 - 18)
        path_d, plen, _ = smooth_path([p0, mid, (s["x"], s["y"])])
        flares = [(s, plen, "last")]
        mode = "meteor"
    else:  # aucun jour actif : une étoile filante traverse le ciel
        path_d, plen, _ = smooth_path([(W * 0.2, 34), (W * 0.48, 62), (W * 0.8, 120)])
        mode = "meteor"

    travel = clamp(2.4 + plen / 170.0, 2.6, 7.0) if mode == "constellation" else 2.2
    b = A + travel                # la comète arrive au bout
    c = min(b + 3.0, 11.4)        # la trace allumée commence à s'éteindre
    dfade = c + 1.6               # ... et a disparu
    spline_mid = " ".join(f2(v) for v in EASE)
    ksp = "0 0 1 1;%s;0 0 1 1" % spline_mid
    rep = 'dur="%ss" repeatCount="indefinite"' % f1(T)

    o('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d" '
      'fill="none" role="img" aria-labelledby="t">' % (W, H, W, H))
    o('<title id="t">%s</title>' % escape(
        "GitHub contributions of %s over the last year, drawn as a night sky: each star is a "
        "day of activity, a light trace runs through them in order and a cursor marks "
        "today" % login))

    # --- styles -------------------------------------------------------------------------
    # CSS : scintillement (désynchronisé par nature) et clignotement du curseur.
    # .mo = calques animés en SMIL ; .st = leur version fixe, montrée seulement si
    # l'utilisateur a demandé moins d'animations (le CSS ne peut pas suspendre le SMIL,
    # mais il peut masquer les calques qui le portent).
    css = [
        "@keyframes tw{0%%,100%%{opacity:1}50%%{opacity:%s}}" % f2(th["twinkle"][0]),
        "@keyframes ds{0%%,100%%{opacity:1}50%%{opacity:%s}}" % f2(th["twinkle"][1]),
        "@keyframes cu{0%{opacity:1}50%{opacity:0}}",
    ]
    for k, (dur, delay) in enumerate([(3.7, -0.4), (4.9, -2.1), (6.1, -3.3), (5.3, -1.2),
                                       (7.3, -5.0)]):
        css.append(".k%d{animation:tw %ss ease-in-out %ss infinite}" % (k, f1(dur), f1(delay)))
    css.append(".d1{animation:ds 6.5s ease-in-out -1s infinite}")
    css.append(".d2{animation:ds 8.3s ease-in-out -4.6s infinite}")
    css.append(".cu{animation:cu %ss step-end infinite}" % f2(2 * BLINK))
    css.append(".st{display:none}")
    css.append("@media (prefers-reduced-motion:reduce){*{animation:none!important}"
               ".mo{display:none}.st{display:inline}}")
    o("<style>%s</style>" % "".join(css))

    # --- dégradés -----------------------------------------------------------------------
    o("<defs>")
    hop = th["halo_op"] * (0.45 + 0.55 * size)
    o('<radialGradient id="hl"><stop offset="0" stop-color="%s" stop-opacity="%s"/>'
      '<stop offset=".35" stop-color="%s" stop-opacity="%s"/>'
      '<stop offset="1" stop-color="%s" stop-opacity="0"/></radialGradient>'
      % (th["halo"], f2(hop), th["halo"], f2(hop * 0.32), th["halo"]))
    o('<radialGradient id="fl"><stop offset="0" stop-color="%s" stop-opacity=".9"/>'
      '<stop offset=".3" stop-color="%s" stop-opacity=".35"/>'
      '<stop offset="1" stop-color="%s" stop-opacity="0"/></radialGradient>'
      % (th["flare"], th["flare"], th["flare"]))
    o('<radialGradient id="hg"><stop offset="0" stop-color="%s" stop-opacity=".95"/>'
      '<stop offset=".28" stop-color="%s" stop-opacity=".4"/>'
      '<stop offset="1" stop-color="%s" stop-opacity="0"/></radialGradient>'
      % (th["head_glow"], th["head_glow"], th["head_glow"]))
    for i, nb in enumerate(scene["nebula"]):
        lo, hi = th["neb_op"]
        op = lo + (hi - lo) * nb["k"]
        c0, c1 = th["neb"]
        o('<radialGradient id="n%d"><stop offset="0" stop-color="%s" stop-opacity="%s"/>'
          '<stop offset=".3" stop-color="%s" stop-opacity="%s"/>'
          '<stop offset=".62" stop-color="%s" stop-opacity="%s"/>'
          '<stop offset="1" stop-color="%s" stop-opacity="0"/></radialGradient>'
          % (i, c0, f2(op), c0, f2(op * 0.62), c1, f2(op * 0.22), c1))
    o("</defs>")

    # --- nébuleuse : respire avec le passage de la comète ----------------------------------
    nebula = "".join('<ellipse cx="%s" cy="%s" rx="%s" ry="%s" fill="url(#n%d)"/>'
                     % (f1(nb["x"]), f1(nb["y"]), f1(nb["rx"]), f1(nb["ry"]), i)
                     for i, nb in enumerate(scene["nebula"]))
    o('<g class="mo" opacity=".7">')
    o('<animate attributeName="opacity" values=".7;.7;1;1;.7;.7" keyTimes="%s" %s/>'
      % (keytimes([0, A, b, c, dfade, T]), rep))
    o(nebula)
    o("</g>")
    o('<g class="st" opacity=".85">%s</g>' % nebula)

    # --- poussière : un grain par jour vide ----------------------------------------------
    lo, hi = th["dust_op"]
    for g in range(3):
        grains = [d for d in scene["dust"] if d["g"] == g]
        if not grains:
            continue
        o('<g fill="%s"%s>' % (th["dust"], ' class="d%d"' % g if g else ""))
        for d in grains:
            o('<circle cx="%s" cy="%s" r="%s" opacity="%s"/>'
              % (f1(d["x"]), f1(d["y"]), f2(d["r"]), f2(lo + (hi - lo) * d["o"])))
        o("</g>")

    def stroke(color, op, width, extra=""):
        return ('<path d="%s" stroke="%s" stroke-opacity="%s" stroke-width="%s" '
                'stroke-linecap="round" stroke-linejoin="round"%s'
                % (path_d, color, f2(op), f2(width), extra))

    if mode == "constellation":
        # --- trace fantôme : toujours là, la constellation existe à chaque image ----------
        o(stroke(th["ghost_under"], th["ghost_under_op"], GHOST_W[0], "/>"))
        o(stroke(th["ghost"], th["ghost_op"], GHOST_W[1], "/>"))
        # --- trace allumée : dessinée derrière la comète, tenue, puis éteinte ----------
        lit = ((th["lit_wide"], th["lit_wide_op"], LIT_W[0]), (th["lit"], th["lit_op"], LIT_W[1]))
        o('<g class="mo">')
        o('<animate attributeName="opacity" values="1;1;0;0" keyTimes="%s" %s/>'
          % (keytimes([0, c, dfade, T]), rep))
        for color, op, width in lit:
            o(stroke(color, op, width, ' stroke-dasharray="%s %s" stroke-dashoffset="%s">'
                     % (f1(plen + 1), f1(plen + 12), f1(plen + 3))))
            o('<animate attributeName="stroke-dashoffset" values="%s;%s;0;0" keyTimes="%s" '
              'calcMode="spline" keySplines="%s" %s/>'
              % (f1(plen + 3), f1(plen + 3), keytimes([0, A, b, T]), ksp, rep))
            o("</path>")
        o("</g>")
        # version fixe (moins d'animations) : la trace entière, allumée
        o('<g class="st">%s</g>' % "".join(stroke(cl, op, wd, "/>") for cl, op, wd in lit))

    # --- comète : traînée en 4 couches (un tiret qui glisse, de plus en plus court, fin et
    # opaque vers la tête : un dégradé le long du trait sans dégradé SVG) + tête --------
    o('<g class="mo">')
    speed = plen / travel
    for color, width, op, tail in zip(th["tail"], TAIL_W, (0.22, 0.38, 0.62, 1.0),
                                      (130.0, 80.0, 42.0, 16.0)):
        tail = min(tail, plen * 0.6)
        retract = b + tail / speed
        o('<path d="%s" stroke="%s" stroke-opacity="%s" stroke-width="%s" '
          'stroke-linecap="round" stroke-dasharray="%s %s" stroke-dashoffset="%s">'
          % (path_d, color, f2(op), f2(width), f1(tail), f1(plen + tail + 20), f1(tail + 3)))
        o('<animate attributeName="stroke-dashoffset" values="%s;%s;%s;%s;%s" keyTimes="%s" '
          'calcMode="spline" keySplines="0 0 1 1;%s;.3 0 .7 1;0 0 1 1" %s/>'
          % (f1(tail + 3), f1(tail + 3), f1(tail - plen), f1(-plen - 3), f1(-plen - 3),
             keytimes([0, A, b, retract, T]), spline_mid, rep))
        o("</path>")
    o('<g opacity="0">')
    o('<animate attributeName="opacity" values="0;0;1;1;0;0" keyTimes="%s" %s/>'
      % (keytimes([0, A, A + 0.3, b - 0.15, b + 0.45, T]), rep))
    o('<animateMotion path="%s" keyPoints="0;0;1;1" keyTimes="%s" calcMode="spline" '
      'keySplines="%s" %s/>' % (path_d, keytimes([0, A, b, T]), ksp, rep))
    o('<circle r="12" fill="url(#hg)"/>')
    o('<circle r="2.2" fill="%s"/>' % th["head"])
    o("</g>")
    o("</g>")

    # --- étoiles ---------------------------------------------------------------------------
    core_lo, core_mid, core_hi = th["core"]
    for s in stars:
        t = s["t"]
        hr = min((5.2 + 10.5 * t) * size, edge_room(s["x"], s["y"]))
        cr = (1.35 + 1.9 * t) * (0.5 + 0.5 * size)
        core = core_hi if t > 0.8 else core_mid if t > 0.4 else core_lo
        o('<g class="k%d" transform="translate(%s %s)">'
          % (int(h01(s["date"], "tw") * 5), f1(s["x"]), f1(s["y"])))
        o('<circle r="%s" fill="url(#hl)"/>' % f1(hr))
        if s["date"] in scene["glints"]:
            # aigrette anamorphique : longues branches horizontales, verticales courtes
            # (les jours d'une même semaine sont empilés tous les 18)
            ln = (3.5 + 17.0 * t) * size
            sc = "%s %s" % (f2(ln), f2(ln * GLINT_V))
            gop = f2(0.5 + 0.4 * t)
            spark = '<path d="%s" fill="%s" opacity="%s" transform="scale(%s)"' % (
                SPARK, th["glint"], gop, sc)
            if scene["glints"][s["date"]]:
                sc2 = "%s %s" % (f2(ln * 0.6), f2(ln * GLINT_V * 0.75))
                o('%s class="mo"><animateTransform attributeName="transform" type="scale" '
                  'values="%s;%s;%s" dur="%ss" repeatCount="indefinite"/></path>'
                  % (spark, sc, sc2, sc, f1(3.1 + 2.6 * h01(s["date"], "gl"))))
                o('%s class="st"/>' % spark)
            else:
                o(spark + "/>")
        o('<circle r="%s" fill="%s"/>' % (f2(cr), core))
        o("</g>")

    # --- éclats : chaque étoile s'allume au passage de la comète (reliée : plein éclat ;
    # dernière : le plus grand et le plus long ; non reliée : plus discret) ---------------
    o('<g class="mo">')
    for s, dist, kind in flares:
        ti = A + travel * ease_time_for_progress(clamp(dist / plen if plen else 1.0, 0.0, 1.0))
        decay, grow, peak = {"last": (2.4, 2.6, "1"), "node": (1.3, 1.9, ".85"),
                             "side": (1.1, 1.6, ".6")}[kind]
        room = edge_room(s["x"], s["y"])            # l'éclat ne touche jamais le bord
        r1 = min((6 + 8 * s["t"]) * (0.4 + 0.6 * size) * grow, room)
        r0 = r1 / grow
        times = keytimes([0, max(ti - 0.06, 0.01), ti + 0.14, ti + decay, T])
        o('<circle cx="%s" cy="%s" r="%s" fill="url(#fl)" opacity="0">'
          % (f1(s["x"]), f1(s["y"]), f1(r0)))
        o('<animate attributeName="opacity" values="0;0;%s;0;0" keyTimes="%s" %s/>'
          % (peak, times, rep))
        o('<animate attributeName="r" values="%s;%s;%s;%s;%s" keyTimes="%s" %s/>'
          % (f1(r0 * 0.5), f1(r0 * 0.5), f1(r0 * 0.9), f1(r1), f1(r1), times, rep))
        o("</circle>")
    o("</g>")

    # --- curseur : celui de l'en-tête, posé sur aujourd'hui --------------------------------
    cx, cy = scene["cursor"]["x"], scene["cursor"]["y"]
    o('<g class="cu" transform="translate(%s %s)">' % (f1(cx), f1(cy)))
    o('<rect x="-2.6" y="-8.5" width="7" height="17" rx="3.5" fill="%s" opacity="%s"/>'
      % (th["cursor_halo"], f2(th["cursor_halo_op"])))
    o('<rect y="-7.5" width="2.2" height="15" rx="1" fill="%s"/>' % th["cursor"])
    o("</g>")

    o("</svg>")
    return "\n".join(out) + "\n"


# --------------------------------------------------------------------------- auto-test ----

# Forme de l'année réelle au 2026-10-12 : {jours avant la fin du calendrier: contributions}.
# Rafales (4 jours d'une même semaine, deux paires de semaines voisines) : c'est sur ce
# calendrier, plus une rafale de deux semaines à la fin, que la trace se croisait.
REAL_SHAPE = {336: 6, 335: 27, 334: 11, 333: 5, 327: 7, 133: 8, 132: 5, 124: 7, 123: 4, 0: 2}


def synthetic_weeks(active, end=datetime.date(2026, 10, 12)):
    """Calendrier au format GraphQL (semaines dimanche -> samedi, la dernière incomplète)."""
    day = end - datetime.timedelta(days=365)
    day -= datetime.timedelta(days=(day.weekday() + 1) % 7)       # recule au dimanche
    weeks = []
    while day <= end:
        if day.weekday() == 6 or not weeks:
            weeks.append({"contributionDays": []})
        weeks[-1]["contributionDays"].append({
            "date": day.isoformat(), "weekday": (day.weekday() + 1) % 7,
            "contributionCount": active.get((end - day).days, 0)})
        day += datetime.timedelta(days=1)
    return weeks


def self_test():
    """Calendriers synthétiques (sans réseau) ; s'arrête en erreur au premier défaut.
    Vérifie : la trace avance toujours vers la droite (jamais de retour ni de croisement),
    finit sur l'étoile la plus récente, ne s'effondre pas quand une rafale s'ajoute (pas de
    palier), et chaque SVG tient dans le budget (octets, nombre d'éléments)."""
    burst = [d for d in range(13, 0, -1) if d not in REAL_SHAPE]   # les 14 derniers jours
    cases = []
    for k in range(len(burst) + 1):
        cal = dict(REAL_SHAPE)
        cal.update({d: 3 + (i * 7) % 9 for i, d in enumerate(burst[:k])})
        cases.append(("real+%d" % k, cal))
    cases += [
        ("empty", {}),
        ("single", {40: 3}),
        ("one week", {d: 1 + d for d in range(7, 14)}),
        ("two weeks", {d: 2 + d % 5 for d in range(14)}),
        ("dense", {d: 1 + int(20 * h01(d, "n")) for d in range(366) if h01(d, "a") < 0.8}),
        ("full", {d: 1 + d % 9 for d in range(366)}),
    ]
    prev = 0
    for name, cal in cases:
        def fail(msg):
            raise SystemExit("self-test %s: %s" % (name, msg))
        scene = build_scene(*to_days(synthetic_weeks(cal)))
        stars, trace = scene["stars"], scene["trace"]
        if len(stars) != len(cal):
            fail("%d stars for %d active days" % (len(stars), len(cal)))
        if stars and trace[-1] is not stars[-1]:
            fail("the trace does not end on the most recent star")
        if len(trace) > MAX_TRACE:
            fail("%d linked stars > %d" % (len(trace), MAX_TRACE))
        for a, b in zip(trace, trace[1:]):
            if b["w"] <= a["w"] or b["x"] <= a["x"]:
                fail("the trace goes back (%s -> %s)" % (a["date"], b["date"]))
        if name.startswith("real+"):
            if len(trace) < prev:
                fail("linked stars drop from %d to %d" % (prev, len(trace)))
            prev = len(trace)
        sizes = []
        for theme in THEMES:
            svg = render(scene, theme, "self-test")
            size, elems = len(svg.encode("utf-8")), svg.count("<") - svg.count("</")
            if size > MAX_BYTES or elems > 1500:
                fail("%s: %d B, %d elements" % (theme, size, elems))
            sizes.append("%s %d B / %d el." % (theme, size, elems))
        print("ok  %-10s %3d stars, %2d linked | %s"
              % (name, len(stars), len(trace), ", ".join(sizes)))


# --------------------------------------------------------------------------------- main ----

def main(argv=None):
    ap = argparse.ArgumentParser(
        description="GitHub contribution graph as a night sky (dark + light SVG).")
    ap.add_argument("--user", default="Bisiaux-dev", help="GitHub login (default: Bisiaux-dev)")
    ap.add_argument("--out", default="dist", help="output directory (default: ./dist)")
    ap.add_argument("--from-json", help="read the calendar from a JSON file instead of the API")
    ap.add_argument("--save-json", help="also save the raw API response to this file")
    ap.add_argument("--self-test", action="store_true",
                    help="check the drawing on synthetic calendars (no network, writes nothing)")
    args = ap.parse_args(argv)

    if args.self_test:
        self_test()
        return
    if args.from_json:
        try:
            with open(args.from_json, encoding="utf-8") as fh:
                payload = json.load(fh)
        except (OSError, ValueError) as exc:
            raise SystemExit("cannot read %s (%s)" % (args.from_json, exc.__class__.__name__))
    else:
        token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        if not token:
            raise SystemExit("set GITHUB_TOKEN (or GH_TOKEN) to read the contribution calendar")
        payload = fetch_calendar(args.user, token)
        if args.save_json:
            with open(args.save_json, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, indent=1, sort_keys=True)

    days, nweeks = to_days(extract_weeks(payload))
    scene = build_scene(days, nweeks)

    # tout construire et vérifier, puis écrire : jamais un thème neuf à côté d'un ancien
    built = {}
    for theme in ("dark", "light"):
        svg = render(scene, theme, args.user)
        size = len(svg.encode("utf-8"))
        if size > MAX_BYTES:
            raise SystemExit("contrib-%s.svg too big: %d B > %d B" % (theme, size, MAX_BYTES))
        built[theme] = (svg, size)
    os.makedirs(args.out, exist_ok=True)
    for theme, (svg, size) in built.items():
        path = os.path.join(args.out, "contrib-%s.svg" % theme)
        with open(path + ".tmp", "w", encoding="utf-8", newline="\n") as fh:
            fh.write(svg)
        os.replace(path + ".tmp", path)
        print("%s  %d bytes  (%d stars, %d linked)"
              % (path, size, len(scene["stars"]), len(scene["trace"])))


if __name__ == "__main__":
    main()
