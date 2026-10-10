"""Spike S1 : temps de réaction des modèles System 1 servis par Ollama local.

Mesure la durée des appels ``/v1/systemone`` à froid (modèle déchargé) puis à
chaud, selon la primitive, la taille du ``state``, le nombre de questions et
l'usage du cache. Voir ``README.md`` pour la question, le protocole et le
critère de décision.

Une erreur de configuration lève une exception ; l'échec d'un appel mesuré est
enregistré comme résultat, avec son erreur.
"""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

SPIKE_DIR = Path(__file__).resolve().parent
PARAMS_FILE = SPIKE_DIR / "params.yml"
ERROR_MESSAGE_MAX_CHARS = 300


class ConfigError(Exception):
    """Configuration du spike invalide ou incomplète."""


@dataclass
class CallResult:
    """Résultat d'un appel mesuré.

    Attributes:
        config: nom de la configuration (``cold`` pour les appels à froid).
        index: rang de l'appel dans la configuration.
        latency_s: durée côté client, de l'envoi à la réponse complète.
        http_status: statut HTTP, None si l'appel n'a pas abouti.
        input_tokens: ``usage.input_tokens`` rapporté, si présent.
        cached_tokens: ``prompt_eval_cached_count`` rapporté, si présent.
        answers: réponses compactées (valeur principale par question).
        error: type et message de l'erreur, si l'appel a échoué.
    """

    config: str
    index: int
    latency_s: float | None = None
    http_status: int | None = None
    input_tokens: int | None = None
    cached_tokens: int | None = None
    answers: dict[str, Any] | None = None
    error: str | None = None


# --------------------------------------------------------------------------
# Fonctions pures (testées sans réseau)
# --------------------------------------------------------------------------


