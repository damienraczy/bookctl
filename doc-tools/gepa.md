# Note technique — GEPA (Genetic-Pareto)

> **Outil :** [GEPA](https://github.com/gepa-ai/gepa) — optimiseur « Reflective Prompt Evolution ».
> **Auteurs :** Lakshya A Agrawal et al. (Berkeley/Stanford — Omar Khattab, Matei Zaharia, Dan Klein, Christopher Potts, Ion Stoica).
> **Papier :** *« GEPA: Reflective Prompt Evolution Can Outperform Reinforcement Learning »*, arXiv **2507.19457** (2025).
> **Licence :** MIT. Python ≥ 3.10.
> **Statut :** GA depuis v0.1.0, API 0.x en évolution (v0.1.4 sur PyPI en octobre 2026). **Épingler la version.**
> **Usage dans `bookctl` :** les deux boucles d'optimisation (`specs/06-boucles-dspy.md`).

---

## 1. À quoi sert GEPA

GEPA fait évoluer des **textes** (instructions, prompts) contre une métrique qui
renvoie un **score et un feedback textuel**. Un LLM de réflexion lit les traces
d'exécution et le feedback, diagnostique les échecs, et propose une nouvelle
version du texte. Une **frontière de Pareto** conserve les candidats meilleurs
sur au moins un exemple, ce qui préserve la diversité.

Le feedback textuel (*Actionable Side Information*) joue le rôle d'un gradient
dans une optimisation sans gradient : c'est ce qui distingue GEPA d'un
optimiseur qui ne voit qu'un nombre.

---

## 2. Deux façons de l'utiliser

| Mode | Paquet | Ce qui est optimisé | Usage dans `bookctl` |
|---|---|---|---|
| **Intégré à DSPy** | `dspy.GEPA` | les instructions des prédicteurs d'un programme DSPy (qui appellent un `dspy.LM`) | **boucle 2** : le Rédacteur est un module DSPy |
| **Autonome** | `gepa` (`gepa.optimize`) | un *candidat* = dictionnaire `{nom de composant: texte}`, évalué par un **adaptateur** qu'on écrit | **boucle 1** : le candidat est le texte d'une question System 1 |

DSPy dépend de `gepa` : c'est la même implémentation.

### 2.1 Pourquoi le mode autonome pour la boucle 1

`dspy.GEPA` mute les instructions de prédicteurs DSPy. Une question System 1
est envoyée à `/v1/systemone`, qui n'est pas un `dspy.LM` : il n'y a pas de
prédicteur à muter. Le mode autonome résout cela : on implémente un
**`GEPAAdapter`** avec deux méthodes :

- `evaluate` : exécute le candidat (la question) sur un minibatch d'exemples,
  via `System1Client`, et renvoie scores et traces ;
- `make_reflective_dataset` : met en forme, pour le LLM de réflexion, les
  exemples, les réponses et le feedback.

GEPA se charge du reste (sélection, réflexion, mutation, Pareto).

```python
import gepa

result = gepa.optimize(
    seed_candidate={"instructions": "Le passage contient-il un ternaire creux ?"},
    trainset=train_examples,
    valset=val_examples,
    adapter=System1Adapter(client, question_spec, params),   # adaptateur bookctl
    reflection_lm=reflect_model_id,                           # rôle `reflect` de params.yml
    max_metric_calls=params.dspy.loop1.max_metric_calls,
)
best = result.best_candidate["instructions"]
```

La signature exacte de `gepa.optimize` (paramètre `adapter`) et de
`EvaluationBatch` est à vérifier dans `src/gepa/core/adapter.py` de la version
épinglée : c'est l'objet du spike prévu avant P2.

---

## 3. Principe de fonctionnement

```
1. SÉLECTION   → un candidat de la frontière de Pareto
2. EXÉCUTION   → sur un minibatch, avec capture des traces
3. RÉFLEXION   → le reflection_lm lit traces et feedback, diagnostique
4. MUTATION    → nouveau texte qui hérite des leçons des ancêtres
5. ACCEPTATION → si le minibatch s'améliore, évaluation sur le valset
+ FUSION       → combinaison de deux candidats Pareto-optimaux
```

---

## 4. Entrées et sorties (mode DSPy)

| Paramètre | Requis | Description |
|---|---|---|
| `metric` | oui | `metric(example, prediction, trace=None, …) → dspy.Prediction(score=…, feedback=…)` |
| `trainset` | oui | exemples pour la réflexion (≥ 3) |
| `valset` | oui | exemples pour la frontière de Pareto |
| Budget | — | exactement un de : `auto` (`light` / `medium` / `heavy`), `max_full_evals`, `max_metric_calls` |
| `reflection_lm` | oui | LLM fort, **distinct** du modèle optimisé |
| `reflection_minibatch_size` | — | défaut 3 |

```python
optimizer = dspy.GEPA(metric=editorial_metric, reflection_lm=reflect_lm, auto="light")
optimized = optimizer.compile(writer, trainset=trainset, valset=valset)
```

`bookctl` extrait l'instruction optimisée vers `book/style_system.md` et écrit
les métadonnées dans `book/style.meta.yml` (`specs/06-boucles-dspy.md` § 3.5).

---

## 5. Coût

Le coût d'une compilation = **nombre d'appels de métrique** × coût d'un appel,
plus les appels du `reflection_lm` (un par itération).

| Repère publié | Valeur |
|---|---|
| Budget `auto` (2 prédicteurs, 100 exemples) | light ≈ 1 330 appels de métrique, heavy ≈ 2 045 |
| Recommandation de la FAQ | 15 à 30 × taille du valset |
| Comparaison au RL (GRPO, HotPotQA) | 35 × moins de rollouts |

Estimation pour `bookctl` :

- **Boucle 1** : un appel de métrique = un appel System 1 (Jev : facturé à
  l'entrée seulement, 0,042 $/M tokens). Le poste de coût est le
  `reflection_lm`.
- **Boucle 2** : un appel de métrique = génération d'une section (rôle `write`)
  + Vale + System 1. Coût ≈ appels × (tokens d'entrée + tokens de sortie d'une
  section) au tarif du modèle `write`, plus la réflexion. `bookctl` affiche
  cette estimation avant de lancer la compilation, à partir des tarifs déclarés
  dans `params.yml`.

---

## 6. Données nécessaires

| Boucle | Données | Annotation |
|---|---|---|
| 1 | dataset FR étiqueté (`specs/05-dataset-calibration.md`) | oui (étiquettes humaines) |
| 2 | tranches de plan détaillé (entrées du Rédacteur) | **non** : la métrique est sans référence |

GEPA fonctionne dès 3 exemples ; 30 à 300 sont recommandés.

---

## 7. Limites connues

| Limite | Détail | Parade dans `bookctl` |
|---|---|---|
| **Surapprentissage** | l'instruction peut recopier des mots-clés ou fragments d'exemples | test gelé ; relecture humaine avant d'entrer une formulation dans le dépôt (les exemples viennent des textes de l'utilisateur) |
| **Dérive de format** | l'instruction mutée peut changer l'échelle ou le format attendu | validation du format de sortie dans la métrique |
| **Pas de test automatique** | GEPA n'évalue pas sur un test séparé | mesure finale sur le test, dans le rapport |
| **API 0.x** | changements probables | version épinglée |

---

## 8. Cas d'usage publiés

Shopify, Databricks, Nubank, Dropbox, Google ADK, Microsoft (cités par la doc
GEPA), tutoriels DSPy à visée stylistique (haïku, dialogues), notation de
rédactions par grille. Aucun cas publié d'optimisation de guide stylistique
pour un ouvrage long en français.

---

## 9. Sources

- **Vérifié** : dépôt `gepa-ai/gepa` (MIT, `gepa.optimize`, candidats en
  dictionnaire de composants texte, adaptateur `evaluate` +
  `make_reflective_dataset`), intégration DSPy, arXiv 2507.19457.
- **Non vérifié** : signature complète de `gepa.optimize` et de
  `EvaluationBatch` sur la version épinglée ; comportement sur un juge non-LM.

*Mise à jour le 9 octobre 2026.*
