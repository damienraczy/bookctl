"""Spike B5, approfondissement : le paramètre ``think`` sur Ollama Cloud.

Pour chaque modèle Ollama déclaré dans ``params.sample.yml``, mesure :

1. ce que le modèle déclare dans ``/api/show`` (capacités, ``thinking.values``) ;
2. en API native ``/api/chat``, l'effet de chaque valeur de ``think`` (booléens et
   niveaux annoncés) : présence et longueur de ``message.thinking``, tokens
   générés, justesse de la réponse ;
3. en compatibilité OpenAI ``/v1/chat/completions`` (appel HTTP brut), l'effet de
   ``reasoning_effort`` : champs de raisonnement présents dans le message,
   tokens de sortie ;
4. par DSPy (``openai/<nom>``), si le raisonnement remonte dans la réponse
   brute conservée par ``lm.history``.

Comme ``b5_spike.py`` : une erreur de configuration lève une exception ;
l'échec d'un appel testé est enregistré comme résultat.
"""

from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

from dotenv import load_dotenv

from b5_spike import (
    PARAMS_FILE,
    SPIKE_DIR,
    ModelSpec,
    describe_error,
    is_correct,
    load_prompt,
    load_yaml,
    ollama_models,
    require_env,
    require_key,
)

REASONING_KEYS = ("reasoning", "reasoning_content", "thinking")  # ordre de recherche


@dataclass
class ThinkResult:
    """Résultat d'un appel testé avec un réglage de raisonnement.

    Attributes:
        step: ``native``, ``openai_raw`` ou ``dspy``.
        model_key: nom logique du modèle.
        setting: valeur envoyée (``think`` ou ``reasoning_effort``), en texte.
        ok: l'appel a abouti.
        correct: la réponse contient le résultat attendu.
        reasoning_field: nom du champ de raisonnement trouvé dans la réponse, ou None.
        reasoning_chars: longueur du raisonnement renvoyé (0 si absent).
        output_tokens: tokens générés rapportés par l'API.
        latency_s: durée de l'appel.
        answer: réponse (tronquée).
        error: erreur, si l'appel a échoué.
    """

    step: str
    model_key: str
    setting: str
    ok: bool = False
    correct: bool | None = None
    reasoning_field: str | None = None
    reasoning_chars: int = 0
    output_tokens: int | None = None
    latency_s: float | None = None
    answer: str | None = None
    error: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


def find_reasoning(message: dict[str, Any]) -> tuple[str | None, int]:
    """Cherche un champ de raisonnement non vide dans un message de réponse.

    Args:
        message: message renvoyé par l'API (dictionnaire).

    Returns:
        Le nom du premier champ de raisonnement non vide et sa longueur,
        ou ``(None, 0)``.
    """
    for key in REASONING_KEYS:
        value = message.get(key)
        if isinstance(value, str) and value.strip():
            return key, len(value)
    return None, 0


def thinking_values(show: dict[str, Any]) -> list[Any]:
    """Extrait les valeurs de ``think`` déclarées par ``/api/show``.

    Args:
        show: réponse de ``/api/show``.

    Returns:
        Les valeurs déclarées (booléens ou niveaux), liste vide si absentes.
    """
    thinking = show.get("thinking")
    if isinstance(thinking, dict) and isinstance(thinking.get("values"), list):
        return list(thinking["values"])
    return []


def settings_to_test(base: list[Any], declared: list[Any]) -> list[Any]:
    """Fusionne les valeurs de base et les valeurs déclarées, sans doublon.

    Args:
        base: valeurs toujours testées (ex. ``[False, True]``).
        declared: valeurs annoncées par le modèle.

    Returns:
        Les valeurs à tester, dans l'ordre : base puis déclarées.
    """
    out: list[Any] = []
    for value in [*base, *declared]:
        if value not in out:
            out.append(value)
    return out


def show_model(base: str, api_key: str, name: str, timeout: float) -> dict[str, Any]:
    """Appelle ``POST <base>/show``.

    Raises:
        httpx.HTTPError: échec de l'appel (enregistré par l'appelant).
    """
    import httpx

    response = httpx.post(f"{base.rstrip('/')}/show", json={"model": name},
                          headers={"Authorization": f"Bearer {api_key}"}, timeout=timeout)
    response.raise_for_status()
    return response.json()


