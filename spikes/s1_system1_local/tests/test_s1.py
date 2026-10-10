"""Tests des fonctions pures du spike S1 (sans réseau)."""

import pytest

import s1_latence as s1

QUESTIONS = {
    "a": {"type": "noul", "instructions": "A ?"},
    "b": {"type": "score", "instructions": "B ?", "criteria": ["x", "y"]},
    "c": {"type": "choice", "instructions": "C ?", "criteria": {"A": None, "B": None}},
}


def test_select_questions_par_primitive():
    assert s1.select_questions(QUESTIONS, {"name": "n", "primitive": "b"}) == {"b": QUESTIONS["b"]}


def test_select_questions_par_nombre_garde_l_ordre():
    assert list(s1.select_questions(QUESTIONS, {"name": "n", "questions": 2})) == ["a", "b"]


@pytest.mark.parametrize("config", [
    {"name": "n"},
    {"name": "n", "primitive": "a", "questions": 1},
    {"name": "n", "primitive": "inconnue"},
    {"name": "n", "questions": 0},
    {"name": "n", "questions": 4},
])
def test_select_questions_refuse_les_configurations_invalides(config):
    with pytest.raises(s1.ConfigError):
        s1.select_questions(QUESTIONS, config)


def test_build_state_cache_identique_sinon_prefixe_unique():
    assert s1.build_state("texte", 1, True, "a-3") == s1.build_state("texte", 1, True, "b-4") == "texte"
    assert s1.build_state("texte", 1, False, "a-3") != s1.build_state("texte", 1, False, "b-3")


def test_build_state_repete_le_texte():
    assert s1.build_state("t", 3, True, "x") == "t\n\nt\n\nt"


def test_build_state_refuse_repeat_nul():
    with pytest.raises(s1.ConfigError):
        s1.build_state("t", 0, True, "x")


def test_compact_answers():
    answers = {"a": {"type": "noul", "noul": 0.123456}, "b": {"type": "choice", "choice": "B"},
               "c": {"type": "autre"}}
    assert s1.compact_answers(answers) == {"a": 0.123, "b": "B", "c": None}


def test_percentile():
    assert s1.percentile([3.0, 1.0, 2.0], 0.5) == 2.0
    assert s1.percentile([1.0, 2.0], 0.95) == pytest.approx(1.95)
    with pytest.raises(ValueError):
        s1.percentile([], 0.5)


def test_summarize_ignore_les_echecs_dans_les_durees():
    results = [s1.CallResult("x", 0, latency_s=1.0, input_tokens=10),
               s1.CallResult("x", 1, latency_s=9.0, error="HTTPStatusError: 500"),
               s1.CallResult("y", 0, latency_s=2.0)]
    rows = s1.summarize(results)
    assert [r["config"] for r in rows] == ["x", "y"]
    assert rows[0]["ok"] == 1 and rows[0]["total"] == 2 and rows[0]["max"] == 1.0
    assert rows[0]["errors"] == ["HTTPStatusError: 500"]


def test_report_stem_remplace_les_separateurs():
    assert s1.report_stem("tev1:4b", "20261010") == "s1_tev1-4b_20261010"
    assert s1.report_stem("org/nimble", "x") == "s1_org-nimble_x"
