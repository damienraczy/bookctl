"""Tests des fonctions pures du spike B5 (sans réseau)."""

from pathlib import Path

import pytest

import b5_spike as b5


def test_name_variants_strips_colon_cloud() -> None:
    assert b5.name_variants("glm-5.3-flash:cloud", [":cloud", "-cloud"]) == [
        "glm-5.3-flash:cloud", "glm-5.3-flash"]


def test_name_variants_strips_dash_cloud() -> None:
    assert b5.name_variants("gemma4:31b-cloud", [":cloud", "-cloud"]) == ["gemma4:31b-cloud", "gemma4:31b"]


def test_name_variants_without_suffix_keeps_single_name() -> None:
    assert b5.name_variants("gemma4:31b", [":cloud", "-cloud"]) == ["gemma4:31b"]


def test_ollama_models_filters_provider_and_reads_think() -> None:
    declared = {"models": {
        "a": {"provider": "ollama", "name": "a:cloud", "think": "high"},
        "b": {"provider": "anthropic", "name": "b"},
    }}
    assert b5.ollama_models(declared) == [b5.ModelSpec(key="a", name="a:cloud", think="high")]


def test_ollama_models_without_ollama_raises() -> None:
    with pytest.raises(b5.ConfigError):
        b5.ollama_models({"models": {"b": {"provider": "anthropic", "name": "b"}}})


def test_ollama_models_missing_name_raises() -> None:
    with pytest.raises(b5.ConfigError):
        b5.ollama_models({"models": {"a": {"provider": "ollama"}}})


def test_require_key_nested_and_missing() -> None:
    assert b5.require_key({"a": {"b": 1}}, "a.b") == 1
    with pytest.raises(b5.ConfigError):
        b5.require_key({"a": {}}, "a.b")


def test_require_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("B5_TEST_VAR", "x")
    assert b5.require_env("B5_TEST_VAR") == "x"
    monkeypatch.setenv("B5_TEST_VAR", "")
    with pytest.raises(b5.ConfigError):
        b5.require_env("B5_TEST_VAR")
    monkeypatch.delenv("B5_TEST_VAR")
    with pytest.raises(b5.ConfigError):
        b5.require_env("B5_TEST_VAR")


def test_render_prompt_checks_variables() -> None:
    assert b5.render_prompt("Capitale de {t} ?", {"t": "X"}) == "Capitale de X ?"
    with pytest.raises(b5.ConfigError):
        b5.render_prompt("Capitale de {t} ?", {})
    with pytest.raises(b5.ConfigError):
        b5.render_prompt("Capitale de {t} ?", {"t": "X", "u": "Y"})


def test_load_prompt(tmp_path: Path) -> None:
    (tmp_path / "p_system.md").write_text("Réponds court.\n", encoding="utf-8")
    (tmp_path / "p_user.md").write_text("Capitale de {t} ?\n", encoding="utf-8")
    assert b5.load_prompt(tmp_path, "p", {"t": "X"}) == ("Réponds court.", "Capitale de X ?")
    with pytest.raises(b5.ConfigError):
        b5.load_prompt(tmp_path, "p", {"t": "X", "u": "Y"})
    with pytest.raises(b5.ConfigError):
        b5.load_prompt(tmp_path, "absent", {"t": "X"})


def test_spike_prompts_are_consistent_with_params() -> None:
    params = b5.load_yaml(b5.PARAMS_FILE)
    probe = params["probe"]
    system, user = b5.load_prompt(b5.SPIKE_DIR / probe["prompt_dir"], probe["prompt_name"], probe["variables"])
    assert "Nouvelle-Calédonie" in user


def test_is_correct() -> None:
    assert b5.is_correct("La capitale est Nouméa.", "Nouméa") is True
    assert b5.is_correct("la capitale est nouméa", "Nouméa") is True
    assert b5.is_correct("Paris", "Nouméa") is False
    assert b5.is_correct(None, "Nouméa") is None


def test_describe_error_truncates_and_flattens() -> None:
    text = b5.describe_error(ValueError("ligne 1\nligne 2" + "x" * 1000))
    assert text.startswith("ValueError: ligne 1 ligne 2")
    assert "\n" not in text
    assert len(text) <= len("ValueError: ") + b5.ERROR_MESSAGE_MAX_CHARS


def test_load_yaml_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(b5.ConfigError):
        b5.load_yaml(tmp_path / "absent.yml")


def test_summarize_counts_correct_successes() -> None:
    results = [
        b5.ProbeResult(step="native", model_key="m", name="m:cloud", ok=True, correct=True, latency_s=1.0),
        b5.ProbeResult(step="native", model_key="m", name="m", ok=False, error="HTTPStatusError: 404"),
    ]
    report = b5.summarize(results, ["m"])
    assert "| native | 1 / 2 |" in report
    assert "| native | m | `m` | oui | non |" in report
