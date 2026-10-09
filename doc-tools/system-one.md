# Note technique — Les modèles « System 1 » et leurs options de déploiement

> **Objet :** les modèles de décision « System 1 » (Jev, Clef, Clef-flash, Nimble,
> Tev1…) et les manières de les utiliser dans `bookctl`.
> **Catégorie :** modèles de décision calibrés, exposés par l'API `/v1/systemone`,
> distincts des LLM génératifs.
> **Usage dans `bookctl` :** juge gradué de la chaîne qualité
> (`specs/04-primitives-system1.md`), calibré par la boucle 1
> (`specs/06-boucles-dspy.md`).
> **Consulté :** 9 octobre 2026 — docs TypeSafe (`docs.typesafe.ai` : API,
> Models, Confidence, Primitives/Noul, SDK Python), pages Ollama (tev1, nimble,
> clef), docs Ollama Cloud et compatibilité OpenAI, doc Pydantic AI « System One ».

---

## 1. Ce qu'est un modèle System 1

Un modèle System 1 n'est pas un « petit LLM rapide » : c'est un **contrat
d'entrée/sortie** et un **objectif d'entraînement** différents.

- Un LLM **génère des tokens** destinés à un humain.
- Un modèle System 1 **ne génère pas de texte** : il reçoit un `state` et des
  `questions` typées, et renvoie des **valeurs structurées** avec des
  **probabilités**.

| Critère | LLM génératif | Modèle System 1 |
|---|---|---|
| Sortie | texte libre | valeurs typées (`choice`, `score`, `noul`) |
| Consommation | générer puis analyser | aucune analyse |
| Raisonnement produit | oui | non : ni réponse, ni explication |
| Calcul | autorégressif, token par token | une passe, toutes les options scorées ensemble |
| Incertitude | absente ou simulée | `probabilities` (+ `confidence` pour `choice`/`score`) |
| Plusieurs questions | séquentielles, dépendantes de l'ordre | parallèles, isolées, même `state` |

Le nom renvoie au « Système 1 » de Kahneman (jugement rapide et intuitif),
revendiqué par TypeSafe.

---

## 2. Le contrat `/v1/systemone`

### 2.1 Requête

```json
{
  "model": "jev-latest",
  "state": "Le texte à juger (chaîne, objet ou tableau JSON).",
  "questions": {
    "ternaire": {
      "type": "noul",
      "instructions": "Le passage contient-il un ternaire creux ?",
      "criteria": {"true": "contient un ternaire creux", "false": "aucun ternaire creux"}
    },
    "tics": {
      "type": "score",
      "instructions": "Densité de tics stylistiques ?",
      "criteria": ["Aucun", "Faible", "Modéré", "Élevé"]
    },
    "partie": {
      "type": "choice",
      "instructions": "À quelle partie ce chapitre appartient-il ?",
      "criteria": {"A": "Fondamentaux", "B": "Mise en œuvre", "C": "Cas avancés"}
    }
  }
}
```

- `noul` : `criteria` optionnel (`true` / `false`).
- `choice` : `criteria` obligatoire, options → description (ou `null`).
- `score` : `criteria` obligatoire, niveaux ordonnés du plus bas au plus haut,
  numérotés à partir de 0.

### 2.2 Réponse

```json
{
  "model": "jev-1.13.0",
  "answers": {
    "ternaire": {"type": "noul", "noul": 0.93},
    "tics": {"type": "score", "score": 1.42, "legend": {"0": "Aucun", "...": "..."},
             "probabilities": {"0": 0.10, "1": 0.45, "2": 0.38, "3": 0.07}, "confidence": 0.41},
    "partie": {"type": "choice", "choice": "B",
               "probabilities": {"A": 0.08, "B": 0.84, "C": 0.08}, "confidence": 0.76}
  },
  "usage": {"input_tokens": 412, "output_tokens": 3}
}
```

| Primitive | Champs renvoyés |
|---|---|
| `choice` | `choice`, `probabilities`, `confidence` |
| `score` | `score` (niveau pondéré, peut tomber entre deux niveaux), `legend`, `probabilities`, `confidence` |
| `noul` | `noul` (probabilité que la réponse soit vraie) **uniquement** |

### 2.3 `confidence` : définition exacte

