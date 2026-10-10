# Spike B5 — Ollama Cloud via DSPy

## Question

Comment `bookctl` doit-il construire le `dspy.LM` d'un modèle Ollama Cloud
déclaré dans `params.yml` ? Trois points sont non vérifiés dans
`doc-tools/llm-cloud.md` :

1. **Noms de modèles** : l'API accepte-t-elle les noms du stock tels quels
   (`glm-5.3-flash:cloud`, `gemma4:31b-cloud`), ou faut-il le nom listé par
   `/api/tags` (sans suffixe `cloud`) ?
2. **Voie d'accès DSPy** : compatibilité OpenAI (`openai/<nom>` sur
   `https://ollama.com/v1`) ou voie native (`ollama_chat/<nom>` sur
   `https://ollama.com`) ? La clé est-elle bien transmise par les deux ?
3. **`think`** : le niveau de raisonnement est-il transmis, en API native
   (`"think"`) et par DSPy (`reasoning_effort`) ?

## Protocole

Pour chaque modèle `provider: ollama` du stock (`params.sample.yml` du dépôt) :

| Étape | Appel | Mesure |
|---|---|---|
| 1. Catalogue | `GET <OLLAMA_CLOUD_URL>/tags` | liste des noms disponibles ; présence de chaque variante de nom |
| 2. Natif | `POST <OLLAMA_CLOUD_URL>/chat` pour chaque variante de nom | statut HTTP, réponse correcte |
| 3. Natif + `think` | idem avec `"think": <niveau>` (modèles qui déclarent `think`) | présence de `message.thinking` |
| 4. DSPy OpenAI | `dspy.LM("openai/<nom>", api_base=<openai_base_url>)` + `dspy.Predict` | succès, réponse correcte, latence, tokens |
| 5. DSPy OpenAI + `think` | idem avec `reasoning_effort=<niveau>` | succès, tokens de raisonnement rapportés |
| 6. DSPy natif | `dspy.LM("ollama_chat/<nom>", api_base=<ollama_chat_base_url>)` | succès (clé transmise ?), réponse correcte |

La question posée est fixe et vérifiable : « Quelle est la capitale de la
Nouvelle-Calédonie ? ». Une réponse est **correcte** si elle contient
`Nouméa` (paramètre `expected_substring`).

## Critère de décision

- **Noms** : on retient la forme de nom qui réussit pour **tous** les modèles.
- **Voie DSPy** : on retient la voie qui réussit pour tous les modèles avec une
  réponse correcte ; à égalité, la compatibilité OpenAI (documentée par Ollama
  pour le cloud).
- **`think`** : transmis si `message.thinking` est non vide en natif, et si la
  voie DSPy retenue accepte le paramètre sans erreur.

La décision est reportée dans `doc-tools/llm-cloud.md` et, si le format change,
dans `params.sample.yml`.

## Lancer

```bash
cd spikes/b5_ollama_dspy
uv sync
uv run pytest                 # tests des fonctions pures, sans réseau
uv run python b5_spike.py     # l'essai (appels réseau)
```

Prérequis dans `~/.env` : `OLLAMA_CLOUD_URL` (API native, ex.
`https://ollama.com/api`) et `OLLAMA_API_KEY`.

Résultats : `out/b5_<horodatage>.json` (brut) et `out/b5_<horodatage>.md`
(synthèse), non versionnés.
