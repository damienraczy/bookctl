# bookctl

Outil en ligne de commande pour rédiger un manuel technique en français, étape
par étape, avec des LLM dans le cloud, sous le contrôle permanent de l'auteur.

> **Statut :** spécification. Pas encore de code.

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
| [`specs/`](specs/) | spécifications : principes, architecture, agents, CLI, System 1, dataset, boucles DSPy |
| [`doc-tools/`](doc-tools/) | notes techniques sur les outils (System 1, Vale, DSPy, GEPA, LLM cloud, Pandoc, CLI, git) |
| [`params.sample.yml`](params.sample.yml) | modèle de fichier de paramètres |

Point d'entrée : [`specs/01-architecture.md`](specs/01-architecture.md), puis
[`specs/PRINCIPES.md`](specs/PRINCIPES.md).

## Données

Ce dépôt ne contient **que le code et la documentation de l'outil**. Les
manuscrits, rapports, journaux et datasets construits à partir des textes de
l'auteur restent dans l'espace de travail local, hors dépôt
([`doc-tools/git.md`](doc-tools/git.md)).
