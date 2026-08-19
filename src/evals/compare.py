"""Compare two runs against the same golden set.

A single pass rate tells you where you are. A comparison tells you whether the
change you just made helped — which is the question you actually have.

The important output is not the headline delta. It is `regressions`: cases the
baseline passed and the candidate fails. A change that lifts the overall rate
by four points while breaking two safety cases is a bad change, and only a
per-case diff makes that visible.
"""

from dataclasses import asdict, dataclass, field
from typing import Dict, List

from src.evals.runner import RunResult


@dataclass
class CaseDiff:
    id: str
    tags: List[str]
    baseline_passed: bool
    candidate_passed: bool
    outcome: str                # fixed | regression | both_pass | both_fail
    baseline_output: str = ""
    candidate_output: str = ""
    candidate_detail: str = ""


@dataclass
class Comparison:
    baseline: str
    candidate: str
    baseline_rate: float
    candidate_rate: float
    delta: float
    fixed: List[str] = field(default_factory=list)
    regressions: List[str] = field(default_factory=list)
    by_tag: Dict[str, dict] = field(default_factory=dict)
    cases: List[dict] = field(default_factory=list)
    verdict: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def _classify(base_pass: bool, cand_pass: bool) -> str:
    if base_pass and cand_pass:
        return "both_pass"
    if not base_pass and not cand_pass:
        return "both_fail"
    return "fixed" if cand_pass else "regression"


def compare(baseline: RunResult, candidate: RunResult) -> Comparison:
    base_by_id = {c["id"]: c for c in baseline.cases}
    cand_by_id = {c["id"]: c for c in candidate.cases}

    shared = [cid for cid in base_by_id if cid in cand_by_id]
    if not shared:
        raise ValueError(
            "The two runs share no case ids — they were not run against the "
            "same dataset, so a comparison would be meaningless."
        )

    diffs: List[CaseDiff] = []
    for cid in shared:
        b, c = base_by_id[cid], cand_by_id[cid]
        failing = [
            f"{k}: {v['detail']}" for k, v in c["checks"].items() if not v["passed"]
        ]
        diffs.append(
            CaseDiff(
                id=cid,
                tags=c["tags"],
                baseline_passed=b["passed"],
                candidate_passed=c["passed"],
                outcome=_classify(b["passed"], c["passed"]),
                baseline_output=b["output"][:300],
                candidate_output=c["output"][:300],
                candidate_detail=failing[0] if failing else (c["error"] or ""),
            )
        )

    # Per-tag deltas. An overall gain can hide a per-tag collapse — this is
    # where you see that "safety" dropped while "factual" carried the average.
    by_tag: Dict[str, dict] = {}
    for d in diffs:
        for tag in d.tags:
            bucket = by_tag.setdefault(tag, {"total": 0, "baseline": 0, "candidate": 0})
            bucket["total"] += 1
            bucket["baseline"] += int(d.baseline_passed)
            bucket["candidate"] += int(d.candidate_passed)
    for bucket in by_tag.values():
        bucket["baseline_rate"] = round(bucket["baseline"] / bucket["total"], 4)
        bucket["candidate_rate"] = round(bucket["candidate"] / bucket["total"], 4)
        bucket["delta"] = round(bucket["candidate_rate"] - bucket["baseline_rate"], 4)

    fixed = sorted(d.id for d in diffs if d.outcome == "fixed")
    regressions = sorted(d.id for d in diffs if d.outcome == "regression")

    base_rate = round(sum(d.baseline_passed for d in diffs) / len(diffs), 4)
    cand_rate = round(sum(d.candidate_passed for d in diffs) / len(diffs), 4)
    delta = round(cand_rate - base_rate, 4)

    # A regression is disqualifying regardless of the headline number. Net
    # improvement is not the same as improvement, and averaging over a broken
    # safety case is how bad changes get shipped.
    if regressions:
        verdict = "REGRESSED"
    elif delta > 0:
        verdict = "IMPROVED"
    elif delta == 0:
        verdict = "NO CHANGE"
    else:
        verdict = "WORSE"

    return Comparison(
        baseline=baseline.target,
        candidate=candidate.target,
        baseline_rate=base_rate,
        candidate_rate=cand_rate,
        delta=delta,
        fixed=fixed,
        regressions=regressions,
        by_tag=by_tag,
        cases=[asdict(d) for d in diffs],
        verdict=verdict,
    )
