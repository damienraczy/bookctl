# Note technique — LLM dans le cloud (Ollama Cloud) via DSPy

> **Objet :** comment `bookctl` appelle les LLM génératifs de ses agents.
> **Fournisseur principal :** Ollama Cloud (`https://ollama.com`). Autres fournisseurs possibles par `params.yml` (Anthropic, OpenAI, xAI).
> **Usage dans `bookctl` :** agents LLM (`specs/02-agents.md` § 6) et `reflection_lm` des boucles DSPy (`specs/06-boucles-dspy.md`).
> **Consulté :** 10 octobre 2026 — docs.ollama.com (`cloud`, `api/openai-compatibility`), fiche du modèle Gemma 4 (ai.google.dev), docs.z.ai (thinking mode), api-docs.deepseek.com (thinking mode). Mesures : essai `spikes/b5_ollama_dspy`.

---

## 1. Principe

- **Aucun LLM génératif local.** Les modèles sont appelés dans le cloud.
- Fournisseurs, modèles, réglages et profils sont **déclarés par l'utilisateur**
  dans son `params.yml`, jamais codés en dur. `params.sample.yml` n'en donne que
  des exemples.
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
| Description d'un modèle | `POST https://ollama.com/api/show` `{"model": "<nom>"}` : capacités (`thinking`, `tools`, `vision`…), valeurs de `think` acceptées et valeur par défaut, longueur de contexte ; `404` si le modèle n'existe pas |
| Liste des modèles | `GET https://ollama.com/api/tags` : **incomplète**, un modèle peut y manquer et répondre quand même |
| Authentification | `Authorization: Bearer $OLLAMA_API_KEY` ; clé créée sur ollama.com/settings/keys |
| Noms de modèles | acceptés avec ou sans suffixe `cloud` (`glm-5.3-flash:cloud` ou `glm-5.3-flash`) |
| Champs acceptés (compat. OpenAI) | `temperature`, `top_p`, `max_tokens`, `seed`, `stop`, `frequency_penalty`, `presence_penalty`, `response_format`, `tools`, `reasoning_effort` |
| Non pris en charge (compat. OpenAI) | `tool_choice`, `logit_bias`, `n`, `user`, `top_k` (non documenté) ; **pas de `logprobs`** |
| Modèles retirés | selon un calendrier visible dans les réglages d'usage : surveiller et changer de modèle avant la date |
| Tarifs et quotas | ollama.com/pricing, ollama.com/settings/usage |

---

## 3. Déclaration dans `params.yml`

Exemple (les noms logiques, modèles et profils sont libres) :

```yaml
models:
  glm-5.3-flash:
    provider: ollama
    name: glm-5.3-flash:cloud
    url: OLLAMA_CLOUD_URL        # variable d'environnement → API native, https://ollama.com/api
    api_key: OLLAMA_API_KEY      # variable d'environnement → la clé
    timeout: 720
    think: high                  # valeur acceptée par le modèle (§ 5)
    price: { input_per_mtok: 0.0, output_per_mtok: 0.0 }   # Ollama Cloud : abonnement → 0

  gemma4:
    provider: ollama
    name: gemma4:31b-cloud
    url: OLLAMA_CLOUD_URL
    api_key: OLLAMA_API_KEY
    timeout: 120
    think: false
    options: { temperature: 1.0, top_p: 0.95 }             # réglages de génération (§ 6)

.profils:
  standard: &standard
    llm:
      plan: deepseek-v4-pro
      write: glm-5.3-flash
      integrate: deepseek-v4-pro
      rewrite: gemma4
      audit: deepseek-v4-pro
      reflect: deepseek-v4-pro

llm_config: *standard
```

Règles :

- `url` et `api_key` sont des **noms** de variables d'environnement, lues dans
  `~/.env` au moment de l'appel.
