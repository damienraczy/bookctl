# Spike S1 — Temps de réaction des modèles System 1 en Ollama local

## Question

Sur le poste de développement, les modèles System 1 servis par Ollama local
(`/v1/systemone`, modèles listés dans `models` : Tev1 4B, Nimble 9B) répondent-ils assez vite pour servir de juge System 1 pendant le
développement, et comment son temps de réponse varie-t-il avec :

1. le **chargement** du modèle (premier appel à froid, puis modèle chargé) ;
2. la **primitive** (`noul`, `score`, `choice`) ;
3. la **taille du `state`**, jusqu'au-delà du contexte du modèle (`num_ctx` : 2 048 pour Tev1, 8 192 pour Nimble) ;
4. le **nombre de questions** posées sur le même `state` ;
5. le **cache** d'Ollama (même `state` répété ou `state` toujours différent) ?

## Protocole

Paramètres dans `params.yml` ; textes jugés dans `state/` (texte générique,
aucune donnée personnelle).

Les modèles sont mesurés l'un après l'autre ; chacun est déchargé après sa
série, pour ne pas peser sur la mémoire du suivant.

| Étape | Mesure |
|---|---|
| Froid | décharger le modèle (`keep_alive: 0`), puis un appel ; répété `cold.repeats` fois |
| Chaud | pour chaque configuration de `configs` : un appel de mise en route non compté, puis `warm.repeats` appels |

Chaque appel mesure la durée côté client (de l'envoi à la réponse complète),
le statut HTTP, `usage.input_tokens` et `prompt_eval_cached_count`. Sans cache
demandé, chaque `state` est préfixé d'une étiquette unique sur tout l'essai, ce qui empêche la
réutilisation du préfixe mis en cache. Un appel en échec est enregistré avec son
erreur, jamais masqué.

Synthèse par configuration : médiane, p95, min, max.

## Critère de décision

- **Utilisable en développement** : médiane à chaud ≤ 1 s pour un `state` de
  taille de section (`moyen`) et 4 questions.
- **Contexte** : ce qui se passe au-delà du contexte du modèle (erreur, troncature
  silencieuse) est reporté dans `doc-tools/system-one.md` ; une troncature
  silencieuse impose à `bookctl` de vérifier la taille du `state` avant l'appel.

## Lancer

```bash
cd spikes/s1_system1_local
uv sync
uv run pytest                 # tests des fonctions pures, sans réseau
uv run python s1_latence.py   # l'essai (Ollama local lancé, modèles tirés)
```

Prérequis dans `~/.env` : `OLLAMA_LOCAL_URL` (ex. `http://localhost:11434`).

Résultats : `out/s1_<modèle>_<horodatage>.json` (brut) et
`out/s1_<modèle>_<horodatage>.md` (synthèse), non versionnés.