`confidence` est une statistique calculée sur la distribution renvoyée : 1 quand
toute la probabilité est sur une option, 0 quand elle est uniformément répartie.
**Ce n'est pas la probabilité d'avoir raison.**

- **`choice`** (n options, p_max = probabilité de tête) :
  `(p_max − 1/n) / (1 − 1/n)`.
- **`score`** (n niveaux, m = niveau le plus probable) :
  `max(0, 1 − Σ pᵢ·|i − m| / MAD_unif)`, où `MAD_unif` est la même distance
  moyenne pour une distribution uniforme, mesurée depuis le niveau central. Une
  probabilité sur un niveau voisin pénalise moins qu'une probabilité éloignée.
- **`noul`** : **pas de `confidence`**. La probabilité suffit : proche de 0 ou 1
  = certain, proche de 0,5 = incertain. La doc TypeSafe suggère `|2p − 1|` si
  l'on veut un nombre comparable.

### 2.4 Routage recommandé par l'éditeur

- Trois bandes : agir automatiquement si certitude forte, vérifier si moyenne,
  ne pas agir si faible.
- Pour `noul` : deux seuils (exemple de la doc : ≥ 0,8 → oui, ≤ 0,2 → non,
  entre les deux → revue humaine). Le seuil dépend du coût de chaque erreur.
- Les seuils sont **propres à chaque modèle** : un seuil réglé pour un modèle ne
  se transpose pas à un autre. Les mesurer sur ses propres données étiquetées.

`bookctl` applique ce schéma : `specs/04-primitives-system1.md` § 3.

### 2.5 Patterns documentés

1. **Fan-out spéculatif** — poser la même question sous plusieurs formulations
   et combiner.
2. **Routage par certitude** — seuil → agir ou escalader.
3. **Routage d'intention** — distribuer via un `choice`.
4. **Score composite** — combiner des `score` avec des coefficients **en code**.

Principe directeur : **questions atomiques, composées en code**. Une question
est un « gut-check » qu'un expert tranche en quelques secondes ; un jugement
multi-facteurs se décompose en sous-questions.

---

## 3. Options de déploiement

`bookctl` appelle les LLM dans le cloud. Pour System 1, les options sont les
suivantes.

### 3.1 Option A — Jev (TypeSafe, cloud) — **option cible**

| Élément | Valeur |
|---|---|
| Endpoint | `POST https://api.typesafe.ai/v1/systemone` |
| Authentification | `Authorization: Bearer <clé>` ; clé créée dans la console TypeSafe |
| Variable d'environnement (SDK) | `TYPESAFE_API_KEY` |
| SDK Python | `typesafe-sdk` (`TypeSafeClient`, `AsyncTypeSafeClient`) ; résultats dans `response.nouls`, `.choices`, `.scores` |
| Modèle | `jev-1.13.0` ; alias `jev-latest` et `jev-preview` (pointent sur 1.13) |
| Contexte | 64k tokens par requête (state + toutes les questions) ; 32k pour state + la plus longue question |
| Entrée | texte seulement |
| Tarif | 0,042 $ par million de tokens d'entrée ; sortie gratuite |
| Limites de débit | 100k tokens/s, 80 requêtes/s (susceptibles de changer) |
| Limites de questions | `choice` ≤ 255 options ; `score` 2 à 10 niveaux |
| Erreurs | 401 (clé), 422 (validation), 429 (débit), 529 (surcharge) ; retenter 429/529 avec backoff (le SDK le fait par défaut) |
| Langues | anglais prioritaire et le plus précis ; autres langues prises en charge « pas aussi bien » : **à tester sur ses propres données** |

**Forces** : cloud (conforme au choix du projet), contexte suffisant pour juger
une section entière, coût négligeable, aucun matériel.
**Limites** : API propriétaire ; calibration en français inconnue ; `score`
limité à 10 niveaux.

### 3.2 Option B — Ollama en local (poste de développement)

Ollama ≥ 0.35 sert des modèles System 1 sur `http://localhost:11434/v1/systemone`
(même contrat). Usage **réservé au poste de développement**, si le matériel le
permet : expérimenter des formulations, comparer des modèles, travailler hors
ligne. Pas d'usage en exécution.

