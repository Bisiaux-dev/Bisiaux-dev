<!--
  DA tirée de l'avatar : une seule trace de lumière violette dans une nuit d'orage.
  Jetons (mesurés sur l'avatar, ou milieu exact de deux jetons mesurés) :
    nuit       #0b0910  bord de la tuile du bandeau (thème clair) ; encre du serpent (thème clair)
    aubergine  #302040  fond des badges
    violet     #765082  lueur du bandeau, traits de section, texte animé (thème clair)
    lilas      #8f6a99  repli du texte animé : lisible sur fond sombre (4,2:1) ET blanc (4,5:1)
    glow       #e3b7e6  texte animé (thème sombre), logos des badges
    éclair     #fbd4ff  le point le plus lumineux : nom, serpent (thème sombre), cœur du trait final
  Rampes du serpent (source de vérité : .github/workflows/snake.yml, color_dots = 0 contribution -> max) :
    sombre : #281838 #533861 #765082 #8f6a99 #a87fb0 (serpent #fbd4ff)
    clair  : #f6ebf7 #e3b7e6 #a87fb0 #765082 #533861 (serpent #0b0910)
  Règle : ce qui est opaque reste "de nuit" dans les deux thèmes ; ce qui est transparent change
  via <picture>. Les bords des traits et du bandeau sombre sont transparents (#76508200) pour se
  fondre dans tous les thèmes sombres, "dimmed" compris.
  Dans un srcset, toujours écrire les virgules en %2C (le nettoyeur de GitHub coupe l'URL à la
  première virgule).
-->

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://capsule-render.vercel.app/api?type=waving&color=0:76508200%2C56:765082%2C100:76508200&height=180&section=header&text=Bisiaux-dev&fontColor=fbd4ff&fontSize=58&fontAlignY=38&animation=fadeIn">
  <source media="(prefers-color-scheme: light)" srcset="https://capsule-render.vercel.app/api?type=soft&color=0:0b0910%2C56:765082%2C100:0b0910&height=180&section=header&text=Bisiaux-dev&fontColor=fbd4ff&fontSize=58&fontAlignY=50&animation=fadeIn">
  <img alt="Bisiaux-dev" width="100%" src="https://capsule-render.vercel.app/api?type=soft&color=0:0b0910%2C56:765082%2C100:0b0910&height=180&section=header&text=Bisiaux-dev&fontColor=fbd4ff&fontSize=58&fontAlignY=50&animation=fadeIn">
</picture>

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://readme-typing-svg.demolab.com?font=JetBrains+Mono&weight=500&size=20&duration=3000&pause=1400&color=E3B7E6&center=true&vCenter=true&width=560&height=44&lines=Salut%2C+moi+c%27est+Pierre;Dev+Python+%C2%B7+JavaScript+%C2%B7+TypeScript;APIs+Node.js+%C2%B7+Express+%C2%B7+Next.js;Automatisation+%3A+Notion+API+%26+GitHub+Actions">
    <source media="(prefers-color-scheme: light)" srcset="https://readme-typing-svg.demolab.com?font=JetBrains+Mono&weight=500&size=20&duration=3000&pause=1400&color=765082&center=true&vCenter=true&width=560&height=44&lines=Salut%2C+moi+c%27est+Pierre;Dev+Python+%C2%B7+JavaScript+%C2%B7+TypeScript;APIs+Node.js+%C2%B7+Express+%C2%B7+Next.js;Automatisation+%3A+Notion+API+%26+GitHub+Actions">
    <img alt="Salut, moi c'est Pierre — Dev Python, JavaScript, TypeScript — APIs Node.js, Express, Next.js — Automatisation : Notion API et GitHub Actions" src="https://readme-typing-svg.demolab.com?font=JetBrains+Mono&weight=500&size=20&duration=3000&pause=1400&color=8F6A99&center=true&vCenter=true&width=560&height=44&lines=Salut%2C+moi+c%27est+Pierre;Dev+Python+%C2%B7+JavaScript+%C2%B7+TypeScript;APIs+Node.js+%C2%B7+Express+%C2%B7+Next.js;Automatisation+%3A+Notion+API+%26+GitHub+Actions">
  </picture>
</p>

<p align="center">
  Je construis des APIs, des automatisations et des plugins Obsidian,<br>
  du premier commit jusqu'au déploiement.
</p>

<h3 align="center">Stack</h3>
<p align="center"><img alt="Trait de lumière" width="100%" src="https://capsule-render.vercel.app/api?type=rect&height=4&section=header&color=0:76508200%2C40:76508200%2C50:765082%2C60:76508200%2C100:76508200"></p>

<p align="center">
  <sub><b>Langages</b></sub><br>
  <img alt="Python" src="https://img.shields.io/badge/Python-302040?style=flat-square&logo=python&logoColor=e3b7e6">
  <img alt="JavaScript" src="https://img.shields.io/badge/JavaScript-302040?style=flat-square&logo=javascript&logoColor=e3b7e6">
  <img alt="TypeScript" src="https://img.shields.io/badge/TypeScript-302040?style=flat-square&logo=typescript&logoColor=e3b7e6">
  <img alt="HTML" src="https://img.shields.io/badge/HTML-302040?style=flat-square&logo=html5&logoColor=e3b7e6">
  <br><sub><b>Back-end</b></sub><br>
  <img alt="Node.js" src="https://img.shields.io/badge/Node.js-302040?style=flat-square&logo=nodedotjs&logoColor=e3b7e6">
  <img alt="Express" src="https://img.shields.io/badge/Express-302040?style=flat-square&logo=express&logoColor=e3b7e6">
  <img alt="Next.js" src="https://img.shields.io/badge/Next.js-302040?style=flat-square&logo=nextdotjs&logoColor=e3b7e6">
  <img alt="Prisma" src="https://img.shields.io/badge/Prisma-302040?style=flat-square&logo=prisma&logoColor=e3b7e6">
  <br><sub><b>Cloud</b></sub><br>
  <img alt="Railway" src="https://img.shields.io/badge/Railway-302040?style=flat-square&logo=railway&logoColor=e3b7e6">
  <img alt="Cloudflare Workers" src="https://img.shields.io/badge/Cloudflare_Workers-302040?style=flat-square&logo=cloudflareworkers&logoColor=e3b7e6">
  <img alt="Cloudflare D1" src="https://img.shields.io/badge/Cloudflare_D1-302040?style=flat-square&logo=cloudflare&logoColor=e3b7e6">
  <br><sub><b>Outils &amp; CI</b></sub><br>
  <img alt="GitHub Actions" src="https://img.shields.io/badge/GitHub_Actions-302040?style=flat-square&logo=githubactions&logoColor=e3b7e6">
  <img alt="Notion API" src="https://img.shields.io/badge/Notion_API-302040?style=flat-square&logo=notion&logoColor=e3b7e6">
  <img alt="Obsidian" src="https://img.shields.io/badge/Obsidian-302040?style=flat-square&logo=obsidian&logoColor=e3b7e6">
</p>

<h3 align="center">Projets</h3>
<p align="center"><img alt="Trait de lumière" width="100%" src="https://capsule-render.vercel.app/api?type=rect&height=4&section=header&color=0:76508200%2C40:76508200%2C50:765082%2C60:76508200%2C100:76508200"></p>

<div align="center">
<p>
  <a href="https://github.com/Bisiaux-dev/obsidian-lore-graph"><b>Lore Graph</b></a><br>
  Masque des dossiers entiers du graphe Obsidian et révèle leurs notes à la demande, d'un clic sur un nœud lié.
</p>
<details>
  <summary><sub>Voir la démo</sub></summary>
  <img alt="Démo de Lore Graph : un clic sur une note fait apparaître en violet ses notes liées, masquées jusque-là dans la vue graphe d'Obsidian" width="560" src="https://raw.githubusercontent.com/Bisiaux-dev/obsidian-lore-graph/main/assets/demo.gif">
</details>
<p>
  <a href="https://github.com/Bisiaux-dev/obsidian_satisfactory_plugin"><b>Satisfactory chains</b></a><br>
  Schématise des usines <i>Satisfactory</i> en graphes, directement dans Obsidian.
</p>
<details>
  <summary><sub>Voir un aperçu</sub></summary>
  <a href="https://raw.githubusercontent.com/Bisiaux-dev/obsidian_satisfactory_plugin/main/assets/demo.gif"><img alt="Aperçu de Satisfactory chains : une chaîne de production dessinée en graphe dans Obsidian (cliquer pour la démo animée)" width="560" src="https://raw.githubusercontent.com/Bisiaux-dev/obsidian_satisfactory_plugin/main/assets/portal-1-graph.png"></a><br>
  <sub>Cliquer sur l'image pour la démo animée.</sub>
</details>
</div>

<h3 align="center">Activité</h3>
<p align="center"><img alt="Trait de lumière" width="100%" src="https://capsule-render.vercel.app/api?type=rect&height=4&section=header&color=0:76508200%2C40:76508200%2C50:765082%2C60:76508200%2C100:76508200"></p>

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/Bisiaux-dev/Bisiaux-dev/output/snake-dark.svg">
    <source media="(prefers-color-scheme: light)" srcset="https://raw.githubusercontent.com/Bisiaux-dev/Bisiaux-dev/output/snake-light.svg">
    <img alt="Serpent qui parcourt et mange le graphe de contributions GitHub de Bisiaux-dev" src="https://raw.githubusercontent.com/Bisiaux-dev/Bisiaux-dev/output/snake-light.svg">
  </picture>
  <br>
  <sub>Graphe de contributions, régénéré chaque nuit.</sub>
</p>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://capsule-render.vercel.app/api?type=rect&height=4&section=footer&color=0:76508200%2C30:765082%2C50:fbd4ff%2C70:765082%2C100:76508200">
  <source media="(prefers-color-scheme: light)" srcset="https://capsule-render.vercel.app/api?type=rect&height=4&section=footer&color=0:76508200%2C30:a87fb0%2C50:765082%2C70:a87fb0%2C100:76508200">
  <img alt="Trait de lumière violet, fin de page" width="100%" src="https://capsule-render.vercel.app/api?type=rect&height=4&section=footer&color=0:76508200%2C30:a87fb0%2C50:765082%2C70:a87fb0%2C100:76508200">
</picture>
