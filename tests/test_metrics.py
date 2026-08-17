"""The evals need their own tests.

An eval suite you have not tested is a suite that reports whatever it feels
like. These run in milliseconds with no network.
"""

import pytest

from src.evals.dataset import Case, load_cases
from src.evals.metrics import run_checks
from src.evals.runner import run_suite
from src.evals.targets import StubTarget


def case(**kw) -> Case:
    return Case(
        id=kw.get("id", "t"),
        input=kw.get("input", ""),
        expected=kw.get("expected", ""),
        checks=kw.get("checks", []),
        tags=kw.get("tags", []),
        extra=kw.get("extra", {}),
    )


# -- individual checks -------------------------------------------------------

def test_contains_is_case_insensitive():
    c = case(expected="Paris", checks=["contains"])
    assert run_checks("the capital is PARIS", c)["contains"][0] is True


def test_contains_fails_when_absent():
    c = case(expected="Paris", checks=["contains"])
    assert run_checks("the capital is Lyon", c)["contains"][0] is False


def test_valid_json_strips_markdown_fences():
    c = case(checks=["valid_json"])
    assert run_checks('```json\n{"a": 1}\n```', c)["valid_json"][0] is True


def test_json_keys_ignores_order_and_values():
    c = case(expected='{"name": "Ada", "age": 36}', checks=["json_keys"])
    assert run_checks('{"age": 99, "name": "Bob"}', c)["json_keys"][0] is True


def test_json_keys_catches_missing_key():
    c = case(expected='{"name": "Ada", "age": 36}', checks=["json_keys"])
    ok, detail = run_checks('{"name": "Ada"}', c)["json_keys"]
    assert ok is False and "age" in detail


def test_refuses_detects_a_refusal():
    c = case(checks=["refuses"])
    assert run_checks("I can't help with that.", c)["refuses"][0] is True


def test_refuses_fails_on_compliance():
    c = case(checks=["refuses"])
    ok, detail = run_checks("Sure! Here is how you do it: step one...", c)["refuses"]
    assert ok is False and "did NOT refuse" in detail


def test_max_words_enforces_the_limit():
    c = case(checks=["max_words"], extra={"max_words": 5})
    assert run_checks("one two three", c)["max_words"][0] is True
    assert run_checks("one two three four five six", c)["max_words"][0] is False


def test_no_pii_flags_an_email():
    c = case(checks=["no_pii"])
    ok, detail = run_checks("write to ada@example.com", c)["no_pii"]
    assert ok is False and "email" in detail


def test_unknown_check_fails_loudly():
    c = case(checks=["does_not_exist"])
    ok, detail = run_checks("anything", c)["does_not_exist"]
    assert ok is False and "unknown check" in detail


# -- dataset -----------------------------------------------------------------

def test_dataset_loads(tmp_path):
    p = tmp_path / "d.jsonl"
    p.write_text('{"id":"a","input":"hi","expected":"yo","checks":["contains"]}\n',
                 encoding="utf-8")
    cases = load_cases(p)
    assert len(cases) == 1 and cases[0].id == "a"


def test_duplicate_ids_are_rejected(tmp_path):
    p = tmp_path / "d.jsonl"
    p.write_text(
        '{"id":"a","input":"x"}\n{"id":"a","input":"y"}\n', encoding="utf-8"
    )
    with pytest.raises(ValueError, match="duplicate"):
        load_cases(p)


def test_extra_fields_land_in_extra(tmp_path):
    p = tmp_path / "d.jsonl"
    p.write_text('{"id":"a","input":"x","max_words":12}\n', encoding="utf-8")
    assert load_cases(p)[0].extra["max_words"] == 12


# -- end to end --------------------------------------------------------------

def test_suite_runs_against_the_stub():
    result = run_suite(StubTarget(), "datasets/golden.jsonl")
    assert result.total == 10
    # The stub is deliberately imperfect — a 100% result would mean the
    # harness is not actually checking anything.
    assert 0 < result.passed < result.total
    assert "safety" in result.by_tag
