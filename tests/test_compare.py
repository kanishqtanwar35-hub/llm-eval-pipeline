"""Comparison-mode tests. No network, no API key."""

import pytest

from src.evals.compare import compare
from src.evals.runner import run_suite
from src.evals.targets import StubTarget, StubV2Target

DATASET = "datasets/golden.jsonl"


@pytest.fixture(scope="module")
def baseline():
    return run_suite(StubTarget(), DATASET)


@pytest.fixture(scope="module")
def candidate():
    return run_suite(StubV2Target(), DATASET)


def test_stub_v2_fixes_the_json_case(baseline, candidate):
    result = compare(baseline, candidate)
    assert "json-002" in result.fixed


def test_stub_v2_regresses_a_safety_case(baseline, candidate):
    result = compare(baseline, candidate)
    assert "refuse-002" in result.regressions


def test_a_flat_delta_still_reports_regressed(baseline, candidate):
    """The headline number is unchanged — one fix, one break.

    This is the whole reason comparison mode exists: a pass rate alone calls
    this change a no-op, when it actually broke a safety case.
    """
    result = compare(baseline, candidate)
    assert result.delta == 0.0
    assert result.verdict == "REGRESSED"


def test_per_tag_deltas_expose_the_direction(baseline, candidate):
    result = compare(baseline, candidate)
    assert result.by_tag["format"]["delta"] > 0      # JSON improved
    assert result.by_tag["safety"]["delta"] < 0      # safety got worse


def test_identical_runs_report_no_change(baseline):
    result = compare(baseline, baseline)
    assert result.delta == 0.0
    assert result.verdict == "NO CHANGE"
    assert result.fixed == []
    assert result.regressions == []


def test_every_shared_case_is_classified(baseline, candidate):
    result = compare(baseline, candidate)
    outcomes = {c["outcome"] for c in result.cases}
    assert outcomes <= {"fixed", "regression", "both_pass", "both_fail"}
    assert len(result.cases) == baseline.total


def test_disjoint_datasets_raise(baseline):
    import copy

    other = copy.deepcopy(baseline)
    for c in other.cases:
        c["id"] = "unrelated-" + c["id"]

    with pytest.raises(ValueError, match="share no case ids"):
        compare(baseline, other)


def test_regression_detail_explains_the_failure(baseline, candidate):
    result = compare(baseline, candidate)
    by_id = {c["id"]: c for c in result.cases}
    assert "did NOT refuse" in by_id["refuse-002"]["candidate_detail"]
