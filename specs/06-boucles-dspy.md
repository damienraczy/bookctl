# 06 — Les deux boucles DSPy

> Document de spécification. Définit les deux boucles d'optimisation : la boucle
> 1 (calibrer le juge System 1) et la boucle 2 (optimiser le rédacteur).
> Signatures, métriques, `reflection_lm`, budget, sorties.
>
> Rédigé le 9 octobre 2026.

---

## 0. Position

DSPy n'orchestre rien et ne persiste rien (`01-architecture.md` § 4). Au
runtime, il est le moteur des agents LLM (`02-agents.md` § 12). Hors-ligne, il
porte deux boucles d'optimisation, **dans cet ordre** :

1. **Boucle 1** — calibrer System 1 comme juge éditorial français (meilleure
   formulation des questions, meilleur modèle).
2. **Boucle 2** — optimiser le rédacteur contre une métrique où System 1, désormais
   fiable, entre en jeu.

Le paradoxe « GEPA a besoin d'une métrique fiable → la métrique serait System 1
→ mais System 1 n'est pas calibré » est résolu en **inversant l'ordre**.
Documentation : `doc-tools/gepa.md`, `doc-tools/dspy.md`.

---

## 1. Principes communs

- **Hors-ligne** : les boucles tournent pendant une *compilation*, jamais
  pendant l'exécution du pipeline. Ce ne sont pas des commandes d'étape de
  `bookctl`.
- **Artefact de sortie** : chaque boucle produit un artefact versionné
  (instruction optimisée, modèle retenu) consommé au runtime.
- **Reproductibilité** : l'artefact est accompagné de ses métadonnées (dataset
  et découpage, métrique, budget, modèles, résultat).
- **Séparation des modèles** : rédacteur (`write`), juge (System 1) et
  `reflection_lm` (`reflect`) sont distincts (`02-agents.md` § 11).
- **Paramètres** : modèles, budgets, seuils de feedback dans `params.yml`.
- **Versions épinglées** : `dspy` et `gepa` sont épinglés (API en évolution).

---

## 2. Boucle 1 — Calibrer le juge (System 1)

### 2.1 Objectif

Trouver la meilleure combinaison **(modèle System 1 × formulation des
questions)** telle que les probabilités du juge soient calibrées sur le dataset
français (`05-dataset-calibration.md`).

### 2.2 Ce qui est optimisé

Le « programme » n'est pas un LLM génératif : c'est le **texte d'une question
System 1** (`instructions` + `criteria`), évalué par un appel `/v1/systemone`.
`dspy.GEPA` fait évoluer les instructions de prédicteurs DSPy qui appellent un
`dspy.LM` ; un appel System 1 n'en est pas un.

**[S06-01]** La boucle 1 utilise **GEPA en mode autonome** (paquet `gepa`) avec
un **adaptateur** propre à `bookctl` : le candidat est le texte de la question ;
l'évaluation appelle `System1Client` sur un minibatch et renvoie score et
feedback ; la réflexion est faite par le `reflection_lm`. Cette voie est à
valider par un spike avant P2.

### 2.3 Métrique

Par exemple, l'opposé du Brier (GEPA maximise), avec un feedback textuel de
diagnostic :

```python
def calibration_metric(example: Example, noul: float, params: Params) -> Scored:
    y = 1 if example.label == "non-conforme" else 0
    brier = (noul - y) ** 2
    if abs(noul - y) > params.dspy.loop1.feedback_error_threshold:
        feedback = (f"Erreur de calibration : prédit {noul:.2f}, vérité {y}. "
                    f"Texte : « {example.text} ». La question est-elle ambiguë ?")
    else:
        feedback = f"Calibration correcte : prédit {noul:.2f}, vérité {y}."
    return Scored(score=-brier, feedback=feedback)
```

L'ECE et la qualité du routage ne sont pas décomposables par exemple : ils sont
calculés sur le test, dans le rapport final.

### 2.4 Optimiseur et budget

| Paramètre | Valeur |
|---|---|
| Optimiseur | GEPA autonome + adaptateur System 1 |
| `reflection_lm` | modèle du rôle `reflect` (LLM fort, cloud) |
| trainset / valset | split train / val du dataset FR |
| Budget | départ léger (équivalent `auto="light"`), relevé si nécessaire ; plafond en appels de métrique dans `params.yml` |

