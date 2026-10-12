#!/usr/bin/env python3
"""Constellations : l'année de contributions GitHub dessinée comme un ciel d'étoiles reliées.

Grille du graphe GitHub : 53 semaines en colonnes (la plus ancienne à gauche, aujourd'hui à
droite) x 7 jours en lignes (dimanche en haut). Chaque jour est posé dans sa case avec un
décalage tiré d'un hachage de sa date (disque de rayon 45 % de la case) : d'une nuit à
l'autre, un jour garde exactement le même décalage.

Éclat : une étoile par jour actif, que le jour ait des liens ou non. Sa taille ET sa
brillance croissent strictement avec le nombre de contributions du jour :
  t = PLANCHER + (1 - PLANCHER) * ln((1+n)/2) / ln((1+max)/2)   (échelle log1p relative au
  record de l'année ; 1 contribution -> t = 0,2, nettement au-dessus de la poussière)
  rayon, halo, opacité du halo et couleur du cœur suivent t ; aigrette à 4 branches à partir
  de t >= 0,3 (longueur en t²) ; long reflet horizontal seulement au-delà de t > 0,75.
  Deux jours égaux sont deux étoiles identiques. Les jours vides sont de la poussière (grains
  de taille et d'opacité variées, toujours plus petits et plus ternes qu'une étoile).

Constellations : deux jours actifs sont reliables s'ils se touchent dans la grille
(8 voisins : colonnes et lignes à 1 d'écart au plus ; le samedi et le dimanche suivant ne se
touchent donc pas) ET partagent au moins un dépôt (commits, issues, pull requests, revues,
création de dépôt). Seul l'arbre couvrant minimal de chaque groupe est tracé (distance entre
positions décalées, départage par les dates) : des constellations, jamais un maillage.
Une nébuleuse violette par groupe, nuages d'orage en fond (décor fixe), mois discrets en bas.

Mouvement (calme, CSS @keyframes seulement) : les étoiles restent toujours visibles et
scintillent doucement ; tant qu'une étoile n'est pas liée, elle est atténuée (80 %).
Propagation : une constellation après l'autre, de la plus ancienne à la plus récente (0,5 s
de pause entre deux) ; chacune part de son jour le plus ancien ; un trait part toujours d'une
étoile déjà allumée et se trace à vitesse constante, la même pour tous (~0,55 s entre deux
cases voisines) ; une étoile ne s'allume (pleine opacité,
éclair) qu'à l'instant où un trait complet l'atteint (la racine : à la fin de son premier
trait). Après la dernière : tout reste affiché quelques secondes, puis seuls les liens
s'effacent (les étoiles restent, atténuées) et la boucle reprend. Cycle de 16 à 60 s quelle
que soit l'année (au besoin, la vitesse commune augmente). Le temps 0 tombe pendant la pose : un rendu sans animation (aperçu, vignette) montre
toutes les constellations. Année sans lien : étoiles seules, scintillement doux.
prefers-reduced-motion : image fixe, tous les liens tracés.

Confidentialité (dépôt public : journaux d'Actions et branche output sont visibles de tous) :
dès la réponse lue, chaque nom de dépôt est remplacé en mémoire par une empreinte SHA-256
salée (sel fixe, tronquée à 12 caractères hexadécimaux) avant d'atteindre toute autre
fonction ; le reste du code ne voit que ces identifiants opaques, qui servent seulement à
comparer deux jours : rien de ce qui en dérive n'entre dans le dessin. Aucun nom de dépôt
dans les SVG (titre, description, commentaires, id, classes compris), la sortie standard, les
erreurs ou --save-json (nombres et identifiants opaques seulement). Messages d'erreur
génériques (statut HTTP, « réponse invalide »), jamais le corps de la réponse ; toute
exception imprévue se résume à son nom de classe (jamais son message ni une trace). Le jeton
ne part que vers https://api.github.com/graphql, redirections HTTP refusées (urllib y
recopierait l'en-tête Authorization). Journal : des nombres seulement (jours, jours actifs,
dépôts distincts, liens) et le mode de jeton (« perso » / « Actions »).

Jetons : CONTRIB_TOKEN (jeton personnel du propriétaire, qui voit ses dépôts privés) s'il est
défini et non vide ; absent ou refusé (401/403) -> repli sur GITHUB_TOKEN (ou GH_TOKEN) : les
dépôts privés sont alors invisibles, leurs jours restent des étoiles (nombres du calendrier),
sans liens. Jamais la valeur, la longueur ou un préfixe d'un jeton dans le journal.

Sortie : contrib-dark.svg et contrib-light.svg (fond transparent, viewBox 884x192, sans JS
ni ressource externe). Bibliothèque standard uniquement. Sortie déterministe : même
calendrier -> mêmes octets (décor et décalages viennent d'un hachage SHA-256 de la date). Les
deux SVG sont construits et vérifiés (octets, éléments, nœuds animés) avant d'écrire quoi que
ce soit, puis remplacés (fichier temporaire + os.replace) : jamais de paire dépareillée.
Réponse vide, illisible ou en erreur -> sortie en erreur, aucun fichier écrit.

Usage :
  CONTRIB_TOKEN=... GITHUB_TOKEN=... python gen_contrib.py --out dist [--user Bisiaux-dev]
  python gen_contrib.py --from-json donnees.json --out dist      # sans réseau (tests)
  python gen_contrib.py --save-json donnees.json ...             # garde les données anonymes
  python gen_contrib.py --self-test       # années synthétiques, sans réseau, n'écrit rien
"""

import argparse
import base64
import contextlib
import datetime
import hashlib
import io
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from xml.sax.saxutils import escape

# ------------------------------------------------------------------------------ requêtes ----

API = "https://api.github.com/graphql"
# listes « par dépôt » de contributionsCollection ; les commits y sont agrégés par jour
KINDS = ("commitContributionsByRepository", "issueContributionsByRepository",
         "pullRequestContributionsByRepository", "pullRequestReviewContributionsByRepository")
DAY_KINDS = ("commitContributionsByRepository",)
PAGE = 100                   # nœuds par page (maximum de l'API)
MAX_PAGES = 40               # pages supplémentaires au plus (au-delà : liens incomplets)
MAX_COUNT = 10 ** 6          # un jour à plus d'un million de contributions : réponse invalide
CAL_Q = "contributionCalendar{weeks{contributionDays{date contributionCount}}}"
AUTH_TYPES = {"FORBIDDEN", "INSUFFICIENT_SCOPES", "UNAUTHORIZED"}


def _by_repo(kinds, after):
    a = ",after:$after" if after else ""
    return "".join(
        "%s(maxRepositories:100){repository{nameWithOwner}contributions(first:%d%s)"
        "{pageInfo{hasNextPage endCursor}nodes{occurredAt}}}" % (k, PAGE, a) for k in kinds)


def _repo_created(after):
    return ("repositoryContributions(first:%d%s){pageInfo{hasNextPage endCursor}"
            "nodes{occurredAt repository{nameWithOwner}}}"
            % (PAGE, ",after:$after" if after else ""))


def _query(body, after):
    return ("query($login:String!%s){user(login:$login){contributionsCollection{startedAt %s}}}"
            % (",$after:String!" if after else "", body))


# plage par défaut de contributionsCollection : l'année glissante qui finit aujourd'hui
Q_MAIN = _query(CAL_Q + _by_repo(KINDS, False) + _repo_created(False), False)

# --------------------------------------------------------------------------------------------
# Palette (jetons mesurés sur l'avatar)
#   nuit #0b0910 · ombre #281838 · aubergine #302040 · violet profond #533861 · violet #765082
#   lilas #8f6a99 · mauve #a87fb0 · glow #e3b7e6 · éclair #fbd4ff · givre #f6ebf7
# Sombre : nuages d'orage aubergine, nébuleuses violettes, la lumière monte vers le blanc ; en
# « dark dimmed » (#22272e), aucune couleur n'est plus sombre que la page sur un canal.
# Clair : carte du ciel à l'encre de nuit ; « plus brillant » = encre plus dense.
# core : couleur du cœur de t = 0 à t = 1 (chaque canal varie dans un seul sens).
# Liens : fins, blancs en sombre, noirs en clair.
# --------------------------------------------------------------------------------------------
THEMES = {
    "dark": {
        "cloud": "#3c284c", "cloud_op": 0.55, "haze": "#765082", "haze_op": 0.32,
        "dust": "#a87fb0", "core": ("#c9a3d0", "#ffffff"), "halo": "#e3b7e6", "halo_op": 0.5,
        "spark": "#fbd4ff", "line": "#ffffff", "line_op": 0.6, "month": "#5d4b6b",
        # éclat : centre chauffé à blanc, puis éclair, puis rien (offset, couleur, opacité)
        "flash": ((0, "#ffffff", 1.0), (0.18, "#fbd4ff", 0.8), (0.5, "#e3b7e6", 0.25),
                  (1, "#e3b7e6", 0)),
    },
    "light": {
        "cloud": "#f3e9f4", "cloud_op": 0.7, "haze": "#e3b7e6", "haze_op": 0.38,
        "dust": "#8f6a99", "core": ("#8f6a99", "#2a1838"), "halo": "#e3b7e6", "halo_op": 0.6,
        "spark": "#533861", "line": "#000000", "line_op": 0.5, "month": "#b9a3bf",
        "flash": ((0, "#302040", 0.9), (0.18, "#765082", 0.6), (0.5, "#a87fb0", 0.2),
                  (1, "#e3b7e6", 0)),
    },
}
LINE_W = 0.75

# Géométrie (unités du viewBox) : la grille du graphe GitHub
P = 16                       # pas d'une case
NCOLS, NROWS = 53, 7         # semaines x jours (dimanche en haut)
ML, MT, MB = 18, 34, 46      # marges gauche/droite, haut, bas (les mois sont en bas)
W, H = 2 * ML + NCOLS * P, MT + NROWS * P + MB      # 884 x 192
JITTER = 0.45                # rayon du disque de décalage, en fraction de case
EDGE = 1.0                   # aucun dégradé ne touche le bord du viewBox (pas de couture)
N_CLOUDS = 14                # nuages d'orage (décor fixe)
MAX_NEBULAE = 80             # une nébuleuse par groupe, les 80 plus grands groupes au plus
MONTH_Y = H - 14             # ligne de base des repères de mois
MONTH_FS = 10                # taille des repères (~10 px à 884 px de large)
MONTH_FS_NARROW = 17         # écran étroit : un mois sur trois, en plus grand (~7 px à 360 px)
NARROW_PX = 560              # largeur d'image (px CSS) en dessous de laquelle on passe en étroit
MONTH_NAMES = ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")

# Éclat
STAR_SCALE = 0.425             # taille des étoiles (cœur, halo, aigrette, reflet, éclair) : 1 = d'origine
UNLINKED = 0.8               # opacité d'une étoile tant qu'elle n'est pas liée (1 dès son 1er trait)
FLOOR = 0.2                  # t d'un jour à 1 contribution (0 = poussière, 1 = record)
LADDER = 0.004               # écart minimal de t entre deux nombres distincts (stricte croissance)
SPARK_T = 0.3                # année éparse : aigrette à 4 branches à partir de ce t
FLARE_T = 0.75               # année éparse : long reflet horizontal au-delà de ce t
SPARSE_MAX = 20              # au-delà de 20 jours actifs, aigrettes et reflets se méritent :
SPARK_SHARE = 0.12           #   aigrette pour les ~12 % de jours les plus contributifs,
FLARE_SHARE = 0.02           #   reflet pour les ~2 %,
FLARE_MAX = 5                #   5 jours au plus (seuils sur le nombre : jamais deux jours
                             #   égaux traités différemment)
SOFT_HALO = (1.5, 1.3)       # année dense, étoile sans aigrette : halo r * (1,5 + 1,3 t)
SOFT_HALO_OP = (0.22, 0.38)  #   et opacité halo_op * (0,22 + 0,38 t) (le reste : 2,6 + 2,6 t
                             #   et 0,4 + 0,6 t) : les voisines ne fusionnent pas en taches
DENSE_NEB = 0.75             # année dense : nébuleuses des seules constellations, plus discrètes
# aigrettes : rapport épaisseur / longueur (0,3 r / L) arrondi au plus proche de ces variantes
SPARK_K = (0.17, 0.14, 0.115, 0.095, 0.08, 0.067, 0.055)
DUST_R = (0.21, 0.17)        # rayon des grains : 0,21 + 0,17 * hachage (< plus petit cœur, 0,41)
DUST_O = (0.22, 0.38)        # opacité des grains

# Animation (secondes)
LEAD = 0.8                   # ciel seul avant les premiers traits
SPEED = 29.0                 # vitesse de tracé (unités/s), la même pour tous : ~0,55 s par case
BETWEEN = 0.5                # pause entre deux constellations (l'une après l'autre)
PROP_MAX = 52.0              # toutes les constellations à la suite : au-delà, la vitesse augmente
LIT_EDGE = 0.05              # l'étoile passe à pleine opacité dans les 0,05 s qui finissent le trait
FLASH_RISE = 0.12            # l'éclair monte en 0,12 s, une fois le trait complet
HOLD = 3.2                   # toutes les constellations restent affichées
FADE = 1.8                   # effacement des liens
REST = 1.0                   # étoiles seules avant la boucle suivante
T_MIN, T_MAX = 16.0, 60.0    # bornes du cycle
FLASH_HOLD = 0.15            # puis reste au plus haut 0,15 s
FLASH_DECAY = 1.0            # retour à l'éclat de base 1 s après la fin du trait
DASH_HIDDEN = 1.2            # dashoffset d'un lien non tracé (pathLength = 1, tirets « 1 2 »)

