"""Spike B5 : appeler les modèles Ollama Cloud depuis DSPy.

Mesure, pour chaque modèle Ollama du stock de ``params.sample.yml`` :
la forme de nom acceptée par l'API, la voie d'accès DSPy qui fonctionne
(compatibilité OpenAI ou voie native ``ollama_chat/``) et la transmission du
niveau de raisonnement (``think``). Voir ``README.md`` pour la question, le
protocole et le critère de décision.

Deux sortes d'échecs sont distinguées :

* une erreur de **configuration** (paramètre manquant, variable
  d'environnement absente, prompt incohérent) lève immédiatement une
  exception : l'essai ne peut pas avoir lieu ;
* l'échec d'un **appel testé** (HTTP 404, erreur d'authentification, réponse
  inattendue) est le résultat mesuré : il est enregistré dans le rapport avec
  son type et son message, jamais masqué.
"""

from __future__ import annotations

import json
import os
import re
import string
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

SPIKE_DIR = Path(__file__).resolve().parent
PARAMS_FILE = SPIKE_DIR / "params.yml"
ERROR_MESSAGE_MAX_CHARS = 500


class ConfigError(Exception):
    """Configuration du spike invalide ou incomplète."""


@dataclass(frozen=True)
class ModelSpec:
    """Un modèle du stock de ``params.sample.yml``.

    Attributes:
        key: nom logique du modèle dans le stock.
        name: identifiant déclaré pour le fournisseur.
        think: niveau de raisonnement déclaré (``low``, ``high``, ``max``) ou None.
    """

    key: str
    name: str
    think: str | None


@dataclass
class ProbeResult:
    """Résultat d'un appel testé.

    Attributes:
        step: identifiant de l'étape du protocole (``native``, ``dspy_openai``…).
        model_key: nom logique du modèle.
        name: identifiant envoyé à l'API.
        ok: l'appel a abouti sans erreur.
        correct: la réponse contient la sous-chaîne attendue (None si pas de réponse).
        latency_s: durée de l'appel en secondes.
        answer: réponse textuelle (tronquée).
        http_status: statut HTTP pour les appels natifs.
        thinking_present: un raisonnement a été renvoyé (None si non mesuré).
        usage: comptage de tokens rapporté par l'API, si disponible.
        error: type et message de l'erreur, si l'appel a échoué.
    """

    step: str
    model_key: str
    name: str
    ok: bool = False
    correct: bool | None = None
    latency_s: float | None = None
    answer: str | None = None
    http_status: int | None = None
    thinking_present: bool | None = None
    usage: dict[str, Any] | None = None
    error: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


# --------------------------------------------------------------------------
# Fonctions pures (testées sans réseau)
# --------------------------------------------------------------------------


