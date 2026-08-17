"""Run every case against a target and aggregate the results."""

import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List

from src.evals.dataset import Case, load_cases
from src.evals.metrics import run_checks


@dataclass
class CaseResult:
    id: str
    input: str
    output: str
    passed: bool
    checks: Dict[str, dict] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    latency_ms: int = 0
    error: str = ""


@dataclass
class RunResult:
    target: str
    total: int
    passed: int
    failed: int
    pass_rate: float
    by_tag: Dict[str, dict]
    cases: List[dict]
    duration_s: float

    def to_dict(self) -> dict:
        return asdict(self)


def run_case(target, case: Case) -> CaseResult:
    start = time.perf_counter()
    try:
        output = target(case.input)
        error = ""
    except Exception as e:
        output, error = "", str(e)
    latency = int((time.perf_counter() - start) * 1000)

    if error:
        return CaseResult(
            id=case.id, input=case.input, output="", passed=False,
            tags=case.tags, latency_ms=latency, error=error,
        )

    raw = run_checks(output, case)
    checks = {name: {"passed": ok, "detail": detail} for name, (ok, detail) in raw.items()}
    # A case passes only if EVERY check on it passes.
    passed = all(v["passed"] for v in checks.values()) if checks else False

    return CaseResult(
        id=case.id, input=case.input, output=output, passed=passed,
        checks=checks, tags=case.tags, latency_ms=latency,
    )


def run_suite(target, dataset_path: Path) -> RunResult:
    cases = load_cases(dataset_path)
    start = time.perf_counter()

    results = [run_case(target, c) for c in cases]

    passed = sum(1 for r in results if r.passed)
    total = len(results)

    # Per-tag breakdown. "78% overall" hides that safety is at 50%.
    by_tag: Dict[str, dict] = {}
    for r in results:
        for tag in r.tags:
            bucket = by_tag.setdefault(tag, {"total": 0, "passed": 0})
            bucket["total"] += 1
            bucket["passed"] += int(r.passed)
    for tag, bucket in by_tag.items():
        bucket["pass_rate"] = round(bucket["passed"] / bucket["total"], 4)

    return RunResult(
        target=getattr(target, "name", "unknown"),
        total=total,
        passed=passed,
        failed=total - passed,
        pass_rate=round(passed / total, 4) if total else 0.0,
        by_tag=by_tag,
        cases=[asdict(r) for r in results],
        duration_s=round(time.perf_counter() - start, 2),
    )
