#!/usr/bin/env python3
"""Ciel nocturne : l'année de contributions GitHub dessinée comme une voie lactée.

Une étoile pour CHAQUE jour de l'année glissante (tous les jours du calendrier, ~366), posés
dans l'ordre le long d'une rivière d'étoiles qui traverse l'image de gauche (le plus ancien
jour) à droite (aujourd'hui), comme la traînée de lumière de l'avatar.
  - abscisse : uniquement le rang du jour dans l'année (aucune colonne par semaine) ;
  - hauteur  : un écart à l'axe de la rivière tiré d'un hachage de la date (aucune ligne par
               jour de semaine) ; l'axe ondule doucement sans monter ni descendre : sa hauteur
               ne mesure rien. Il est ancré aux dates : d'une nuit à l'autre, le ciel glisse
               d'un jour vers la gauche au lieu de se redessiner ;
  - largeur  : la rivière s'élargit et sa brume s'épaissit là où l'année a été active.

Éclat : il croît strictement avec le nombre de contributions du jour.
  - 0 contribution  -> poussière : petit grain pâle, identique pour tous les jours vides
  - 1 contribution  -> déjà une vraie étoile (cœur net, halo), nettement au-dessus de 0
  - n contributions -> échelle log relative au record de l'année, avec un plancher :
                       t = PLANCHER + (1 - PLANCHER) * ln((1+n)/2) / ln((1+max)/2)
                       cœur, halo, couleur et aigrette suivent t ; record = t = 1
  - aigrettes       -> la douzaine de plus gros jours (seuil sur le nombre) : toutes les
                       étoiles d'une année clairsemée comme l'année réelle
  - même nombre     -> même étoile (aucun hasard dans l'éclat : seul l'emplacement varie)
Placement : un jour ne fait que 2,3 unités de large, une étoile 4 à 8 ; des jours actifs
rapprochés ne peuvent donc pas s'aligner sans se toucher. Plutôt que de les empiler (une colonne
d'étoiles se lirait comme une semaine), les jours actifs à 3 jours d'écart au plus forment une
rafale, dont les hauteurs suivent un filet continu dans l'ordre des dates (pente douce, jamais
de dents de scie) : jusqu'à 7 jours, un nœud de lumière tressé sur deux brins serrés, cœurs et
halos mêlés ; au-delà, un ruban de perles lumineuses. Une rafale proche (10 jours au plus)
d'une autre la prolonge à sa hauteur. Un jour isolé prend une hauteur tirée de sa date. D'une
rafale à l'autre, ni les cœurs ni les aigrettes ne se touchent, sans saut brusque de hauteur :
chaque rafale choisit, parmi quelques hauteurs proches, la première qui laisse de l'air aux
rafales déjà posées (aujourd'hui d'abord, sur l'axe ; puis dans l'ordre chronologique).

Mouvement (calme) : une comète parcourt la rivière vers aujourd'hui (la lumière ne fait
qu'avancer), allume les plus gros jours au passage et laisse une lueur douce qui s'éteint ;
cycle de 14 s. Les halos scintillent (un peu plus pour les étoiles vives) ; les cœurs restent
fixes, les aigrettes aussi, sauf celle du record (jours record, s'ils sont 5 au plus) qui
respire en grandissant, au même rythme pour tous : aucune aigrette ne dépasse jamais celle d'un
jour plus contributif. Le curseur clignotant de l'en-tête (même barre, même halo, même rythme)
marque aujourd'hui, au bout de la rivière, sans qu'aucune aigrette ne le traverse. Repères de
mois discrets en bas (le mois en cours compris, sous le curseur) ; sur un écran étroit, un mois
sur trois seulement, en plus grand. Aucun total, aucune grille. Thème sombre : nuages d'orage en
fond (décor ; jamais plus sombres que la page, même en « dark dimmed »).

Sortie : contrib-dark.svg et contrib-light.svg (fond transparent, viewBox 900x180, sans JS ni
ressource externe : <style> + @keyframes pour le scintillement et le curseur, SMIL pour ce qui
doit rester synchronisé : comète, lueur, éclats). prefers-reduced-motion : le CSS s'arrête et
les calques SMIL (.mo) sont masqués au profit d'une version fixe (.st).

Cas limites :
  - 0 contribution  -> la rivière de poussière reste là, la comète la traverse (sans lueur)
  - 1 jour actif    -> une seule étoile, la plus brillante, dans une brume qui s'y resserre
  - année dense     -> tailles réduites selon la densité ; les rafales deviennent un ruban
                       de lumière continu qui serpente dans la rivière (la traînée de l'avatar) ;
                       aigrettes et éclats réservés aux plus gros jours (seuil sur le nombre :
                       jamais deux jours égaux traités différemment)
  - jour record     -> échelle log + plancher : les petits jours restent des étoiles
  - réponse vide, illisible ou en erreur -> sortie en erreur, aucun fichier écrit

Bibliothèque standard uniquement. Sortie déterministe : même calendrier -> mêmes octets (tout
l'aléa vient d'un hachage SHA-256 de la date). Les deux SVG sont construits et vérifiés (octets,
éléments, nœuds animés) avant d'écrire quoi que ce soit, puis remplacés (os.replace) : jamais
de paire dépareillée.

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
import re
import subprocess
import sys
import urllib.error
import urllib.request
from xml.sax.saxutils import escape

QUERY = (
    "query($login:String!){user(login:$login){contributionsCollection{contributionCalendar{"
    "weeks{contributionDays{date contributionCount}}}}}}"
)

# --------------------------------------------------------------------------------------------
# Palette (jetons mesurés sur l'avatar)
#   nuit #0b0910 · ombre #281838 · aubergine #302040 · violet profond #533861 · violet #765082
#   lilas #8f6a99 · mauve #a87fb0 · glow #e3b7e6 · éclair #fbd4ff · givre #f6ebf7
# Thème sombre : la lumière monte vers le givre. Thème clair : carte du ciel à l'encre de nuit,
# halos et brume en glow (lilas pâle) sur blanc : « plus brillant » = encre plus dense ; les
# cœurs y restent plus petits (un gros disque d'encre ferait une punaise, pas une étoile) et la
# comète est une lueur mauve, pas un point d'encre.
# core : rampe de couleur du cœur, de t = 0 à t = 1 ; chaque canal varie dans un seul sens
# (luminance monotone même après arrondi) ; le record est un éclair blanchi vers le givre.
# core_r : rayon du cœur = (a + b * t^1,25) * échelle de densité.
# Curseur : mêmes couleurs que celui de l'en-tête (scripts/gen_header.py).
# --------------------------------------------------------------------------------------------
THEMES = {
    "dark": {
        "dust": "#a87fb0", "dust_op": 0.62, "dust_r": 0.82,
        "twinkle": (0.72, 0.6, 0.48, 0.4),   # creux (halos) : t bas, moyen, haut ; poussière
        "halo": "#e3b7e6", "halo_op": 0.78,
        "core": ((0.0, "#b993c1"), (0.7, "#fbd4ff"), (1.0, "#fdebff")),
        "core_r": (1.0, 3.1),
        "glint": "#fbd4ff",
        # aubergine -> violet profond (35 %) : chaque canal >= celui de #22272e, donc l'orage
        # n'assombrit jamais la page, même en « dark dimmed » (il ne fait qu'ajouter du violet)
        "storm": "#3c284c", "storm_op": 0.4,
        "aura": "#533861", "aura_op": 0.3,
        "band": ("#765082", "#533861"), "band_op": 0.55,
        "bcore": ("#a87fb0", "#765082"), "bcore_op": 0.6,
        "neb": ("#8f6a99", "#533861"), "neb_op": (0.36, 0.6),
        "wisp": "#8f6a99", "wisp_op": 0.13,
        "glow": (("#765082", 0.16, 14.0), ("#a87fb0", 0.1, 6.0)),   # lueur derrière la comète
        "tail": ("#765082", "#a87fb0", "#e3b7e6", "#fbd4ff"),
        "head_glow": "#fbd4ff", "head": "#f6ebf7",
        "flare": "#fbd4ff",
        "month": "#8f6a99", "month_op": 0.5,
        "cursor": "#fbd4ff", "cursor_halo": "#a87fb0", "cursor_halo_op": 0.30,
    },
    "light": {
        "dust": "#8f6a99", "dust_op": 0.42, "dust_r": 0.7,
        "twinkle": (0.8, 0.7, 0.6, 0.5),     # sur blanc, une encre qui pâlit vire au gris
        "halo": "#a87fb0", "halo_op": 0.42,
        "core": ((0.0, "#b48cbb"), (0.55, "#835b8f"), (1.0, "#302040")),
        "core_r": (0.95, 2.2),
        "glint": "#533861",
        "storm": None, "storm_op": 0.0,      # carte du ciel : pas d'orage sur blanc
        "aura": "#f6ebf7", "aura_op": 0.55,
        "band": ("#e3b7e6", "#f6ebf7"), "band_op": 0.5,
        "bcore": ("#d6a9da", "#e3b7e6"), "bcore_op": 0.5,
        "neb": ("#e3b7e6", "#f6ebf7"), "neb_op": (0.32, 0.55),
        "wisp": "#e3b7e6", "wisp_op": 0.35,
        "glow": (("#e3b7e6", 0.24, 14.0), ("#e3b7e6", 0.16, 6.0)),
        "tail": ("#f6ebf7", "#e3b7e6", "#d6a9da", "#a87fb0"),
        "head_glow": "#a87fb0", "head": "#fbd4ff",
        "flare": "#a87fb0",
        "month": "#8f6a99", "month_op": 0.5,
        "cursor": "#533861", "cursor_halo": "#e3b7e6", "cursor_halo_op": 0.55,
    },
}

# Géométrie (unités du viewBox ; même rapport que le graphe GitHub, README inchangé)
W, H = 900, 180
X0, X1 = 30.0, 864.0         # abscisse du plus vieux jour, d'aujourd'hui
EDGE = 1.0                   # aucun dégradé ne touche le bord du viewBox (pas de couture)
Y_MID = 84.0                 # hauteur moyenne de l'axe de la rivière
# méandres de l'axe, ancrés aux dates : (amplitude, période en jours, phase) ; pas de pente
MEANDER = ((12.0, 233.0, 0.6), (5.5, 97.0, 2.3))
SIGMA_DUST = 12.0            # demi-largeur typique de la rivière (poussière)
SIGMA_STAR = 9.0             # les jours actifs brillent près du cœur de la rivière
JIT_MAX = 2.5                # écart borné à 2,5 sigmas
ACT_SIGMA = 12.0             # lissage de l'activité le long de l'année (jours)
SWELL = (0.8, 0.55)          # largeur relative : base + gonflement là où l'année a été active
STAR_W_MIN = 0.6             # aux bouts effilés, les étoiles gardent un peu de place
# rafales : jours actifs à RUN_GAP jours d'écart au plus ; leur filet suit un méandre lent
# ancré aux dates (pente bornée par rapport à la rivière), tressé sur deux brins serrés
RUN_GAP = 3
RUN_SLOPE = 0.2              # pente maximale du filet (unités de hauteur par unité d'abscisse)
RUN_PERIOD = 150.0           # période du méandre (jours)
RUN_GMAX = 1.5               # une rafale reste près du cœur de la rivière (sigmas)
BRAID = 1.3                  # rafale courte : demi-écart des deux brins (x échelle des cœurs)
RUN_LONG = 7                 # au-delà de 7 jours, la rafale devient un ruban de lumière
BRAID_LONG = 1.8             # ruban : semis de +-1,8 autour du filet
CONT_DAYS = 10               # deux rafales à <= 10 jours : la seconde prolonge la première
RAMP_MAX = 0.15              # pente ajoutée au plus pour rejoindre deux voisines à la fois
# hauteurs essayées pour une rafale, autour de celle tirée de sa date (sigmas)
DODGE = (0.0, 0.3, -0.3, 0.6, -0.6, 0.9, -0.9, 1.2, -1.2, 1.6, -1.6, 2.0, -2.0, 2.5, -2.5)
SEP = 1.0                    # air minimal entre deux cœurs de rafales différentes
SPIKE_AIR = 0.6              # air minimal entre une aigrette et le cœur d'une autre rafale
STEEP = (7, 1.2, 2.0)        # entre rafales à < 7 jours : pente <= 1,2 (+ 2 unités) si possible
BAND_CLOUDS = 18             # nuages qui font la brume de la rivière
CORE_CLOUDS = 24             # nuages étroits : le cœur lumineux de la rivière
AURA_CLOUDS = 10             # nuages larges : l'aura de la rivière (la nuée de l'avatar)
MONTHS = True                # repères de mois (discrets ; False pour les retirer)
MONTH_Y = 172                # ligne de base des repères de mois
MONTH_FS = 8.5               # taille des repères (unités du viewBox ; ~8 px à 850 px de large)
MONTH_FS_NARROW = 17.0       # écran étroit : un mois sur trois, en plus grand (~6 px à 360 px)
NARROW_PX = 560              # largeur d'image (px CSS) en dessous de laquelle on passe en étroit
MONTH_MIN_DAYS = 14          # un mois partiel n'est nommé que s'il a au moins 14 jours affichés

# Éclat
FLOOR = 0.34                 # t d'un jour à 1 contribution (0 = poussière, 1 = record)
SIZE_EXP = 1.25              # le cœur grandit un peu plus vite en haut de l'échelle
MAX_GLINTS = 12              # aigrettes : la douzaine de plus gros jours (seuil sur le nombre)
MAX_FLARES = 48              # éclats au passage de la comète (même règle de seuil)
MAX_PULSE = 5                # le record respire s'il est partagé par 5 jours au plus
PULSE = (1.22, 1.1)          # respiration de l'aigrette du record (horizontale, verticale)
PULSE_DUR = 4.6              # même période, même phase pour tous les jours record
GLINT_V = 0.55               # aigrette anamorphique : branche verticale / horizontale
# aigrette à 4 branches, longueur 1 (mise à l'échelle par étoile)
SPARK = "M0-1C.07-.07.07-.07 1 0C.07.07.07.07 0 1C-.07.07-.07.07-1 0C-.07-.07-.07-.07 0-1Z"

# Animation (secondes)
T = 14.0                     # durée d'un cycle complet, en boucle
A = 0.9                      # départ de la comète
TRAVEL = 7.2                 # traversée de l'année (calme : ~2 mois par seconde)
EASE = (0.42, 0.0, 0.58, 1.0)
BLINK = 0.53                 # demi-période du curseur (identique à l'en-tête)
TAIL_W = (3.2, 2.4, 1.7, 1.25)

MAX_BYTES = 150 * 1024
MAX_ELEMS = 1500
MAX_ANIM = 300               # nœuds animés (groupes CSS + éléments SMIL)

MONTH_NAMES = ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


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
    """Tous les jours du calendrier, dans l'ordre chronologique (un par date)."""
    by_date = {}
    try:
        for week in weeks:
            for d in week["contributionDays"]:
                date = datetime.date.fromisoformat(str(d["date"])[:10])
                by_date[date] = max(0, int(d["contributionCount"]))
    except (KeyError, TypeError, ValueError, OverflowError):  # Infinity -> OverflowError
        raise SystemExit("unrecognised calendar JSON (malformed week or day)")
    if not by_date:
        raise SystemExit("empty contribution calendar (no days): nothing written")
    return [{"date": k.isoformat(), "day": k, "n": by_date[k]} for k in sorted(by_date)]