- Pour `provider: ollama`, `url` désigne l'**API native** (chemin `/api`) :
  `bookctl` y appelle `/show`, et appelle la compatibilité OpenAI sur le même
  hôte au chemin `/v1` (convention d'Ollama). Une `url` dont le chemin n'est pas
  `/api` → exception au chargement.
- `write` et `rewrite` sont distincts ; `audit` et `reflect` sont chacun
  distincts de `write` et de `rewrite` (`specs/02-agents.md` § 11) ; sinon
  exception au chargement.
- `think` est **obligatoire** pour un modèle qui déclare la capacité `thinking`,
  et interdit pour un modèle qui ne la déclare pas (§ 5).
- `options` (optionnel) ne contient que des champs transmis par la voie
  retenue : `temperature`, `top_p`, `max_tokens`, `seed`. Tout autre champ →
  exception au chargement.
- `price` (optionnel, dollars par million de tokens) sert à estimer les coûts.
  Modèles Ollama Cloud : `0` (abonnement, pas de facturation au token). Jev :
  0,042 $ en entrée, sortie gratuite. Autres fournisseurs : à renseigner. Absent
  → coût affiché comme inconnu, jamais comme nul.

---

## 4. Construction du `dspy.LM`

Voie retenue : la **compatibilité OpenAI** d'Ollama Cloud (`openai/<nom>` sur
`https://ollama.com/v1`). Elle fonctionne pour tous les modèles mesurés. La
voie native de LiteLLM (`ollama_chat/<nom>` sur `https://ollama.com`) échoue
(`404`) et n'est pas utilisée.

```python
import os
import dspy
from dotenv import load_dotenv

def build_lm(spec: ModelSpec) -> dspy.LM:
    """Construit le dspy.LM d'un modèle déclaré dans params.yml.

    Raises:
        ConfigError: variable d'environnement absente, url Ollama hors `/api`
            ou fournisseur inconnu.
    """
    load_dotenv(os.path.expanduser("~/.env"), override=True)
    base_url = require_env(spec.url)          # exception si absente
    api_key = require_env(spec.api_key)
    match spec.provider:
        case "ollama":
            extra = {"reasoning_effort": reasoning_effort(spec.think)} if spec.think is not None else {}
            return dspy.LM(f"openai/{spec.name}", api_base=openai_base(base_url), api_key=api_key,
                           timeout=spec.timeout, **extra, **spec.options)
        case "anthropic":
            return dspy.LM(f"anthropic/{spec.name}", api_key=api_key, timeout=spec.timeout,
                           **spec.options)
        case "openai":
            return dspy.LM(f"openai/{spec.name}", api_base=base_url, api_key=api_key,
                           timeout=spec.timeout, **spec.options)
        case _:
            raise ConfigError(f"Fournisseur inconnu : {spec.provider}")
```

---

## 5. Raisonnement (`think`)

### 5.1 Transmission

| Voie | Réglage | Raisonnement renvoyé dans |
|---|---|---|
| Native `/api/chat` | `"think": false \| true \| "low" \| "high" \| "max"` | `message.thinking` |
| Compat. OpenAI `/v1/chat/completions` | `"reasoning_effort": "none" \| "low" \| "high" \| "max"` | `choices[0].message.reasoning` |
| DSPy 3.4 (`openai/<nom>`) | `dspy.LM(..., reasoning_effort=...)` | `lm.history[-1]["outputs"][0]["reasoning_content"]` ; **absent** de la `Prediction` |

Correspondance appliquée par `build_lm` (`reasoning_effort(think)`) : `false` →
`"none"` ; un niveau → le même niveau ; `true` → `"high"` (un modèle à réglage
binaire traite tout niveau comme `true`).

### 5.2 Comportement d'Ollama

- **Sans réglage, le modèle applique son défaut**, qui varie d'un modèle à
  l'autre (§ 5.3). Ne rien déclarer ne coupe pas le raisonnement.
- **Une valeur non acceptée par le modèle est ignorée sans erreur** : le modèle
  repasse à son défaut. Un modèle sans capacité `thinking` ignore le réglage.
- D'où la règle de `bookctl` : `think` explicite, vérifié contre `/api/show`
  avant le premier appel (`specs/03-cli.md`, [S03-26]).

### 5.3 Modèles mesurés