def load_yaml(path: Path) -> dict[str, Any]:
    """Charge un fichier YAML qui doit contenir un dictionnaire.

    Raises:
        ConfigError: fichier absent ou contenu qui n'est pas un dictionnaire.
    """
    if not path.is_file():
        raise ConfigError(f"Fichier introuvable : {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ConfigError(f"{path} doit contenir un dictionnaire YAML")
    return data


def require_key(mapping: dict[str, Any], key: str) -> Any:
    """Lit une clé obligatoire.

    Raises:
        ConfigError: clé absente.
    """
    if key not in mapping:
        raise ConfigError(f"Paramètre obligatoire absent : {key}")
    return mapping[key]


def require_env(var_name: str) -> str:
    """Lit une variable d'environnement obligatoire.

    Raises:
        ConfigError: variable absente ou vide.
    """
    value = os.environ.get(var_name)
    if not value:
        raise ConfigError(f"Variable d'environnement non définie : {var_name}")
    return value


def select_questions(all_questions: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    """Choisit les questions d'une configuration.

    Args:
        all_questions: questions déclarées dans ``params.yml``, dans l'ordre.
        config: configuration, avec exactement l'une des clés ``primitive``
            (nom d'une question) ou ``questions`` (nombre de premières questions).

    Returns:
        Les questions retenues, au format de la requête ``/v1/systemone``.

    Raises:
        ConfigError: aucune ou les deux clés, question inconnue, nombre hors bornes.
    """
    has_primitive, has_count = "primitive" in config, "questions" in config
    if has_primitive == has_count:
        raise ConfigError(f"{config.get('name')} : déclarer `primitive` ou `questions`, pas les deux")
    if has_primitive:
        name = config["primitive"]
        if name not in all_questions:
            raise ConfigError(f"{config.get('name')} : question inconnue : {name}")
        return {name: all_questions[name]}
    count = config["questions"]
    if not isinstance(count, int) or not 1 <= count <= len(all_questions):
        raise ConfigError(f"{config.get('name')} : `questions` doit être entre 1 et {len(all_questions)}")
    return dict(list(all_questions.items())[:count])


def build_state(text: str, repeat: int, cache: bool, tag: str) -> str:
    """Construit le ``state`` d'un appel.

    Args:
        text: texte de base.
        repeat: nombre de copies concaténées (≥ 1).
        cache: True → state identique à chaque appel ; False → préfixe ``tag``.
        tag: étiquette unique sur tout l'essai (configuration et rang), pour
            qu'aucun appel sans cache ne réutilise le préfixe d'un autre.

    Returns:
        Le state à envoyer.

    Raises:
        ConfigError: ``repeat`` < 1.
    """
    if repeat < 1:
        raise ConfigError("`state_repeat` doit être ≥ 1")
    body = "\n\n".join([text.strip()] * repeat)
    return body if cache else f"[{tag}] {body}"


def compact_answers(answers: dict[str, Any]) -> dict[str, Any]:
    """Réduit chaque réponse à sa valeur principale (``noul``, ``score`` ou ``choice``).

    Args:
        answers: champ ``answers`` de la réponse ``/v1/systemone``.

    Returns:
        Nom de question → valeur principale (None si le type est inattendu).
    """
    compact: dict[str, Any] = {}
    for name, answer in answers.items():
        kind = answer.get("type")
        value = answer.get(kind) if kind in ("noul", "score", "choice") else None
        compact[name] = round(value, 3) if isinstance(value, float) else value
    return compact


def percentile(values: list[float], q: float) -> float:
    """Percentile par interpolation linéaire.

    Args:
        values: valeurs (non vide).
        q: rang entre 0 et 1.

    Returns:
        La valeur au rang ``q``.

    Raises:
        ValueError: liste vide ou ``q`` hors de [0, 1].
    """
    if not values or not 0 <= q <= 1:
        raise ValueError("liste vide ou rang hors de [0, 1]")
    ordered = sorted(values)
    pos = (len(ordered) - 1) * q
    low = int(pos)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (pos - low)


def summarize(results: list[CallResult]) -> list[dict[str, Any]]:
    """Synthèse par configuration : succès, tokens, médiane, p95, min, max.

    Args:
        results: tous les appels mesurés.

    Returns:
        Une ligne par configuration, dans l'ordre d'apparition.
    """
    rows: list[dict[str, Any]] = []
    for name in dict.fromkeys(r.config for r in results):
        group = [r for r in results if r.config == name]
        times = [r.latency_s for r in group if r.error is None and r.latency_s is not None]
        tokens = {r.input_tokens for r in group if r.input_tokens is not None}
        cached = [r.cached_tokens for r in group if r.cached_tokens is not None]
        row: dict[str, Any] = {"config": name, "ok": len(times), "total": len(group),
                               "input_tokens": sorted(tokens), "cached_max": max(cached) if cached else None,
                               "errors": sorted({r.error for r in group if r.error})}
        if times:
            row.update(median=percentile(times, 0.5), p95=percentile(times, 0.95),
                       min=min(times), max=max(times))
        rows.append(row)
    return rows


def render_markdown(meta: dict[str, Any], rows: list[dict[str, Any]],
                    results: list[CallResult]) -> str:
    """Rend la synthèse en Markdown.

    Args:
        meta: description de l'environnement (modèle, machine, version d'Ollama).
        rows: synthèse issue de ``summarize``.
        results: appels bruts (pour les réponses de la configuration la plus longue).

    Returns:
        Le rapport Markdown.
    """
    lines = [f"# Spike S1 — {meta['model']} — {meta['date']}", ""]
    lines += [f"- {k} : {v}" for k, v in meta.items() if k not in ("model", "date")]
    lines += ["", "| Config | OK | Tokens d'entrée | Cache max | Médiane (s) | p95 (s) | Min (s) | Max (s) | Erreurs |",
              "|---|---|---|---|---|---|---|---|---|"]
    for row in rows:
        timing = [f"{row[k]:.3f}" for k in ("median", "p95", "min", "max")] if "median" in row else ["—"] * 4
        lines.append(f"| {row['config']} | {row['ok']}/{row['total']} | {row['input_tokens']} | "
                     f"{row['cached_max']} | " + " | ".join(timing) + f" | {'; '.join(row['errors'])} |")
    lines += ["", "## Réponses (premier appel de chaque configuration)", ""]
    for name in dict.fromkeys(r.config for r in results):
        first = next(r for r in results if r.config == name)
        lines.append(f"- {name} : {first.answers if first.answers is not None else first.error}")
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------
# Appels (réseau)
# --------------------------------------------------------------------------


def call(client: Any, url: str, model: str, state: str, questions: dict[str, Any],
         config: str, index: int) -> CallResult:
    """Appelle ``/v1/systemone`` et mesure la durée ; un échec est enregistré, pas levé."""
    import httpx

    result = CallResult(config=config, index=index)
    start = time.perf_counter()
    try:
        response = client.post(url, json={"model": model, "state": state, "questions": questions})
        result.latency_s = time.perf_counter() - start
        result.http_status = response.status_code
        response.raise_for_status()
        body = response.json()
        result.input_tokens = body.get("usage", {}).get("input_tokens")
        result.cached_tokens = body.get("prompt_eval_cached_count")
        result.answers = compact_answers(body.get("answers", {}))
    except (httpx.HTTPError, ValueError) as exc:
        result.latency_s = result.latency_s or time.perf_counter() - start
        detail = exc.response.text if isinstance(exc, httpx.HTTPStatusError) else str(exc)
        result.error = f"{type(exc).__name__}: {detail}"[:ERROR_MESSAGE_MAX_CHARS]
    return result


def unload(client: Any, base: str, model: str) -> None:
    """Décharge le modèle de la mémoire (``keep_alive: 0``).

    Raises:
        httpx.HTTPError: échec du déchargement (l'essai à froid n'aurait pas de sens).
    """
    response = client.post(f"{base}/api/generate", json={"model": model, "keep_alive": 0})
    response.raise_for_status()


def environment(client: Any, base: str, model: str) -> dict[str, Any]:
    """Décrit la machine et le serveur, pour situer les mesures."""
    chip = subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True, text=True).stdout.strip()
    mem = subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True).stdout.strip()
    show = client.post(f"{base}/api/show", json={"model": model}).json()
    return {"model": model, "date": datetime.now().isoformat(timespec="seconds"),
            "machine": f"{chip or platform.machine()}, {int(mem) // 2**30 if mem else '?'} Gio",
            "ollama": client.get(f"{base}/api/version").json().get("version"),
            "format": f"{show.get('details', {}).get('quantization_level')} / {show.get('details', {}).get('runner')}",
            "parametres": " ; ".join((show.get("parameters") or "").split("\n"))}