MAX_BYTES = 220 * 1024        # un trait = une keyframe : année pleine d'un seul dépôt ~190 Ko
MAX_ELEMS = 4000
MAX_ANIM = 1700              # nœuds animés (éléments portant une animation CSS)


class AuthError(Exception):
    """Jeton refusé (HTTP 401/403 ou erreur GraphQL d'autorisation)."""


class CheckError(Exception):
    """Défaut détecté par l'auto-test."""


def invalid(what):
    """Réponse ou fichier de données inutilisable : message générique (jamais son contenu)."""
    raise SystemExit("réponse invalide (%s) : rien n'est écrit" % what)


# ---------------------------------------------------------------------------- utilitaires ----

def h01(*parts):
    """Flottant déterministe dans [0, 1) dérivé d'une date (+ sel)."""
    digest = hashlib.sha256("|".join(str(p) for p in parts).encode()).digest()
    return int.from_bytes(digest[:6], "big") / float(1 << 48)


def f1(v):
    s = "%.1f" % v
    if s.endswith(".0"):
        s = s[:-2]
    return "0" if s == "-0" else s


def _short(s):
    s = s.rstrip("0").rstrip(".") if "." in s else s
    if s.startswith("0."):
        s = s[1:]
    elif s.startswith("-0."):
        s = "-" + s[2:]
    return "0" if s in ("", "-0", "-") else s


def f2(v):
    return _short("%.2f" % v)


def f3(v):
    return _short("%.3f" % v)


def f4(v):
    return _short("%.4f" % v)


def r1(v):
    """Arrondi au dixième, tel qu'écrit dans le SVG (les calculs suivants partent de là)."""
    return float("%.1f" % v)


def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def mix(c1, c2, f):
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(int(round(x + (y - x) * f)) for x, y in zip(a, b))


def pct(t, total):
    return f2(100.0 * clamp(t / total, 0.0, 1.0))


# ------------------------------------------------------------------------- anonymisation ----

REPO_SALT = b"Bisiaux-dev/contrib-constellations/v1"
RID_LEN = 12


class Anon:
    """Remplace un nom de dépôt par une empreinte opaque (SHA-256 salé, 12 hex), au moment
    même où il est lu dans la réponse : aucune autre fonction ne voit jamais le nom. Les
    empreintes ne servent qu'à comparer deux jours ; le dessin n'en dépend pas (le sel n'est
    paramétrable que pour le vérifier)."""

    def __init__(self, salt=REPO_SALT):
        self._salt = salt

    def rid(self, name):
        if not isinstance(name, str) or not name or len(name) > 300:
            invalid("dépôts")
        digest = hashlib.sha256(self._salt + b"\0" + name.encode("utf-8", "replace"))
        return digest.hexdigest()[:RID_LEN]


# ------------------------------------------------------------------------------ lecture ----

def parse_date(s):
    if not isinstance(s, str) or len(s) != 10:
        invalid("dates")
    try:
        return datetime.date.fromisoformat(s)
    except ValueError:
        invalid("dates")


def parse_ts(s):
    """Horodatage ISO 8601 avec fuseau (« Z » accepté), en UTC."""
    if not isinstance(s, str) or not 10 < len(s) <= 40:
        invalid("horodatages")
    try:
        ts = datetime.datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        invalid("horodatages")
    if ts.tzinfo is None:
        invalid("horodatages")
    return ts.astimezone(datetime.timezone.utc)


def parse_count(n):
    if isinstance(n, bool) or not isinstance(n, int) or not 0 <= n <= MAX_COUNT:
        invalid("calendrier")
    return n


def parse_weeks(weeks):
    """Calendrier -> {date: nombre}. Toute forme inattendue arrête le script."""
    if not isinstance(weeks, list) or not weeks:
        invalid("calendrier vide")
    cal = {}
    for week in weeks:
        if not isinstance(week, dict) or not isinstance(week.get("contributionDays"), list):
            invalid("calendrier")
        for d in week["contributionDays"]:
            if not isinstance(d, dict):
                invalid("calendrier")
            cal[parse_date(d.get("date"))] = parse_count(d.get("contributionCount"))
    if not cal:
        invalid("calendrier vide")
    return cal


def graphql_errors(errors, auth=False):
    """Erreurs GraphQL : on ne garde que leur nombre et leur type (énumération de l'API),
    jamais leur message (il peut citer un dépôt). `auth` : une erreur d'autorisation lève
    AuthError (repli sur l'autre jeton)."""
    types = set()
    for e in errors if isinstance(errors, list) else [errors]:
        t = e.get("type") if isinstance(e, dict) else None
        if isinstance(t, str) and re.fullmatch(r"[A-Z_]{1,40}", t):
            types.add(t)
    if auth and types and types <= AUTH_TYPES:
        raise AuthError("graphql")
    n = len(errors) if isinstance(errors, list) else 1
    raise SystemExit("GitHub GraphQL : réponse en erreur (%d erreur(s)%s) : rien n'est écrit"
                     % (n, (", " + ", ".join(sorted(types))) if types else ""))


def collection(payload):
    """contributionsCollection d'une réponse GraphQL brute."""
    if not isinstance(payload, dict):
        invalid("forme")
    if payload.get("errors"):
        graphql_errors(payload["errors"])
    data = payload.get("data")
    if not isinstance(data, dict):
        invalid("forme")
    user = data.get("user")
    if user is None:
        raise SystemExit("GitHub GraphQL : utilisateur introuvable : rien n'est écrit")
    if not isinstance(user, dict) or not isinstance(user.get("contributionsCollection"), dict):
        invalid("forme")
    return user["contributionsCollection"]


def local_offset(coll, cal):
    """Décalage du fuseau du calendrier par rapport à UTC, déduit de startedAt (minuit local
    du premier jour de la plage). Sans startedAt : UTC."""
    started = coll.get("startedAt")
    if started is None:
        return datetime.timedelta(0)
    ts = parse_ts(started)
    tod = datetime.timedelta(hours=ts.hour, minutes=ts.minute, seconds=ts.second)
    # minuit local = startedAt + décalage ; deux candidats, on garde celui qui tombe sur le
    # premier jour du calendrier, sinon le plus petit en valeur absolue
    cands = [datetime.timedelta(days=1) - tod, -tod]
    first = min(cal)
    for off in cands:
        if datetime.timedelta(hours=-14) <= off <= datetime.timedelta(hours=14) and \
                (ts + off).date() == first:
            return off
    off = min(cands, key=lambda o: (abs(o), o))
    return off if abs(off) <= datetime.timedelta(hours=14) else datetime.timedelta(0)


def page_info(conn):
    info = conn.get("pageInfo") if isinstance(conn, dict) else None
    if info is None:
        return None
    if not isinstance(info, dict) or not isinstance(info.get("hasNextPage", False), bool):
        invalid("pagination")
    cur = info.get("endCursor")
    if cur is not None and (not isinstance(cur, str) or len(cur) > 200):
        invalid("pagination")
    return cur if info.get("hasNextPage") and cur else None


class Events:
    """(dépôt opaque, jour local) : les seuls faits retenus des contributions par dépôt."""

    def __init__(self, cal, offset):
        self.cal, self.offset = cal, offset
        self.repos = {}

    def add(self, rid, ts, per_day):
        if per_day:
            # nœud agrégé par jour, horodaté à minuit d'un fuseau quelconque (-12 h..+12 h) :
            # le minuit le plus proche donne le jour
            day = (ts + datetime.timedelta(hours=12)).date()
            cands = [day]
        else:
            loc = ts + self.offset
            day = loc.date()
            cands = [day]
            # changement d'heure : à moins d'une heure de minuit, le jour voisin peut être le bon
            sec = loc.hour * 3600 + loc.minute * 60 + loc.second
            if sec < 3600:
                cands.append(day - datetime.timedelta(days=1))
            elif sec >= 23 * 3600:
                cands.append(day + datetime.timedelta(days=1))
        for d in cands:
            if self.cal.get(d, 0) > 0:          # un lien ne touche jamais la poussière
                self.repos.setdefault(rid, set()).add(d)
                return


def read_by_repo(coll, kind, anon, events, required=True):
    """Liste « par dépôt » -> événements ; renvoie {dépôt opaque: curseur suivant}."""
    lst = coll.get(kind)
    if lst is None and not required:
        return {}
    if not isinstance(lst, list):
        invalid("dépôts")
    pending = {}
    for entry in lst:
        if not isinstance(entry, dict) or not isinstance(entry.get("repository"), dict):
            invalid("dépôts")
        rid = anon.rid(entry["repository"].get("nameWithOwner"))
        conn = entry.get("contributions")
        if not isinstance(conn, dict) or not isinstance(conn.get("nodes"), list):
            invalid("dépôts")
        for node in conn["nodes"]:
            if not isinstance(node, dict):
                invalid("dépôts")
            events.add(rid, parse_ts(node.get("occurredAt")), kind in DAY_KINDS)
        cur = page_info(conn)
        if cur:
            pending[rid] = cur
    return pending


def read_created(coll, anon, events, required=True):
    """Créations de dépôts -> événements ; renvoie le curseur suivant (ou None)."""
    conn = coll.get("repositoryContributions")
    if conn is None and not required:
        return None
    if not isinstance(conn, dict) or not isinstance(conn.get("nodes"), list):
        invalid("dépôts")
    for node in conn["nodes"]:
        if not isinstance(node, dict) or not isinstance(node.get("repository"), dict):
            invalid("dépôts")
        events.add(anon.rid(node["repository"].get("nameWithOwner")),
                   parse_ts(node.get("occurredAt")), False)
    return page_info(conn)


def parse_payload(payload, anon):
    """Données d'entrée -> {"calendar": {date: n}, "repos": {dépôt opaque: {dates}}}.
    Formats acceptés : réponse GraphQL brute (noms anonymisés ici même), données anonymes
    écrites par --save-json, ou ancien calendrier seul ({"weeks": [...]} / liste de semaines)."""
    if isinstance(payload, dict) and payload.get("format") == "constellations/1":
        return parse_saved(payload, anon)
    if isinstance(payload, dict) and ("data" in payload or "errors" in payload):
        coll = collection(payload)
        cal_node = coll.get("contributionCalendar")
        if not isinstance(cal_node, dict):
            invalid("calendrier")
        cal = parse_weeks(cal_node.get("weeks"))
        events = Events(cal, local_offset(coll, cal))
        for kind in KINDS:
            read_by_repo(coll, kind, anon, events, required=False)
        read_created(coll, anon, events, required=False)
        return {"calendar": cal, "repos": events.repos}
    node = payload
    if isinstance(node, dict):
        if "weeks" not in node:
            invalid("forme")
        node = node["weeks"]
    return {"calendar": parse_weeks(node), "repos": {}}


def parse_saved(payload, anon):
    rows, repos = payload.get("calendar"), payload.get("repos")
    if not isinstance(rows, list) or not rows or not isinstance(repos, list):
        invalid("forme")
    cal = {}
    for row in rows:
        if not isinstance(row, list) or len(row) != 2:
            invalid("calendrier")
        cal[parse_date(row[0])] = parse_count(row[1])
    out = {}
    for row in repos:
        if not isinstance(row, list) or len(row) != 2 or not isinstance(row[1], list) or \
                not isinstance(row[0], str) or not re.fullmatch(r"[0-9a-f]{%d}" % RID_LEN, row[0]):
            invalid("dépôts")
        rid = anon.rid("id:" + row[0])
        for s in row[1]:
            d = parse_date(s)
            if cal.get(d, 0) > 0:
                out.setdefault(rid, set()).add(d)
    return {"calendar": cal, "repos": out}


def saved_form(data):
    """Ce que --save-json écrit : des nombres et des identifiants opaques, aucun nom."""
    return {
        "format": "constellations/1",
        "calendar": [[d.isoformat(), n] for d, n in sorted(data["calendar"].items())],
        "repos": [[rid, sorted(d.isoformat() for d in dates)]
                  for rid, dates in sorted(data["repos"].items())],
    }


# ------------------------------------------------------------------------------- réseau ----

class RedirectRefused(Exception):
    """Redirection HTTP refusée : urllib y recopierait l'en-tête Authorization."""


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RedirectRefused(code)


# le jeton ne part que vers cette adresse, en HTTPS, sans jamais suivre de redirection
OPENER = urllib.request.build_opener(NoRedirect)


def gql(token, query, variables):
    body = json.dumps({"query": query, "variables": variables}).encode()
    req = urllib.request.Request(API, data=body, headers={
        "Authorization": "bearer " + token,
        "Content-Type": "application/json",
        "User-Agent": "gen-contrib-constellations",
    })
    if req.full_url != "https://api.github.com/graphql" or req.host != "api.github.com":
        raise SystemExit("adresse de l'API inattendue : rien n'est envoyé")
    try:  # jamais le jeton ni le corps de la réponse dans les messages
        with OPENER.open(req, timeout=30) as resp:
            payload = json.load(resp)
    except RedirectRefused as exc:
        raise SystemExit("GitHub GraphQL : redirection HTTP %s refusée : rien n'est écrit"
                         % exc.args[0])
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            raise AuthError("http")
        raise SystemExit("GitHub GraphQL : HTTP %d : rien n'est écrit" % exc.code)
    except urllib.error.URLError:
        raise SystemExit("GitHub GraphQL : erreur réseau : rien n'est écrit")
    except (ValueError, OSError) as exc:  # corps non JSON, coupure, délai dépassé
        raise SystemExit("GitHub GraphQL : réponse illisible (%s) : rien n'est écrit"
                         % exc.__class__.__name__)
    if isinstance(payload, dict) and payload.get("errors"):
        graphql_errors(payload["errors"], auth=True)
    return payload


