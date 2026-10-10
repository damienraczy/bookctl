# Note technique — git : le code seulement

> **Objet :** règles de versionnement du dépôt `bookctl`.
> **Référence normative :** `specs/PRINCIPES.md` § 2.

---

## 1. Ce qui est versionné

**Seul le code de l'outil** : sources Python, tests, prompts de l'outil, règles
Vale, liste des motifs, specs, documentation, modèle de paramètres
(`params.sample.yml`).

**Jamais** : versions archivées des documents (`*.arN.*`), anciennes versions,
contenu des dossiers `old`, manuscrits, instructions de l'utilisateur, rapports, journaux
d'audit, dataset étiqueté, `params.yml`, secrets. Ce sont des données
personnelles ou sensibles ; elles vivent dans l'espace de travail, hors dépôt.

Le dépôt est **public**.

---

## 2. `.gitignore` en liste blanche

Tout est ignoré, puis chaque chemin de l'outil est réautorisé explicitement :

```gitignore
# Tout ignorer par défaut
/*

# Réautoriser explicitement les chemins de l'outil
!/.gitignore
!/README.md
!/specs/
!/doc-tools/
/doc-tools/*
!/doc-tools/*.md
!/params.sample.yml
!/LICENSE.md
!/LICENSE-docs.md
!/NOTICE

# Exclus même dans les chemins autorisés
.DS_Store
*.ar[0-9]*.*
old/
```

Au fil du développement, on ajoute `!/src/`, `!/tests/`, `!/prompt/`, `!/vale/`,
`!/dataset/` (pour `motifs.yml` seulement, avec une liste blanche interne),
`!/pyproject.toml`… **une ligne par chemin, ajoutée volontairement**.

Conséquences :

- un espace de travail ou un sujet créé par erreur dans le clone n'est jamais
  ajouté ;
- un nouveau dossier n'entre dans git que par une décision explicite.

---

## 3. Contrôles

| Contrôle | Quand |
|---|---|
| Test : les chemins d'un sujet (`book/`, `state/`, `history/`, `reports/`) et `params.yml` sont ignorés (`git check-ignore`) | suite de tests [S00-06] |
| Recherche de secrets (motifs de clés d'API) dans les fichiers suivis | avant chaque push |
| Relecture des formulations issues de GEPA avant de les entrer dans `prompt/` | boucle 1 (`specs/06-boucles-dspy.md` § 2.6) |

---

## 4. Versionnement des travaux

Les artefacts d'un sujet sont versionnés par `bookctl` lui-même (historique de
révisions et manifeste, `specs/03-cli.md` § 8), pas par git.

*Note rédigée le 9 octobre 2026.*