# ---------------------------------------------------------------------------- utilitaires ----

def h01(*parts):
    """Flottant déterministe dans [0, 1) dérivé de la date (+ sel)."""
    digest = hashlib.sha256("|".join(str(p) for p in parts).encode()).digest()
    return int.from_bytes(digest[:6], "big") / float(1 << 48)


def gauss(*parts):
    """Quasi-normale déterministe (somme de 4 uniformes, moyenne 0, écart-type 1)."""
    return (sum(h01(*(parts + (k,))) for k in range(4)) - 2.0) * math.sqrt(3.0)


def f1(v):
    s = "%.1f" % v
    if s.endswith(".0"):
        s = s[:-2]
    return "0" if s == "-0" else s


def f2(v):
    s = ("%.2f" % v).rstrip("0").rstrip(".")
    if s.startswith("0."):
        s = s[1:]
    elif s.startswith("-0."):
        s = "-" + s[2:]
    return "0" if s in ("", "-0", "-") else s


def f3(v):
    s = ("%.3f" % v).rstrip("0").rstrip(".")
    if s.startswith("0."):
        s = s[1:]
    return "0" if s in ("", "-0") else s


def f4(v):
    s = ("%.4f" % v).rstrip("0").rstrip(".")
    return "0" if s in ("", "-0") else s


def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def mix(c1, c2, f):
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(int(round(x + (y - x) * f)) for x, y in zip(a, b))


def ramp(stops, t):
    for (t0, c0), (t1, c1) in zip(stops, stops[1:]):
        if t <= t1:
            return mix(c0, c1, (t - t0) / (t1 - t0) if t1 > t0 else 1.0)
    return stops[-1][1]


