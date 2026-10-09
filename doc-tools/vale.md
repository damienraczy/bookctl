# Note technique — Vale (linter de prose)

> **Outil :** [Vale](https://github.com/vale-cli/vale) — linter de prose écrit en Go, configuré par des fichiers YAML.
> **Auteur principal :** Joseph Kato (@jdkato).
> **Licence :** MIT.
> **Version :** v3.14.2 est la dernière indexée sur pkg.go.dev (mai 2026) ; des paquets WinGet/Snap annoncent des numéros plus récents. **Épingler** la version vérifiée à l'installation.
> **Usage dans `bookctl` :** première barrière de la chaîne qualité (`specs/01-architecture.md` § 3), couplée à System 1.

---

## 1. Rôle dans `bookctl`

Vale lit un fichier texte (Markdown pour `bookctl`), applique des règles
déclarées en YAML et produit des diagnostics (ligne, colonne, message, niveau
`error` / `warning` / `suggestion`).

C'est la couche **déterministe** : sans appel de modèle, rapide, reproductible,
sans aucun biais commun avec le rédacteur.

**Ce que Vale ne fait pas** : il ne détecte que les chaînes qu'on a codées. Une
variante (« il conviendrait sans doute de » au lieu de « il convient de »), une
tournure équivalente ou un emploi légitime du même mot lui échappent ou le
trompent. Chaque variante ajoutée alourdit la maintenance. C'est pourquoi Vale
est **couplé à System 1**, qui juge le motif en contexte
(`specs/05-dataset-calibration.md` § 1.1) :

| | Vale | System 1 |
|---|---|---|
| Détecte | formes figées codées | le motif, variantes comprises |
| Faux négatifs | toute forme non codée | selon calibration |
| Faux positifs | emplois légitimes d'une forme codée | selon calibration |
| Coût | nul | très faible |
| Rôle | barrière rapide, sans appel réseau | jugement gradué, routage |

---

## 2. Forces opérationnelles

| Force | Détail |
| --- | --- |
| **Binaire Go unique, hors ligne** | démarrage à froid ~156 ms (page de 2 Ko, mesure communautaire) |
| **Performance** | cas GitLab : 2 826 pages Markdown, 82 règles, 19,5 s ; largement suffisant pour un livre |
| **Hunspell intégré** | dictionnaires LibreOffice `fr_FR` pris en charge depuis la v3 (bug de flag long corrigé) |
| **LSP** | `vale-ls` : diagnostics dans l'éditeur pendant la relecture manuelle |
| **Sortie JSON** | `--output=JSON`, lue par `bookctl` pour construire le verdict |

---

## 3. Types de règles utiles

| Type | Effet | Usage dans `bookctl` |
| --- | --- | --- |
| **`existence`** | signale un motif | formes figées des motifs (`dataset/motifs.yml`) |
| **`substitution`** | propose un remplacement | lexique contrôlé (`terminology.yml` : terme interdit → terme retenu) |
| **`occurrence`** | borne le nombre d'occurrences dans une portée | phrases trop longues, ponctuation |
| **`consistency`** | interdit la coexistence de deux variantes | cohérence terminologique |
| `repetition` | répétition de mots | — |
| `metric` | seuil sur une métrique (lisibilité, longueur) | longueur de paragraphe |
| `spelling` | Hunspell | orthographe |

---

## 4. Le français

| Question | Réponse |
| --- | --- |
| Style français officiel ? | **Non.** Aucun style FR dans le registre Vale. |
| Style communautaire stable ? | Non. |
| Hunspell `fr_FR` ? | Oui depuis la v3. |
| Ce qu'il faut faire | **Écrire son propre style FR**, dérivé de `dataset/motifs.yml`. |

### 4.1 Pièges propres au français

- **Deux apostrophes.** « l'ère » (`'`, U+0027) et « l’ère » (`’`, U+2019)
  coexistent. Toute règle contenant une apostrophe doit accepter les deux :
  `l['’]ère du numérique`.
- **Portée.** Les motifs en deux parties (`non seulement … mais aussi`) doivent
  être limités à la phrase (`scope: sentence`), sinon `.*` traverse plusieurs
  phrases.
- **Élision et casse.** Prévoir les formes en début de phrase (`Il convient`)
  avec `ignorecase: true`.
- **Typographie.** Espaces insécables avant `;:!?` et à l'intérieur des
  guillemets « », guillemets français : règles `existence` en
  `scope: text`, jamais `raw` (sinon le code et le front matter sont signalés).

---

## 5. Organisation dans le dépôt

Pas de fichier caché : la configuration s'appelle `vale/vale.ini` et est passée
explicitement (`vale --config=vale/vale.ini`).

```
bookctl/vale/
├── vale.ini
└── styles/
    └── fr/
        ├── Ternaires.yml        # un fichier par catégorie de motif (05 § 1.2)
        ├── Chevilles.yml
        ├── Formules.yml
        ├── Transitions.yml
        ├── Metaphores.yml
        ├── Nominalisations.yml
        ├── Hyperboles.yml
        └── Typographie.yml
```

Le chemin de la configuration et les niveaux bloquants par étape viennent de
`params.yml` :

```yaml
vale:
  binary: vale
  config: vale/vale.ini
  blocking_level:            # niveau à partir duquel la gate rend fail
    draft: error
    link: error
    polish: warning          # plus strict à la correction stylistique
```

---

## 6. Correspondance avec la gate `bookctl`

| Sortie Vale | Gate `bookctl` |
| --- | --- |
| aucun diagnostic au niveau bloquant de l'étape | contribue `pass` |
| au moins un diagnostic au niveau bloquant | `fail` (code `1`), liste fournie |
| code de sortie `2` (erreur d'exécution Vale) | exception, code `5` |

`bookctl` lance Vale avec `--output=JSON --no-exit` et décide lui-même du
verdict à partir du JSON : les codes de sortie de Vale ne sont pas transmis
tels quels.

---

## 7. Snippets (règles FR de départ)

```yaml
# vale/styles/fr/Chevilles.yml
extends: existence
message: "Cheville : « %s »"
level: error
ignorecase: true
tokens:
  - "il convient de"
  - "il est important de noter"
  - "force est de constater"
  - "il faut souligner que"
```

```yaml
# vale/styles/fr/Ternaires.yml
extends: existence
message: "Ternaire creux : « %s »"
level: error
ignorecase: true
scope: sentence
tokens:
  - 'non seulement\b.*?\bmais aussi'
  - 'à la fois\b.*?\bet\b'
```

```yaml
# vale/styles/fr/Formules.yml
extends: existence
message: "Formule éculée : « %s »"
level: error
ignorecase: true
tokens:
  - "à l['’]ère du numérique"
  - "dans le paysage actuel"
  - "pierre angulaire"
  - "couteau suisse"
```

```ini
# vale/vale.ini
StylesPath = styles
MinAlertLevel = suggestion

[*.md]
BasedOnStyles = fr
```

Chaque règle est couverte par des tests (`tests/vale/`) : un exemple qui doit
déclencher, un qui ne doit pas, pour les deux apostrophes.

---

## 8. Formats et limites

- **Pris en charge** : Markdown (format de travail de `bookctl`), et de nombreux
  autres formats non utilisés ici.
- **LaTeX** : non pris en charge nativement, sans objet pour `bookctl`.

---

## 9. Sources

- **Vérifié** : dépôt `vale-cli/vale`, licence MIT, v3.14.2 sur pkg.go.dev,
  codes de sortie (`0` aucun constat, `1` erreurs, `2` erreur d'exécution),
  formats de sortie, prise en charge de Hunspell `fr_FR` en v3.
- **Non vérifié** : numéro exact de la dernière version, temps de démarrage sur
  le poste de développement.

*Mise à jour le 9 octobre 2026.*