def load_yaml(path: Path) -> dict[str, Any]:
    """Charge un fichier YAML qui doit contenir un dictionnaire.

    Args:
        path: chemin du fichier.

    Returns:
        Le contenu du fichier.

    Raises:
        ConfigError: fichier absent ou contenu qui n'est pas un dictionnaire.
    """
    if not path.is_file():
        raise ConfigError(f"Fichier introuvable : {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ConfigError(f"{path} doit contenir un dictionnaire YAML")
    return data


def require_key(mapping: dict[str, Any], dotted: str) -> Any:
    """Lit une clé obligatoire, éventuellement imbriquée (``a.b.c``).

    Args:
        mapping: dictionnaire source.
        dotted: chemin de la clé, segments séparés par des points.

    Returns:
        La valeur trouvée.

    Raises:
        ConfigError: un segment du chemin est absent.
    """
    current: Any = mapping
    for part in dotted.split("."):
        if not isinstance(current, dict) or part not in current:
            raise ConfigError(f"Paramètre obligatoire absent : {dotted}")
        current = current[part]
    return current


def require_env(var_name: str) -> str:
    """Lit une variable d'environnement obligatoire.

    Args:
        var_name: nom de la variable.

    Returns:
        Sa valeur, non vide.

    Raises:
        ConfigError: variable absente ou vide.
    """
    value = os.environ.get(var_name)
    if not value:
        raise ConfigError(f"Variable d'environnement absente ou vide : {var_name}")
    return value


def ollama_models(stock: dict[str, Any]) -> list[ModelSpec]:
    """Extrait les modèles ``provider: ollama`` du stock.

    Args:
        stock: contenu de ``params.sample.yml``.

    Returns:
        Les modèles Ollama, dans l'ordre du fichier.

    Raises:
        ConfigError: stock absent, modèle sans ``name``, ou aucun modèle Ollama.
    """
    models = require_key(stock, "models")
    if not isinstance(models, dict):
        raise ConfigError("`models` doit être un dictionnaire")
    specs = []
    for key, spec in models.items():
        if not isinstance(spec, dict):
            raise ConfigError(f"Modèle mal formé : {key}")
        if spec.get("provider") != "ollama":
            continue
        if "name" not in spec:
            raise ConfigError(f"Modèle sans `name` : {key}")
        specs.append(ModelSpec(key=key, name=str(spec["name"]), think=spec.get("think")))
    if not specs:
        raise ConfigError("Aucun modèle `provider: ollama` dans le stock")
    return specs


def name_variants(name: str, suffixes: list[str]) -> list[str]:
    """Construit les variantes de nom à tester : déclaré, puis sans suffixe cloud.

    Args:
        name: identifiant déclaré (ex. ``gemma4:31b-cloud``).
        suffixes: suffixes à retirer (ex. ``[":cloud", "-cloud"]``).

    Returns:
        Le nom déclaré, suivi du nom sans suffixe s'il diffère. Sans doublon.
    """
    variants = [name]
    for suffix in suffixes:
        if name.endswith(suffix):
            stripped = name[: -len(suffix)]
            if stripped and stripped not in variants:
                variants.append(stripped)
            break
    return variants


def template_variables(template: str) -> set[str]:
    """Liste les variables ``{nom}`` d'un gabarit.

    Args:
        template: texte du gabarit.

    Returns:
        Les noms de variables présents.
    """
    return {field_name for _, field_name, _, _ in string.Formatter().parse(template) if field_name}


def render_prompt(template: str, variables: dict[str, str]) -> str:
    """Remplit un gabarit en vérifiant la cohérence des variables.

    Args:
        template: texte du gabarit, variables au format ``{nom}``.
        variables: valeurs fournies.

    Returns:
        Le texte rempli.

    Raises:
        ConfigError: variable requise non fournie, ou variable fournie non utilisée.
    """
    required = template_variables(template)
    provided = set(variables)
    missing, unused = required - provided, provided - required
    if missing or unused:
        raise ConfigError(
            f"Variables incohérentes : manquantes={sorted(missing)}, en trop={sorted(unused)}"
        )
    return template.format(**variables)


def load_prompt(prompt_dir: Path, prompt_name: str, variables: dict[str, str]) -> tuple[str, str]:
    """Charge le couple de prompts ``<nom>_system.md`` / ``<nom>_user.md``.

    Args:
        prompt_dir: dossier des prompts.
        prompt_name: libellé commun aux deux fichiers.
        variables: variables injectées dans les deux gabarits (chacune doit
            servir dans au moins l'un des deux).

    Returns:
        Le texte système et le texte utilisateur.

    Raises:
        ConfigError: fichier absent ou variables incohérentes.
    """
    texts = {}
    for role in ("system", "user"):
        path = prompt_dir / f"{prompt_name}_{role}.md"
        if not path.is_file():
            raise ConfigError(f"Prompt introuvable : {path}")
        texts[role] = path.read_text(encoding="utf-8").strip()
    required = template_variables(texts["system"]) | template_variables(texts["user"])
    missing, unused = required - set(variables), set(variables) - required
    if missing or unused:
        raise ConfigError(
            f"Variables incohérentes : manquantes={sorted(missing)}, en trop={sorted(unused)}"
        )
    rendered = {
        role: render_prompt(text, {k: v for k, v in variables.items() if k in template_variables(text)})
        for role, text in texts.items()
    }
    return rendered["system"], rendered["user"]


def is_correct(answer: str | None, expected: str) -> bool | None:
    """Vérifie qu'une réponse contient la sous-chaîne attendue (casse ignorée).

    Args:
        answer: réponse du modèle, ou None si aucune.
        expected: sous-chaîne attendue.

    Returns:
        None sans réponse, sinon le résultat de la vérification.
    """
    if answer is None:
        return None
    return expected.casefold() in answer.casefold()


def describe_error(exc: BaseException) -> str:
    """Résume une exception pour le rapport (type + message tronqué).

    Args:
        exc: l'exception capturée.

    Returns:
        ``Type: message``, message tronqué et sans retours à la ligne.
    """
    message = re.sub(r"\s+", " ", str(exc)).strip()
    return f"{type(exc).__name__}: {message[:ERROR_MESSAGE_MAX_CHARS]}"


def summarize(results: list[ProbeResult], catalogue: list[str] | None) -> str:
    """Produit la synthèse Markdown des résultats.

    Args:
        results: résultats de tous les appels testés.
        catalogue: noms listés par ``/api/tags``, ou None si le catalogue a échoué.

    Returns:
        Le rapport Markdown.
    """
    lines = ["# Spike B5 — résultats", ""]
    lines.append(f"Catalogue `/api/tags` : {len(catalogue)} modèles." if catalogue is not None
                 else "Catalogue `/api/tags` : échec (voir JSON).")
    lines += ["", "| Étape | Modèle | Nom envoyé | Au catalogue | OK | Correct | Raisonnement | Latence (s) | Erreur |",
              "|---|---|---|---|---|---|---|---|---|"]
    for r in results:
        in_cat = "—" if catalogue is None else ("oui" if r.name in catalogue else "non")
        lat = "" if r.latency_s is None else f"{r.latency_s:.1f}"
        flag = lambda v: "—" if v is None else ("oui" if v else "non")  # noqa: E731
        err = (r.error or "").replace("|", "\\|")
        lines.append(f"| {r.step} | {r.model_key} | `{r.name}` | {in_cat} | {flag(r.ok)} | "
                     f"{flag(r.correct)} | {flag(r.thinking_present)} | {lat} | {err} |")
    lines += ["", "## Bilan par étape", "", "| Étape | Réussites correctes / appels |", "|---|---|"]
    for step in dict.fromkeys(r.step for r in results):
        subset = [r for r in results if r.step == step]
        good = sum(1 for r in subset if r.ok and r.correct)
        lines.append(f"| {step} | {good} / {len(subset)} |")
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------
# Appels réseau (mesurés)
# --------------------------------------------------------------------------


def fetch_catalogue(native_base: str, api_key: str, timeout: float) -> list[str]:
    """Liste les modèles disponibles via ``GET <native_base>/tags``.

    Args:
        native_base: URL de l'API native (ex. ``https://ollama.com/api``).
        api_key: clé Ollama.
        timeout: délai maximal en secondes.

    Returns:
        Les noms de modèles.

    Raises:
        httpx.HTTPError: échec de l'appel (traité par l'appelant comme un résultat).
    """
    import httpx

    response = httpx.get(f"{native_base.rstrip('/')}/tags",
                         headers={"Authorization": f"Bearer {api_key}"}, timeout=timeout)
    response.raise_for_status()
    return [m["name"] for m in response.json().get("models", [])]


def probe_native(model: ModelSpec, name: str, native_base: str, api_key: str,
                 system: str, user: str, probe: dict[str, Any], think: str | None) -> ProbeResult:
    """Appelle ``POST <native_base>/chat`` et mesure la réponse.

    Args:
        model: modèle testé.
        name: identifiant envoyé.
        native_base: URL de l'API native.
        api_key: clé Ollama.
        system: prompt système.
        user: prompt utilisateur.
        probe: paramètres ``probe`` du spike.
        think: niveau de raisonnement à demander, ou None.

    Returns:
        Le résultat de l'appel (succès ou échec enregistré).
    """
    import httpx

    result = ProbeResult(step="native_think" if think else "native", model_key=model.key, name=name)
    payload: dict[str, Any] = {
        "model": name,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "stream": False,
        "options": {"temperature": probe["temperature"], "num_predict": probe["max_tokens"]},
    }
    if think:
        payload["think"] = think
    start = time.monotonic()
    try:
        response = httpx.post(f"{native_base.rstrip('/')}/chat", json=payload,
                              headers={"Authorization": f"Bearer {api_key}"},
                              timeout=probe["http_timeout"])
        result.http_status = response.status_code
        response.raise_for_status()
        body = response.json()
        message = body.get("message", {})
        result.answer = (message.get("content") or "")[:300]
        result.ok = True
        result.correct = is_correct(result.answer, probe["expected_substring"])
        result.thinking_present = bool(message.get("thinking")) if think else None
        result.usage = {k: body[k] for k in ("prompt_eval_count", "eval_count") if k in body}
    except Exception as exc:  # l'échec de l'appel est le résultat mesuré
        result.error = describe_error(exc)
    result.latency_s = time.monotonic() - start
    return result


def probe_dspy(step: str, model: ModelSpec, lm_model: str, api_base: str, api_key: str,
               system: str, user: str, probe: dict[str, Any], extra: dict[str, Any]) -> ProbeResult:
    """Appelle le modèle via un ``dspy.Predict`` et mesure la réponse.

    Args:
        step: identifiant de l'étape (``dspy_openai``, ``dspy_openai_think``, ``dspy_ollama_chat``).
        model: modèle testé.
        lm_model: identifiant LiteLLM/DSPy (``openai/<nom>`` ou ``ollama_chat/<nom>``).
        api_base: URL de base passée à ``dspy.LM``.
        api_key: clé Ollama.
        system: instruction de la signature (prompt système).
        user: question posée (prompt utilisateur).
        probe: paramètres ``probe`` du spike.
        extra: paramètres supplémentaires de ``dspy.LM`` (ex. ``reasoning_effort``).

    Returns:
        Le résultat de l'appel (succès ou échec enregistré).
    """
    import dspy

    class Question(dspy.Signature):
        """Instruction remplacée à l'exécution par le prompt système."""

        question: str = dspy.InputField()
        answer: str = dspy.OutputField()

    name = lm_model.split("/", 1)[1]
    result = ProbeResult(step=step, model_key=model.key, name=name, extra={"lm_model": lm_model, **extra})
    start = time.monotonic()
    try:
        lm = dspy.LM(lm_model, api_base=api_base, api_key=api_key, temperature=probe["temperature"],
                     max_tokens=probe["max_tokens"], cache=False, **extra)
        with dspy.context(lm=lm):
            prediction = dspy.Predict(Question.with_instructions(system))(question=user)
        result.answer = str(prediction.answer)[:300]
        result.ok = True
        result.correct = is_correct(result.answer, probe["expected_substring"])
        last = lm.history[-1] if lm.history else {}
        usage = last.get("usage")
        result.usage = dict(usage) if usage else None
        if extra.get("reasoning_effort") and usage:
            details = usage.get("completion_tokens_details") or {}
            reasoning = details.get("reasoning_tokens") if isinstance(details, dict) else None
            result.thinking_present = bool(reasoning) if reasoning is not None else None
    except Exception as exc:  # l'échec de l'appel est le résultat mesuré
        result.error = describe_error(exc)
    result.latency_s = time.monotonic() - start
    return result


# --------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------


def run() -> Path:
    """Exécute le protocole complet et écrit les rapports dans ``out/``.

    Returns:
        Le chemin du rapport Markdown.

    Raises:
        ConfigError: configuration ou environnement invalides.
    """
    load_dotenv(os.path.expanduser("~/.env"), override=True)
    params = load_yaml(PARAMS_FILE)
    stock = load_yaml((SPIKE_DIR / require_key(params, "models_file")).resolve())
    models = ollama_models(stock)
    native_base = require_env(require_key(params, "endpoints.native_base_url"))
    api_key = require_env(require_key(params, "endpoints.api_key"))
    openai_base = require_key(params, "endpoints.openai_base_url")
    ollama_chat_base = require_key(params, "endpoints.ollama_chat_base_url")
    suffixes = require_key(params, "cloud_name_suffixes")
    probe = require_key(params, "probe")
    for key in ("prompt_dir", "prompt_name", "variables", "expected_substring",
                "max_tokens", "temperature", "http_timeout"):
        require_key(probe, key)
    system, user = load_prompt(SPIKE_DIR / probe["prompt_dir"], probe["prompt_name"], probe["variables"])

    results: list[ProbeResult] = []
    catalogue: list[str] | None
    catalogue_error = None
    try:
        catalogue = fetch_catalogue(native_base, api_key, probe["http_timeout"])
    except Exception as exc:  # résultat mesuré
        catalogue, catalogue_error = None, describe_error(exc)

    for model in models:
        print(f"→ {model.key}", file=sys.stderr)
        variants = name_variants(model.name, suffixes)
        native = [probe_native(model, n, native_base, api_key, system, user, probe, None) for n in variants]
        results += native
        working = next((r.name for r in native if r.ok), model.name)
        if model.think:
            results.append(probe_native(model, working, native_base, api_key, system, user, probe, model.think))
        results.append(probe_dspy("dspy_openai", model, f"openai/{working}", openai_base, api_key,
                                  system, user, probe, {}))
        if model.think:
            results.append(probe_dspy("dspy_openai_think", model, f"openai/{working}", openai_base, api_key,
                                      system, user, probe, {"reasoning_effort": model.think}))
        results.append(probe_dspy("dspy_ollama_chat", model, f"ollama_chat/{working}", ollama_chat_base,
                                  api_key, system, user, probe, {}))

    out_dir = SPIKE_DIR / require_key(params, "output_dir")
    out_dir.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    raw = {"timestamp": stamp, "catalogue": catalogue, "catalogue_error": catalogue_error,
           "results": [asdict(r) for r in results]}
    (out_dir / f"b5_{stamp}.json").write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
    report = out_dir / f"b5_{stamp}.md"
    report.write_text(summarize(results, catalogue), encoding="utf-8")
    return report


if __name__ == "__main__":
    print(run())