| Modèle | Auteur | Base | Tailles (téléchargement) | Licence | Contexte effectif | Remarques |
|---|---|---|---|---|---|---|
| **Clef** | Cloudflare | Qwen3.8-27B | 27B (18 Go) | Apache 2.0 | 64k annoncé dans les points forts (256k dans la liste des tags) | texte + image ; Ollama ≥ 0.35.1 |
| **Clef-flash** | Cloudflare | Qwen3.5-9B | 9B | Apache 2.0 | — | le plus rapide mesuré |
| **Nimble** | Bespoke Labs | Qwen3.5-9B | 9B (9,3–9,5 Go) | Apache 2.0 | **8 192 tokens** (les tags annoncent 256k, les notes 8k) | < 100 ms sur MacBook Pro M5 Max |
| **Tev1** | Together AI | Qwen3.5 | 4B (4,4 Go), 0.8B (≈ 800 Mo) | MIT pour les scripts d'entraînement et le dataset ; licence des poids non précisée sur la page | **≈ 2 000 tokens** (notes de la page) | `choice` entraîné sur 2 à 24 options |

Limites communes Ollama : 64 questions par appel, 26 options ou niveaux au
maximum, requête ≤ 64 Kio. Pas de clé d'API en local.

**Point d'attention** : le contexte effectif de Tev1 (≈ 2k tokens) et de Nimble
(8k) **interdit** de juger une section longue ou un chapitre en une requête. Ces
modèles ne conviennent qu'aux unités courtes (phrase, paragraphe).

**Matériel** : non documenté par les pages. Un modèle de 9 Go demande au moins
autant de mémoire libre (GPU ou mémoire unifiée). À mesurer sur le poste avant
de retenir cette option.

### 3.3 Option C — Ollama Cloud : **non disponible**

Ollama Cloud (`https://ollama.com`, clé `OLLAMA_API_KEY`) sert des LLM
génératifs via `/api/chat` et `/v1/chat/completions`. Ses pages ne mentionnent
pas `/v1/systemone`, et les modèles System 1 n'ont pas de tag `:cloud`. À
réévaluer si Ollama ajoute ce service.

### 3.4 Option D — Ollama sur une machine cloud dédiée

Faire tourner Ollama et un modèle System 1 ouvert (Clef, Nimble) sur une
machine GPU louée. Conforme au choix « cloud » et sans dépendance à une API
propriétaire, mais : coût fixe de la machine, exploitation à sa charge, et les
limites de contexte du modèle choisi restent valables. Pertinent seulement si
Jev ne convient pas (calibration FR insuffisante, contrainte de souveraineté).
Non évalué.

### 3.5 Option E — Émuler System 1 avec un LLM génératif

Demander à un LLM de répondre par une option unique et lire les **log-probabilités**
des tokens d'option pour reconstituer une distribution. Possible seulement chez
un fournisseur qui expose les `logprobs` : la compatibilité OpenAI d'Ollama
**ne les prend pas en charge**. Calibration non garantie (le LLM n'a pas été
entraîné à cela), coût et latence supérieurs. Option de dernier recours, non
retenue.

### 3.6 Autres serveurs

La doc Pydantic AI mentionne d'autres modèles servis par la même API (CLM,
Laya), sans préciser leur hébergeur. Non vérifié.

### 3.7 Synthèse

| Option | Cloud | Contexte pour une section | Coût | Usage dans `bookctl` |
|---|---|---|---|---|
| A — Jev | oui | oui (32k) | très faible | **exécution et calibration** |
| B — Ollama local | non | non (Tev1, Nimble) / oui (Clef) | matériel | **expérimentation sur le poste de développement** |
| C — Ollama Cloud | — | — | — | indisponible |
| D — Ollama sur machine cloud | oui | selon modèle | fixe | repli si A ne convient pas |
| E — Émulation par logprobs | oui | oui | moyen | non retenue |

---

## 4. Le point français

### 4.1 Faits

- Les modèles ouverts sont presque tous des fine-tunes de Qwen, une famille
  multilingue qui comprend bien le français.
- TypeSafe indique que Jev est surtout entraîné en anglais et que les autres
  langues sont moins bien traitées.
- Un modèle communautaire, `iapp/openthai-systemone` (0.8B), revendique en thaï
  un score supérieur à Nimble 9B : indice qu'un petit System 1 spécialisé sur une
  langue peut battre un modèle plus gros non spécialisé (chiffre auto-déclaré).

### 4.2 Conséquence