def fetch(login, token, anon, post=None):
    """Calendrier + jours de chaque dépôt, pages suivantes comprises. Les curseurs des listes
    « par dépôt » ne se choisissent pas dépôt par dépôt : la page suivante est demandée pour
    toutes les listes avec un même curseur, et seuls les dépôts qui attendaient ce curseur-là
    en retiennent la réponse."""
    post = post or gql
    coll = collection(post(token, Q_MAIN, {"login": login}))
    cal_node = coll.get("contributionCalendar")
    if not isinstance(cal_node, dict):
        invalid("calendrier")
    cal = parse_weeks(cal_node.get("weeks"))
    events = Events(cal, local_offset(coll, cal))
    pending = {}
    for kind in KINDS:
        for rid, cur in read_by_repo(coll, kind, anon, events).items():
            pending[(kind, rid)] = cur
    created = read_created(coll, anon, events)
    pages, truncated = 0, False
    while pending or created:
        if pages >= MAX_PAGES:
            truncated = True
            break
        pages += 1
        if pending:
            cur = min(pending.values())
            kinds = [k for k in KINDS
                     if any(c == cur and kk == k for (kk, _), c in pending.items())]
            page = collection(post(token, _query(_by_repo(kinds, True), True),
                                   {"login": login, "after": cur}))
            waiting = {key for key, c in pending.items() if c == cur}
            for key in waiting:
                del pending[key]
            for kind in kinds:
                sub = Events(cal, events.offset)
                nxt = read_by_repo(page, kind, anon, sub)
                for rid, dates in sub.repos.items():
                    if (kind, rid) in waiting:
                        events.repos.setdefault(rid, set()).update(dates)
                for rid, c in nxt.items():
                    if (kind, rid) in waiting and c != cur:
                        pending[(kind, rid)] = c
        else:
            page = collection(post(token, _query(_repo_created(True), True),
                                   {"login": login, "after": created}))
            prev, created = created, read_created(page, anon, events)
            if created == prev:
                created = None
    if truncated:
        print("pagination arrêtée après %d pages : liens peut-être incomplets" % MAX_PAGES)
    return {"calendar": cal, "repos": events.repos}


def fetch_with_fallback(login, anon, post=None):
    """CONTRIB_TOKEN (mode « perso ») si présent ; absent ou refusé : GITHUB_TOKEN (« Actions »)."""
    perso = (os.environ.get("CONTRIB_TOKEN") or "").strip()
    actions = (os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or "").strip()
    if perso:
        try:
            data = fetch(login, perso, anon, post)
            print("jeton : perso")
            return data
        except AuthError:
            if not actions:
                raise SystemExit("jeton perso refusé et aucun GITHUB_TOKEN : rien n'est écrit")
            print("jeton : Actions (jeton perso refusé) : liens des dépôts privés désactivés")
    elif actions:
        print("jeton : Actions (CONTRIB_TOKEN absent) : liens des dépôts privés désactivés")
    else:
        raise SystemExit("définir CONTRIB_TOKEN ou GITHUB_TOKEN (ou GH_TOKEN) pour lire le "
                         "calendrier")
    try:
        return fetch(login, actions, anon, post)
    except AuthError:
        raise SystemExit("GitHub GraphQL : accès refusé (401/403) : rien n'est écrit")


# --------------------------------------------------------------------------------- jours ----

def weekday_row(d):
    return (d.weekday() + 1) % 7                 # dimanche = 0 (en haut)


def to_days(data):
    """Jours de la grille (53 dernières semaines), dans l'ordre chronologique, chacun avec sa
    colonne, sa ligne et l'ensemble (opaque) des dépôts touchés ce jour-là s'il est actif."""
    cal = data["calendar"]
    last = max(cal)
    last_sunday = last - datetime.timedelta(days=weekday_row(last))
    by_day = {}
    for rid, dates in data["repos"].items():
        for d in dates:
            by_day.setdefault(d, set()).add(rid)
    days = []
    for d in sorted(cal):
        col = NCOLS - 1 - (last_sunday - (d - datetime.timedelta(days=weekday_row(d)))).days // 7
        if col < 0:
            continue                             # au-delà de 53 semaines : hors de la grille
        n = cal[d]
        days.append({"date": d.isoformat(), "day": d, "n": n, "col": col, "row": weekday_row(d),
                     "repos": frozenset(by_day.get(d, ())) if n > 0 else frozenset()})
    return days


# ------------------------------------------------------------------------------- dessin ----

def level(n, nmax):
    """Éclat 0..1 d'un jour : 0 pour un jour vide, FLOOR pour 1 contribution, 1 pour le
    record ; log relatif au record entre les deux (strictement croissant en n)."""
    if n <= 0:
        return 0.0
    if nmax <= 1:
        return 1.0
    return FLOOR + (1.0 - FLOOR) * math.log((1.0 + n) / 2.0) / math.log((1.0 + nmax) / 2.0)


def star_levels(counts):
    """{nombre: t}. Deux nombres distincts gardent au moins LADDER d'écart (ce que le SVG
    arrondi peut encore distinguer) ; si l'échelle déborde, elle est recomprimée sur
    [FLOOR, 1] (année pathologique seulement)."""
    vals = sorted(set(c for c in counts if c > 0))
    if not vals:
        return {}
    ts = []
    for v in vals:
        t = level(v, vals[-1])
        if ts and t < ts[-1] + LADDER:
            t = ts[-1] + LADDER
        ts.append(t)
    if ts[-1] > 1.0 and len(ts) > 1:
        k = (1.0 - FLOOR) / (ts[-1] - FLOOR)
        ts = [FLOOR + (t - FLOOR) * k for t in ts]
    return dict(zip(vals, ts))


def spark_variant(t):
    """Indice de la variante d'aigrette (rapport épaisseur / longueur) la plus proche."""
    k = 0.3 / (1.4 + 4.2 * t * t)
    return min(range(len(SPARK_K)), key=lambda i: (abs(SPARK_K[i] - k), i))


def star_style(t, th, spark=None, flare=None, soft=False):
    """Tout l'éclat d'une étoile, en fonction de t et de son rang (aigrette, reflet, halo doux,
    décidés par des seuils sur le nombre de contributions) : deux jours égaux, deux étoiles
    identiques ; chaque grandeur croît avec t, et le halo doux (étoile ordinaire d'une année
    dense) reste toujours plus petit et plus pâle que celui d'une étoile à aigrette.
    Par défaut (année éparse) : aigrette dès t >= 0,3, reflet au-delà de 0,75."""
    spark = t >= SPARK_T if spark is None else spark
    flare = t > FLARE_T if flare is None else flare
    r = STAR_SCALE * (1.0 + 1.9 * t)
    if soft and not spark:
        hr, ho = r * (SOFT_HALO[0] + SOFT_HALO[1] * t), th["halo_op"] * (
            SOFT_HALO_OP[0] + SOFT_HALO_OP[1] * t)
    else:
        hr, ho = r * (2.6 + 2.6 * t), th["halo_op"] * (0.4 + 0.6 * t)
    st = {"cr": 0.7 * r, "hr": hr, "ho": ho,
          "color": mix(th["core"][0], th["core"][1], t),
          "fr": STAR_SCALE * 6.0 + 2.6 * r * (1.0 + t)}
    if spark:
        st["L"] = r * (1.4 + 4.2 * t * t)
        st["so"] = 0.45 + 0.5 * t
        st["sk"] = spark_variant(t)
        if flare:
            st["flare"] = 2.2 * st["L"]
    return st


def count_threshold(counts, k):
    """Plus petit nombre v tel qu'au plus k jours aient >= v contributions (l'infini si le
    record lui-même est partagé par plus de k jours) : un traitement réservé aux plus gros
    jours ne départage jamais deux jours égaux."""
    thr, acc = math.inf, 0
    for v in sorted(set(counts), reverse=True):
        acc += counts.count(v)
        if acc > k:
            break
        thr = v
    return thr


def rank_marks(counts):
    """(seuil d'aigrette, seuil de reflet, année dense ?) pour ces nombres de jours actifs."""
    n = len(counts)
    if n <= SPARSE_MAX:
        return None, None, False
    return (count_threshold(counts, max(1, int(round(SPARK_SHARE * n)))),
            count_threshold(counts, min(FLARE_MAX, max(1, int(round(FLARE_SHARE * n))))), True)


def cell_center(col, row):
    return ML + col * P + P / 2.0, MT + row * P + P / 2.0


def jitter(date):
    """Décalage dans la case : disque de rayon JITTER * P, tiré du hachage de la date seule."""
    a = h01("jitter", date, "angle")
    rad = math.sqrt(h01("jitter", date, "radius")) * JITTER * P
    return rad * math.cos(2.0 * math.pi * a), rad * math.sin(2.0 * math.pi * a)


def place(d):
    cx, cy = cell_center(d["col"], d["row"])      # centres entiers
    dx, dy = jitter(d["date"])
    return r1(cx + r1(dx)), r1(cy + r1(dy))


def eligible(stars):
    """Paires (ancien, récent) de jours actifs voisins qui partagent au moins un dépôt."""
    grid = {(s["col"], s["row"]): s for s in stars}
    out = []
    for s in stars:
        for dc in (-1, 0, 1):
            for dr in (-1, 0, 1):
                e = grid.get((s["col"] + dc, s["row"] + dr))
                if (dc or dr) and e and e["date"] > s["date"] and s["repos"] & e["repos"]:
                    out.append((s["date"], e["date"]))
    return sorted(out)


class Forest:
    def __init__(self):
        self.parent = {}

    def find(self, a):
        self.parent.setdefault(a, a)
        while self.parent[a] != a:
            self.parent[a] = self.parent[self.parent[a]]
            a = self.parent[a]
        return a

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return False
        self.parent[max(ra, rb)] = min(ra, rb)
        return True


def spanning_forest(edges, pos):
    """Kruskal : arbre couvrant minimal de chaque composante (distance entre positions
    arrondies, départage par les dates) -> constellations sans maillage."""
    def key(e):
        (x1, y1), (x2, y2) = pos[e[0]], pos[e[1]]
        return (round((x1 - x2) ** 2 + (y1 - y2) ** 2, 6), e)
    forest, keep = Forest(), []
    for e in sorted(edges, key=key):
        if forest.union(*e):
            keep.append(e)
    return keep


def propagate(stars, links, pos):
    """Propagation, une constellation (arbre) après l'autre, de la plus ancienne à la plus
    récente, BETWEEN s de pause entre deux ; dans chacune, racine = jour le plus ancien ; un
    trait part de l'étoile déjà allumée vers la suivante, en longueur / vitesse (vitesse
    commune) ; une étoile s'allume à la fin du trait complet qui l'atteint (la racine : à la
    fin de son premier trait).
    Renvoie (traits, {date: indice du trait qui l'allume}, chronologie) ; tout lien hors de
    l'arbre (impossible en temps normal) est quand même tracé, pour que l'auto-test le voie."""
    if not links:
        return [], {}, None
    adj = {}
    for a, b in links:
        adj.setdefault(a, set()).add(b)
        adj.setdefault(b, set()).add(a)
    xy = {d: (r1(pos[d][0]), r1(pos[d][1])) for d in adj}

    def length(a, b):
        return math.hypot(xy[a][0] - xy[b][0], xy[a][1] - xy[b][1])
    seen, comps = set(), []
    for root in sorted(adj):                 # le premier non vu est le plus ancien du groupe
        if root in seen:
            continue
        seen.add(root)
        order, dist, parent, i = [root], {root: 0.0}, {root: None}, 0
        while i < len(order):
            u = order[i]
            i += 1
            for v in sorted(adj[u]):
                if v not in seen:
                    seen.add(v)
                    parent[v], dist[v] = u, dist[u] + length(u, v)
                    order.append(v)
        comps.append((root, order, dist, parent))
    depth = sum(max(c[2].values()) for c in comps)       # comps : racines par date croissante
    # pauses : 0,5 s, ramenées pour ne jamais dépasser 25 % du temps (année en mosaïque)
    between = min(BETWEEN, 0.25 * PROP_MAX / max(len(comps) - 1, 1))
    speed = max(SPEED, depth / (PROP_MAX - between * (len(comps) - 1)))
    draws, tree, t0 = [], [], LEAD
    for root, order, dist, parent in comps:
        for v in order[1:]:
            u = parent[v]
            draws.append({"a": u, "b": v, "s": t0 + dist[u] / speed, "e": t0 + dist[v] / speed})
            tree.append(frozenset((u, v)))
        t0 += max(dist.values()) / speed + between        # la suivante quand celle-ci est finie
    left = list(tree)
    for a, b in links:                       # liens hors arbre (cycle, doublon) : tracés aussi
        k = frozenset((a, b))
        if k in left:
            left.remove(k)
        else:
            src = min((a, b), key=lambda d: next((w["e"] for w in draws if w["b"] == d), 0.0))
            dst = b if src == a else a
            s0 = next((w["e"] for w in draws if w["b"] == src), LEAD)
            draws.append({"a": src, "b": dst, "s": s0, "e": s0 + length(a, b) / speed})
    draws.sort(key=lambda w: (w["e"], w["s"], w["a"], w["b"]))
    lights = {}
    for i, w in enumerate(draws):
        w["i"] = i
        lights.setdefault(w["b"], i)         # l'étoile atteinte : à la fin de son trait
    for i, w in enumerate(draws):            # la racine : à la fin de son premier trait
        lights.setdefault(w["a"], i)
    last = max(w["e"] for w in draws)
    hold, rest = HOLD, REST
    raw = last + FLASH_DECAY + hold + FADE + rest
    if raw < T_MIN:                          # peu de liens : on étire les pauses, pas les traits
        extra = T_MIN - raw
        hold, rest = hold + 0.6 * extra, rest + 0.4 * extra
    fade0 = last + FLASH_DECAY + hold
    # temps 0 du document au milieu de la pose : un rendu figé montre les constellations
    return draws, lights, {"T": fade0 + FADE + rest, "fade0": fade0, "fade1": fade0 + FADE,
                           "phase": fade0 - hold / 2.0, "speed": speed, "last": last,
                           "between": between}


