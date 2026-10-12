<!--
  DA tirée de l'avatar : une seule trace de lumière violette dans une nuit d'orage.
  Jetons : nuit #0b0910 · ombre #281838 · aubergine #302040 · violet profond #533861 · violet #765082
           lilas #8f6a99 · mauve #a87fb0 · glow #e3b7e6 · éclair #fbd4ff · givre #f6ebf7
  En-tête (assets/header-*.svg, versionnés sur main) : modifier LINES dans scripts/gen_header.py,
    puis  python scripts/gen_header.py --out assets  et committer les deux SVG.
  Ciel des contributions : constellations sur la grille de l'année écoulée, une étoile par jour
    actif (plus grande et plus brillante avec le nombre de contributions), reliée à ses voisines
    de la grille qui ont touché le même dépôt ; régénéré chaque nuit sur la branche output par
    .github/workflows/contrib.yml (scripts/gen_contrib.py).
  srcset : toujours des URL absolues (un chemin relatif n'y est pas réécrit par GitHub) et les
    virgules écrites %2C (le nettoyeur de GitHub coupe l'URL à la première virgule).
-->

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/Bisiaux-dev/Bisiaux-dev/main/assets/header-dark.svg">
    <source media="(prefers-color-scheme: light)" srcset="https://raw.githubusercontent.com/Bisiaux-dev/Bisiaux-dev/main/assets/header-light.svg">
    <img alt="Hi, I'm Pierre. Python · JavaScript · TypeScript developer. Building APIs with Node.js, Express &amp; Next.js. Automating with Notion API &amp; GitHub Actions." src="https://raw.githubusercontent.com/Bisiaux-dev/Bisiaux-dev/main/assets/header-light.svg">
  </picture>
</p>

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/Bisiaux-dev/Bisiaux-dev/output/contrib-dark.svg">
    <source media="(prefers-color-scheme: light)" srcset="https://raw.githubusercontent.com/Bisiaux-dev/Bisiaux-dev/output/contrib-light.svg">
    <img alt="GitHub contributions of Bisiaux-dev over the last year, drawn as constellations on the contribution grid: one star per active day, one column per week from the oldest on the left to today on the right, and the more contributions that day, the bigger and brighter the star. Neighbouring days that worked on the same repository are joined by thin lines, drawn one after another." src="https://raw.githubusercontent.com/Bisiaux-dev/Bisiaux-dev/output/contrib-light.svg">
  </picture>
</p>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://capsule-render.vercel.app/api?type=rect&height=4&section=footer&color=0:76508200%2C30:765082%2C50:fbd4ff%2C70:765082%2C100:76508200">
  <source media="(prefers-color-scheme: light)" srcset="https://capsule-render.vercel.app/api?type=rect&height=4&section=footer&color=0:76508200%2C30:a87fb0%2C50:765082%2C70:a87fb0%2C100:76508200">
  <img alt="" width="100%" src="https://capsule-render.vercel.app/api?type=rect&height=4&section=footer&color=0:76508200%2C30:a87fb0%2C50:765082%2C70:a87fb0%2C100:76508200">
</picture>