def luminance(c):
    def lin(v):
        v /= 255.0
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (int(c[i:i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)


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


def cubic_len(p0, c1, c2, p3, steps=120):
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


def count_threshold(counts, k, hard=None):
    """Plus petit nombre v tel qu'au plus k jours aient >= v contributions : un traitement
    réservé aux « gros jours » ne départage jamais deux jours égaux au hasard. Si le record
    lui-même est partagé par plus de k jours, il garde le traitement tant qu'ils sont au plus
    `hard` ; sinon personne (renvoie l'infini)."""
    thr, acc = float("inf"), 0
    for v in sorted(set(c for c in counts if c > 0), reverse=True):
        acc += sum(1 for c in counts if c == v)
        if acc > k:
            if thr == float("inf") and hard is not None and acc <= hard:
                thr = v
            break
        thr = v
    return thr


# ------------------------------------------------------------------------- la rivière ----

def spine_at(ordf):
    """Hauteur de l'axe au jour `ordf` (ordinal, éventuellement fractionnaire) : des méandres
    ancrés aux dates, sans tendance (la hauteur ne mesure rien)."""
    return Y_MID + sum(a * math.sin(2.0 * math.pi * ordf / p + ph) for a, p, ph in MEANDER)


def taper(u):
    """Largeur relative de la rivière selon la position : effilée aux deux bouts (comme une
    traînée), plus fine encore à droite pour se resserrer sur le curseur."""
    s = math.sin(math.pi * clamp(u, 0.0, 1.0))
    return (0.26 + 0.74 * s ** 0.6) * (1.0 - 0.35 * clamp((u - 0.9) / 0.1, 0.0, 1.0))


def level(n, nmax):
    """Éclat 0..1 d'un jour : 0 pour un jour vide, FLOOR pour 1 contribution, 1 pour le
    record ; log relatif au record entre les deux (strictement croissant en n)."""
    if n <= 0:
        return 0.0
    if nmax <= 1:
        return 1.0
    return FLOOR + (1.0 - FLOOR) * math.log((1.0 + n) / 2.0) / math.log((1.0 + nmax) / 2.0)


def core_scale(size):
    """Échelle des cœurs (et de la poussière) selon la densité de l'année : une année dense
    garde de petits points nets (des étoiles, pas des perles)."""
    return 0.3 + 0.7 * size


def star_style(t, size, th):
    """Tout ce qui fait l'éclat d'une étoile, en fonction de t seul (et de la densité de
    l'année, la même pour tous les jours) : deux jours égaux sont deux étoiles identiques."""
    s2 = core_scale(size)
    a, b = th["core_r"]
    return {
        "cr": (a + b * t ** SIZE_EXP) * s2,         # rayon du cœur
        "hr": (4.0 + 13.5 * t) * size,              # rayon du halo
        "ho": 0.3 + 0.7 * t,                        # opacité du halo
        "color": ramp(th["core"], t),
        "spark": (3.5 + 17.0 * t) * size,           # longueur de l'aigrette (si gros jour)
        "spark_op": 0.45 + 0.45 * t,
        "tier": 0 if t < 0.55 else 1 if t < 0.85 else 2,   # amplitude du scintillement
    }


def star_geom(t, size, glint, pulse):
    """Encombrement d'une étoile, commun aux deux thèmes : le plus grand des deux cœurs et la
    portée de l'aigrette (à son maximum si elle respire)."""
    cr = max(star_style(t, size, th)["cr"] for th in THEMES.values())
    sp = star_style(t, size, THEMES["dark"])["spark"] if glint else 0.0
    return {"cr": cr, "reach_h": sp * (PULSE[0] if pulse else 1.0),
            "reach_v": sp * GLINT_V * (PULSE[1] if pulse else 1.0)}


def _arm_profile():
    # bord d'une branche de SPARK : de (0, 1) à (1, 0), points de contrôle (.07, .07)
    out = []
    for k in range(401):
        u = k / 400.0
        v = 1.0 - u
        out.append((0.21 * u * v + u ** 3, v ** 3 + 0.21 * u * v))
    return out


ARM = _arm_profile()


def arm_half(f):
    """Demi-épaisseur de l'aigrette (fraction de la portée de l'autre branche) à la fraction f
    de la portée d'une branche ; arrondie par excès."""
    if f >= 1.0:
        return 0.0
    prev = 1.0
    for x, y in ARM:
        if x >= f:
            return prev
        prev = y
    return 0.0


def arm_extent(g):
    """Portée d'une branche (fraction) à la hauteur g (fraction de l'autre branche) ;
    arrondie par excès : inverse de arm_half."""
    if g <= 0.0:
        return 1.0
    for x, y in ARM:
        if y <= g:
            return x
    return 0.0


def in_star(s, px, py, air=0.0):
    """Le point (px, py) est-il sur l'étoile s (cœur ou aigrette, à son maximum) ?"""
    dx, dy = abs(px - s["x"]), abs(py - s["y"])
    if math.hypot(dx, dy) <= s["cr"] + air:
        return True
    lh, lv = s["reach_h"] + air, s["reach_v"] + air
    return bool(s["reach_h"]) and dx < lh and dy < lv and dy <= arm_half(dx / lh) * lv + air


def spike_hits(a, b, air=SPIKE_AIR):
    """L'aigrette de l'étoile a touche-t-elle le cœur de l'étoile b (air compris) ?"""
    lh, lv = a["reach_h"], a["reach_v"]
    if not lh:
        return False
    dx, dy, r = b["x"] - a["x"], b["y"] - a["y"], b["cr"] + air
    if abs(dx) > lh + r or abs(dy) > lv + r:
        return False
    for tx, ty in ((lh, 0.0), (-lh, 0.0), (0.0, lv), (0.0, -lv)):
        if math.hypot(tx - dx, ty - dy) <= r:
            return True
    for k in range(48):
        ang = 2.0 * math.pi * k / 48.0
        px, py = abs(dx + r * math.cos(ang)), abs(dy + r * math.sin(ang))
        if px < lh and py < lv and py <= arm_half(px / lh) * lv:
            return True
    return False


# curseur (barre + halo de l'en-tête) autour de son point d'ancrage
CUR_L, CUR_R, CUR_H = 2.6, 4.4, 8.5


def smooth_activity(days, sigma):
    w = [math.log1p(d["n"]) for d in days]
    n = len(days)
    reach = int(3 * sigma) + 1
    out = []
    for i in range(n):
        acc = 0.0
        for j in range(max(0, i - reach), min(n, i + reach + 1)):
            if w[j]:
                acc += w[j] * math.exp(-((i - j) ** 2) / (2 * sigma * sigma))
        out.append(acc)
    return out


def fit_ellipse(x, y, rx, ry, rot):
    """Réduit une ellipse tournée pour que sa boîte englobante reste dans le viewBox (moins
    EDGE) : un dégradé coupé par le bord ferait une couture."""
    a = math.radians(rot)
    hw = math.hypot(rx * math.cos(a), ry * math.sin(a))
    hh = math.hypot(rx * math.sin(a), ry * math.cos(a))
    k = min(1.0, (x - EDGE) / hw, (W - x - EDGE) / hw, (y - EDGE) / hh, (H - y - EDGE) / hh)
    return rx * max(k, 0.0), ry * max(k, 0.0)


def month_marks(days, pos):
    """Repères de mois : chaque mois affiché, au milieu de sa portion d'année ; un mois partiel
    au début n'est nommé que s'il a assez de jours (et s'il ne répète pas le mois en cours) ; le
    mois en cours est toujours nommé, sous le curseur. `back` : mois d'écart avec le mois en
    cours. `narrow` : le repère reste visible sur écran étroit (un mois sur trois, en plus
    grand). Chevauchements testés par affichage : à la taille normale entre repères voisins, à
    la grande taille seulement entre repères visibles sur écran étroit (un repère trop serré
    pour l'écran étroit y est seulement masqué, il garde sa place sur grand écran)."""
    spans = []
    for i, d in enumerate(days):
        key = (d["day"].year, d["day"].month)
        if spans and spans[-1][0] == key:
            spans[-1][2] = i
        else:
            spans.append([key, i, i])
    last = spans[-1][0]

    def clear(x, label, right, fs):   # `label` en x tient à gauche de `right`, avec de l'air
        return x + 0.5 * month_width(label, fs) + 4.0 <= \
            right["x"] - 0.5 * month_width(right["label"], fs)

    def inside(x, label, fs):
        return 0.0 <= x - 0.5 * month_width(label, fs) and \
            x + 0.5 * month_width(label, fs) <= W

    marks, right_narrow = [], None
    for k in range(len(spans) - 1, -1, -1):          # de droite à gauche : le mois en cours
        key, i0, i1 = spans[k]                        # garde toujours sa place
        current = k == len(spans) - 1
        label = MONTH_NAMES[key[1] - 1]
        if not current and i1 - i0 + 1 < MONTH_MIN_DAYS:
            continue
        if not current and key[1] == last[1] and days[i0]["day"].day != 1:
            continue                                  # « Oct ... Oct » : le partiel s'efface
        x = (pos(i0) + pos(i1)) / 2.0
        if current:
            x = min(x, X1 + 2.0)
        if not inside(x, label, MONTH_FS) or (marks and not clear(x, label, marks[-1],
                                                                   MONTH_FS)):
            continue
        back = (last[0] * 12 + last[1]) - (key[0] * 12 + key[1])
        narrow = back % 3 == 0 and inside(x, label, MONTH_FS_NARROW) and (
            right_narrow is None or clear(x, label, right_narrow, MONTH_FS_NARROW))
        mark = {"x": x, "label": label, "back": back, "narrow": narrow}
        if narrow:
            right_narrow = mark
        marks.append(mark)
    return marks[::-1]


def month_width(label, fs):
    return len(label) * 0.6 * fs + 0.4 * max(len(label) - 1, 0)


def storm_clouds(days):
    """Nuages d'orage sombres (décor, sans lien avec l'activité) : un par mois calendaire au
    plus, ancrés au milieu du mois -> ils glissent avec le ciel d'une nuit à l'autre."""
    o0, o1 = days[0]["day"].toordinal(), days[-1]["day"].toordinal()
    span = max(o1 - o0, 1)
    out = []
    y, m = days[0]["day"].year, days[0]["day"].month
    while (y, m) <= (days[-1]["day"].year, days[-1]["day"].month):
        key = y * 12 + m
        mid = datetime.date(y, m, 15).toordinal()
        x = X0 + (X1 - X0) * (mid - o0) / span + (h01("sx", key) - 0.5) * 40.0
        if h01("sk", key) >= 0.25 and EDGE < x < W - EDGE:
            side = 1 if h01("sd", key) < 0.5 else -1
            cy = clamp(spine_at(mid) + side * (40.0 + 22.0 * h01("sy", key)), 18.0, H - 18.0)
            rx, ry = fit_ellipse(x, cy, 62.0 + 52.0 * h01("sr", key), 20.0 + 16.0 * h01("sq", key),
                                 (h01("sa", key) - 0.5) * 14.0)
            if rx > 20 and ry > 8:
                out.append({"x": x, "y": cy, "rx": rx, "ry": ry,
                            "rot": (h01("sa", key) - 0.5) * 14.0,
                            "o": 0.45 + 0.55 * h01("so", key)})
        m += 1
        if m > 12:
            y, m = y + 1, 1
    return out


def build_scene(days):
    n = len(days)
    counts = [d["n"] for d in days]
    nmax = max(counts)
    active = sum(1 for c in counts if c > 0)
    # densité : plus il y a d'étoiles, plus elles sont petites (un ciel dense reste lisible)
    size = 1.0 / (1.0 + 1.4 * active / float(n))
    o0, o1 = days[0]["day"].toordinal(), days[-1]["day"].toordinal()

    def u_of(i):
        return i / float(n - 1) if n > 1 else 1.0

    def pos(i):                                       # abscisse : le rang du jour, rien d'autre
        return X0 + (X1 - X0) * u_of(i)

    def ord_at(u):
        return o0 + (o1 - o0) * u

    def slope_at(u):
        du = 1e-4
        return (spine_at(ord_at(u + du)) - spine_at(ord_at(u - du))) / (2 * du) / (X1 - X0)

    # activité lissée le long de l'année (0..1) : la rivière s'élargit et sa brume s'épaissit
    # là où l'année a été active
    act = smooth_activity(days, ACT_SIGMA)
    peak = max(act)
    actn = [a / peak if peak > 0 else 0.0 for a in act]

    def act_at(u):
        return actn[int(round(u * (n - 1)))] if n > 1 else actn[0]

    def width(u):
        return taper(u) * (SWELL[0] + SWELL[1] * act_at(u))

    pts = []
    for i, d in enumerate(days):
        u = u_of(i)
        # écart à l'axe mesuré perpendiculairement à la rivière, appliqué en vertical
        # (l'abscisse reste exactement celle du rang du jour)
        tilt = math.sqrt(1.0 + slope_at(u) ** 2)
        pts.append({"date": d["date"], "day": d["day"], "n": d["n"], "i": i, "u": u,
                    "x": pos(i), "sy": spine_at(ord_at(u)), "w": width(u) * tilt,
                    "g": clamp(gauss(d["date"], "off"), -JIT_MAX, JIT_MAX)})
    pts[-1]["g"] = 0.0                                # aujourd'hui : sur l'axe, contre le curseur

    # éclat et encombrement : fonctions du nombre seul, connus avant de placer
    star_counts = [c for c in counts if c > 0]
    glint_thr = count_threshold(star_counts, MAX_GLINTS, hard=2 * MAX_GLINTS)
    records = sum(1 for c in star_counts if c == nmax)
    pulse_n = nmax if 0 < records <= MAX_PULSE and nmax >= glint_thr else None
    braid = BRAID * core_scale(size)
    dx_day = (X1 - X0) / float(n - 1) if n > 1 else 0.0

    def band_lim(p):
        return JIT_MAX * SIGMA_STAR * max(p["w"], STAR_W_MIN)

    def slope(i, phase):                              # pente du filet entre deux jours
        return RUN_SLOPE * math.sin(2.0 * math.pi * (o0 + i) / RUN_PERIOD + phase)

    def strands(run):
        """Écart de chaque jour d'une rafale à son filet (jours vides compris), en fraction de
        l'amplitude renvoyée. Rafale courte : deux brins serrés, en alternance (parité de la
        date) : chaque jour du nœud reste visible. Longue : un léger semis tiré de la date
        autour du filet (un ruban de lumière, ni zigzag régulier ni colonne)."""
        i0, i1 = run[0]["i"], run[-1]["i"]
        if len(run) == 1:
            return {i0: 0.0}, 0.0
        if i1 - i0 + 1 <= RUN_LONG:
            return {i: 1.0 if days[i]["day"].toordinal() % 2 == 0 else -1.0
                    for i in range(i0, i1 + 1)}, braid
        return {i: 2.0 * h01(days[i]["date"], "jit") - 1.0 for i in range(i0, i1 + 1)}, \
            BRAID_LONG

    # rafales : jours actifs à RUN_GAP jours d'écart au plus
    runs = []
    for p in pts:
        if p["n"] > 0:
            if runs and p["i"] - runs[-1][-1]["i"] <= RUN_GAP:
                runs[-1].append(p)
            else:
                runs.append([p])
    # aujourd'hui d'abord (sur l'axe), puis dans l'ordre chronologique
    if runs and runs[-1][-1] is pts[-1]:
        runs = [runs[-1]] + runs[:-1]

    stars, dust, placed = [], [], []
    for rid, run in enumerate(runs):
        today = run[-1] is pts[-1]
        anchor = run[-1] if today else run[0]
        phase = 2.0 * math.pi * h01(anchor["date"], "ph")
        # filet : intégrale de la pente, jour par jour (jours vides de la rafale compris)
        rel = {anchor["i"]: 0.0}
        for i in range(anchor["i"] + 1, run[-1]["i"] + 1):
            rel[i] = rel[i - 1] + slope(i - 0.5, phase) * dx_day
        for i in range(anchor["i"] - 1, run[0]["i"] - 1, -1):
            rel[i] = rel[i + 1] - slope(i + 0.5, phase) * dx_day
        if not today:                                 # filet centré sur la hauteur tirée
            mid = (max(rel.values()) + min(rel.values())) / 2.0
            rel = {i: v - mid for i, v in rel.items()}
        strand, sp = strands(run)
        geo = []
        for p in run:
            t = level(p["n"], nmax)
            glint = p["n"] >= glint_thr
            g = star_geom(t, size, glint, glint and p["n"] == pulse_n)
            g.update({"date": p["date"], "n": p["n"], "t": t, "x": p["x"], "u": p["u"],
                      "i": p["i"], "sy": p["sy"], "day": p["day"], "run": rid,
                      "glint": glint, "pulse": glint and p["n"] == pulse_n, "rl": len(run),
                      "off": rel[p["i"]] + strand[p["i"]] * sp, "lim": band_lim(p)})
            geo.append(g)
        a_side = strand[anchor["i"]] * sp if today else 0.0
        if today:
            cands = [0.0]
        else:
            gmax = JIT_MAX if len(run) == 1 else RUN_GMAX
            flip = 1.0 if h01(anchor["date"], "fl") < 0.5 else -1.0
            g0 = clamp(anchor["g"], -gmax, gmax)
            unit = SIGMA_STAR * max(anchor["w"], STAR_W_MIN)
            # une rafale proche d'une autre rafale déjà posée (CONT_DAYS jours au plus) la
            # prolonge à sa hauteur : une année dense reste un seul ruban, sans marches
            near = [q for q in placed if q["rl"] > 1 and len(run) > 1 and (
                0 < run[0]["i"] - q["i"] <= CONT_DAYS or 0 < q["i"] - run[-1]["i"] <= CONT_DAYS)]
            if near:
                q = min(near, key=lambda q: (min(abs(q["i"] - run[0]["i"]),
                                                 abs(q["i"] - run[-1]["i"])), q["i"]))
                end = geo[0] if q["i"] < run[0]["i"] else geo[-1]
                g0 = clamp((q["y"] - q["sy"] - end["off"]) / unit, -JIT_MAX, JIT_MAX)
                gmax = JIT_MAX
                # voisines des deux côtés : le filet s'incline doucement pour les rejoindre
                prev = [r for r in near if r["i"] < run[0]["i"]]
                nxt = [r for r in near if r["i"] > run[-1]["i"]]
                if prev and nxt:
                    a = max(prev, key=lambda r: r["i"])
                    z = min(nxt, key=lambda r: r["i"])
                    ramp = ((z["y"] - z["sy"] - geo[-1]["off"]) -
                            (a["y"] - a["sy"] - geo[0]["off"])) / (geo[-1]["x"] - geo[0]["x"])
                    if abs(ramp) <= RAMP_MAX:
                        for s in geo:
                            s["off"] += ramp * (s["x"] - geo[0]["x"])
                        g0 = clamp((a["y"] - a["sy"] - geo[0]["off"]) / unit, -JIT_MAX, JIT_MAX)
            cands = [clamp(g0 + flip * c, -gmax, gmax) for c in DODGE]
        best = None
        for gk in cands:
            base = gk * SIGMA_STAR * max(anchor["w"], STAR_W_MIN) - a_side
            for s in geo:
                s["y"] = s["sy"] + clamp(base + s["off"], -s["lim"], s["lim"])
            hits, steep, room = 0, 0, 99.0
            for s in geo:
                for q in placed:
                    ddx = abs(q["x"] - s["x"])
                    if ddx > 60.0:
                        continue
                    ddy = abs(q["y"] - s["y"])
                    room = min(room, math.hypot(ddx, ddy) - s["cr"] - q["cr"] - SEP)
                    hits += spike_hits(s, q) + spike_hits(q, s)
                    if ddx < STEEP[0] * dx_day and ddy > STEEP[1] * ddx + STEEP[2]:
                        steep += 1
            score = (hits == 0 and room >= 0.0, -hits, min(room, 0.0), -steep)
            if best is None or score > best[0]:
                best = (score, [s["y"] for s in geo])
            if score[0] and steep == 0:
                break
        for s, y in zip(geo, best[1]):
            s["y"] = y
            del s["off"], s["lim"]
            placed.append(s)
            stars.append(s)
    stars.sort(key=lambda s: s["i"])
    for p in pts:
        if p["n"] == 0:
            dust.append({"date": p["date"], "day": p["day"], "i": p["i"], "x": p["x"],
                         "sy": p["sy"], "y": p["sy"] + p["g"] * SIGMA_DUST * p["w"],
                         "g": int(h01(p["date"], "dg") * 3)})

    def clouds(tag, count, rxr, ryr, jit, op):
        out = []
        for k in range(count):
            u = (k + 0.2 + 0.6 * h01(tag, k)) / count
            x = X0 + (X1 - X0) * u
            y = spine_at(ord_at(u)) + (h01(tag, k, "y") - 0.5) * jit
            rot = math.degrees(math.atan(slope_at(u)))
            rx, ry = fit_ellipse(x, y, rxr[0] + rxr[1] * h01(tag, k, "rx"),
                                 (ryr[0] + ryr[1] * h01(tag, k, "ry")) * width(u) + ryr[2], rot)
            a = act_at(u)
            out.append({"x": x, "y": y, "rx": rx, "ry": ry, "rot": rot,
                        "o": (op[0] + op[1] * h01(tag, k, "o")) * (op[2] + op[3] * a)})
        return out

    aura = clouds("aura", AURA_CLOUDS, (80.0, 30.0), (24.0, 10.0, 12.0), 10.0,
                  (0.6, 0.4, 0.5, 0.5))
    haze = clouds("cloud", BAND_CLOUDS, (50.0, 25.0), (14.0, 8.0, 8.0), 6.0,
                  (0.45, 0.3, 0.55, 0.7))
    core = clouds("core", CORE_CLOUDS, (30.0, 16.0), (4.0, 3.0, 2.5), 3.0,
                  (0.6, 0.4, 0.22, 0.78))

    # nébuleuses : maxima locaux de l'activité (4 au plus, espacés de 40 jours)
    nebula = []
    if peak > 0:
        cands = [i for i in range(n)
                 if act[i] > 0.2 * peak
                 and act[i] >= (act[i - 1] if i > 0 else -1)
                 and act[i] >= (act[i + 1] if i + 1 < n else -1)]
        cands.sort(key=lambda i: (-act[i], i))
        picked = []
        for i in cands:
            if all(abs(i - j) >= 40 for j in picked):
                picked.append(i)
            if len(picked) == 4:
                break
        for i in sorted(picked):
            u = u_of(i)
            k = act[i] / peak
            rx, ry = 64 + 46 * k, 30 + 14 * k
            x = clamp(pos(i), rx * 0.75, W - rx * 0.75)
            y = spine_at(ord_at(u))
            rot = math.degrees(math.atan(slope_at(u)))
            rx, ry = fit_ellipse(x, y, rx, ry, rot)
            nebula.append({"x": x, "y": y, "k": k, "rot": rot, "rx": rx, "ry": ry})

    # mèches : quelques filets de brume qui longent la rivière (la touche peinte de l'avatar)
    wisps = []
    for off, amp, ph, u0, u1, wd, op in (
            (-16.0, 5.0, 0.3, 0.04, 0.46, 3.2, 0.8), (14.0, 4.0, 1.9, 0.16, 0.64, 3.8, 1.0),
            (-11.0, 6.0, 3.1, 0.40, 0.93, 3.0, 0.9), (19.0, 5.0, 4.4, 0.55, 0.97, 2.6, 0.7),
            (4.0, 7.0, 2.2, 0.08, 0.30, 2.2, 0.6), (-23.0, 4.0, 5.5, 0.66, 0.90, 2.4, 0.55)):
        line = []
        for j in range(13):
            u = u0 + (u1 - u0) * j / 12.0
            line.append((X0 + (X1 - X0) * u,
                         spine_at(ord_at(u)) + (off + amp * math.sin(ph + 9.0 * u)) * width(u)))
        wisps.append({"pts": line, "x0": X0 + (X1 - X0) * u0, "x1": X0 + (X1 - X0) * u1,
                      "w": wd, "o": op})

    # axe de la comète (= la rivière) : une fonction de x, donc toujours vers la droite
    spine = [(X0 + (X1 - X0) * j / 32.0, spine_at(ord_at(j / 32.0))) for j in range(33)]

    # Aujourd'hui = dernier jour du calendrier : le curseur s'y pose, juste après, et au-delà
    # de tout ce qui pourrait le traverser à sa hauteur (cœur ou aigrette, à son maximum).
    cy = spine_at(o1)
    reach = X1
    for s in stars:
        gap = max(0.0, abs(s["y"] - cy) - CUR_H - 1.0)
        if gap < s["cr"]:
            reach = max(reach, s["x"] + math.sqrt(s["cr"] ** 2 - gap ** 2))
        if s["reach_h"] and gap < s["reach_v"]:
            reach = max(reach, s["x"] + s["reach_h"] * arm_extent(gap / s["reach_v"]))
    cursor = {"x": min(max(X1 + 7.0, reach + CUR_L + 1.5), W - EDGE - CUR_R - 0.5), "y": cy}

    return {"stars": stars, "dust": dust, "aura": aura, "clouds": haze, "core": core,
            "nebula": nebula, "wisps": wisps, "spine": spine, "storm": storm_clouds(days),
            "months": month_marks(days, pos) if MONTHS else [],
            "cursor": cursor, "size": size, "nmax": nmax, "lit": peak > 0,
            "glint_thr": glint_thr,
            "flare_thr": count_threshold(star_counts, MAX_FLARES, hard=72)}


# -------------------------------------------------------------------------------- SVG ----

def keytimes(times):
    return ";".join(f4(clamp(t / T, 0.0, 1.0)) for t in times)


def radial(gid, stops):
    return '<radialGradient id="%s">%s</radialGradient>' % (gid, "".join(
        '<stop offset="%s" stop-color="%s" stop-opacity="%s"/>' % (f2(o), c, f2(a))
        for o, c, a in stops))


def render(scene, theme_name, login):
    th = THEMES[theme_name]
    stars, size = scene["stars"], scene["size"]
    out = []
    o = out.append

    path_d, plen, cum = smooth_path(scene["spine"])
    xs = [rounded(p)[0] for p in scene["spine"]]

    def along(x):
        if x <= xs[0]:
            return 0.0
        for k in range(len(xs) - 1):
            if x <= xs[k + 1]:
                return cum[k] + (cum[k + 1] - cum[k]) * (x - xs[k]) / (xs[k + 1] - xs[k])
        return cum[-1]

    b = A + TRAVEL                # la comète arrive sur aujourd'hui
    c = b + 1.4                   # la lueur commence à s'éteindre
    dfade = c + 1.6               # ... et a disparu
    spline_mid = " ".join(f2(v) for v in EASE)
    ksp = "0 0 1 1;%s;0 0 1 1" % spline_mid
    rep = 'dur="%ss" repeatCount="indefinite"' % f1(T)

    o('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d" '
      'fill="none" role="img" aria-labelledby="t d">' % (W, H, W, H))
    o('<title id="t">%s</title>' % escape(
        "GitHub contributions of %s over the last year, drawn as a night sky" % login))
    o('<desc id="d">%s</desc>' % escape(
        "One star for every day of the last year, from the oldest day on the left to today on "
        "the right. The more contributions a day has, the brighter its star; days without "
        "contributions are faint dust. A comet runs along the band of stars and a blinking "
        "cursor marks today."))

    # --- styles -------------------------------------------------------------------------
    # CSS : scintillement (sur des groupes, pas étoile par étoile) et clignotement du curseur.
    # .mo = calques animés en SMIL ; .st = leur version fixe, montrée seulement si
    # l'utilisateur a demandé moins d'animations (le CSS ne peut pas suspendre le SMIL,
    # mais il peut masquer les calques qui le portent).
    css = []
    for k, lo in enumerate(th["twinkle"]):
        css.append("@keyframes w%d{0%%,100%%{opacity:1}50%%{opacity:%s}}" % (k, f2(lo)))
    css.append("@keyframes cu{0%{opacity:1}50%{opacity:0}}")
    # 3 amplitudes (t bas, moyen, haut) x 3 phases ; les plus brillantes scintillent un peu plus
    phases = [(5.9, -0.7), (7.3, -3.1), (8.7, -5.6)]
    for tier in range(3):
        for p, (dur, delay) in enumerate(phases):
            css.append(".a%d%d{animation:w%d %ss ease-in-out %ss infinite}"
                       % (tier, p, tier, f1(dur - 0.6 * tier), f1(delay)))
    css.append(".d1{animation:w3 6.5s ease-in-out -1s infinite}")
    css.append(".d2{animation:w3 8.3s ease-in-out -4.6s infinite}")
    css.append(".cu{animation:cu %ss step-end infinite}" % f2(2 * BLINK))
    css.append("text{font:500 %spx 'JetBrains Mono','Cascadia Code',Consolas,'SF Mono',"
               "ui-monospace,Menlo,'Liberation Mono',monospace;letter-spacing:.4px;"
               "text-anchor:middle}" % f1(MONTH_FS))
    # écran étroit (image < 560 px) : un mois sur trois, lisible ; les autres s'effacent
    css.append("@media (max-width:%dpx){text{font-size:%spx;letter-spacing:0}.m{display:none}}"
               % (NARROW_PX, f1(MONTH_FS_NARROW)))
    css.append(".st{display:none}")
    css.append("@media (prefers-reduced-motion:reduce){*{animation:none!important}"
               ".mo{display:none}.st{display:inline}}")
    o("<style>%s</style>" % "".join(css))

    # --- dégradés -----------------------------------------------------------------------
    o("<defs>")
    hop = th["halo_op"] * (0.45 + 0.55 * size)
    o(radial("hl", ((0, th["halo"], hop), (0.35, th["halo"], hop * 0.32), (1, th["halo"], 0))))
    o(radial("fl", ((0, th["flare"], 0.9), (0.3, th["flare"], 0.35), (1, th["flare"], 0))))
    o(radial("hg", ((0, th["head_glow"], 0.95), (0.28, th["head_glow"], 0.4),
                    (1, th["head_glow"], 0))))
    c0, c1 = th["band"]
    o(radial("bd", ((0, c0, th["band_op"]), (0.45, c1, th["band_op"] * 0.45), (1, c1, 0))))
    o(radial("ba", ((0, th["aura"], th["aura_op"]), (0.5, th["aura"], th["aura_op"] * 0.4),
                    (1, th["aura"], 0))))
    k0, k1 = th["bcore"]
    o(radial("bc", ((0, k0, th["bcore_op"]), (0.5, k1, th["bcore_op"] * 0.4), (1, k1, 0))))
    storm = scene["storm"] if th["storm"] else []
    if storm:
        o(radial("sc", ((0, th["storm"], th["storm_op"]), (0.55, th["storm"],
                                                           th["storm_op"] * 0.45),
                        (1, th["storm"], 0))))
    for i, nb in enumerate(scene["nebula"]):
        lo, hi = th["neb_op"]
        op = lo + (hi - lo) * nb["k"]
        n0, n1 = th["neb"]
        o(radial("n%d" % i, ((0, n0, op), (0.3, n0, op * 0.62), (0.62, n1, op * 0.22),
                             (1, n1, 0))))
    # la lueur naît dans le noir à gauche et arrive pleine sur aujourd'hui
    o('<linearGradient id="tr" gradientUnits="userSpaceOnUse" x1="%s" x2="%s" y1="0" y2="0">'
      '<stop offset="0" stop-color="#fff" stop-opacity="0"/>'
      '<stop offset=".12" stop-color="#fff" stop-opacity="1"/></linearGradient>'
      '<mask id="tm" maskUnits="userSpaceOnUse" x="0" y="0" width="%d" height="%d">'
      '<rect width="%d" height="%d" fill="url(#tr)"/></mask>'
      % (f1(X0), f1(X1), W, H, W, H))
    for k, wp in enumerate(scene["wisps"]):
        o('<linearGradient id="w%d" gradientUnits="userSpaceOnUse" x1="%s" x2="%s" y1="0" '
          'y2="0"><stop offset="0" stop-color="%s" stop-opacity="0"/>'
          '<stop offset=".5" stop-color="%s"/>'
          '<stop offset="1" stop-color="%s" stop-opacity="0"/></linearGradient>'
          % (k, f1(wp["x0"]), f1(wp["x1"]), th["wisp"], th["wisp"], th["wisp"]))
    o("</defs>")

    def ellipse(cl, fill, op=None):
        return ('<ellipse cx="%s" cy="%s" rx="%s" ry="%s" transform="rotate(%s %s %s)" '
                'fill="url(#%s)"%s/>'
                % (f1(cl["x"]), f1(cl["y"]), f1(cl["rx"]), f1(cl["ry"]), f1(cl["rot"]),
                   f1(cl["x"]), f1(cl["y"]), fill,
                   "" if op is None else ' opacity="%s"' % f2(min(op, 1.0))))

    # --- nuages d'orage (sombre seulement) : le fond peint de l'avatar, immobile -----------
    if storm:
        o("<g>%s</g>" % "".join(ellipse(cl, "sc", cl["o"]) for cl in storm))

    # --- la rivière : aura large, brume, puis cœur étroit, plus denses là où l'année a brillé
    o("<g>")
    for layer, grad in (("aura", "ba"), ("clouds", "bd"), ("core", "bc")):
        for cl in scene[layer]:
            if cl["rx"] > 0.5 and cl["ry"] > 0.5:
                o(ellipse(cl, grad, cl["o"]))
    o("</g>")
    # nébuleuses des périodes actives : respirent avec le passage de la comète
    nebula = "".join(ellipse(nb, "n%d" % i) for i, nb in enumerate(scene["nebula"]))
    if nebula:
        o('<g class="mo" opacity=".75">')
        o('<animate attributeName="opacity" values=".75;.75;1;1;.75;.75" keyTimes="%s" %s/>'
          % (keytimes([0, A, b, c, dfade, T]), rep))
        o(nebula)
        o("</g>")
        o('<g class="st" opacity=".88">%s</g>' % nebula)
    # mèches de brume
    for k, wp in enumerate(scene["wisps"]):
        d, _, _ = smooth_path(wp["pts"])
        o('<path d="%s" stroke="url(#w%d)" stroke-opacity="%s" stroke-width="%s" '
          'stroke-linecap="round"/>' % (d, k, f2(th["wisp_op"] * wp["o"]), f2(wp["w"])))

    # --- lueur : la rivière s'éclaire derrière la comète, puis s'éteint (sous la poussière)
    # (large et douce : jamais un fil fin qui ferait courbe de graphique ; aucune lueur sur
    # une année vide, la comète y passe seule)
    def stroke(color, op, width, extra=""):
        return ('<path d="%s" stroke="%s" stroke-opacity="%s" stroke-width="%s" '
                'stroke-linecap="round"%s' % (path_d, color, f2(op), f2(width), extra))

    if scene["lit"]:
        o('<g class="mo" mask="url(#tm)">')
        o('<animate attributeName="opacity" values="1;1;0;0" keyTimes="%s" %s/>'
          % (keytimes([0, c, dfade, T]), rep))
        for color, op, width in th["glow"]:
            o(stroke(color, op, width, ' stroke-dasharray="%s %s" stroke-dashoffset="%s">'
                     % (f1(plen + 1), f1(plen + 12), f1(plen + 3))))
            o('<animate attributeName="stroke-dashoffset" values="%s;%s;0;0" keyTimes="%s" '
              'calcMode="spline" keySplines="%s" %s/>'
              % (f1(plen + 3), f1(plen + 3), keytimes([0, A, b, T]), ksp, rep))
            o("</path>")
        o("</g>")
        # version fixe (moins d'animations) : la lueur entière, plus discrète
        o('<g class="st" mask="url(#tm)" opacity=".7">%s</g>'
          % "".join(stroke(cl, op, wd, "/>") for cl, op, wd in th["glow"]))

    # --- poussière : un grain par jour vide (tous identiques) ------------------------------
    dust_r = th["dust_r"] * core_scale(size)        # même échelle que les cœurs d'étoiles
    for g in range(3):
        grains = [d for d in scene["dust"] if d["g"] == g]
        if not grains:
            continue
        o('<g fill="%s" opacity="%s"%s>'
          % (th["dust"], f2(th["dust_op"]), ' class="d%d"' % g if g else ""))
        for d in grains:
            o('<circle cx="%s" cy="%s" r="%s"/>' % (f1(d["x"]), f1(d["y"]), f2(dust_r)))
        o("</g>")

    # --- comète : traînée en 4 couches (un tiret qui glisse, de plus en plus court, fin et
    # opaque vers la tête : un dégradé le long du trait sans dégradé SVG) + tête --------
    o('<g class="mo">')
    speed = plen / TRAVEL
    for color, width, op, tail in zip(th["tail"], TAIL_W, (0.22, 0.38, 0.62, 1.0),
                                      (150.0, 92.0, 48.0, 18.0)):
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
      % (keytimes([0, A, A + 0.4, b - 0.15, b + 0.45, T]), rep))
    o('<animateMotion path="%s" keyPoints="0;0;1;1" keyTimes="%s" calcMode="spline" '
      'keySplines="%s" %s/>' % (path_d, keytimes([0, A, b, T]), ksp, rep))
    o('<circle r="11" fill="url(#hg)"/>')
    o('<circle r="2" fill="%s"/>' % th["head"])
    o("</g>")
    o("</g>")

    # --- étoiles ---------------------------------------------------------------------------
    # halos : seuls à scintiller, regroupés par classe (amplitude x phase) -> une poignée de
    # groupes animés, quel que soit le nombre d'étoiles
    by_n = sorted(stars, key=lambda s: (s["n"], s["date"]))
    styles = {s["date"]: star_style(s["t"], size, th) for s in stars}
    groups = {}
    for s in by_n:
        st = styles[s["date"]]
        cls = "a%d%d" % (st["tier"], int(h01(s["date"], "tw") * 3))
        groups.setdefault(cls, []).append(
            '<circle cx="%s" cy="%s" r="%s" fill="url(#hl)" fill-opacity="%s"/>'
            % (f1(s["x"]), f1(s["y"]), f3(min(st["hr"], edge_room(s["x"], s["y"]))),
               f2(st["ho"])))
    o('<g id="h">')
    for cls in sorted(groups):
        o('<g class="%s">' % cls)
        o("\n".join(groups[cls]))
        o("</g>")
    o("</g>")
    # cœurs et aigrettes : fixes (ils portent l'éclat du jour), du plus faible au plus
    # brillant (le record passe devant). Seule l'aigrette du record respire, en grandissant
    # seulement, au même rythme et à la même phase pour tous les jours record : à tout
    # instant, aucune aigrette ne dépasse celle d'un jour plus contributif.
    o('<g id="s">')
    for s in by_n:
        st = styles[s["date"]]
        x, y = f1(s["x"]), f1(s["y"])
        g = []
        if s["glint"]:
            # aigrette anamorphique : longues branches horizontales (la rivière est horizontale)
            ln = st["spark"]
            sc = "%s %s" % (f2(ln), f2(ln * GLINT_V))
            body = 'd="%s" fill="%s" fill-opacity="%s"' % (SPARK, th["glint"], f2(st["spark_op"]))
            if s["pulse"]:
                # l'échelle animée s'ajoute (additive) à la translation de base
                sc2 = "%s %s" % (f2(ln * PULSE[0]), f2(ln * GLINT_V * PULSE[1]))
                g.append('<path class="mo" %s transform="translate(%s %s)">'
                         '<animateTransform attributeName="transform" type="scale" '
                         'additive="sum" values="%s;%s;%s" dur="%ss" repeatCount="indefinite"/>'
                         '</path><path class="st" %s transform="translate(%s %s) scale(%s)"/>'
                         % (body, x, y, sc, sc2, sc, f1(PULSE_DUR), body, x, y, sc))
            else:
                g.append('<path %s transform="translate(%s %s) scale(%s)"/>' % (body, x, y, sc))
        g.append('<circle cx="%s" cy="%s" r="%s" fill="%s"/>' % (x, y, f2(st["cr"]), st["color"]))
        o("".join(g))
    o("</g>")

    # --- éclats : chaque gros jour s'allume au passage de la comète -----------------------
    flares = [s for s in stars if s["n"] >= scene["flare_thr"]]
    if flares:
        o('<g class="mo">')
        for s in flares:
            dist = along(s["x"])
            ti = A + TRAVEL * ease_time_for_progress(clamp(dist / plen, 0.0, 1.0))
            today = s["u"] >= 1.0                       # la comète finit sur aujourd'hui
            decay, grow, peak = (2.4, 2.6, "1") if today else (1.4, 1.9, ".85")
            room = edge_room(s["x"], s["y"])            # l'éclat ne touche jamais le bord
            r1 = min((6 + 9 * s["t"]) * (0.4 + 0.6 * size) * grow, room)
            r0 = r1 / grow
            times = keytimes([0, max(ti - 0.06, 0.01), ti + 0.14, min(ti + decay, T - 0.01), T])
            o('<circle cx="%s" cy="%s" r="%s" fill="url(#fl)" opacity="0">'
              % (f1(s["x"]), f1(s["y"]), f1(r0)))
            o('<animate attributeName="opacity" values="0;0;%s;0;0" keyTimes="%s" %s/>'
              % (peak, times, rep))
            o('<animate attributeName="r" values="%s;%s;%s;%s;%s" keyTimes="%s" %s/>'
              % (f1(r0 * 0.5), f1(r0 * 0.5), f1(r0 * 0.9), f1(r1), f1(r1), times, rep))
            o("</circle>")
        o("</g>")

    # --- repères de mois : discrets, en bas, comme l'axe du graphe GitHub ------------------
    if scene["months"]:
        o('<g fill="%s" opacity="%s">' % (th["month"], f2(th["month_op"])))
        for m in scene["months"]:
            o('<text%s x="%s" y="%d">%s</text>'
              % ("" if m["narrow"] else ' class="m"', f1(m["x"]), MONTH_Y, m["label"]))
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


def budget(svg):
    """(octets, éléments, nœuds animés : groupes à animation CSS + éléments SMIL)."""
    elems = svg.count("<") - svg.count("</")
    anim = len(re.findall(r'class="(?:a\d\d|d\d|cu)"', svg)) + svg.count("<animate")
    return len(svg.encode("utf-8")), elems, anim


def over_budget(svg):
    size, elems, anim = budget(svg)
    if size > MAX_BYTES or elems > MAX_ELEMS or anim > MAX_ANIM:
        return "%d B (max %d), %d elements (max %d), %d animated (max %d)" % (
            size, MAX_BYTES, elems, MAX_ELEMS, anim, MAX_ANIM)
    return None


# --------------------------------------------------------------------------- auto-test ----

# Forme de l'année réelle au 2026-10-12 : {jours avant la fin du calendrier: contributions}.
REAL_SHAPE = {336: 6, 335: 27, 334: 11, 333: 5, 327: 7, 133: 8, 132: 5, 124: 7, 123: 4, 0: 4}

HALO_GROUP_RE = re.compile(r'<g class="a(\d)\d">\n(.*?)\n</g>', re.S)
HALO_RE = re.compile(r'<circle cx="([-\d.]+)" cy="([-\d.]+)" r="([\d.]+)" fill="url\(#hl\)" '
                     r'fill-opacity="([\d.]+)"/>')
CORE_RE = re.compile(  # un cœur par ligne, précédé de son aigrette éventuelle
    r'(?:<path (?:class="mo" )?d="[^"]+" fill="#[0-9a-f]{6}" fill-opacity="([\d.]+)" '
    r'transform="translate\([-\d. ]+\)(?: scale\(([\d.]+) [\d.]+\))?"'
    r'(?:/>|>.*?</path><path class="st" [^>]*? scale\(([\d.]+) [\d.]+\)"/>))?'
    r'<circle cx="([-\d.]+)" cy="([-\d.]+)" r="([\d.]+)" fill="(#[0-9a-f]{6})"/>')
DUST_RE = re.compile(r'<circle cx="[-\d.]+" cy="[-\d.]+" r="([\d.]+)"/>')
DUST_INK_RE = re.compile(r'<g fill="(#[0-9a-f]{6})" opacity="([\d.]+)"(?: class="d\d")?>'
                         r'\n<circle')
PULSE_RE = re.compile(r'<path class="mo" d="[^"]+" fill="#[0-9a-f]{6}" fill-opacity="[\d.]+" '
                      r'transform="translate\(([-\d.]+) [-\d.]+\)"><animateTransform ([^>]*)/>')
PULSE_VALUES_RE = re.compile(r'values="([\d.]+) ([\d.]+);([\d.]+) ([\d.]+);([\d.]+) ([\d.]+)" '
                             r'dur="([\d.]+)s" repeatCount="indefinite"$')
# fonds de page GitHub pour chaque variante (sombre, sombre atténué, sombre contrasté ; clair)
PAGES = {"dark": ("#0d1117", "#22272e", "#010409"), "light": ("#ffffff",)}


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


def parse_stars(svg, theme, fail):
    """Relit dans le SVG produit, pour chaque étoile : (tier, halo r, halo op, aigrette op,
    aigrette, cœur r, couleur du cœur), indexé par abscisse (une par jour, toutes distinctes)."""
    hl = svg[svg.index('<g id="h">'):svg.index('<g id="s">')]
    halos = {}
    for gm in HALO_GROUP_RE.finditer(hl):
        for line in gm.group(2).split("\n"):
            m = HALO_RE.fullmatch(line)
            if not m:
                fail("%s: unexpected halo markup: %s" % (theme, line[:120]))
            halos[m.group(1)] = (int(gm.group(1)), float(m.group(3)), float(m.group(4)))
    layer = svg[svg.index('<g id="s">'):]
    layer = layer[:layer.index("\n</g>\n")]
    stars = {}
    for line in layer.split("\n")[1:]:
        m = CORE_RE.fullmatch(line)
        if not m:
            fail("%s: unexpected star markup: %s" % (theme, line[:120]))
        sop, sc, sc_st, cx, _, cr, color = m.groups()
        if cx not in halos:
            fail("%s: star at x=%s has no halo" % (theme, cx))
        stars[cx] = halos[cx] + (float(sop or 0), float(sc or sc_st or 0), float(cr), color)
    if len(stars) != len(halos):
        fail("%s: %d halos for %d stars" % (theme, len(halos), len(stars)))
    return stars


def check_brightness(scene, svg, theme, fail):
    """L'éclat est une fonction croissante du nombre, lue dans le SVG produit : chaque
    attribut (scintillement, halo, opacité, aigrette, cœur, luminance) ne décroît jamais quand
    le nombre augmente, deux jours égaux sont identiques, deux nombres distincts diffèrent, le
    record est le plus brillant, et tout jour actif est nettement au-dessus de la poussière."""
    parsed = parse_stars(svg, theme, fail)
    order = sorted(scene["stars"], key=lambda s: (s["n"], s["date"]))
    if len(parsed) != len(order):
        fail("%s: parsed %d stars, expected %d" % (theme, len(parsed), len(order)))

    def key(p):
        lum = luminance(p[6])
        if theme == "light":
            lum = -lum                          # encre sur blanc : plus sombre = plus brillant
        return (p[0], p[1], p[2], p[3], p[4], p[5], lum)

    prev = None
    for s in order:
        p = parsed.get(f1(s["x"]))
        if p is None:
            fail("%s: no star drawn for %s" % (theme, s["date"]))
        k = key(p)
        if prev is not None:
            pn, pk = prev
            if any(a < b - 1e-9 for a, b in zip(k, pk)):
                fail("%s: %d contributions drawn dimmer than %d (%s < %s)"
                     % (theme, s["n"], pn, k, pk))
            if s["n"] == pn and k != pk:
                fail("%s: two days with %d contributions drawn differently" % (theme, s["n"]))
            # strictement plus brillant dès que l'écart d'éclat survit à l'arrondi du SVG
            # (le modèle, lui, est vérifié strictement pour tout écart, cf. self_test)
            dt = s["t"] - pt
            if s["n"] > pn and dt >= 0.004 and not k[1] > pk[1]:
                fail("%s: %d and %d contributions: same halo" % (theme, pn, s["n"]))
            if s["n"] > pn and dt >= 0.02 and not (k[2] > pk[2] and k[5] > pk[5]):
                fail("%s: %d -> %d contributions: halo or core not strictly brighter"
                     % (theme, pn, s["n"]))
        prev = (s["n"], k)
        pt = s["t"]
    if order:
        top = parsed[f1(order[-1]["x"])]
        if order[-1]["n"] != scene["nmax"] or top[6] != ramp(THEMES[theme]["core"], 1.0):
            fail("%s: the record day is not the brightest star" % theme)
        if top[1] < max(p[1] for p in parsed.values()) - 1e-9 or top[2] < 0.99:
            fail("%s: the record day does not have the strongest halo" % theme)
    # aigrettes qui respirent (le record seulement) : même période, même phase, et à tout
    # instant aucune aigrette ne dépasse celle d'un jour plus contributif (le pic d'un jour
    # reste sous le repos de tout jour qui compte plus de contributions)
    pulses = {}
    for m in PULSE_RE.finditer(svg):
        vm = PULSE_VALUES_RE.search(m.group(2))
        if not vm or "begin" in m.group(2):
            fail("%s: unexpected pulse markup: %s" % (theme, m.group(2)[:120]))
        v = [float(a) for a in vm.groups()[:6]]
        if v[0:2] != v[4:6] or v[2] < v[0] or v[3] < v[1]:
            fail("%s: a pulsing aigrette shrinks below its resting size" % theme)
        pulses[m.group(1)] = (v[2], vm.group(7), tuple(v))
    if len(set(p[1] for p in pulses.values())) > 1:
        fail("%s: pulsing aigrettes do not share one period" % theme)
    longest, i = 0.0, 0
    while i < len(order):
        grp = [s for s in order[i:] if s["n"] == order[i]["n"]]
        i += len(grp)
        looks = set(pulses.get(f1(s["x"]), (None, None, None))[2] for s in grp)
        if len(looks) > 1:
            fail("%s: two days with %d contributions pulse differently" % (theme, grp[0]["n"]))
        for s in grp:
            rest = parsed[f1(s["x"])][4]
            if rest < longest - 1e-9:
                fail("%s: %d contributions: aigrette shorter than a smaller day's at its peak"
                     % (theme, s["n"]))
        longest = max([longest] + [pulses.get(f1(s["x"]), (parsed[f1(s["x"])][4],))[0]
                                   for s in grp])
    if pulses and any(s["n"] != scene["nmax"] for s in order
                      if f1(s["x"]) in pulses):
        fail("%s: an aigrette other than the record's pulses" % theme)
    dust = DUST_RE.findall(svg[:svg.index('<g id="h">')])
    if len(set(dust)) > 1:
        fail("%s: empty days drawn differently" % theme)
    if dust and parsed:
        if not min(p[5] for p in parsed.values()) > 2 * float(dust[0]):
            fail("%s: a 1-contribution star is not clearly above the dust" % theme)
        # ... et plus lumineux : luminance de la poussière posée sur la page (couleur x
        # opacité) contre le cœur du jour le moins contributif ; sur blanc, encre plus claire
        ink = set(DUST_INK_RE.findall(svg[:svg.index('<g id="h">')]))
        if len(ink) != 1:
            fail("%s: dust ink not found or not uniform" % theme)
        fill, op = ink.pop()
        lc = luminance(parsed[f1(order[0]["x"])][6])
        for bg in PAGES[theme]:
            ld = luminance(mix(bg, fill, float(op)))
            ratio = (lc + 0.05) / (ld + 0.05) if theme == "dark" else (ld + 0.05) / (lc + 0.05)
            if ratio < 1.5:
                fail("%s: on %s the dust is not clearly dimmer than a 1-contribution star "
                     "(contrast %.2f)" % (theme, bg, ratio))
    if len(dust) + len(parsed) != len(scene["stars"]) + len(scene["dust"]):
        fail("%s: not one mark per day" % theme)


def check_months(days, ms, fail):
    """Repères de mois : le mois en cours sous aujourd'hui, tout mois complet nommé, aucun
    chevauchement ni coupure, à la taille normale comme sur écran étroit (un mois sur trois)."""
    n = len(days)

    def x_of(i):
        return X0 + (X1 - X0) * (i / float(n - 1) if n > 1 else 1.0)

    spans = {}
    for i, d in enumerate(days):
        spans.setdefault((d["day"].year, d["day"].month), []).append(i)
    last = (days[-1]["day"].year, days[-1]["day"].month)
    cur = spans[last]
    if ms[-1]["label"] != MONTH_NAMES[last[1] - 1] or \
            not x_of(cur[0]) - 1e-6 <= ms[-1]["x"] <= X1 + 2.0 + 1e-6 or \
            (len(cur) <= 31 and n >= 300 and ms[-1]["x"] < X1 - 40) or not ms[-1]["narrow"]:
        fail("the current month is not labelled under today")
    for (y, m), idx in spans.items():
        nxt = datetime.date(y + m // 12, m % 12 + 1, 1)
        if (y, m) != last and len(idx) == (nxt - datetime.date(y, m, 1)).days and not any(
                mk["label"] == MONTH_NAMES[m - 1] and x_of(idx[0]) <= mk["x"] <= x_of(idx[-1])
                for mk in ms):
            fail("%s %d is a full month of the year but has no label" % (MONTH_NAMES[m - 1], y))
    for fs in (MONTH_FS, MONTH_FS_NARROW):
        vis = [m for m in ms if fs == MONTH_FS or m["narrow"]]
        for a, b in zip(vis, vis[1:]):
            if a["x"] + month_width(a["label"], fs) / 2 + 2 > \
                    b["x"] - month_width(b["label"], fs) / 2:
                fail("month labels %s and %s overlap" % (a["label"], b["label"]))
        for m in vis:
            if m["x"] - month_width(m["label"], fs) / 2 < 0 or \
                    m["x"] + month_width(m["label"], fs) / 2 > W:
                fail("month label %s is cut by the edge" % m["label"])
    if any(m["narrow"] and m["back"] % 3 for m in ms):
        fail("a month other than one in three stays on narrow screens")
    if len(ms) > 13:
        fail("too many month markers")


def check_layout(days, scene, fail, apart=False):
    """Une marque par jour, l'abscisse ne dépend que du rang du jour, la hauteur ne dépend pas
    du jour de la semaine, rien ne sort du ciel. Rafales : quelques jours actifs d'affilée
    forment un nœud plus large que haut, en filet continu (jamais une colonne de semaine).
    Rien ne traverse le curseur. `apart` : d'une rafale à l'autre, ni cœur ni aigrette ne se
    touchent, sans saut brusque de hauteur (jours épars ou petites rafales, comme l'année
    réelle)."""
    n = len(days)
    pts = sorted(scene["stars"] + scene["dust"], key=lambda p: p["i"])
    if [p["date"] for p in pts] != [d["date"] for d in days]:
        fail("not exactly one star or dust grain per day, in date order")
    for p in pts:
        want = X0 + (X1 - X0) * (p["i"] / float(n - 1) if n > 1 else 1.0)
        if abs(p["x"] - want) > 1e-9:
            fail("x of %s does not come from its rank in the year" % p["date"])
        if not (8 < p["y"] < MONTH_Y - 12):
            fail("%s leaves the sky (y=%.1f)" % (p["date"], p["y"]))
    if n >= 300:
        # part de la dispersion verticale (autour de l'axe) expliquée par le jour de la semaine :
        # ~0,02 attendu ; des lignes par jour de semaine donneraient ~1
        res = [(p["day"].weekday(), p["y"] - p["sy"]) for p in pts]
        mean = sum(r for _, r in res) / len(res)
        tot = sum((r - mean) ** 2 for _, r in res) or 1.0
        between = 0.0
        for wd in range(7):
            grp = [r for w, r in res if w == wd]
            if grp:
                between += len(grp) * (sum(grp) / len(grp) - mean) ** 2
        if between / tot > 0.1:
            fail("height depends on the weekday (R2 = %.2f)" % (between / tot))
    stars = scene["stars"]
    by_i = {s["i"]: s for s in stars}
    dx_day = (X1 - X0) / float(n - 1) if n > 1 else 0.0
    spread = 2.0 * max(BRAID * core_scale(scene["size"]), BRAID_LONG)
    # jours actifs d'affilée (2 à 7) : y-span <= 1,5 x-span + un diamètre de cœur ; à partir
    # de 4 jours, plus large que 2/3 de haut ; 7 jours : plus large que haut
    for s in stars:
        win = [s]
        while len(win) < 7 and win[-1]["i"] + 1 in by_i:
            win.append(by_i[win[-1]["i"] + 1])
            k = len(win)
            xspan = (k - 1) * dx_day
            yspan = max(w["y"] for w in win) - min(w["y"] for w in win)
            if yspan > 1.5 * xspan + 2 * max(w["cr"] for w in win) + 1e-6 or \
                    (k >= 4 and yspan > 1.5 * xspan) or (k == 7 and yspan >= xspan):
                fail("%d active days from %s stack up (%.1f wide, %.1f tall)"
                     % (k, s["date"], xspan, yspan))
    # dans une rafale, le filet avance par petits pas, dans l'ordre des dates (pas de dents
    # de scie) : |dy| <= pente douce + l'épaisseur du nœud ou du ruban ; de même d'une rafale
    # à la suivante quand elle la prolonge (une année dense reste un ruban, sans marches)
    for a, b in zip(stars, stars[1:]):
        joined = a["run"] == b["run"] or (
            a["rl"] > 1 and b["rl"] > 1 and b["i"] - a["i"] <= CONT_DAYS)
        if joined and abs(b["y"] - a["y"]) > \
                0.7 * (b["x"] - a["x"]) + spread + 0.5 + 1e-6:
            fail("burst path jumps between %s and %s (%.1f)"
                 % (a["date"], b["date"], b["y"] - a["y"]))
    if apart:
        for a in stars:
            for b in stars:
                if a["run"] == b["run"] or not a["i"] < b["i"] <= a["i"] + 30:
                    continue
                if math.hypot(a["x"] - b["x"], a["y"] - b["y"]) < a["cr"] + b["cr"]:
                    fail("stars %s and %s overlap" % (a["date"], b["date"]))
                if spike_hits(a, b, 0.0) or spike_hits(b, a, 0.0):
                    fail("an aigrette of %s / %s runs into the other's core"
                         % (a["date"], b["date"]))
                ddx = b["x"] - a["x"]
                if ddx < STEEP[0] * dx_day and abs(b["y"] - a["y"]) > STEEP[1] * ddx + STEEP[2]:
                    fail("stars %s and %s stack up" % (a["date"], b["date"]))
    # curseur : ni cœur ni aigrette (à son maximum) ne touchent sa barre ni son halo
    cx, cy = scene["cursor"]["x"], scene["cursor"]["y"]
    x0, x1, y0, y1 = cx - CUR_L - 1.0, cx + CUR_R + 1.0, cy - CUR_H - 1.0, cy + CUR_H + 1.0
    if x1 > W - EDGE:
        fail("the cursor leaves the sky")
    edge = [(x0 + (x1 - x0) * k / 40.0, y) for k in range(41) for y in (y0, y1)] + \
        [(x, y0 + (y1 - y0) * k / 80.0) for k in range(81) for x in (x0, x1)]
    for s in stars:
        tips = [(s["x"], s["y"]), (s["x"] + max(s["cr"], s["reach_h"]), s["y"])]
        if any(x0 <= px <= x1 and y0 <= py <= y1 for px, py in tips) or \
                any(in_star(s, px, py) for px, py in edge):
            fail("the star of %s runs into the cursor" % s["date"])
    xs = [p[0] for p in scene["spine"]]
    if any(q <= p for p, q in zip(xs, xs[1:])):
        fail("the comet path goes back")
    if scene["months"]:
        check_months(days, scene["months"], fail)


def self_test():
    """Calendriers synthétiques (sans réseau) ; s'arrête en erreur au premier défaut.
    Vérifie : l'échelle d'éclat (modèle) ; une marque par jour, de gauche à droite selon le
    rang, sans dépendre du jour de la semaine ; des rafales plus larges que hautes, sans dents
    de scie (jamais une colonne de semaine) ; ni cœur ni aigrette sur une autre rafale ni sur le
    curseur ; l'éclat strictement croissant avec le nombre de contributions, relu dans le SVG
    produit (aigrette du record qui respire comprise, poussière plus terne qu'un jour à 1
    contribution sur chaque fond de page) ; rien de plus sombre que la page « dark dimmed » ;
    des repères de mois complets pour 366 fins d'année ; sortie déterministe (ordre d'entrée,
    graine de hachage) ; SVG valide et dans le budget (octets, éléments, nœuds animés), pires
    cas compris ; calendriers malformés refusés."""
    def fail_model(msg):
        raise SystemExit("self-test level(): " + msg)

    # modèle : 0 < 1 < 2 < ... < max, plancher solide, record = 1, sur plusieurs records
    for nmax in (1, 2, 3, 5, 27, 100, 1000, 10000):
        ts = [level(k, nmax) for k in range(min(nmax, 2000) + 1)] + [level(nmax, nmax)]
        if ts[0] != 0.0 or ts[1] < FLOOR - 1e-12 or abs(ts[-1] - 1.0) > 1e-12:
            fail_model("bad range for max %d" % nmax)
        if any(b <= a for a, b in zip(ts[:-1], ts[1:-1])):
            fail_model("not strictly increasing for max %d" % nmax)
        for th in THEMES.values():
            sts = [star_style(t, 0.6, th) for t in ts[1:-1]]
            for k in ("cr", "hr", "ho", "spark", "spark_op", "tier"):
                if any(b[k] < a[k] for a, b in zip(sts, sts[1:])):
                    fail_model("%s decreases for max %d" % (k, nmax))
            for k in ("cr", "hr", "ho"):
                if any(b[k] <= a[k] for a, b in zip(sts, sts[1:])):
                    fail_model("%s not strictly increasing for max %d" % (k, nmax))

    # années où, d'une rafale à l'autre, ni cœur ni aigrette ne se touchent (l'année réelle
    # et ses rafales comprises) ; dans une année dense, les rafales se touchent
    APART = ("real", "single", "today only", "ladder", "ones", "record", "leap", "two days",
             "streak14", "week7", "streak20+real", "dec 1st", "mar 1st", "today record",
             "eve record", "twin records", "bursts")
    sat = datetime.date(2026, 10, 17)            # fin un samedi -> calendrier de 371 jours
    cases = [
        ("real", synthetic_weeks(REAL_SHAPE)),
        ("empty", synthetic_weeks({})),
        ("single", synthetic_weeks({40: 3})),
        ("today only", synthetic_weeks({0: 1})),
        ("first day only", synthetic_weeks({365: 5})),
        ("one week", synthetic_weeks({d: 1 + d for d in range(7, 14)})),
        # rafales : jamais une colonne (un nœud plus large que haut, en filet continu)
        ("streak14", synthetic_weeks({d: 1 for d in range(100, 114)})),
        ("week7", synthetic_weeks({d: 1 + d % 5 for d in range(150, 157)})),
        ("streak20+real", synthetic_weeks(dict(list(REAL_SHAPE.items()) +
                                               [(d, 1 + d % 4) for d in range(200, 220)]))),
        ("bursts", synthetic_weeks({d: 1 + (d * 5) % 17 for k in range(0, 360, 9)
                                    for d in range(k, k + 1 + k % 4)})),
        # aujourd'hui (ou la veille) est le record : son aigrette ne traverse pas le curseur
        ("today record", synthetic_weeks({0: 30, 6: 2, 40: 3, 41: 1})),
        ("eve record", synthetic_weeks({1: 30, 0: 1, 90: 2})),
        # record partagé : les aigrettes record respirent ensemble (même période, même phase)
        ("twin records", synthetic_weeks({300: 9, 120: 9, 119: 2, 30: 1})),
        # fin un 1er du mois : le mois précédent garde son repère
        ("dec 1st", synthetic_weeks(REAL_SHAPE, datetime.date(2026, 12, 1))),
        ("mar 1st", synthetic_weeks(REAL_SHAPE, datetime.date(2027, 3, 1))),
        ("burst", synthetic_weeks({d: 1 + (d * 7) % 13 for d in range(0, 14)})),
        ("ladder", synthetic_weeks({330: 1, 290: 2, 250: 3, 210: 5, 170: 8, 130: 13, 90: 21,
                                    50: 34, 10: 1})),
        ("ones", synthetic_weeks({d: 1 for d in range(0, 300, 7)})),
        ("record", synthetic_weeks({d: 240 if d == 200 else 1 + d % 3
                                    for d in list(range(0, 360, 11)) + [200]})),
        ("dense", synthetic_weeks({d: 1 + int(20 * h01(d, "n")) for d in range(366)
                                   if h01(d, "a") < 0.8})),
        ("half", synthetic_weeks({d: 1 + int(20 * h01(d, "n5")) for d in range(366)
                                  if h01(d, "a5") < 0.5})),
        ("full", synthetic_weeks({d: 1 + d % 9 for d in range(366)})),
        ("wide", synthetic_weeks({d: 1 + int(h01(d, "w") ** 3 * 120) for d in range(366)})),
        # pires cas pour le budget : 371 jours tous actifs
        ("full371", synthetic_weeks({d: 1 + d % 9 for d in range(371)}, sat)),
        ("ties371", synthetic_weeks({d: 50 if d % 15 == 0 else 1 + d % 9 for d in range(371)},
                                    sat)),
        ("huge371", synthetic_weeks({d: 1 + int(h01(d, "h") ** 3 * 10000) for d in range(371)},
                                    sat)),
        ("leap", synthetic_weeks({d: 2 for d in range(0, 366, 30)}, datetime.date(2028, 3, 1))),
        ("one day", [{"contributionDays": [{"date": "2026-10-12", "contributionCount": 3}]}]),
        ("two days", [{"contributionDays": [{"date": "2026-10-11", "contributionCount": 0},
                                            {"date": "2026-10-12", "contributionCount": 2}]}]),
    ]
    for name, weeks in cases:
        def fail(msg):
            raise SystemExit("self-test %s: %s" % (name, msg))
        days = to_days(weeks)
        scene = build_scene(days)
        check_layout(days, scene, fail, name in APART)
        # même calendrier, semaines et jours dans le désordre -> mêmes octets
        shuffled = [{"contributionDays": w["contributionDays"][::-1]} for w in weeks[::-1]]
        scene2 = build_scene(to_days(shuffled))
        sizes = []
        for theme in THEMES:
            svg = render(scene, theme, "self-test")
            if svg != render(scene2, theme, "self-test"):
                fail("%s: output depends on input order" % theme)
            if re.search(r'(?:\br|rx|ry|width|height)="-|="[-\d. ]*(?:nan|inf)', svg):
                fail("%s: negative or invalid size in the output" % theme)
            if theme == "dark":   # rien n'assombrit la page, même « dark dimmed » (#22272e)
                floor = [int(PAGES["dark"][1][k:k + 2], 16) for k in (1, 3, 5)]
                for c in sorted(set(re.findall(r'#[0-9a-f]{6}\b', svg))):
                    if any(int(c[k:k + 2], 16) < f for k, f in zip((1, 3, 5), floor)):
                        fail("dark: %s is darker than the dimmed page in some channel" % c)
            check_brightness(scene, svg, theme, fail)
            err = over_budget(svg)
            if err:
                fail("%s: over budget: %s" % (theme, err))
            size, elems, anim = budget(svg)
            sizes.append("%s %d B / %d el. / %d anim." % (theme, size, elems, anim))
        print("ok  %-14s %3d days, %3d stars | %s"
              % (name, len(days), len(scene["stars"]), ", ".join(sizes)))

    # repères de mois pour chaque fin d'année possible (366 fins consécutives) : tout mois
    # complet garde son repère, sans chevauchement, en grand comme sur écran étroit
    for k in range(366):
        end = datetime.date(2026, 10, 12) + datetime.timedelta(days=k)
        days = to_days(synthetic_weeks(REAL_SHAPE, end))

        def fail_months(msg):
            raise SystemExit("self-test months (end %s): %s" % (end, msg))

        def pos(i):
            return X0 + (X1 - X0) * (i / float(len(days) - 1))
        check_months(days, month_marks(days, pos), fail_months)
    print("ok  month labels for 366 consecutive end dates")

    # graine de hachage de Python : sans effet sur la sortie (deux processus neufs)
    code = ("import hashlib,importlib.util,sys;sys.dont_write_bytecode=True;"
            "s=importlib.util.spec_from_file_location('g',sys.argv[1]);"
            "g=importlib.util.module_from_spec(s);s.loader.exec_module(g);"
            "c=g.build_scene(g.to_days(g.synthetic_weeks(g.REAL_SHAPE)));"
            "print(hashlib.sha256((g.render(c,'dark','x')+g.render(c,'light','x'))"
            ".encode()).hexdigest())")
    scene = build_scene(to_days(synthetic_weeks(REAL_SHAPE)))
    want = hashlib.sha256((render(scene, "dark", "x") + render(scene, "light", "x"))
                          .encode()).hexdigest()
    for seed in ("0", "4242"):
        env = dict(os.environ, PYTHONHASHSEED=seed)
        got = subprocess.run([sys.executable, "-c", code, os.path.abspath(__file__)],
                             capture_output=True, text=True, env=env, check=False)
        if got.returncode != 0 or got.stdout.strip() != want:
            raise SystemExit("self-test: output changes with PYTHONHASHSEED=%s" % seed)
    print("ok  same bytes under other hash seeds")

    # erreurs : rien n'est écrit, sortie en erreur
    def day(date, count):
        return [{"contributionDays": [{"date": date, "contributionCount": count}]}]
    for bad in ({"errors": [{"message": "boom"}]}, {"data": {"user": None}}, {"data": None},
                {"weeks": []}, {"foo": 1}, None, 42, "x", {"weeks": [None]},
                [{"contributionDays": None}], [{"contributionDays": []}],
                [{"contributionDays": ["2026-01-01"]}], day("x", 1), day("2026-02-30", 1),
                day("2026-02-03", "abc"), day("2026-02-03", float("inf")),
                day("2026-02-03", float("nan")), [{"contributionDays": [{"date": "2026-02-03"}]}]):
        try:
            to_days(extract_weeks(bad))
        except SystemExit:
            continue
        raise SystemExit("self-test: malformed calendar accepted: %r" % (bad,))
    print("ok  malformed calendars rejected")


# --------------------------------------------------------------------------------- main ----

def main(argv=None):
    ap = argparse.ArgumentParser(
        description="GitHub contribution year as a night sky (dark + light SVG).")
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

    days = to_days(extract_weeks(payload))
    scene = build_scene(days)

    # tout construire et vérifier, puis écrire : jamais un thème neuf à côté d'un ancien
    built = {}
    for theme in ("dark", "light"):
        svg = render(scene, theme, args.user)
        err = over_budget(svg)
        if err:
            raise SystemExit("contrib-%s.svg over budget: %s" % (theme, err))
        built[theme] = (svg, len(svg.encode("utf-8")))
    os.makedirs(args.out, exist_ok=True)
    for theme, (svg, size) in built.items():
        path = os.path.join(args.out, "contrib-%s.svg" % theme)
        with open(path + ".tmp", "w", encoding="utf-8", newline="\n") as fh:
            fh.write(svg)
        os.replace(path + ".tmp", path)
        print("%s  %d bytes  (%d days, %d stars)"
              % (path, size, len(days), len(scene["stars"])))


if __name__ == "__main__":
    main()