def month_width(label, fs):
    return len(label) * 0.6 * fs + 0.4 * max(len(label) - 1, 0)


def month_marks(days):
    """Repères comme sur GitHub : un mois est nommé sur la première colonne dont le premier
    jour lui appartient, à 3 colonnes au moins du repère précédent. Écran étroit : un repère
    sur trois en partant du plus récent, en plus grand, s'il tient dans l'image."""
    top = {}
    for d in days:
        if d["col"] not in top or d["row"] < top[d["col"]]["row"]:
            top[d["col"]] = d
    marks, last, prev = [], -9, None
    for col in sorted(top):
        m = top[col]["day"].month
        if m != prev and col - last >= 3:
            marks.append({"x": ML + col * P + 2.0, "label": MONTH_NAMES[m - 1], "narrow": False})
            last = col
        prev = m
    right, since = None, 3
    for mk in reversed(marks):
        wide = month_width(mk["label"], MONTH_FS_NARROW)
        if since >= 3 and mk["x"] + wide <= W - EDGE and \
                (right is None or mk["x"] + wide + 6.0 <= right["x"]):
            mk["narrow"], right, since = True, mk, 1
        else:
            since += 1
    return marks


def edge_room(x, y):
    return min(x, W - x, y, H - y) - EDGE


def clouds():
    """Nuages d'orage : décor fixe (aucun lien avec l'activité), entiers dans l'image."""
    out = []
    for i in range(N_CLOUDS):
        a, b, c, d, e = (h01("cloud", i, k) for k in range(5))
        rx, ry = 60.0 + c * 90.0, 16.0 + d * 22.0
        x = EDGE + rx + a * (W - 2 * (rx + EDGE))
        y = clamp(MT - 10 + b * (NROWS * P + 30), ry + EDGE, H - ry - EDGE)
        out.append({"x": x, "y": y, "rx": rx, "ry": ry, "o": 0.35 + 0.5 * e})
    return out


def build_scene(days):
    pos = {d["date"]: place(d) for d in days}
    stars = [dict(d) for d in days if d["n"] > 0]
    lv = star_levels([s["n"] for s in stars])
    spark_thr, flare_thr, dense = rank_marks([s["n"] for s in stars])
    for s in stars:
        s["t"] = lv[s["n"]]
        s["x"], s["y"] = pos[s["date"]]
        if dense:   # année dense : aigrettes et reflets réservés aux plus gros jours
            s["spark"], s["flare"] = s["n"] >= spark_thr, s["n"] >= flare_thr
        else:       # année éparse : comme toujours, d'après t
            s["spark"], s["flare"] = s["t"] >= SPARK_T, s["t"] > FLARE_T
        s["soft"] = dense
    dust = []
    for d in days:
        if d["n"] == 0:
            x, y = pos[d["date"]]
            dust.append({"date": d["date"], "x": x, "y": y,
                         "r": DUST_R[0] + DUST_R[1] * h01("dust", d["date"], "r"),
                         "o": DUST_O[0] + DUST_O[1] * h01("dust", d["date"], "o"),
                         "g": int(h01("dust", d["date"], "tw") * 3)})
    # liens : arbre couvrant minimal, puis ordre chronologique (récent, puis ancien)
    links = sorted(spanning_forest(eligible(stars), pos), key=lambda e: (e[1], e[0]))
    draws, lights, tl = propagate(stars, links, pos)
    # groupes -> nébuleuses : une par constellation (et par étoile isolée si l'année est
    # éparse) ; année dense : constellations seulement, plus discrètes
    forest = Forest()
    for a, b in links:
        forest.union(a, b)
    groups = {}
    for s in stars:
        groups.setdefault(forest.find(s["date"]), []).append(s)
    ranked = sorted((g for g in groups.values() if len(g) > 1 or not dense),
                    key=lambda g: (-len(g), -max(s["t"] for s in g), g[0]["date"]))
    nebulae = []
    for g in sorted(ranked[:MAX_NEBULAE], key=lambda g: g[0]["date"]):
        xs, ys = [s["x"] for s in g], [s["y"] for s in g]
        t = max(s["t"] for s in g)
        cx, cy = sum(xs) / len(xs), sum(ys) / len(ys)
        room = edge_room(cx, cy)
        rx = min(22.0 + (max(xs) - min(xs)) * 0.8 + 14.0 * t, min(cx, W - cx) - EDGE)
        ry = min(12.0 + (max(ys) - min(ys)) * 0.7 + 8.0 * t, min(cy, H - cy) - EDGE)
        if room > 0 and rx > 2 and ry > 2:
            nebulae.append({"x": cx, "y": cy, "rx": rx, "ry": ry,
                            "o": (0.4 + 0.6 * t) * (DENSE_NEB if dense else 1.0)})
    return {"days": days, "pos": pos, "stars": stars, "dust": dust, "links": links,
            "draws": draws, "lights": lights, "tl": tl,
            "nebulae": nebulae, "clouds": clouds(), "months": month_marks(days)}


# ---------------------------------------------------------------------------------- SVG ----

def radial(gid, color, stops):
    return '<radialGradient id="%s">%s</radialGradient>' % (gid, "".join(
        '<stop offset="%s" stop-color="%s" stop-opacity="%s"/>' % (f2(o), color, f2(a))
        for o, a in stops))


def spark_path(k):
    """Aigrette à 4 branches effilées de longueur 1 (courbes concaves vers le centre)."""
    a, b = f3(1 - k), f3(k)
    return "M-1 0q%s -%s 1 -1q%s %s 1 1q-%s %s -1 1q-%s -%s -1 -1z" % (a, b, b, a, a, b, b, a)


def render(scene, theme, login):
    th = THEMES[theme]
    tl, draws, lights = scene["tl"], scene["draws"], scene["lights"]
    out = []
    o = out.append
    # étoile pas (encore) liée : atténuée (UNLINKED) ; elle prend la keyframe e<i> du trait
    # qui l'allume (pleine opacité à la fin du trait complet, atténuée quand les liens
    # s'effacent) ; jamais liée : classe d
    def lit(date):
        return ' class="e%d"' % lights[date] if date in lights else ' class="d"'
    o('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d" '
      'fill="none" role="img" aria-labelledby="t d">' % (W, H, W, H))
    o('<title id="t">%s</title>' % escape(
        "GitHub contributions of %s over the last year, drawn as constellations" % login))
    o('<desc id="d">%s</desc>' % escape(
        "One star per active day, laid out like the contribution graph: one column per week "
        "from the oldest on the left to today on the right, Sunday at the top. The more "
        "contributions a day has, the bigger and brighter its star; days without "
        "contributions are faint dust. Neighbouring days that touched the same repository "
        "are joined by thin lines, drawn one after another."))

    # --- styles : CSS seulement (pas de SMIL) -> prefers-reduced-motion coupe tout -------
    css = ["@keyframes tw{0%,100%{opacity:1}50%{opacity:.72}}",
           "@keyframes td{0%,100%{opacity:1}50%{opacity:.55}}"]
    for k, (dur, delay) in enumerate(((5.9, -0.7), (7.3, -3.1), (8.7, -5.6), (6.6, -2.2))):
        css.append(".w%d{animation:tw %ss ease-in-out %ss infinite}" % (k, f1(dur), f1(delay)))
    css.append(".u1{animation:td 6.5s ease-in-out -1s infinite}")
    css.append(".u2{animation:td 8.3s ease-in-out -4.6s infinite}")
    css.append(".d{opacity:%s}" % f2(UNLINKED))
    if tl:
        T, ph = tl["T"], tl["phase"]
        anim = "%ss ease-in-out -%ss infinite" % (f2(T), f2(ph))
        css.append("@keyframes lf{0%%,%s%%{opacity:1}%s%%,100%%{opacity:0}}"
                   % (pct(tl["fade0"], T), pct(tl["fade1"], T)))
        css.append(".L{animation:lf %s}" % anim)
        lin = "%ss linear -%ss infinite" % (f2(T), f2(ph))
        dim = f2(UNLINKED)
        # un trait = une keyframe : caché jusqu'à son départ, tracé à vitesse constante
        # (linéaire) ; la même keyframe allume l'étoile qu'il atteint (opacité pleine à la fin
        # seulement) et la ré-atténue quand les liens s'effacent
        for w in draws:
            e = w["e"]
            css.append("@keyframes e%d{0%%{stroke-dashoffset:%spx;opacity:%s}%s%%{"
                       "stroke-dashoffset:%spx}%s%%{opacity:%s}%s%%,%s%%{stroke-dashoffset:0;"
                       "opacity:1}%s%%,100%%{opacity:%s}}.e%d{animation:e%d %s}"
                       % (w["i"], f1(DASH_HIDDEN), dim, pct(w["s"], T), f1(DASH_HIDDEN),
                          pct(e - min(LIT_EDGE, 0.5 * (e - w["s"])), T), dim, pct(e, T),
                          pct(tl["fade0"], T), pct(tl["fade1"], T), dim, w["i"], w["i"], lin))
        # éclair : part de 0 à la fin du trait complet (retard propre à chaque étoile)
        css.append("@keyframes fl{0%%{opacity:0}%s%%,%s%%{opacity:1}%s%%,100%%{opacity:0}}"
                   % (pct(FLASH_RISE, T), pct(FLASH_RISE + FLASH_HOLD, T), pct(FLASH_DECAY, T)))
        css.append(".F circle{opacity:0;animation:fl %ss ease-out infinite}" % f2(T))
    css.append("text{font:600 %dpx ui-monospace,SFMono-Regular,Consolas,'Liberation Mono',"
               "monospace}" % MONTH_FS)
    # écran étroit (image < 560 px) : un mois sur trois, lisible ; les autres s'effacent
    css.append("@media (max-width:%dpx){text{font-size:%dpx}.m{display:none}}"
               % (NARROW_PX, MONTH_FS_NARROW))
    css.append("@media (prefers-reduced-motion:reduce){*{animation:none!important}}")
    o("<style>%s</style>" % "".join(css))

    # --- dégradés et aigrettes ----------------------------------------------------------
    styles = {s["date"]: star_style(s["t"], th, s["spark"], s["flare"], s["soft"])
              for s in scene["stars"]}
    o("<defs>")
    o(radial("c", th["cloud"], ((0, 1), (1, 0))))
    o(radial("z", th["haze"], ((0, 1), (1, 0))))
    o(radial("h", th["halo"], ((0, 1), (0.35, 0.35), (1, 0))))
    if tl:
        o('<radialGradient id="f">%s</radialGradient>' % "".join(
            '<stop offset="%s" stop-color="%s" stop-opacity="%s"/>' % (f2(of), c, f2(a))
            for of, c, a in th["flash"]))
    for k in sorted({st["sk"] for st in styles.values() if "sk" in st}):
        o('<path id="s%d" d="%s"/>' % (k, spark_path(SPARK_K[k])))
    o("</defs>")

    # --- nuages d'orage puis nébuleuses (une par groupe) ----------------------------------
    o('<g fill="url(#c)">')
    for cl in scene["clouds"]:
        o('<ellipse cx="%s" cy="%s" rx="%s" ry="%s" opacity="%s"/>'
          % (f1(cl["x"]), f1(cl["y"]), f1(cl["rx"]), f1(cl["ry"]), f2(th["cloud_op"] * cl["o"])))
    o("</g>")
    if scene["nebulae"]:
        o('<g fill="url(#z)">')
        for nb in scene["nebulae"]:
            o('<ellipse cx="%s" cy="%s" rx="%s" ry="%s" opacity="%s"/>'
              % (f1(nb["x"]), f1(nb["y"]), f1(nb["rx"]), f1(nb["ry"]),
                 f2(th["haze_op"] * nb["o"])))
        o("</g>")

    pos = scene["pos"]

    # --- poussière : un grain par jour vide (taille et opacité variées) --------------------
    if scene["dust"]:
        o('<g fill="%s">' % th["dust"])
        for g in range(3):
            grains = [d for d in scene["dust"] if d["g"] == g]
            if grains:
                o('<g class="u%d">' % g if g else "<g>")
                for d in grains:
                    o('<circle cx="%s" cy="%s" r="%s" opacity="%s"/>'
                      % (f1(d["x"]), f1(d["y"]), f2(d["r"]), f2(d["o"])))
                o("</g>")
        o("</g>")

    # --- étoiles : halos (scintillent par groupes), aigrettes, reflets, cœurs --------------
    by_n = sorted(scene["stars"], key=lambda s: (s["n"], s["date"]))
    if by_n:
        o('<g fill="url(#h)">')
        for k in range(4):
            group = [s for s in by_n if int(h01(s["date"], "tw") * 4) == k]
            if group:
                o('<g class="w%d">' % k)
                for s in group:
                    st = styles[s["date"]]
                    o('<circle%s cx="%s" cy="%s" r="%s" fill-opacity="%s"/>'
                      % (lit(s["date"]), f1(s["x"]), f1(s["y"]), f3(st["hr"]), f4(st["ho"])))
                o("</g>")
        o("</g>")

    # --- liens : au-dessus des halos et des nébuleuses (lisibles), sous aigrettes et cœurs ;
    # un groupe par étape, tracés de l'ancien jour vers le récent
    if draws:
        o('<g class="L" stroke="%s" stroke-opacity="%s" stroke-width="%s" stroke-linecap="round" '
          'stroke-dasharray="1 2">' % (th["line"], f2(th["line_op"]), f2(LINE_W)))
        for w in draws:                      # de l'étoile allumée vers celle qu'il va allumer
            a, b = w["a"], w["b"]
            o('<path class="e%d" d="M%s %s %s %s" pathLength="1"/>'
              % (w["i"], f1(pos[a][0]), f1(pos[a][1]), f1(pos[b][0]), f1(pos[b][1])))
        o("</g>")

    if by_n:
        sparks = [s for s in by_n if "L" in styles[s["date"]]]
        if sparks:
            o('<g fill="%s">' % th["spark"])
            for s in sparks:
                st = styles[s["date"]]
                o('<use%s href="#s%d" transform="translate(%s %s)scale(%s)" fill-opacity="%s"/>'
                  % (lit(s["date"]), st["sk"], f1(s["x"]), f1(s["y"]), f2(st["L"]), f3(st["so"])))
            o("</g>")
        flares = [s for s in by_n if "flare" in styles[s["date"]]]
        if flares:
            o('<g stroke="%s" stroke-width=".5" stroke-opacity=".45">' % th["spark"])
            for s in flares:
                ln = styles[s["date"]]["flare"]
                a, b = min(ln, s["x"] - EDGE), min(ln, W - EDGE - s["x"])
                o('<path%s d="M%s %sm-%s 0h%s"/>'
                  % (lit(s["date"]), f1(s["x"]), f1(s["y"]), f1(a), f1(a + b)))
            o("</g>")
        o("<g>")
        for s in by_n:
            st = styles[s["date"]]
            o('<circle%s cx="%s" cy="%s" r="%s" fill="%s"/>'
              % (lit(s["date"]), f1(s["x"]), f1(s["y"]), f3(st["cr"]), st["color"]))
        o("</g>")

    # --- éclairs : une étoile s'illumine à l'instant où un trait complet l'atteint ---------
    if draws:
        o('<g class="F" fill="url(#f)">')
        for date in sorted(lights, key=lambda d: (draws[lights[d]]["e"], d)):
            x, y = pos[date]
            st = styles[date]
            o('<circle cx="%s" cy="%s" r="%s" style="animation-delay:-%ss"/>'
              % (f1(x), f1(y), f1(min(st["fr"], edge_room(x, y))),
                 f3((tl["phase"] - draws[lights[date]]["e"]) % tl["T"])))
        o("</g>")

    # --- repères de mois : discrets, en bas, comme l'axe du graphe GitHub ------------------
    if scene["months"]:
        o('<g fill="%s">' % th["month"])
        for m in scene["months"]:
            o('<text%s x="%s" y="%d">%s</text>'
              % ("" if m["narrow"] else ' class="m"', f1(m["x"]), MONTH_Y, m["label"]))
        o("</g>")
    o("</svg>")
    return "\n".join(out) + "\n"


