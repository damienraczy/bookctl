# 05 — Dataset de calibration français

> Document de spécification. Définit la construction du dataset français
> étiqueté et la mesure de calibration qui déverrouille la boucle 1 DSPy
> (calibration de System 1).
>
> Rédigé le 9 octobre 2026.

---

## 0. Position

La boucle 1 exige un **dataset français étiqueté** avant de pouvoir calibrer
System 1 (`01-architecture.md` § 7). C'est le premier livrable débloquant.

Le dataset sert **deux fois** :

1. **Calibration de System 1** : mesurer si les probabilités du juge sont
   fiables sur des jugements éditoriaux français.
2. **Source des règles Vale** : les formes récurrentes et stables d'un motif
   deviennent des règles déterministes.

---

## 1. Les motifs

### 1.1 Vale et System 1 : couplés, pas redondants

Vale ne détecte que les chaînes exactes qu'on a programmées : « il convient de »
est attrapé, « il conviendrait sans doute de » ou une variante syntaxique ne
l'est pas, et chaque variante ajoutée alourdit la maintenance. System 1 juge le
**motif en contexte**, variantes comprises, et distingue un emploi fautif d'un
emploi légitime. Les deux sont couplés :

- Vale : formes figées, à coût nul et sans faux négatif sur ce qu'il connaît ;
- System 1 : le motif lui-même, y compris ses variantes et les cas où le même
  mot est légitime.

Le dataset couvre donc **tous** les motifs, avec leurs formes canoniques **et**
leurs variantes, **et** des contre-exemples légitimes.

### 1.2 Catégories initiales

Cible indicative : **~50 motifs**.

| Catégorie | Exemples de motifs |
|---|---|
| Ternaires creux | « non seulement… mais aussi », « à la fois… et… » |
| Chevilles / remplissage | « il convient de », « il est important de noter », « force est de constater » |
| Formules éculées | « à l'ère du numérique », « dans le paysage actuel », « pierre angulaire », « couteau suisse » |
| Transitions vides | « en somme », « en définitive », « cela dit » (abusifs) |
| Métaphores creuses | « naviguer dans le paysage », « lever le voile » |
| Nominalisations lourdes | « la mise en œuvre de », « la réalisation de » |
| Hyperboles / intensifs | « véritable », « littéralement », « sans précédent » |

Liste **initiale et non exhaustive**, à stabiliser sur un corpus réel. Chaque
ajout de motif est un commit daté et justifié.

### 1.3 Emplacement

| Artefact | Emplacement | Raison |
|---|---|---|
| Liste des motifs (`motifs.yml` : nom, catégorie, description, formes canoniques) | **dépôt** : `bookctl/dataset/motifs.yml` | outil, aucune donnée personnelle |
| Règles Vale dérivées | **dépôt** : `bookctl/vale/` | outil |
| Exemples étiquetés (train / val / test) | **espace de travail** : `dataset/calibration/` | construits à partir des textes de l'utilisateur |
| Rapports de calibration | **espace de travail** : `reports/calibration/` | contiennent des exemples |

**[S05-01]** Les exemples étiquetés ne sont jamais dans le dépôt.

---

## 2. Format du dataset

Chaque exemple est un texte à l'**unité de jugement** de la question visée
(phrase, paragraphe, section ou document, `04-primitives-system1.md` § 4.2),
avec une étiquette et un tag de motif :

**[S05-04]** Stockage en **JSON Lines** (`.jsonl`, UTF-8, un exemple par
ligne) : facile à valider ligne à ligne, à fusionner et à compléter sans
réécrire le fichier.

```json
{"id": "ex-001", "unit": "phrase", "text": "Cette solution n'est pas seulement rapide, mais aussi robuste.", "label": "non-conforme", "motif": "ternaire", "source": "corpus-ref-01"}
{"id": "ex-002", "unit": "phrase", "text": "Le module compile les sources puis génère l'artefact.", "label": "conforme", "motif": "", "source": "corpus-ref-01"}
```

