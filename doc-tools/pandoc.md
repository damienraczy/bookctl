# Note technique — Pandoc (assemblage, L10)

> **Outil :** [Pandoc](https://pandoc.org) — convertisseur de documents universel (John MacFarlane).
> **Licence :** GPL-2.0-or-later. `bookctl` l'appelle comme **programme externe** (sous-processus), sans l'embarquer ni le lier.
> **Usage dans `bookctl` :** commande `build` (L10), composant déterministe (`specs/02-agents.md` § 4).

---

## 1. Rôle

`build` assemble les fichiers de cibles d'un sujet (`book/chapters/NN/<cible>.md`)
dans l'ordre de `book/outline.md`, puis produit les formats d'export dans
`exports/`. Le Markdown reste la source de vérité ; les exports sont jetables et
régénérables.

---

## 2. Formats de sortie

| Format | Commande type | Prérequis |
|---|---|---|
| **EPUB** | `pandoc … -o ouvrage.epub` | aucun |
| **DOCX** | `pandoc … -o ouvrage.docx --reference-doc=modele.docx` | un document de référence pour les styles (optionnel) |
| **PDF** | `pandoc … -o ouvrage.pdf --pdf-engine=<moteur>` | un moteur : LaTeX (`xelatex`, `lualatex`) ou `typst` |
| **HTML** | `pandoc … -s -o ouvrage.html` | aucun |

Pour le PDF en français, `xelatex` ou `lualatex` (Unicode, polices système) ;
`typst` est plus léger à installer. Le moteur est un paramètre de `params.yml`.

---

## 3. Éléments à prévoir

| Élément | Mécanisme Pandoc |
|---|---|
| Métadonnées (titre, auteur, langue) | bloc YAML ou `--metadata-file` ; **`lang: fr-FR`** pour la césure et la typographie |
| Table des matières | `--toc`, `--toc-depth=3` |
| Numérotation des sections | `--number-sections` (ou numérotation explicite issue du plan) |
| Renvois internes | identifiants d'en-tête `{#s-3-2}` et liens `[voir](#s-3-2)` ; `state/crossrefs.yml` en est la source |
| Figures | images Markdown avec légende ; chemins relatifs au sujet (`--resource-path`) |
| Index | pas d'index natif : en PDF via LaTeX (`\index`) ; à décider (hors P0) |
| Marquage du contenu généré | mention dans les métadonnées et la page de titre (bonne pratique de transparence) |

---

## 4. Intégration dans `bookctl`

```yaml
# params.yml (extrait)
build:
  pandoc: pandoc                 # binaire
  formats: [epub, docx, pdf]
  pdf_engine: xelatex
  reference_docx: null           # chemin explicite, ou null
  toc_depth: 3
```

- `bookctl` construit la liste des fichiers dans l'ordre du plan, vérifie que
  chaque cible est acceptée et non `stale`, puis appelle Pandoc.
- **Fail-fast** : binaire absent, moteur PDF absent, code de retour non nul →
  exception (code `5`) avec la sortie d'erreur de Pandoc.
- Version de Pandoc consignée dans le rapport de build.
- Tests : un sujet minimal de démonstration (textes de test, sans donnée
  personnelle) est assemblé en EPUB et DOCX dans la suite d'intégration.

---

## 5. Points ouverts

- Index et glossaire en sortie.
- Modèle DOCX de l'éditeur, le cas échéant.
- Gestion des notes de bas de page et des citations (`--citeproc`) si L1
  (documentation) produit une bibliographie.

*Note rédigée le 9 octobre 2026.*