def budget(svg):
    """(octets, éléments, nœuds animés : éléments dont la classe porte une animation CSS)."""
    elems = svg.count("<") - svg.count("</")
    anim = len(re.findall(r'class="(?:w\d|u[12]|L|e\d+)"', svg)) + svg.count('style="animation')
    return len(svg.encode("utf-8")), elems, anim


def over_budget(svg):
    size, elems, anim = budget(svg)
    if size > MAX_BYTES or elems > MAX_ELEMS or anim > MAX_ANIM:
        return "%d o (max %d), %d éléments (max %d), %d animés (max %d)" % (
            size, MAX_BYTES, elems, MAX_ELEMS, anim, MAX_ANIM)
    return None


def build_all(data, login):
    """Les deux SVG, construits et vérifiés avant toute écriture."""
    days = to_days(data)
    scene = build_scene(days)
    built = {}
    for theme in ("dark", "light"):
        svg = render(scene, theme, login)
        err = over_budget(svg)
        if err:
            raise SystemExit("contrib-%s.svg hors budget : %s : rien n'est écrit" % (theme, err))
        built[theme] = svg
    return days, scene, built


def write_all(built, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    for theme, svg in built.items():
        path = os.path.join(out_dir, "contrib-%s.svg" % theme)
        with open(path + ".tmp", "w", encoding="utf-8", newline="\n") as fh:
            fh.write(svg)
        os.replace(path + ".tmp", path)
        size, _, anim = budget(svg)
        print("%s  %d octets, %d nœuds animés" % (path, size, anim))


# ------------------------------------------------------------------------------ auto-test ----

END = datetime.date(2026, 10, 12)              # un lundi : calendrier de 366 jours
SAT_END = datetime.date(2026, 10, 17)          # un samedi : calendrier de 371 jours (53 x 7)
# noms fictifs, repérables : aucun ne doit jamais sortir du script
FIXTURE_NAMES = ("acme-corp/secret-client-repo-xyz", "zq-org/vault-sync-internal",
                 "acme-corp/payroll-zq-api", "zq-org/site-vitrine-zq", "Bisiaux-dev/zq-notes",
                 "acme-corp/crm-zq-backend", "zq-org/bot-zq-notion")
LOGIN = "Bisiaux-dev"
PAGES_BG = {"dark": ("#0d1117", "#22272e"), "light": ("#ffffff",)}


def cal_dates(end):
    """Dates d'un calendrier GitHub qui finit `end` (semaines dimanche -> samedi)."""
    day = end - datetime.timedelta(days=365)
    day -= datetime.timedelta(days=weekday_row(day))
    out = []
    while day <= end:
        out.append(day)
        day += datetime.timedelta(days=1)
    return out


def fixture(end, counts, repos, page=PAGE):
    """Réponse GraphQL brute synthétique. counts : {date: n} ; repos : {nom: (genre, [dates])}
    (genre : commit, issue, pr, review, created). Fuseau de Paris (UTC+2) : startedAt la veille
    à 22:00Z, contributions horodatées à 00:30 heure locale (22:30Z la veille) pour vérifier
    la conversion. `page` : taille des pages servies par fake_post()."""
    dates = cal_dates(end)
    weeks = []
    for d in dates:
        if weekday_row(d) == 0 or not weeks:
            weeks.append({"contributionDays": []})
        weeks[-1]["contributionDays"].append(
            {"date": d.isoformat(), "weekday": weekday_row(d),
             "contributionCount": counts.get(d, 0)})
    started = datetime.datetime.combine(dates[0], datetime.time()) - datetime.timedelta(hours=2)
    kind_key = {"commit": KINDS[0], "issue": KINDS[1], "pr": KINDS[2], "review": KINDS[3]}
    coll = {"startedAt": started.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "contributionCalendar": {"weeks": weeks},
            "repositoryContributions": {"nodes": []}}
    for k in KINDS:
        coll[k] = []
    for name, (kind, ds) in sorted(repos.items()):
        if kind == "commit":   # agrégé par jour : minuit heure du Pacifique
            ts = [(d.isoformat() + "T07:00:00Z") for d in sorted(ds)]
        else:                  # instant exact : 00:30 à Paris = 22:30Z la veille
            ts = [(datetime.datetime.combine(d, datetime.time(0, 30)) -
                   datetime.timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
                  for d in sorted(ds)]
        if kind == "created":
            coll["repositoryContributions"]["nodes"] += [
                {"occurredAt": t, "repository": {"nameWithOwner": name}} for t in ts]
        else:
            coll[kind_key[kind]].append({"repository": {"nameWithOwner": name},
                                         "contributions": {"nodes": ts}})
    for k in KINDS:
        for entry in coll[k]:
            entry["contributions"]["nodes"] = [{"occurredAt": t}
                                               for t in entry["contributions"]["nodes"]]
    return {"data": {"user": {"contributionsCollection": coll}}}


def fake_post(full, page):
    """Faux serveur GraphQL : sert `full` par pages de `page` nœuds, curseur = base64 du rang
    (comme l'API), pour tester la pagination sans réseau."""
    def cut(conn, after):
        start = int(base64.b64decode(after).decode()) if after else 0
        nodes = conn["nodes"][start:start + page]
        nxt = start + len(nodes)
        cursor = base64.b64encode(str(nxt).encode()).decode().rstrip("=") if nodes else None
        return {"nodes": nodes,
                "pageInfo": {"hasNextPage": nxt < len(conn["nodes"]), "endCursor": cursor}}

    def post(token, query, variables):
        src = full["data"]["user"]["contributionsCollection"]
        after = variables.get("after")
        coll = {"startedAt": src["startedAt"]}
        if "contributionCalendar" in query:
            coll["contributionCalendar"] = src["contributionCalendar"]
        for k in KINDS:
            if k in query:
                coll[k] = [{"repository": e["repository"],
                            "contributions": cut(e["contributions"], after)} for e in src[k]]
        if "repositoryContributions" in query:
            coll["repositoryContributions"] = cut(src["repositoryContributions"], after)
        return {"data": {"user": {"contributionsCollection": coll}}}
    return post


def real_shape():
    """Forme de l'année publique réelle au 2026-10-12 (même dépôt du 10 au 13 novembre et le
    19 ; 1er-2 juin ; 10-11 juin ; création de dépôt le 12 octobre)."""
    D = datetime.date
    counts = {D(2025, 11, 10): 6, D(2025, 11, 11): 27, D(2025, 11, 12): 11, D(2025, 11, 13): 5,
              D(2025, 11, 19): 7, D(2026, 6, 1): 8, D(2026, 6, 2): 5, D(2026, 6, 10): 7,
              D(2026, 6, 11): 4, D(2026, 10, 12): 4}
    repos = {FIXTURE_NAMES[0]: ("commit", [D(2025, 11, d) for d in (10, 11, 12, 13, 19)]),
             FIXTURE_NAMES[1]: ("commit", [D(2026, 6, 1), D(2026, 6, 2)]),
             FIXTURE_NAMES[2]: ("commit", [D(2026, 6, 10), D(2026, 6, 11)]),
             FIXTURE_NAMES[3]: ("created", [D(2026, 10, 12)])}
    expected = {("2026-06-01", "2026-06-02"), ("2026-06-10", "2026-06-11")}   # hors novembre
    return counts, repos, expected


def dense_year():
    """~200 jours actifs, 5 projets qui se chevauchent dans le temps, quelques jours à deux
    dépôts ; issues, pull requests et revues en plus des commits."""
    dates = cal_dates(END)
    projects = [(FIXTURE_NAMES[k], a, b) for k, (a, b) in
                enumerate(((0, 14), (8, 22), (18, 34), (30, 44), (40, 53)))]
    counts, repos = {}, {}
    kinds = ("commit", "pr", "commit", "review", "issue")
    for i, d in enumerate(dates):
        col, row = i // 7, weekday_row(d)
        if h01("dense", d, "a") >= (0.15 if row in (0, 6) else 0.72):
            continue
        live = [p for p in projects if p[1] <= col < p[2]]
        if not live:
            continue
        counts[d] = min(1 + int(-4.0 * math.log(1.0 - h01("dense", d, "n") * 0.999)), 30)
        pick = [live[int(h01("dense", d, "p") * len(live))]]
        if len(live) > 1 and h01("dense", d, "q") < 0.25:
            pick.append(live[int(h01("dense", d, "r") * len(live))])
        for name, _, _ in pick:
            k = kinds[FIXTURE_NAMES.index(name)]
            repos.setdefault(name, (k, []))[1].append(d)
    return counts, repos


def full_year(mosaic):
    """371 jours tous actifs. Un seul dépôt (le plus de liens) ou une mosaïque de dépôts
    (le plus de groupes, donc de nébuleuses)."""
    dates = cal_dates(SAT_END)
    counts = {d: 1 + i % 9 for i, d in enumerate(dates)}
    if not mosaic:
        return counts, {FIXTURE_NAMES[0]: ("commit", dates)}
    repos = {}
    for i, d in enumerate(dates):
        name = FIXTURE_NAMES[int(h01("mosaic", d) * len(FIXTURE_NAMES))]
        repos.setdefault(name, ("commit", []))[1].append(d)
    return counts, repos


def sat_sun():
    """Samedi + dimanche suivant (voisins dans le temps, pas dans la grille) et dimanche +
    samedi de la même semaine : même dépôt, aucun lien permis."""
    D = datetime.date
    ds = [D(2026, 3, 7), D(2026, 3, 8), D(2026, 4, 12), D(2026, 4, 18)]
    return {d: 3 for d in ds}, {FIXTURE_NAMES[4]: ("commit", ds)}


def parse_svg_links(svg, scene):
    """Paires de jours reliées par un trait dans le SVG (extrémités -> dates)."""
    at = {(f1(x), f1(y)): date for date, (x, y) in scene["pos"].items()}
    pairs = []
    for m in re.finditer(r'<path(?: class="e\d+")? d="M([\d.]+) ([\d.]+) ([\d.]+) ([\d.]+)" '
                         r'pathLength="1"/>', svg):
        a, b = at.get((m.group(1), m.group(2))), at.get((m.group(3), m.group(4)))
        if a is None or b is None:
            raise CheckError("trait qui ne part pas d'un jour de la grille")
        pairs.append((a, b))
    return pairs


def check_links(pairs, days):
    """Règles des liens, recalculées sans passer par les colonnes du script : voisins dans
    la grille (d'après les seules dates), dépôt commun, ni doublon ni cycle, et chaque groupe
    reliable entièrement relié (forêt couvrante)."""
    by_date = {d["date"]: d for d in days}
    seen, forest = set(), Forest()
    for a, b in pairs:
        key = (min(a, b), max(a, b))
        if key in seen:
            raise CheckError("lien en double %s-%s" % key)
        seen.add(key)
        da, db = by_date.get(key[0]), by_date.get(key[1])
        if not da or not db or da["n"] < 1 or db["n"] < 1:
            raise CheckError("lien vers un jour sans étoile %s-%s" % key)
        gap, wd = (db["day"] - da["day"]).days, weekday_row(da["day"])
        if not ((gap == 1 and wd != 6) or gap == 7 or (gap == 6 and wd != 0) or
                (gap == 8 and wd != 6)):
            raise CheckError("lien entre jours non voisins dans la grille %s-%s" % key)
        if not da["repos"] & db["repos"]:
            raise CheckError("lien sans dépôt commun %s-%s" % key)
        if not forest.union(*key):
            raise CheckError("cycle dans les liens (%s-%s)" % key)
    stars = [d for d in days if d["n"] > 0]
    for a, b in eligible(stars):
        if forest.find(a) != forest.find(b):
            raise CheckError("groupe reliable non relié (%s-%s)" % (a, b))


def check_grid(scene, days):
    """Chaque jour dans sa case : colonne d'après la date seule (la plus récente à droite),
    dimanche en haut ; décalage dans le disque de 45 %."""
    last = max(d["day"] for d in days)
    last_sun = last - datetime.timedelta(days=weekday_row(last))
    for d in days:
        col = NCOLS - 1 - (last_sun - (d["day"] - datetime.timedelta(
            days=weekday_row(d["day"])))).days // 7
        cx, cy = cell_center(col, weekday_row(d["day"]))
        x, y = scene["pos"][d["date"]]
        if math.hypot(x - cx, y - cy) > JITTER * P + 0.08:
            raise CheckError("%s hors de sa case" % d["date"])


def check_jitter(scenes):
    """Le décalage d'un jour dans sa case ne dépend que de sa date (pas de l'année affichée)."""
    seen = {}
    for scene in scenes:
        for d in scene["days"]:
            cx, cy = cell_center(d["col"], d["row"])
            x, y = scene["pos"][d["date"]]
            off = (round(x - cx, 1), round(y - cy, 1))
            if seen.setdefault(d["date"], off) != off:
                raise CheckError("le décalage du %s change d'une année à l'autre" % d["date"])


LIT = r'(?: class="(?:e\d+|d)")?'     # classe d'allumage optionnelle (étoile liée ou non)
STAR_RES = {
    "halo": re.compile(r'<circle' + LIT + r' cx="([\d.]+)" cy="([\d.]+)" r="([\d.]+)" '
                       r'fill-opacity="([\d.]+)"/>'),
    "core": re.compile(r'<circle' + LIT + r' cx="([\d.]+)" cy="([\d.]+)" r="([\d.]+)" '
                       r'fill="(#[0-9a-f]{6})"/>'),
    "spark": re.compile(r'<use' + LIT + r' href="#s(\d)" transform="translate\(([\d.]+) ([\d.]+)\)'
                        r'scale\(([\d.]+)\)" fill-opacity="([\d.]+)"/>'),
    "flare": re.compile(r'<path' + LIT + r' d="M([\d.]+) ([\d.]+)m-([\d.]+) 0h([\d.]+)"/>'),
    "dust": re.compile(r'<circle cx="([\d.]+)" cy="([\d.]+)" r="([\d.]+)" opacity="([\d.]+)"/>'),
}


def check_stars(svg, scene, theme):
    """Relu dans le SVG produit : une étoile par jour actif, un grain par jour vide ; taille
    (cœur, halo) et brillance (opacité du halo) strictement croissantes avec le nombre de
    contributions ; couleur du cœur, aigrette et reflet jamais décroissants ; deux jours égaux
    identiques ; la poussière toujours plus petite et plus terne que la plus faible étoile."""
    at = {(f1(x), f1(y)): date for date, (x, y) in scene["pos"].items()}
    n_of = {d["date"]: d["n"] for d in scene["days"]}
    star = {}

    def slot(date, part, value):
        if date is None or n_of[date] == 0:
            raise CheckError("%s posé hors d'un jour actif" % part)
        if part in star.setdefault(date, {}):
            raise CheckError("%s en double pour le %s" % (part, date))
        star[date][part] = value

    for m in STAR_RES["halo"].finditer(svg):
        slot(at.get((m.group(1), m.group(2))), "halo", (float(m.group(3)), float(m.group(4))))
    for m in STAR_RES["core"].finditer(svg):
        c = m.group(4)
        rgb = tuple(int(c[k:k + 2], 16) for k in (1, 3, 5))
        slot(at.get((m.group(1), m.group(2))), "core", (float(m.group(3)), rgb))
    for m in STAR_RES["spark"].finditer(svg):
        slot(at.get((m.group(2), m.group(3))), "spark", (float(m.group(4)), float(m.group(5))))
    for m in STAR_RES["flare"].finditer(svg):
        slot(at.get((m.group(1), m.group(2))), "flare", True)
    actives = [d for d in scene["days"] if d["n"] > 0]
    if len(star) != len(actives) or any(not {"halo", "core"} <= set(v) for v in star.values()):
        raise CheckError("%s : il faut exactement une étoile (halo + cœur) par jour actif" % theme)
    dust = [(float(m.group(3)), float(m.group(4))) for m in STAR_RES["dust"].finditer(svg)]
    if len(dust) != len(scene["days"]) - len(actives):
        raise CheckError("%s : il faut exactement un grain de poussière par jour vide" % theme)
    sign = 1 if theme == "dark" else -1      # clair : l'encre fonce quand l'éclat monte

    def key(date):
        v = star[date]
        return (v["core"][0], v["halo"][0], v["halo"][1], tuple(sign * c for c in v["core"][1]),
                v.get("spark", (0.0, 0.0)), "flare" in v)
    by_n = {}
    for date in star:
        k = key(date)
        if by_n.setdefault(n_of[date], k) != k:
            raise CheckError("%s : deux jours à %d contributions dessinés différemment"
                             % (theme, n_of[date]))
    ns = sorted(by_n)
    for lo, hi in zip(ns, ns[1:]):
        a, b = by_n[lo], by_n[hi]
        if not (b[0] > a[0] and b[1] > a[1] and b[2] > a[2]):
            raise CheckError("%s : taille ou brillance pas strictement croissante (%d -> %d)"
                             % (theme, lo, hi))
        if any(y < x for x, y in zip(a[3], b[3])) or b[4][0] < a[4][0] or b[4][1] < a[4][1] \
                or (a[5] and not b[5]):
            raise CheckError("%s : couleur, aigrette ou reflet décroissant (%d -> %d)"
                             % (theme, lo, hi))
    if ns and dust:
        weakest = by_n[ns[0]]
        if max(r for r, _ in dust) >= weakest[0] or max(o for _, o in dust) >= 1.0:
            raise CheckError("%s : poussière aussi visible qu'une étoile" % theme)


def check_marks_share(svg, scene):
    """Année dense : aigrettes pour ~12 % des jours actifs au plus, reflets pour ~2 % (5 jours
    au plus) ; le reflet n'existe jamais sans aigrette. Les liens passent au-dessus des halos,
    sous les aigrettes et les cœurs."""
    n = len(scene["stars"])
    sparks = len(STAR_RES["spark"].findall(svg))
    flares = len(STAR_RES["flare"].findall(svg))
    if flares > sparks:
        raise CheckError("reflet sans aigrette")
    if n > SPARSE_MAX:
        if sparks > max(1, round(SPARK_SHARE * n)):
            raise CheckError("trop d'aigrettes (%d pour %d jours actifs)" % (sparks, n))
        if flares > min(FLARE_MAX, max(1, round(FLARE_SHARE * n))):
            raise CheckError("trop de reflets (%d pour %d jours actifs)" % (flares, n))
    if scene["draws"]:
        core = STAR_RES["core"].search(svg)
        at = {"halos": svg.find('fill="url(#h)"'), "liens": svg.find('class="L"'),
              "cœurs": core.start() if core else len(svg)}
        if not 0 <= at["halos"] < at["liens"] < at["cœurs"]:
            raise CheckError("liens pas entre les halos et les cœurs")
        first_spark = svg.find("<use href=")
        if first_spark != -1 and first_spark < at["liens"]:
            raise CheckError("liens au-dessus des aigrettes")


def check_animation(svg, scene):
    """Relu dans le SVG : un trait par lien ; tous à la même vitesse ; un trait part de
    l'étoile déjà allumée (ou de la racine, jour le plus ancien de sa constellation) ; chaque
    étoile liée prend pleine opacité et son éclair à la fin du trait complet qui l'atteint
    (la racine : de son premier trait), jamais avant ; une étoile jamais liée reste atténuée ;
    cycle borné ; année sans lien : aucune animation de lien."""
    tl = scene["tl"]
    if not scene["draws"]:
        if 'class="L"' in svg or "@keyframes e" in svg or 'class="F"' in svg:
            raise CheckError("animation de liens dans une année sans lien")
        return
    T = tl["T"]
    if not T_MIN - 1e-9 <= T <= T_MAX + 1e-9:
        raise CheckError("cycle de %.1f s hors de [%g, %g]" % (T, T_MIN, T_MAX))
    tol = 0.0002 * T + 0.002                 # arrondi des pourcentages écrits
    at = {(f1(x), f1(y)): date for date, (x, y) in scene["pos"].items()}
    kf = {}
    for m in re.finditer(r"@keyframes e(\d+)\{0%\{[^}]*\}([\d.]+)%\{stroke-dashoffset:[^}]*\}"
                         r"([\d.]+)%\{opacity:([\d.]+)\}([\d.]+)%,", svg):
        if float(m.group(4)) >= 1:
            raise CheckError("étoile pleine avant la fin de son trait")
        kf[int(m.group(1))] = (float(m.group(2)) * T / 100, float(m.group(5)) * T / 100)
    paths = {}
    for m in re.finditer(r'<path class="e(\d+)" d="M([\d.]+) ([\d.]+) ([\d.]+) ([\d.]+)" '
                         r'pathLength="1"/>', svg):
        a, b = at.get((m.group(2), m.group(3))), at.get((m.group(4), m.group(5)))
        ln = math.hypot(float(m.group(2)) - float(m.group(4)), float(m.group(3)) - float(m.group(5)))
        paths[int(m.group(1))] = (a, b, ln)
    if set(paths) != set(kf) or len(paths) != len(scene["links"]):
        raise CheckError("un tracé (keyframe) par lien attendu")
    for i, (a, b, ln) in paths.items():
        if abs((kf[i][1] - kf[i][0]) - ln / tl["speed"]) > 2 * tol:
            raise CheckError("traits à des vitesses différentes")
    incoming = {}
    for i, (a, b, _) in paths.items():
        if b in incoming:
            raise CheckError("étoile atteinte par deux traits")
        incoming[b] = i
    lit_at = {b: kf[i][1] for b, i in incoming.items()}
    roots = {a for a, b, _ in paths.values() if a not in incoming}
    for r in roots:
        lit_at[r] = min(kf[i][1] for i, (a, b, _) in paths.items() if a == r)
    for i, (a, b, _) in paths.items():
        if a in incoming and abs(kf[i][0] - kf[incoming[a]][1]) > tol:
            raise CheckError("trait parti d'une étoile pas encore allumée")
    forest = Forest()
    for a, b, _ in paths.values():
        forest.union(a, b)
    for r in roots:
        if r != min(d for d in lit_at if forest.find(d) == forest.find(r)):
            raise CheckError("propagation qui ne part pas du jour le plus ancien")
    # une constellation après l'autre, de la plus ancienne à la plus récente
    span = {}
    for i, (a, b, _) in paths.items():
        lo, hi = span.get(forest.find(a), (math.inf, -math.inf))
        span[forest.find(a)] = (min(lo, kf[i][0]), max(hi, kf[i][1]))
    seq = sorted((min(d for d in lit_at if forest.find(d) == k), v) for k, v in span.items())
    for (_, (s0, e0)), (_, (s1, e1)) in zip(seq, seq[1:]):
        if s1 < e0 + tl["between"] - tol:
            raise CheckError("constellations pas tracées à la suite (de la plus ancienne)")
    seen = 0
    for m in re.finditer(r'<(?:circle|use|path) class="(e\d+|d)"[^>]*?(?:cx="([\d.]+)" '
                         r'cy="([\d.]+)"|translate\(([\d.]+) ([\d.]+)\)|d="M([\d.]+) ([\d.]+)m)',
                         svg):
        xy = next((m.group(k), m.group(k + 1)) for k in (2, 4, 6) if m.group(k))
        date, cls = at.get(xy), m.group(1)
        if date not in lit_at:
            if cls != "d":
                raise CheckError("étoile jamais liée qui s'allume (%s)" % date)
        elif cls == "d" or abs(kf[int(cls[1:])][1] - lit_at[date]) > tol:
            raise CheckError("étoile du %s : classe %s, pas allumée à la fin de son trait"
                             % (date, cls))
        seen += 1
    if seen < 2 * len(scene["stars"]):
        raise CheckError("allumage : classes manquantes sur des étoiles")
    if 'class="d"' in svg and ".d{opacity:%s}" % f2(UNLINKED) not in svg:
        raise CheckError("étoiles non liées pas atténuées")
    flashes = {}
    for x, y, dl in re.findall(r'<circle cx="([\d.]+)" cy="([\d.]+)" r="[\d.]+" '
                               r'style="animation-delay:-([\d.]+)s"/>', svg):
        flashes[at.get((x, y))] = (tl["phase"] - float(dl)) % T
    if set(flashes) != set(lit_at):
        raise CheckError("un éclair par étoile allumée attendu")
    for d, t in flashes.items():
        gap = abs(t - lit_at[d])
        if min(gap, T - gap) > tol:
            raise CheckError("éclair du %s pas à la fin de son trait" % d)
    if not re.search(r"@keyframes fl\{0%\{opacity:0\}", svg):
        raise CheckError("éclair qui ne part pas de zéro")


def check_leaks(text, names, ids=()):
    """Aucun nom de dépôt (complet, propriétaire ou nom seul ; hors login public) ni identifiant
    opaque dans un texte de sortie."""
    low = text.lower()
    for name in names:
        owner, _, repo = name.lower().partition("/")
        for frag in (name.lower(), repo) + (() if owner == LOGIN.lower() else (owner,)):
            if frag and frag in low:
                raise CheckError("fuite d'un nom de dépôt de test dans la sortie")
    for rid in ids:
        if rid in text:
            raise CheckError("fuite d'un identifiant de dépôt dans la sortie")


def check_dimmed(svg):
    """Sombre : aucune couleur plus sombre que la page « dark dimmed » (#22272e) sur un canal."""
    floor = [int(PAGES_BG["dark"][1][k:k + 2], 16) for k in (1, 3, 5)]
    for c in sorted(set(re.findall(r"#[0-9a-f]{6}\b", svg))):
        if any(int(c[k:k + 2], 16) < f for k, f in zip((1, 3, 5), floor)):
            raise CheckError("sombre : %s plus sombre que la page atténuée" % c)


def check_months(marks):
    xs = [m["x"] for m in marks]
    if xs != sorted(xs):
        raise CheckError("repères de mois dans le désordre")
    for fs, sel in ((MONTH_FS, marks), (MONTH_FS_NARROW, [m for m in marks if m["narrow"]])):
        for a, b in zip(sel, sel[1:]):
            if a["x"] + month_width(a["label"], fs) + 4.0 > b["x"]:
                raise CheckError("repères de mois qui se chevauchent")
        if sel and sel[-1]["x"] + month_width(sel[-1]["label"], fs) > W - EDGE:
            raise CheckError("repère de mois qui sort de l'image")
    if marks and not any(m["narrow"] for m in marks):
        raise CheckError("aucun repère de mois sur écran étroit")


def expect_failure(label, fn, needle):
    """Témoin : une règle qui ne détecte rien passerait toujours ; on la prouve sur une
    entrée volontairement fautive, qui doit échouer pour la bonne raison (`needle`)."""
    try:
        fn()
    except (CheckError, SystemExit) as exc:
        if needle in str(exc):
            return
        raise SystemExit("self-test témoin « %s » : refusé pour une autre raison (%s)"
                         % (label, exc))
    raise SystemExit("self-test témoin « %s » : défaut non détecté" % label)


def must(cond, msg):
    if not cond:
        raise CheckError(msg)


def run_captured(argv):
    """run() comme en production (enveloppe d'erreurs comprise), sortie capturée pour y
    chercher des fuites. Renvoie (code de sortie, texte de stdout + stderr)."""
    buf = io.StringIO()
    code = 0
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        try:
            run(argv)
        except SystemExit as exc:
            if exc.code not in (None, 0):
                code = 1
                buf.write(exc.code if isinstance(exc.code, str) else "")
    return code, buf.getvalue()


@contextlib.contextmanager
def patched(env=None, **names):
    """Remplace temporairement des variables d'environnement et des fonctions du module."""
    env = env or {}
    old_env = {k: os.environ.get(k) for k in env}
    old = {k: globals()[k] for k in names}
    try:
        for k, v in env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        globals().update(names)
        yield
    finally:
        globals().update(old)
        for k, v in old_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def check_redirects():
    """Le jeton ne suit jamais une redirection : un serveur local répond 302 vers une autre
    adresse, qui ne doit recevoir aucune requête (donc aucun en-tête Authorization)."""
    import http.server
    import threading
    hits = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            hits.append((self.path, self.headers.get("Authorization")))
            self.send_response(302)
            self.send_header("Location", "/ailleurs")
            self.send_header("Content-Length", "0")
            self.end_headers()
        do_GET = do_POST

        def log_message(self, *args):
            pass
    try:
        NoRedirect().redirect_request(None, None, 302, "Found", {}, "https://ailleurs.example/")
        raise CheckError("NoRedirect laisse passer une redirection")
    except RedirectRefused:
        pass
    if any(type(h) is urllib.request.HTTPRedirectHandler for h in OPENER.handlers):
        raise CheckError("l'ouvreur garde le gestionnaire de redirections par défaut")
    srv = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    try:
        req = urllib.request.Request("http://127.0.0.1:%d/graphql" % srv.server_port, data=b"{}",
                                     headers={"Authorization": "bearer jeton-factice"})
        try:
            OPENER.open(req, timeout=10).close()
            raise CheckError("redirection suivie")
        except RedirectRefused:
            pass
    finally:
        srv.shutdown()
        srv.server_close()
    if [p for p, _ in hits] != ["/graphql"]:
        raise CheckError("une requête est partie vers l'adresse de redirection")


def self_test():
    """Années synthétiques au format de l'API (sans réseau) ; s'arrête au premier défaut."""
    # modèle d'éclat : 0 < 1 < 2 < ... < max, plancher net, record = 1 (371 nombres distincts
    # au plus : un par jour du calendrier)
    for nmax in (1, 2, 3, 5, 27, 100, 1000, 10000):
        counts = sorted(set(range(1, min(nmax, 370) + 1)) | {nmax})
        lv = star_levels(counts)
        ts = [lv[c] for c in sorted(lv)]
        if abs(ts[-1] - 1.0) > 1e-9 or (nmax > 1 and abs(ts[0] - FLOOR) > 1e-9):
            raise SystemExit("self-test éclat : échelle fausse pour un record de %d" % nmax)
        if any(b - a < LADDER * 0.3 for a, b in zip(ts, ts[1:])):
            raise SystemExit("self-test éclat : pas strictement croissant (record %d)" % nmax)
    print("ok  échelle d'éclat (log, plancher, stricte croissance)")

    real_counts, real_repos, real_expected = real_shape()
    ladder = {d: i + 1 for i, d in enumerate(cal_dates(SAT_END))}
    ladder[SAT_END] = 10000
    cases = [
        ("vide", fixture(END, {}, {})),
        ("un jour", fixture(END, {datetime.date(2026, 2, 3): 3},
                            {FIXTURE_NAMES[5]: ("pr", [datetime.date(2026, 2, 3)])})),
        ("réel épars", fixture(END, real_counts, real_repos)),
        ("sam-dim", fixture(END, *sat_sun())),
        ("dense", fixture(END, *dense_year())),
        ("plein", fixture(SAT_END, *full_year(False))),
        ("mosaïque", fixture(SAT_END, *full_year(True))),
        # 371 nombres distincts et un record énorme : la stricte croissance survit à l'arrondi
        ("échelle", fixture(SAT_END, ladder, {})),
    ]
    scenes, results = [], {}
    for name, payload in cases:
        def fail(msg, name=name):
            raise SystemExit("self-test %s : %s" % (name, msg))
        data = parse_payload(payload, Anon())
        days = to_days(data)
        scene = build_scene(days)
        scenes.append(scene)
        ids = sorted(data["repos"])
        try:
            check_grid(scene, days)
            check_months(scene["months"])
            sizes = []
            for theme in THEMES:
                svg = render(scene, theme, LOGIN)
                # mêmes données, autre ordre, autre sel -> mêmes octets
                shuffled = json.loads(json.dumps(payload))
                c2 = shuffled["data"]["user"]["contributionsCollection"]
                c2["contributionCalendar"]["weeks"] = [
                    {"contributionDays": w["contributionDays"][::-1]}
                    for w in c2["contributionCalendar"]["weeks"][::-1]]
                for k in KINDS:
                    c2[k] = c2[k][::-1]
                other = parse_payload(shuffled, Anon(b"un autre sel"))
                if render(build_scene(to_days(other)), theme, LOGIN) != svg:
                    fail("%s : la sortie dépend de l'ordre d'entrée ou du sel" % theme)
                if re.search(r'(?:\br|rx|ry|width|height)="-|="[-\d. ]*(?:nan|inf)', svg):
                    fail("%s : taille négative ou invalide" % theme)
                check_links(parse_svg_links(svg, scene), days)
                check_stars(svg, scene, theme)
                check_animation(svg, scene)
                check_marks_share(svg, scene)
                check_leaks(svg, FIXTURE_NAMES, ids)
                if theme == "dark":
                    check_dimmed(svg)
                err = over_budget(svg)
                if err:
                    fail("%s : hors budget : %s" % (theme, err))
                size, elems, anim = budget(svg)
                sizes.append("%s %d o / %d él. / %d anim." % (theme, size, elems, anim))
                results[(name, theme)] = svg
        except CheckError as exc:
            fail(str(exc))
        tl = scene["tl"]
        print("ok  %-10s %3d jours, %3d étoiles, %3d liens%s | %s"
              % (name, len(days), len(scene["stars"]), len(scene["links"]),
                 ", vitesse %.0f u/s, cycle %.1f s" % (tl["speed"], tl["T"]) if tl else "",
                 ", ".join(sizes)))
        if name == "réel épars":
            got = set(scene["links"])
            nov = {e for e in got if e[0].startswith("2025-11")}
            if got - nov != real_expected or len(nov) != 4 or \
                    {d for e in nov for d in e} != {"2025-11-%d" % k for k in (10, 11, 12, 13, 19)}:
                fail("liens attendus : 4 en novembre (10-13 + 19), 1er-2 juin, 10-11 juin")
        if name in ("vide", "un jour", "sam-dim", "échelle") and scene["links"]:
            fail("lien impossible tracé")
    try:
        check_jitter(scenes)
    except CheckError as exc:
        raise SystemExit("self-test décalage : %s" % exc)
    print("ok  décalage fixe par date, d'une année à l'autre")

    # repères de mois pour 371 fins d'année consécutives
    for k in range(371):
        end = END + datetime.timedelta(days=k)
        try:
            check_months(month_marks(to_days(parse_payload(fixture(end, {}, {}), Anon()))))
        except CheckError as exc:
            raise SystemExit("self-test mois (fin %s) : %s" % (end, exc))
    print("ok  repères de mois pour 371 fins d'année")

    # pagination : un dépôt sur 250 jours, des revues sur 106 jours, 130 créations ; pages de 100
    dates = cal_dates(END)
    long_counts = {d: 2 for d in dates[:250]}
    long_counts.update({d: 1 for d in dates[260:]})
    full = fixture(END, long_counts, {FIXTURE_NAMES[0]: ("commit", dates[:250]),
                                      FIXTURE_NAMES[6]: ("review", dates[260:]),
                                      FIXTURE_NAMES[3]: ("created", dates[:130])})
    data = fetch(LOGIN, "jeton-factice", Anon(), post=fake_post(full, PAGE))
    ref = parse_payload(full, Anon())
    if data["repos"] != ref["repos"] or \
            sorted(len(v) for v in data["repos"].values()) != [106, 130, 250]:
        raise SystemExit("self-test pagination : jours de dépôts perdus entre les pages")
    print("ok  pagination des contributions (plus de 100 jours par dépôt)")

    # témoins : chaque règle doit refuser une entrée volontairement fautive, pour sa raison
    by_name = dict(zip([c[0] for c in cases], scenes))
    dense, real, sd = by_name["dense"], by_name["réel épars"], by_name["sam-dim"]

    def with_links(scene, extra):
        s = dict(scene)
        s["links"] = list(scene["links"]) + extra
        s["draws"], s["lights"], s["tl"] = propagate(s["stars"], s["links"], s["pos"])
        return s

    def links_of(scene):
        return lambda: check_links(parse_svg_links(render(scene, "dark", LOGIN), scene),
                                   scene["days"])
    expect_failure("samedi -> dimanche suivant relié",
                   links_of(with_links(sd, [("2026-03-07", "2026-03-08")])), "non voisins")
    expect_failure("dimanche -> samedi de la même semaine relié",
                   links_of(with_links(sd, [("2026-04-12", "2026-04-18")])), "non voisins")
    expect_failure("voisins sans dépôt commun reliés (2 et 10 juin)",
                   links_of(with_links(real, [("2026-06-02", "2026-06-10")])), "sans dépôt commun")
    expect_failure("non voisins reliés",
                   links_of(with_links(real, [("2025-11-10", "2025-11-19")])), "non voisins")
    extra = next(e for e in eligible(dense["stars"]) if e not in dense["links"])
    expect_failure("cycle", links_of(with_links(dense, [extra])), "cycle")
    expect_failure("lien en double", links_of(with_links(dense, [dense["links"][0]])), "double")
    expect_failure("groupe incomplet", lambda: check_links(dense["links"][1:], dense["days"]),
                   "non relié")
    svg = results[("dense", "dark")]
    cores = list(STAR_RES["core"].finditer(svg))
    lo = min(float(m.group(3)) for m in cores)
    hi = max(float(m.group(3)) for m in cores)
    bad = svg
    for m in cores:          # tous les jours au plus petit nombre deviennent énormes
        if float(m.group(3)) == lo:
            bad = bad.replace(m.group(0), m.group(0).replace('r="%s"' % m.group(3), 'r="9.999"'))
    expect_failure("taille non monotone", lambda: check_stars(bad, dense, "dark"),
                   "pas strictement croissante")
    bad = svg
    for m in cores:          # tous les jours record virent au gris
        if float(m.group(3)) == hi:
            bad = bad.replace(m.group(0), m.group(0).replace(m.group(4), "#c0c0c0"))
    expect_failure("couleur non monotone", lambda: check_stars(bad, dense, "dark"), "décroissant")
    halos = list(STAR_RES["halo"].finditer(svg))
    dim = min(float(m.group(4)) for m in halos)
    bad = svg
    for m in halos:          # les halos des jours les plus faibles deviennent les plus vifs
        if float(m.group(4)) == dim:
            bad = bad.replace(m.group(0), m.group(0).replace(
                'fill-opacity="%s"' % m.group(4), 'fill-opacity=".9999"'))
    expect_failure("brillance non monotone", lambda: check_stars(bad, dense, "dark"),
                   "pas strictement croissante")
    moved = dict(dense)
    moved["pos"] = dict(dense["pos"])
    date0 = dense["days"][100]["date"]
    moved["pos"][date0] = (moved["pos"][date0][0] + 0.5, moved["pos"][date0][1])
    expect_failure("décalage instable", lambda: check_jitter([dense, moved]), "décalage")
    expect_failure("fuite d'un nom", lambda: check_leaks(
        svg.replace("</svg>", "<!-- secret-client-repo-xyz --></svg>"), FIXTURE_NAMES), "fuite")
    expect_failure("budget", lambda: must(not over_budget(svg + "<!--%s-->" % ("x" * MAX_BYTES)),
                                          "hors budget"), "hors budget")
    crowded = dict(dense)
    crowded["stars"] = [dict(st, spark=True, flare=True) for st in dense["stars"]]
    expect_failure("aigrettes partout", lambda: check_marks_share(
        render(crowded, "dark", LOGIN), crowded), "trop d'aigrettes")
    last = len(dense["draws"]) - 1
    overlap = dict(dense)                    # 2e constellation avancée sur la 1re
    overlap["draws"] = [dict(w) for w in dense["draws"]]
    roots = sorted({w["a"] for w in overlap["draws"]} - {w["b"] for w in overlap["draws"]})
    if len(roots) < 2:
        raise SystemExit("self-test : il faut au moins deux constellations dans « dense »")
    fo = Forest()
    for w in overlap["draws"]:
        fo.union(w["a"], w["b"])
    second = [w for w in overlap["draws"] if fo.find(w["a"]) == fo.find(roots[1])]
    shift = min(w["s"] for w in second) - LEAD
    for w in second:
        w["s"], w["e"] = w["s"] - shift, w["e"] - shift
    expect_failure("constellations superposées", lambda: check_animation(
        render(overlap, "dark", LOGIN), overlap), "à la suite")
    expect_failure("étoile allumée par un autre trait", lambda: check_animation(
        svg.replace(' class="e0"', ' class="e%d"' % last, 1), dense), "fin de son trait")
    expect_failure("éclair avant la fin du trait", lambda: check_animation(re.sub(
        r'animation-delay:-([\d.]+)s', lambda m: "animation-delay:-%ss" % f2(
            (float(m.group(1)) + 0.5) % dense["tl"]["T"]), svg, count=1), dense), "éclair")
    print("ok  témoins : chaque règle détecte son défaut, pour la bonne raison")

    # données malformées : sortie en erreur, message générique (sans nom de dépôt)
    good = fixture(END, real_counts, real_repos)

    def mutated(path, value):
        p = json.loads(json.dumps(good))
        node = p
        for k in path[:-1]:
            node = node[k]
        node[path[-1]] = value
        return p
    C = ["data", "user", "contributionsCollection"]
    day0 = C + ["contributionCalendar", "weeks", 0, "contributionDays", 0]
    node0 = C + [KINDS[0], 0, "contributions", "nodes", 0, "occurredAt"]
    secret = FIXTURE_NAMES[0]
    bads = [{"errors": [{"message": "boom " + secret}]},
            {"errors": [{"message": "Resource protected: " + secret, "type": "FORBIDDEN"}]},
            {"errors": [{"message": secret, "type": secret}]}, {"data": {"user": None}},
            {"data": None}, {"weeks": []}, {"foo": 1}, None, 42, "x", {"weeks": [None]},
            [{"contributionDays": None}], [{"contributionDays": []}],
            [{"contributionDays": ["2026-01-01"]}],
            mutated(day0 + ["date"], "x"), mutated(day0 + ["date"], "2026-02-30"),
            mutated(day0 + ["date"], secret),
            mutated(day0 + ["contributionCount"], "abc"), mutated(day0 + ["contributionCount"], -1),
            mutated(day0 + ["contributionCount"], 2.5), mutated(day0 + ["contributionCount"], True),
            mutated(day0 + ["contributionCount"], float("inf")),
            mutated(day0 + ["contributionCount"], secret),
            mutated(C + ["contributionCalendar"], None),
            mutated(C + [KINDS[0]], {"x": 1}), mutated(C + [KINDS[0], 0, "repository"], None),
            mutated(C + [KINDS[0], 0, "repository", "nameWithOwner"], 7),
            mutated(C + [KINDS[0], 0, "repository", "nameWithOwner"], {secret: secret}),
            mutated(C + [KINDS[0], 0, "contributions"], secret),
            mutated(node0, "hier"), mutated(node0, "2026-01-01T10:00:00"), mutated(node0, secret),
            mutated(C + ["repositoryContributions", "nodes"], None),
            mutated(C + ["startedAt"], "jamais"),
            {"format": "constellations/1", "calendar": [["2026-01-01", 1]],
             "repos": [[secret, ["2026-01-01"]]]}]
    for bad in bads:
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
                parse_payload(bad, Anon())
        except SystemExit as exc:
            try:
                check_leaks(str(exc.code) + buf.getvalue(), FIXTURE_NAMES)
            except CheckError:
                raise SystemExit("self-test : un message d'erreur cite un nom de dépôt")
            continue
        raise SystemExit("self-test : données malformées acceptées (cas %d)" % bads.index(bad))
    print("ok  données malformées refusées (messages génériques)")

    try:
        check_redirects()
    except CheckError as exc:
        raise SystemExit("self-test redirections : %s" % exc)
    print("ok  aucune redirection suivie (le jeton ne part que vers l'API)")

    # de bout en bout, comme en production (run() et son enveloppe d'erreurs) : aucun nom de
    # dépôt dans les SVG, la sortie standard, les erreurs ni --save-json ; aucun jeton dans
    # la sortie ; repli « perso » -> « Actions » ; chemins d'erreur compris
    tmp = tempfile.mkdtemp(prefix="contrib-selftest-")
    tok = {"CONTRIB_TOKEN": "tok-perso-Zx81Qa", "GITHUB_TOKEN": "tok-actions-Yw27Pb",
           "GH_TOKEN": None}
    texts = []

    def out(sub):
        return os.path.join(tmp, sub)

    def expect_run(argv, code, needle, **patch):
        with patched(**patch):
            got, log = run_captured(argv)
        texts.append(log)
        if got != code or needle not in log:
            raise SystemExit("self-test bout en bout : %s -> code %d, attendu %d « %s »"
                             % (argv[0], got, code, needle))
        return log

    def server(refuse=(), error=None):
        base = fake_post(fixture(END, *dense_year()), PAGE)

        def post(token, query, variables):
            if token in refuse:
                raise AuthError("http")
            if error is not None:
                if isinstance(error, dict):
                    graphql_errors(error["errors"], auth=True)
                raise error
            return base(token, query, variables)
        return post
    try:
        src = os.path.join(tmp, "brut.json")
        with open(src, "w", encoding="utf-8") as fh:
            json.dump(fixture(END, *dense_year()), fh)
        expect_run(["--from-json", src, "--out", out("a"), "--save-json", out("anonyme.json")],
                   0, "liens tracés")
        expect_run(["--from-json", out("anonyme.json"), "--out", out("b")], 0, "liens tracés")
        expect_run(["--out", out("c")], 0, "jeton : perso", env=tok, gql=server())
        expect_run(["--out", out("d")], 0, "jeton : Actions (jeton perso refusé)", env=tok,
                   gql=server(refuse=(tok["CONTRIB_TOKEN"],)))
        expect_run(["--out", out("e")], 0, "jeton : Actions (CONTRIB_TOKEN absent)",
                   env=dict(tok, CONTRIB_TOKEN=""), gql=server())
        # chemins d'erreur : rien n'est écrit, rien ne fuit
        expect_run(["--out", out("x")], 1, "accès refusé", env=tok,
                   gql=server(refuse=tuple(v for v in tok.values() if v)))
        expect_run(["--out", out("x")], 1, "réponse en erreur", env=tok, gql=server(
            error={"errors": [{"message": "Not found: " + secret, "type": "NOT_FOUND"}]}))
        expect_run(["--out", out("x")], 1, "erreur inattendue (KeyError)", env=tok,
                   gql=server(error=KeyError(secret)))
        expect_run(["--from-json", src, "--out", out("x")], 1, "erreur inattendue (ValueError)",
                   build_scene=lambda days: (_ for _ in ()).throw(ValueError(secret)))
        with open(os.path.join(tmp, "bad.json"), "w", encoding="utf-8") as fh:
            json.dump(mutated(C + [KINDS[0], 0, "repository", "nameWithOwner"], [secret]), fh)
        expect_run(["--from-json", os.path.join(tmp, "bad.json"), "--out", out("x")], 1,
                   "réponse invalide")
        if os.path.exists(out("x")):
            raise SystemExit("self-test : un fichier a été écrit malgré une erreur")
        svgs = {}
        for sub in "abcde":
            for theme in THEMES:
                with open(os.path.join(out(sub), "contrib-%s.svg" % theme), encoding="utf-8") as fh:
                    svgs[sub, theme] = fh.read()
        with open(out("anonyme.json"), encoding="utf-8") as fh:
            texts.append(fh.read())
        try:
            for text in texts + list(svgs.values()):
                check_leaks(text, FIXTURE_NAMES)
                for value in (v for v in tok.values() if v):
                    if value in text or value[:8] in text:
                        raise CheckError("fuite d'un jeton dans la sortie")
        except CheckError as exc:
            raise SystemExit("self-test bout en bout : %s" % exc)
        if any(svgs[s, t] != svgs["a", t] for s in "bcde" for t in THEMES):
            raise SystemExit("self-test : mêmes données, SVG différents selon le chemin")
        if sorted(os.listdir(out("a"))) != ["contrib-dark.svg", "contrib-light.svg"]:
            raise SystemExit("self-test : fichiers temporaires laissés dans la sortie")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("ok  de bout en bout : aucun nom ni jeton dans les SVG, la sortie, les erreurs ou "
          "--save-json ; repli perso -> Actions")

    # graine de hachage de Python : sans effet sur la sortie (deux processus neufs)
    code = ("import hashlib,importlib.util,sys;sys.dont_write_bytecode=True;"
            "s=importlib.util.spec_from_file_location('g',sys.argv[1]);"
            "g=importlib.util.module_from_spec(s);s.loader.exec_module(g);"
            "p=g.parse_payload(g.fixture(g.END,*g.dense_year()),g.Anon());"
            "c=g.build_scene(g.to_days(p));"
            "print(hashlib.sha256((g.render(c,'dark','x')+g.render(c,'light','x'))"
            ".encode()).hexdigest())")
    scene = build_scene(to_days(parse_payload(fixture(END, *dense_year()), Anon())))
    want = hashlib.sha256((render(scene, "dark", "x") + render(scene, "light", "x"))
                          .encode()).hexdigest()
    for seed in ("0", "4242"):
        env = dict(os.environ, PYTHONHASHSEED=seed)
        got = subprocess.run([sys.executable, "-c", code, os.path.abspath(__file__)],
                             capture_output=True, text=True, env=env, check=False)
        if got.returncode != 0 or got.stdout.strip() != want:
            raise SystemExit("self-test : la sortie change avec PYTHONHASHSEED=%s" % seed)
    print("ok  mêmes octets sous d'autres graines de hachage")


# --------------------------------------------------------------------------------- main ----

def main(argv=None):
    ap = argparse.ArgumentParser(
        description="GitHub contribution year as constellations (dark + light SVG).")
    ap.add_argument("--user", default="Bisiaux-dev", help="GitHub login (default: Bisiaux-dev)")
    ap.add_argument("--out", default="dist", help="output directory (default: ./dist)")
    ap.add_argument("--from-json", help="read the data from a JSON file instead of the API")
    ap.add_argument("--save-json", help="also save the anonymised data (counts + opaque ids)")
    ap.add_argument("--self-test", action="store_true",
                    help="check the drawing on synthetic years (no network, writes nothing)")
    args = ap.parse_args(argv)

    if args.self_test:
        self_test()
        return
    anon = Anon()
    if args.from_json:
        try:
            with open(args.from_json, encoding="utf-8") as fh:
                payload = json.load(fh)
        except (OSError, ValueError) as exc:
            raise SystemExit("lecture impossible de --from-json (%s)" % exc.__class__.__name__)
        data = parse_payload(payload, anon)
        del payload
    else:
        data = fetch_with_fallback(args.user, anon)

    days, scene, built = build_all(data, args.user)
    print("jours : %d, jours actifs : %d, dépôts distincts : %d, liens tracés : %d"
          % (len(days), len(scene["stars"]), len(data["repos"]), len(scene["links"])))
    if scene["tl"]:
        print("animation : propagation, %d traits, vitesse %.0f u/s, cycle de %.1f s"
              % (len(scene["draws"]), scene["tl"]["speed"], scene["tl"]["T"]))
    if args.save_json:
        tmp = args.save_json + ".tmp"
        with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(saved_form(data), fh, indent=1, sort_keys=True)
        os.replace(tmp, args.save_json)
    write_all(built, args.out)


def run(argv=None):
    """main() enveloppé : toute exception imprévue se résume à son nom de classe, sans son
    message ni trace (un KeyError peut porter un nom de dépôt), et sort en erreur (code 1)."""
    try:
        main(argv)
    except SystemExit:
        raise
    except KeyboardInterrupt:
        sys.stderr.write("interrompu : rien n'est écrit\n")
        sys.exit(1)
    except BaseException as exc:
        sys.stderr.write("erreur inattendue (%s) : rien n'est écrit\n" % exc.__class__.__name__)
        sys.exit(1)


if __name__ == "__main__":
    run()