Fichiers : `dataset/calibration/examples.jsonl` (tous les exemples) et
`dataset/calibration/split.yml` (listes d'`id` de train, val, test).

### 2.1 Champs

| Champ | Type | Rôle |
|---|---|---|
| `id` | str | identifiant stable |
| `unit` | enum | unité de jugement |
| `text` | str | le texte à juger |
| `label` | `conforme` \| `non-conforme` | vérité terrain (étiquette humaine) |
| `motif` | str | tag du motif (vide si conforme) |
| `source` | str | provenance |

Les questions `score` utilisent un champ `level` (entier, niveau attendu) à la
place de `label`.

### 2.2 Prévalence

- **Train / val** : équilibrés entre `conforme` et `non-conforme`, couverture
  homogène des motifs (pour que l'optimisation voie assez de cas de chaque
  classe).
- **[S05-02] Test : prévalence réaliste**, c'est-à-dire la proportion de
  passages fautifs observée dans de vrais premiers jets. La calibration dépend
  de la fréquence des classes : un juge calibré sur 50/50 serait mal calibré
  sur un texte où les tics sont rares. Le rapport donne les mesures sur le test
  réaliste.

---

## 3. Volume et découpage

| Ensemble | Part | Rôle |
|---|---|---|
| **total** | ~500–1 000 exemples | volume cible, atteint progressivement |
| **train** | 60 % | réflexion de GEPA (boucle 1) |
| **val** | 20 % | sélection (frontière de Pareto) |
| **test** | 20 % | mesure finale, jamais vue pendant l'optimisation |

**[S05-03]** Le découpage est fixe et versionné (liste des `id` par ensemble).
Le test est gelé : la calibration y est mesurée *une seule fois* par
compilation.

---

## 4. Mesure de la calibration

La métrique de la boucle 1 n'est **pas la justesse**, mais la **calibration** :
l'accord entre les probabilités annoncées par System 1 et la fréquence réelle
des étiquettes.

### 4.1 Indicateurs

**Brier score** (`noul`) :

```
Brier = moyenne( (p_i − y_i)² )
```

`p_i` = `noul` annoncé, `y_i` = étiquette binaire (1 = non-conforme). Plus bas
= mieux calibré. Pour `choice` et `score`, Brier multi-classe (somme sur les
options des écarts au carré entre probabilité et indicatrice).

**ECE — Expected Calibration Error** :

```
ECE = Σ_bins ( |fréquence_observée_bin − probabilité_moyenne_bin| × poids_bin )
```

10 bins de 0,1. L'ECE n'est fiable qu'avec assez d'exemples par bin : on la
calcule globalement et par catégorie de motif, pas par motif.

### 4.2 Seuils d'acceptation

| Indicateur | Seuil de départ |
|---|---|
| Brier | < 0,15 |
| ECE | < 0,10 |

Hypothèses de départ, à affiner sur les premières mesures.

### 4.3 Le vrai test : le routage

La calibration n'a de valeur que si elle **route bien**. Sur le test, avec les
seuils de `04-primitives-system1.md` § 3 :

```
réponse certaine   →  la décision est-elle correcte ?         (précision)
réponse incertaine →  correspond-elle à un cas réellement difficile ? (rappel)
taux d'escalade    →  reste-t-il supportable pour l'utilisateur ?
```

C'est ce critère, plus que le Brier brut, qui décide si System 1 est utilisable
comme juge.

---

## 5. Le dataset comme métrique DSPy (boucle 1)

- **Étiquette** → vérité terrain.
- **Réponse System 1** → prédiction (`noul`, `probabilities`).
- **Métrique** → Brier par exemple (agrégeable par GEPA) ; ECE et routage en
  rapport final.

GEPA optimise la **formulation des questions** (`_system.md`). Le choix du
modèle System 1 est une boucle externe (`06-boucles-dspy.md` § 2.5).

---

## 6. TDD

- **Chargement** : exception sur champ manquant, `id` dupliqué, `label` ou
  `unit` hors enum.
- **Équilibre** : train et val restent sous un déséquilibre paramétré.
- **Découpage** : séparation train/val/test, absence de fuite.
- **Brier / ECE** : fonctions pures testées sur des cas connus (prédiction
  parfaite → 0 ; prédiction constante 0,5 → Brier 0,25).
- **Routage** : précision, rappel et taux d'escalade calculés et bornés.

---

## 7. Fail-fast et traçabilité

- **Échec de chargement** → exception explicite, pas de valeur par défaut.
- **Calibration insuffisante** → la boucle 1 **échoue explicitement** et rend
  un rapport ; elle ne produit pas un juge « à moitié calibré ».
- **Traçabilité** : chaque mesure est journalisée (modèle System 1, version du
  dataset, métrique, résultat).

---

## 8. Livrables

1. `motifs.yml` stabilisé (dépôt).
2. Le dataset étiqueté et son découpage (espace de travail).
3. `brier_score()`, `ece()`, et les mesures de routage (testées).
4. Le chargeur de dataset (testé, fail-fast).

---

## 9. Valeurs à mesurer

Ce ne sont pas des choix de conception, mais des valeurs fixées par la mesure
(spikes, boucle 1, premiers chapitres).

- **Seuils Brier / ECE définitifs**.
- **Prévalence réaliste** : à mesurer sur les premiers jets du sujet pilote.
- **Double étiquetage** (accord inter-annotateurs) : écarté pour l'instant.
