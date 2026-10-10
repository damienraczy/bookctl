# Note technique — DSPy (Stanford NLP)

> **Outil :** [DSPy](https://github.com/stanfordnlp/dspy) — « Programming—not prompting—Foundation Models ».
> **Équipe :** Omar Khattab, Arnav Singhvi et contributeurs (Stanford NLP).
> **Licence :** MIT.
> **Version :** 3.4.0 (fin septembre 2026), « release de transition LM » ; 3.5 annoncée comme échéance de migration. **Épingler la version.**
> **Usage dans `bookctl` :** moteur des agents LLM au runtime (`specs/02-agents.md` § 12) et cadre de la boucle 2 (`specs/06-boucles-dspy.md`).

---

## 1. À quoi sert DSPy

DSPy remplace le prompt artisanal par une **programmation déclarative** : on
décrit des *signatures* (contrats d'entrée/sortie typés), on les exécute avec
des *modules* (`Predict`, `ChainOfThought`…), et un **optimiseur** (GEPA)
améliore les instructions contre une **métrique**.

Dans `bookctl`, DSPy a deux rôles :

1. **Runtime** : chaque agent LLM (Planificateur, Recherche, Rédacteur,
   Intégrateur, Correcteur) est un module DSPy. Les modèles sont déclarés dans
   `params.yml` et instanciés par `dspy.LM` (`doc-tools/llm-cloud.md`).
2. **Hors-ligne** : la boucle 2 optimise le module Rédacteur avec `dspy.GEPA`.
   La boucle 1 utilise GEPA en mode autonome, hors DSPy (`doc-tools/gepa.md`
   § 2.1).

DSPy **n'orchestre pas** le pipeline et **ne persiste rien** : l'utilisateur
conduit les étapes par le CLI, l'état est dans les fichiers du sujet.

---

## 2. Concepts

### 2.1 Signatures

Contrat déclaratif entrées/sorties, en classe dès que la tâche dépasse
l'évidence :

```python
class WriteSection(dspy.Signature):
    """Rédige une section en français, conforme au guide stylistique."""
    plan: str = dspy.InputField(desc="Tranche du plan détaillé de la section")
    terminology: str = dspy.InputField(desc="Lexique contrôlé")
    concepts: str = dspy.InputField(desc="Concepts déjà introduits (à ne pas redéfinir)")
    section: str = dspy.OutputField(desc="Section rédigée en Markdown")
```

Les optimiseurs réécrivent la docstring (l'instruction), **jamais** les noms de
champs ni leurs `desc` : les nommer correctement dès le départ.

**Articulation avec PRINCIPES** (prompts en `.md`, chargés just-in-time) :
l'instruction d'un agent est lue dans `prompt/<agent>_system.md` (ou
`book/style_system.md` pour le Rédacteur compilé) et injectée dans la signature
à l'exécution (`Signature.with_instructions(...)`), plutôt que codée dans la
docstring.

### 2.2 Modules utilisés

| Module | Rôle | Usage dans `bookctl` |
|---|---|---|
| `Predict` | appel direct au LM | agents simples (Intégrateur, Correcteur) |
| `ChainOfThought` | ajoute un raisonnement intermédiaire | Planificateur, Rédacteur (à mesurer) |
| `Refine` | boucle de feedback + nouvel essai, sélection par fonction de récompense | non utilisé : les nouveaux essais sont décidés par l'utilisateur (`retry`) |
| `BestOfN` | N essais, sélection par récompense | non utilisé, même raison |

`dspy.Assert` et `dspy.Suggest` sont **obsolètes et non pris en charge** depuis
2.6.

### 2.3 Adaptateurs

| Adaptateur | Quand | Remarque |
|---|---|---|
| `ChatAdapter` (défaut) | universel | marqueurs `[[ ## champ ## ]]` |
| `JSONAdapter` | modèles avec sortie structurée | à valider modèle par modèle sur Ollama Cloud |
| `XMLAdapter` | sorties imbriquées | — |

Commencer avec `ChatAdapter` ; changer seulement si l'analyse des sorties
échoue sur un modèle donné.

---

## 3. Optimiseurs

| Optimiseur | Optimise | Coût | Remarque |
|---|---|---|---|
| `LabeledFewShot` / `BootstrapFewShot` | exemples few-shot | bas | non retenu |
| `COPRO` | instructions | moyen | non retenu |
| **`GEPA`** | **instructions, par réflexion** | moyen | **retenu** : lit `Prediction(score, feedback)` |
| `BootstrapFinetune` | poids du modèle | élevé | hors périmètre |

GEPA est retenu parce que les métriques de `bookctl` produisent un **feedback
textuel** (violations Vale, questions System 1 non conformes, points du plan
non couverts), que GEPA exploite directement.

---

## 4. Fournisseurs

DSPy 3.4 dispose d'un moteur natif (`engine="auto"`) et conserve LiteLLM en
secours. Préfixes utiles :

| Fournisseur | Préfixe |
|---|---|
| Ollama (natif, local ou cloud) | `ollama_chat/<modèle>` |
| Compatible OpenAI (dont Ollama Cloud `/v1`) | `openai/<modèle>` + `api_base` |
| Anthropic | `anthropic/<modèle>` |
| OpenAI | `openai/<modèle>` |

Configuration d'Ollama Cloud et passage des paramètres de `params.yml` :
`doc-tools/llm-cloud.md`.

---

## 5. Limites de contexte

| Limite | Détail |
|---|---|
| Sortie | plafonnée par le modèle (`max_tokens`) |
| Long contexte | **aucun mécanisme natif** : DSPy n'est pas un gestionnaire de fenêtre |
| Recommandation de l'équipe | générer un plan, puis section par section |

C'est exactement l'ordre incrémental de `bookctl` : chaque module reçoit une
tranche (une section du plan), jamais le livre entier.

---

## 6. Métrique pour la boucle 2

```python
def editorial_metric(example, prediction, trace=None, pred_name=None, pred_trace=None):
    section = prediction.section
    vale = run_vale(section)                                   # violations par 1 000 mots
    terms = count_term_violations(section, example.terminology)
    judge = judge_section(section, example.plan)               # System 1 : tics + couverture du plan
    w = PARAMS.dspy.loop2.weights                              # coefficients de params.yml
    score = -(w.vale * vale.per_kword + w.terminology * terms
              + w.system1 * judge.nonconformity + w.coverage * judge.uncovered_ratio)
    feedback = (f"Vale : {vale.summary}. Termes hors lexique : {terms}. "
                f"System 1 non conforme : {judge.failed_questions}. "
                f"Points du plan non couverts : {judge.uncovered_points}.")
    return dspy.Prediction(score=score, feedback=feedback)
```

---

## 7. Risques

| Risque | Parade |
|---|---|
| Changements d'API (3.4 → 3.5) | version épinglée, montée de version volontaire |
| Sur-ingénierie (DSPy comme mini-langage) | un module par agent, signatures simples, pas de composition DSPy entre agents (les agents communiquent par fichiers) |
| Adaptateur inadapté à un modèle cloud | tests d'intégration par modèle déclaré dans `params.yml` |

---

## 8. Sources

- **Vérifié** : dépôt `stanfordnlp/dspy` (MIT, 3.4.0), signatures, modules,
  obsolescence de `Assert`/`Suggest`, optimiseurs, fournisseurs.
- **Non vérifié** : `JSONAdapter` sur les modèles Ollama Cloud, comportement au-delà
  de 50k tokens d'entrée.

*Mise à jour le 9 octobre 2026.*