def report_stem(model: str, stamp: str) -> str:
    """Nom de fichier des rapports d'un modèle (``:`` et ``/`` remplacés par ``-``)."""
    return f"s1_{model.replace(':', '-').replace('/', '-')}_{stamp}"


def run() -> list[Path]:
    """Exécute l'essai pour chaque modèle de ``models`` et écrit les rapports.

    Returns:
        Chemins des rapports Markdown, un par modèle.

    Raises:
        ConfigError: configuration invalide.
    """
    import httpx

    load_dotenv(os.path.expanduser("~/.env"), override=True)
    params = load_yaml(PARAMS_FILE)
    models = require_key(params, "models")
    if not isinstance(models, list) or not models:
        raise ConfigError("`models` doit être une liste non vide")
    base = require_env(require_key(params, "base_url")).rstrip("/")
    url = base + require_key(params, "endpoint")
    all_questions = require_key(params, "questions")
    state_dir = SPIKE_DIR / require_key(params, "state_dir")
    configs = require_key(params, "configs")
    warm_repeats = require_key(require_key(params, "warm"), "repeats")
    cold_repeats = require_key(require_key(params, "cold"), "repeats")

    prepared = []
    for config in configs:
        path = state_dir / f"{require_key(config, 'state')}.md"
        if not path.is_file():
            raise ConfigError(f"State introuvable : {path}")
        prepared.append((config, path.read_text(encoding="utf-8"), select_questions(all_questions, config)))

    out_dir = SPIKE_DIR / require_key(params, "output_dir")
    out_dir.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    reports = []
    with httpx.Client(timeout=require_key(params, "http_timeout")) as client:
        for model in models:
            results = measure(client, base, url, model, prepared, cold_repeats, warm_repeats)
            unload(client, base, model)
            meta = environment(client, base, model)
            rows = summarize(results)
            stem = report_stem(model, stamp)
            (out_dir / f"{stem}.json").write_text(
                json.dumps({"meta": meta, "summary": rows, "results": [asdict(r) for r in results]},
                           ensure_ascii=False, indent=2), encoding="utf-8")
            report = out_dir / f"{stem}.md"
            report.write_text(render_markdown(meta, rows, results), encoding="utf-8")
            reports.append(report)
    return reports


def measure(client: Any, base: str, url: str, model: str, prepared: list[tuple[dict[str, Any], str, dict[str, Any]]],
            cold_repeats: int, warm_repeats: int) -> list[CallResult]:
    """Mesure un modèle : appels à froid, puis chaque configuration à chaud.

    Args:
        client: client HTTP.
        base: URL de base d'Ollama.
        url: URL de ``/v1/systemone``.
        model: modèle mesuré.
        prepared: (configuration, texte, questions) pour chaque configuration.
        cold_repeats: nombre d'appels à froid.
        warm_repeats: nombre d'appels comptés par configuration.

    Returns:
        Tous les appels mesurés.

    Raises:
        httpx.HTTPError: échec du déchargement du modèle.
    """
    results: list[CallResult] = []
    _, first_text, first_questions = prepared[0]
    for i in range(cold_repeats):
        unload(client, base, model)
        results.append(call(client, url, model, build_state(first_text, 1, False, f"froid-{i}"), first_questions, "froid", i))
        print(f"{model} froid {i}: {results[-1].latency_s:.2f} s", file=sys.stderr)
    for config, text, questions in prepared:
        repeat, cache = config.get("state_repeat", 1), require_key(config, "cache")
        call(client, url, model, build_state(text, repeat, cache, f"{config['name']}-amorce"), questions, config["name"], -1)
        for i in range(warm_repeats):
            results.append(call(client, url, model, build_state(text, repeat, cache, f"{config['name']}-{i}"),
                                questions, config["name"], i))
        print(f"{model} {config['name']}: fait", file=sys.stderr)
    return results


if __name__ == "__main__":
    for path in run():
        print(path)
