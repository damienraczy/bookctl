"""Tests des fonctions pures de l'approfondissement `think` (sans réseau)."""

import b5_think as bt
import b5_spike as b5


def test_find_reasoning_first_non_empty_field() -> None:
    assert bt.find_reasoning({"content": "99", "reasoning": "", "reasoning_content": "calcul"}) == (
        "reasoning_content", 6)
    assert bt.find_reasoning({"content": "99"}) == (None, 0)
    assert bt.find_reasoning({"thinking": "   "}) == (None, 0)


def test_thinking_values() -> None:
    assert bt.thinking_values({"thinking": {"values": ["low", "high"]}}) == ["low", "high"]
    assert bt.thinking_values({"thinking": {}}) == []
    assert bt.thinking_values({}) == []


def test_settings_to_test_merges_without_duplicates() -> None:
    assert bt.settings_to_test([False, True], [True, "low", "high"]) == [False, True, "low", "high"]


def test_think_prompts_are_consistent_with_params() -> None:
    params = b5.load_yaml(b5.PARAMS_FILE)
    tp = params["think_probe"]
    _, user = b5.load_prompt(b5.SPIKE_DIR / params["probe"]["prompt_dir"], tp["prompt_name"], tp["variables"])
    assert "1853" in user and "1854" in user