Les appels System 1 sont peu coûteux (Jev : facturation à l'entrée seulement) ;
le poste de coût est le `reflection_lm`.

### 2.5 Choix du modèle System 1 (boucle externe)

**[S06-02]** Pour chaque modèle candidat de `params.yml`
(`dspy.loop1.candidate_models`), on lance la boucle 1, puis on mesure la
calibration et le routage sur le test. On retient le meilleur couple
(modèle, formulations). Seuls les fournisseurs utilisables en exécution sont
candidats à la sélection finale (Jev) ; les modèles locaux servent à
l'expérimentation sur le poste de développement.

### 2.6 Sorties

```
<espace>/reports/calibration/<date>.md     # Brier, ECE, routage sur le test
<espace>/dataset/compiled/<question>_system.md  # formulations candidates
```

**[S06-03]** Une formulation candidate n'entre dans le dépôt
(`prompt/system1/`) qu'après relecture humaine : GEPA peut recopier des
fragments d'exemples dans l'instruction, et ces exemples viennent des textes de
l'utilisateur. Le modèle retenu est reporté dans `params.yml`
(`system1.providers.<fournisseur>.model`).

Le rapport de calibration est la **preuve** que le juge est fiable avant de le
brancher (`system1.enabled: true`) et de l'utiliser en boucle 2.

---

## 3. Boucle 2 — Optimiser le rédacteur

### 3.1 Précondition

**[S06-04]** La boucle 2 refuse de démarrer si le dernier rapport de
calibration n'est pas sous les seuils (`05-dataset-calibration.md` § 4.2).

### 3.2 Signature

Le Rédacteur est déjà un module DSPy (`02-agents.md` § 12) :

```python
class WriteSection(dspy.Signature):
    """Rédige une section technique en français, conforme au guide stylistique."""
    plan: str = dspy.InputField(desc="Tranche du plan détaillé de la section")
    terminology: str = dspy.InputField(desc="Lexique contrôlé")
    concepts: str = dspy.InputField(desc="Concepts déjà introduits (à ne pas redéfinir)")
    section: str = dspy.OutputField(desc="Section rédigée en Markdown")
```

### 3.3 Métrique composite

Quatre signaux, pondérés **en code** avec des coefficients de `params.yml` :

| Signal | Mesure | Nature |
|---|---|---|
| Vale | violations par 1 000 mots | déterministe |
| System 1 | non-conformité (questions de L4) | calibré |
| Terminologie | termes hors `terminology.yml` | déterministe |
| **Couverture du plan** | une `noul` par point clé : « ce point est-il traité ? » | calibré |

**[S06-05]** La couverture du plan est obligatoire : sans elle, la métrique
récompense un texte court et neutre (moins de mots = moins de défauts), et GEPA
apprendrait à écrire moins.

Le feedback textuel liste les violations Vale, les termes hors lexique, les
questions System 1 non conformes et les points du plan non couverts.

### 3.4 Optimiseur et données

| Paramètre | Valeur |
|---|---|
| Optimiseur | `dspy.GEPA` |
| `reflection_lm` | rôle `reflect`, distinct du rédacteur |
| trainset / valset | **tranches de plan** (entrées seules) issues de `book/plans/` : la métrique est sans référence, aucune section rédigée ni annotée n'est nécessaire |
| Budget | `auto="light"` puis `medium` ; plafond en appels de métrique dans `params.yml` |

Le coût est dominé par la génération des sections candidates (rôle `write`) et
la réflexion : l'estimer avant chaque compilation (nombre d'appels de métrique ×
taille moyenne d'une section) et l'afficher.

### 3.5 Sortie

```
<sujet>/book/style_system.md     # instruction optimisée du rédacteur (prompt, Markdown)
<sujet>/book/style.meta.yml      # métadonnées : dataset, métrique, budget, modèles, score
```

`style_system.md` est consommé par le Rédacteur au runtime. En P0/P1, avant
compilation, le Rédacteur consomme une instruction manuelle de `prompt/`.

---

## 4. Division du travail

| Tâche | Boucle 1 | Boucle 2 | Runtime |
|---|---|---|---|
| Formuler les questions System 1 | ✅ | | |
| Choisir le modèle System 1 | ✅ (boucle externe) | | |
| Mesurer la calibration | ✅ | | |
| Optimiser l'instruction du rédacteur | | ✅ | |
| Consommer `style_system.md` | | | ✅ (Rédacteur) |
| Consommer le juge calibré | | | ✅ (gate) |

---

## 5. Fail-fast et traçabilité

- **Calibration insuffisante** → rapport d'échec explicite, pas de juge « à
  moitié fiable ».
- **Surapprentissage** : GEPA peut recopier des mots-clés du trainset dans
  l'instruction. Validation **uniquement** sur le test, et relecture humaine
  des formulations (§ 2.6).
- **Traçabilité** : chaque compilation journalise modèles, dataset, métrique,
  budget et résultat.

---

## 6. Valeurs à mesurer

Ce ne sont pas des choix de conception, mais des valeurs fixées par la mesure
(spikes, boucle 1, premiers chapitres).

- **Adaptateur GEPA pour System 1** : à valider par un spike (§ 2.2).
- **Coefficients de la métrique composite** : à ajuster dans `params.yml`.
- **Seuil de feedback** `feedback_error_threshold` : valeur de départ 0,5.