| Modèle | Valeurs (`/api/show`) | Défaut Ollama | Particularités (source) |
|---|---|---|---|
| `deepseek-v4-pro` | `false`, `low`, `high`, `max` | `low` | défaut `high` sur l'API DeepSeek ; avec raisonnement, `temperature`, `presence_penalty` et `frequency_penalty` sont **sans effet** et `top_p` est relevé à au moins 0,95 (doc DeepSeek) |
| `deepseek-v4-flash` | `false`, `low`, `high`, `max` | `high` | idem |
| `glm-5.3-flash` | `low`, `high`, `max` | `max` | raisonnement **forcé**, impossible à couper (doc Z.ai). Avec `false` / `none`, le modèle raisonne quand même et le raisonnement passe dans la réponse : ne jamais déclarer `false`. Les niveaux sont propres à Ollama (Z.ai n'a que `enabled` / `disabled`) ; mesurés croissants de `low` à `max` |
| `gemma4` (31B) | `false`, `true` | `false` | réglage **binaire** (fiche Gemma 4) ; à travers Ollama, seul le paramètre active le raisonnement (le marqueur `<|think|>` écrit dans le message système est sans effet) ; réglages recommandés : `temperature` 1,0, `top_p` 0,95, `top_k` 64 ; contexte 256K |
| `mistral-large-3` | — | — | pas de capacité `thinking` |

Conséquences :

- **Reproductibilité.** Sur DeepSeek avec raisonnement, fixer `temperature` ne
  rend pas les sorties reproductibles : la longueur du raisonnement varie du
  simple au triple d'un appel à l'autre pour la même demande.
- **Budget.** Un niveau ne borne pas le nombre de tokens de raisonnement ; seul
  `max_tokens` le fait.
- **Historique.** Hors appels d'outils, un tour suivant ne renvoie que la
  réponse finale, sans le raisonnement (Gemma 4 et DeepSeek le recommandent ;
  DeepSeek ignore un raisonnement renvoyé).

---

## 6. Réglages de génération (`options`)

Les réglages recommandés par un fournisseur se déclarent dans `options` du
modèle. Limites de la voie retenue :

- `top_k` n'est pas transmis par la compatibilité OpenAI : il ne peut pas être
  déclaré (la recommandation `top_k: 64` de Gemma 4 ne s'applique pas).
- Un réglage accepté par l'API peut être ignoré par le modèle (DeepSeek avec
  raisonnement, § 5.3) : `bookctl` le transmet tel quel, la doc du modèle fait
  foi.

---

## 7. Journalisation et coûts

Chaque appel est journalisé localement (`specs/03-cli.md` § 9) : modèle, nom
exact envoyé, réglages (`think`, `options`), tokens d'entrée et de sortie (champ
`usage`), raisonnement renvoyé, durée, coût estimé. DSPy expose l'historique
des appels (`lm.history`) ; `bookctl` en extrait ces champs après chaque
commande, le raisonnement compris (§ 5.1).

---

## 8. Fail-fast

| Situation | Comportement |
|---|---|
| Variable d'environnement absente | exception au chargement (code `5`) |
| Modèle inconnu (`/api/show` → `404`) | exception avant le premier appel (code `5`) |
| `think` absent pour un modèle qui raisonne, présent pour un modèle qui ne raisonne pas, ou valeur hors de celles déclarées par `/api/show` | exception avant le premier appel (code `5`) |
| Champ d'`options` non transmis par la voie retenue | exception au chargement (code `5`) |
| 401 / 403 | exception immédiate |
| 429, 5xx | nouvelles tentatives bornées avec backoff (`params.yml`), puis exception |
| Réponse non analysable par l'adaptateur DSPy | exception, sortie brute consignée dans l'audit |

Aucun repli vers un autre modèle n'est fait automatiquement : changer de modèle
est une décision de l'utilisateur dans `params.yml`.

---

## 9. Sources

- docs.ollama.com/cloud ; docs.ollama.com/api/openai-compatibility (consultés le
  10 octobre 2026).
- Fiche du modèle Gemma 4 : ai.google.dev/gemma/docs/core/model_card_4.
- Z.ai, thinking mode : docs.z.ai/guides/capabilities/thinking-mode.
- DeepSeek, thinking mode : api-docs.deepseek.com/guides/thinking_mode.
- Mesures : `spikes/b5_ollama_dspy` (`b5_spike.py`, `b5_think.py`), 10 octobre
  2026, deux passages par réglage : les longueurs de raisonnement sont
  indicatives.
