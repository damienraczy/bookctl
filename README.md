# bookctl

Outil en ligne de commande pour rédiger des documents longs et structurés en
français (livres, manuels techniques, documentation, essais, guides
méthodologiques…), étape par étape, avec des LLM dans le cloud, sous le contrôle permanent de l'auteur.

> **Statut :** spécifications v1.0 (finalisées le 9 octobre 2026). Pas encore de code.

## Principe

- **L'ordre de travail fait la qualité.** Le livre est produit de façon
  incrémentale (cadrage → plan → plan détaillé → premier jet → transitions →
  harmonisation → style → contrôle final → assemblage), chaque étape recevant un
  extrait de l'étape supérieure, jamais le livre entier.
- **L'auteur conduit.** Une commande `bookctl` = une étape sur une cible
  explicite. Aucun agent n'enchaîne les étapes de lui-même.
- **Chaîne qualité à trois étages.** Vale (motifs codés) → System 1 (jugement
  calibré, routé) → correcteur LLM.
- **DSPy / GEPA** pour calibrer le juge, puis optimiser le rédacteur.

## Documentation

| Dossier | Contenu |
|---|---|
| [`specs/`](specs/) | spécifications : présentation du projet, principes, architecture, agents, CLI, System 1, dataset, boucles DSPy |
| [`doc-tools/`](doc-tools/) | notes techniques sur les outils (System 1, Vale, DSPy, GEPA, LLM cloud, Pandoc, CLI, git) |
| [`params.sample.yml`](params.sample.yml) | modèle de fichier de paramètres |

Point d'entrée : [`specs/00-projet.md`](specs/00-projet.md), puis
[`specs/01-architecture.md`](specs/01-architecture.md) et
[`specs/PRINCIPES.md`](specs/PRINCIPES.md).

## Données

Ce dépôt ne contient **que le code et la documentation de l'outil**. Les
manuscrits, rapports, journaux et datasets construits à partir des textes de
l'auteur restent dans l'espace de travail local, hors dépôt
([`doc-tools/git.md`](doc-tools/git.md)).

## Licence

- **Code** : [PolyForm Noncommercial 1.0.0](LICENSE.md).
- **Documentation et spécifications** : [CC BY-NC 4.0](LICENSE-docs.md).

Distribution et modification autorisées à des fins non commerciales, à
condition de **conserver le nom de l'auteur, Damien Raczy**, y compris dans les
œuvres dérivées (voir [`NOTICE`](NOTICE)). **Toute utilisation commerciale
nécessite un accord écrit préalable** de l'auteur (coordonnées dans `NOTICE`).

Ce projet n'est donc pas « open source » au sens de l'OSI : son code est
disponible et modifiable, mais pas pour un usage commercial sans accord.