**Comprendre le français ≠ être calibré sur des jugements éditoriaux
français.** La compétence « décider avec des probabilités fiables » est
entraînée sur des décisions surtout anglophones. La calibration sur les motifs
français (`specs/05-dataset-calibration.md`) doit être **mesurée** ; c'est
l'objet de la boucle 1.

### 4.3 Stratégie

1. **Mesurer** : Jev (et, sur le poste, un modèle local) sur un premier lot
   d'exemples étiquetés : Brier, routage, taux d'escalade.
2. **Optimiser les formulations** (boucle 1) : une question mieux formulée peut
   suffire à rendre les probabilités exploitables.
3. **Si cela ne suffit pas** : fine-tuner un modèle ouvert (Tev1 fournit ses
   scripts d'entraînement sous MIT) sur un dataset de décisions éditoriales
   françaises, et le servir selon l'option D. Effort élevé.

---

## 5. Benchmarks publiés

Repris des pages d'origine, non reproduits.

**Latence** (page Clef, matériel non précisé) :

| | Clef | Clef-flash | Jev |
|---|---|---|---|
| Médiane (ms) | 209,3 | 38,8 | 524,1 |
| p95 (ms) | 238,6 | 122,4 | 536,0 |

**Précision** (page Tev1, run Bespoke Labs, 13 jeux publics, 3 880 décisions,
anglais) :

| Modèle | Précision moyenne |
|---|---|
| Jev 1.13 | 76,0 % |
| Nimble 9B | 75,7 % |
| Tev1 4B | 73,3 % |
| Tev1 0.8B | 63,5 % |

Ces chiffres mesurent la **précision**, pas la **calibration**, et en anglais.
Ils ne disent rien de la qualité du routage sur des jugements éditoriaux
français.

---

## 6. Snippets

### 6.1 Jev avec le SDK

```python
# pip install typesafe-sdk  — clé dans TYPESAFE_API_KEY (~/.env)
from typesafe_sdk import Choice, Noul, Score, TypeSafeClient

questions = {
    "ternaire": Noul(instructions="Le passage contient-il un ternaire creux ?"),
    "tics": Score(instructions="Densité de tics stylistiques ?",
                  criteria=["Aucun", "Faible", "Modéré", "Élevé"]),
}
with TypeSafeClient() as client:
    result = client.system_one(state="…", questions=questions)
    p = result.nouls["ternaire"].noul            # probabilité ; pas de confidence
    s = result.scores["tics"]                     # .score, .probabilities, .confidence
```

### 6.2 Ollama local (poste de développement)

```bash
# Ollama ≥ 0.35 (≥ 0.35.1 pour Clef)
ollama pull nimble
curl http://localhost:11434/v1/systemone -d '{
  "model": "nimble",
  "state": "Cette section, il convient de le souligner, est non seulement claire mais aussi précise.",
  "questions": {
    "ternaire": {"type": "noul", "instructions": "Le passage contient-il un ternaire creux ?"}
  }
}'
```

Dans `bookctl`, ces appels passent par `System1Client`, qui lit fournisseur,
URL, clé et modèle dans `params.yml` (`specs/04-primitives-system1.md` § 2).

---

## 7. Limites à garder en tête

- **Calibration française** non démontrée (§ 4).
- **Pas de raisonnement** : System 1 détecte et juge ; il n'explique ni ne
  réécrit. La correction revient au Correcteur LLM.
- **`confidence` ≠ justesse**, et `noul` n'a pas de `confidence`.
- **Seuils propres à chaque modèle** : changer de modèle impose de recalibrer.
- **Écosystème jeune** : modèles et SDK évoluent vite ; épingler les versions et
  consigner la version renvoyée (`model` de la réponse) dans le journal d'audit.

---

## 8. Sources

- docs.typesafe.ai : `api.md`, `models.md`, `confidence.md`,
  `primitives/noul.md`, `sdk/python.md` (consultés le 9 octobre 2026).
- ollama.com/library : `tev1`, `nimble`, `clef` (idem).
- docs.ollama.com : `cloud`, `api/openai-compatibility` (idem).
- pydantic.dev : documentation « System One » de Pydantic AI (idem).
- **Non vérifié** : matériel nécessaire en local, chiffres communautaires
  (openthai-systemone), hébergeurs de CLM et Laya, licence des poids de Tev1.
