# Note technique — LLM dans le cloud (Ollama Cloud) via DSPy

> **Objet :** comment `bookctl` appelle les LLM génératifs de ses agents.
> **Fournisseur principal :** Ollama Cloud (`https://ollama.com`). Autres fournisseurs possibles par `params.yml` (Anthropic, OpenAI, xAI).
> **Usage dans `bookctl` :** agents LLM (`specs/02-agents.md` § 6) et `reflection_lm` des boucles DSPy (`specs/06-boucles-dspy.md`).
> **Consulté :** 9 octobre 2026 — docs.ollama.com (`cloud`, `api/openai-compatibility`).

---

## 1. Principe

- **Aucun LLM génératif local.** Les modèles sont appelés dans le cloud.
- Les modèles sont **déclarés** dans `params.yml` (stock + profils), jamais
  codés en dur.
- Les **secrets** restent dans `~/.env` ; `params.yml` ne contient que les
  **noms** des variables d'environnement.
- Chaque agent est un module DSPy ; son modèle est un `dspy.LM` construit à
  partir de `params.yml`.

---

## 2. Ollama Cloud

| Élément | Valeur |
|---|---|
| API native | `https://ollama.com/api/chat` (`"stream": false` pour une réponse unique) |
| API compatible OpenAI | `https://ollama.com/v1` : `/chat/completions`, `/completions`, `/models`, `/embeddings`, `/responses` (sans état) |
| Liste des modèles | `GET https://ollama.com/api/tags` |
| Authentification | `Authorization: Bearer $OLLAMA_API_KEY` ; clé créée sur ollama.com/settings/keys |
| Noms de modèles | via l'API, le nom exact listé par `/api/tags` ; le suffixe `:cloud` est la forme utilisée par l'app et le CLI Ollama |
| Non pris en charge (compat OpenAI) | `tool_choice`, `logit_bias`, `n`, `user` ; **pas de `logprobs`** |
| Modèles retirés | selon un calendrier visible dans les réglages d'usage : surveiller et changer de modèle avant la date |
| Tarifs et quotas | ollama.com/pricing, ollama.com/settings/usage |

**À vérifier au premier branchement** : que les noms du stock (`glm-5.3-flash:cloud`…)
sont acceptés tels quels par l'API, ou qu'il faut le nom sans suffixe listé par
`/api/tags`. Un test d'intégration appelle `/api/tags` et vérifie que chaque
modèle du stock y figure.

---

## 3. Déclaration dans `params.yml`

Format repris du fichier de configuration LLM utilisé par ailleurs (stock de
modèles + profils + profil actif) :

```yaml
models:
  glm-flash:
    provider: ollama
    name: glm-5.3-flash:cloud
    url: OLLAMA_CLOUD_URL        # variable d'environnement → ex. https://ollama.com/v1
    api_key: OLLAMA_API_KEY      # variable d'environnement → la clé
    timeout: 720
    think: high                  # optionnel : low | high | max
    price: { input_per_mtok: 0.0, output_per_mtok: 0.0 }   # pour l'estimation des coûts

  deepseek-pro:
    provider: ollama
    name: deepseek-v4-pro:cloud
    url: OLLAMA_CLOUD_URL
    api_key: OLLAMA_API_KEY
    timeout: 120

.profils:
  standard: &standard
    llm:
      plan: deepseek-pro
      write: glm-flash
      integrate: deepseek-pro
      rewrite: mistral-large
      reflect: deepseek-pro

llm_config: *standard
```

Règles :

- `url` et `api_key` sont des **noms** de variables d'environnement, lues dans
  `~/.env` au moment de l'appel.
- Les rôles `write`, `rewrite` et `reflect` doivent désigner des modèles
  distincts (`specs/02-agents.md` § 11) ; sinon exception au chargement.
- `price` (optionnel) sert à afficher une estimation de coût ; absent → le coût
  est affiché comme inconnu, jamais comme nul.

---

## 4. Construction du `dspy.LM`

Voie retenue : la **compatibilité OpenAI** d'Ollama Cloud, documentée par
Ollama pour le cloud.

```python
import os
import dspy
from dotenv import load_dotenv

def build_lm(spec: ModelSpec) -> dspy.LM:
    """Construit le dspy.LM d'un modèle du stock.

    Raises:
        ConfigError: variable d'environnement absente ou fournisseur inconnu.
    """
    load_dotenv(os.path.expanduser("~/.env"), override=True)
    base_url = require_env(spec.url)          # exception si absente
    api_key = require_env(spec.api_key)
    match spec.provider:
        case "ollama":
            return dspy.LM(f"openai/{spec.name}", api_base=base_url, api_key=api_key,
                           timeout=spec.timeout)
        case "anthropic":
            return dspy.LM(f"anthropic/{spec.name}", api_key=api_key, timeout=spec.timeout)
        case "openai":
            return dspy.LM(f"openai/{spec.name}", api_base=base_url, api_key=api_key,
                           timeout=spec.timeout)
        case _:
            raise ConfigError(f"Fournisseur inconnu : {spec.provider}")
```

- `OLLAMA_CLOUD_URL` vaut alors `https://ollama.com/v1`.
- Alternative : préfixe natif `ollama_chat/<nom>` avec `api_base=https://ollama.com`.
  Le passage de la clé en en-tête `Authorization` par cette voie est **à
  vérifier** sur la version de DSPy épinglée.
- Le paramètre `think` (raisonnement) se transmet différemment selon la voie
  (`think` en API native, `reasoning_effort` en compatibilité OpenAI) : **à
  vérifier** modèle par modèle, puis figer dans `build_lm`.

---

## 5. Journalisation et coûts

Chaque appel est journalisé localement (`specs/03-cli.md` § 9) : modèle, nom
exact envoyé, tokens d'entrée et de sortie (champ `usage`), durée, coût estimé.
DSPy expose l'historique des appels (`lm.history`) ; `bookctl` en extrait ces
champs après chaque commande.

---

## 6. Fail-fast

| Situation | Comportement |
|---|---|
| Variable d'environnement absente | exception au chargement (code `5`) |
| 401 / 403 | exception immédiate |
| 429, 5xx | nouvelles tentatives bornées avec backoff (`params.yml`), puis exception |
| Modèle absent de `/api/tags` | exception au test d'intégration, et à l'appel |
| Réponse non analysable par l'adaptateur DSPy | exception, sortie brute consignée dans l'audit |

Aucun repli vers un autre modèle n'est fait automatiquement : changer de modèle
est une décision de l'utilisateur dans `params.yml`.

---

## 7. Sources

- docs.ollama.com/cloud ; docs.ollama.com/api/openai-compatibility (consultés le
  9 octobre 2026).
- **Non vérifié** : acceptation du suffixe `:cloud` par l'API, transmission de
  `think`, clé via le préfixe `ollama_chat/`.