def probe_native(model: ModelSpec, base: str, api_key: str, system: str, user: str,
                 probe: dict[str, Any], expected: str, think: Any) -> ThinkResult:
    """Appelle ``/api/chat`` avec une valeur de ``think`` et mesure le raisonnement."""
    import httpx

    result = ThinkResult(step="native", model_key=model.key, setting=json.dumps(think))
    payload = {"model": model.name, "stream": False, "think": think,
               "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
               "options": {"temperature": probe["temperature"]}}
    start = time.monotonic()
    try:
        response = httpx.post(f"{base.rstrip('/')}/chat", json=payload,
                              headers={"Authorization": f"Bearer {api_key}"}, timeout=probe["http_timeout"])
        response.raise_for_status()
        body = response.json()
        message = body.get("message", {})
        result.ok = True
        result.answer = (message.get("content") or "")[:200]
        result.correct = is_correct(result.answer, expected)
        result.reasoning_field, result.reasoning_chars = find_reasoning(message)
        result.output_tokens = body.get("eval_count")
    except Exception as exc:  # résultat mesuré
        result.error = describe_error(exc)
    result.latency_s = time.monotonic() - start
    return result


def probe_openai_raw(model: ModelSpec, base: str, api_key: str, system: str, user: str,
                     probe: dict[str, Any], expected: str, effort: str) -> ThinkResult:
    """Appelle ``/v1/chat/completions`` avec ``reasoning_effort`` (HTTP brut)."""
    import httpx

    result = ThinkResult(step="openai_raw", model_key=model.key, setting=effort)
    payload = {"model": model.name, "reasoning_effort": effort, "temperature": probe["temperature"],
               "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    start = time.monotonic()
    try:
        response = httpx.post(f"{base.rstrip('/')}/chat/completions", json=payload,
                              headers={"Authorization": f"Bearer {api_key}"}, timeout=probe["http_timeout"])
        response.raise_for_status()
        body = response.json()
        message = body["choices"][0]["message"]
        result.ok = True
        result.answer = (message.get("content") or "")[:200]
        result.correct = is_correct(result.answer, expected)
        result.reasoning_field, result.reasoning_chars = find_reasoning(message)
        result.output_tokens = (body.get("usage") or {}).get("completion_tokens")
        result.extra["message_keys"] = sorted(message.keys())
    except Exception as exc:  # résultat mesuré
        result.error = describe_error(exc)
    result.latency_s = time.monotonic() - start
    return result


def probe_dspy(model: ModelSpec, base: str, api_key: str, system: str, user: str,
               probe: dict[str, Any], expected: str, effort: str) -> ThinkResult:
    """Appelle le modèle par DSPy (``openai/<nom>``) et inspecte la réponse brute."""
    import dspy

    class Question(dspy.Signature):
        """Instruction remplacée à l'exécution par le prompt système."""

        question: str = dspy.InputField()
        answer: str = dspy.OutputField()

    result = ThinkResult(step="dspy", model_key=model.key, setting=effort)
    start = time.monotonic()
    try:
        lm = dspy.LM(f"openai/{model.name}", api_base=base, api_key=api_key,
                     temperature=probe["temperature"], max_tokens=probe["max_tokens"],
                     cache=False, reasoning_effort=effort)
        with dspy.context(lm=lm):
            prediction = dspy.Predict(Question.with_instructions(system))(question=user)
        result.ok = True
        result.answer = str(prediction.answer)[:200]
        result.correct = is_correct(result.answer, expected)
        # DSPy 3.4 (moteur lm15) conserve le raisonnement dans history[-1]["outputs"]
        last = lm.history[-1] if lm.history else {}
        outputs = last.get("outputs") or []
        first = outputs[0] if outputs and isinstance(outputs[0], dict) else {}
        result.reasoning_field, result.reasoning_chars = find_reasoning(first)
        result.output_tokens = (last.get("usage") or {}).get("completion_tokens")
        result.extra["output_keys"] = sorted(first.keys())
    except Exception as exc:  # résultat mesuré
        result.error = describe_error(exc)
    result.latency_s = time.monotonic() - start
    return result


def summarize(shows: dict[str, Any], results: list[ThinkResult]) -> str:
    """Produit la synthèse Markdown."""
    lines = ["# Spike B5 — approfondissement `think`", "", "## Déclarations `/api/show`", "",
             "| Modèle | Capacités | `thinking.values` |", "|---|---|---|"]
    for key, show in shows.items():
        if "error" in show:
            lines.append(f"| {key} | erreur : {show['error']} | — |")
        else:
            caps = ", ".join(show.get("capabilities") or []) or "—"
            values = thinking_values(show)
            lines.append(f"| {key} | {caps} | {json.dumps(values) if values else 'absent'} |")
    lines += ["", "## Appels", "",
              "| Voie | Modèle | Réglage | OK | Correct | Champ de raisonnement | Taille | Tokens sortie | Latence (s) | Erreur |",
              "|---|---|---|---|---|---|---|---|---|---|"]
    for r in results:
        flag = "—" if r.correct is None else ("oui" if r.correct else "non")
        lat = "" if r.latency_s is None else f"{r.latency_s:.1f}"
        err = (r.error or "")[:160].replace("|", "\\|")
        lines.append(f"| {r.step} | {r.model_key} | `{r.setting}` | {'oui' if r.ok else 'non'} | {flag} | "
                     f"{r.reasoning_field or '—'} | {r.reasoning_chars} | {r.output_tokens if r.output_tokens is not None else '—'} | {lat} | {err} |")
    return "\n".join(lines) + "\n"


def run() -> str:
    """Exécute l'approfondissement et écrit les rapports dans ``out/``.

    Raises:
        ConfigError: configuration ou environnement invalides.
    """
    load_dotenv(os.path.expanduser("~/.env"), override=True)
    params = load_yaml(PARAMS_FILE)
    models = ollama_models(load_yaml((SPIKE_DIR / require_key(params, "models_file")).resolve()))
    native_base = require_env(require_key(params, "endpoints.native_base_url"))
    api_key = require_env(require_key(params, "endpoints.api_key"))
    openai_base = require_key(params, "endpoints.openai_base_url")
    probe = require_key(params, "probe")
    tp = require_key(params, "think_probe")
    for key in ("prompt_name", "variables", "expected_substring", "native_think_values",
                "openai_reasoning_efforts", "dspy_reasoning_efforts"):
        require_key(tp, key)
    system, user = load_prompt(SPIKE_DIR / probe["prompt_dir"], tp["prompt_name"], tp["variables"])
    expected = tp["expected_substring"]

    shows: dict[str, Any] = {}
    results: list[ThinkResult] = []
    for model in models:
        print(f"→ {model.key}", file=sys.stderr)
        try:
            show = show_model(native_base, api_key, model.name, probe["http_timeout"])
            shows[model.key] = {k: show.get(k) for k in ("capabilities", "thinking", "details")}
        except Exception as exc:  # résultat mesuré
            show, shows[model.key] = {}, {"error": describe_error(exc)}
        for think in settings_to_test(tp["native_think_values"], thinking_values(show)):
            results.append(probe_native(model, native_base, api_key, system, user, probe, expected, think))
        for effort in tp["openai_reasoning_efforts"]:
            results.append(probe_openai_raw(model, openai_base, api_key, system, user, probe, expected, effort))
        for effort in tp["dspy_reasoning_efforts"]:
            results.append(probe_dspy(model, openai_base, api_key, system, user, probe, expected, effort))

    out_dir = SPIKE_DIR / require_key(params, "output_dir")
    out_dir.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    (out_dir / f"b5_think_{stamp}.json").write_text(
        json.dumps({"shows": shows, "results": [asdict(r) for r in results]}, ensure_ascii=False, indent=2,
                   default=str), encoding="utf-8")
    report = out_dir / f"b5_think_{stamp}.md"
    report.write_text(summarize(shows, results), encoding="utf-8")
    return str(report)


if __name__ == "__main__":
    print(run())
