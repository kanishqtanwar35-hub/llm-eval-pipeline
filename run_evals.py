"""Entrypoint.

Single run — "where am I?"

    python run_evals.py                          # stub target, no API key
    python run_evals.py --target gemini          # real model
    python run_evals.py --threshold 0.9          # stricter gate

Comparison — "did my change help?"

    python run_evals.py --target stub-v2 --against stub

Exit codes:
    0  gate passed / comparison clean
    1  pass rate below --threshold, or the candidate regressed a case

That non-zero exit is what makes this a CI gate rather than a report nobody
reads.
"""

import argparse
import json
import sys
from pathlib import Path

from src.evals.compare import compare
from src.evals.report import render, render_comparison
from src.evals.runner import run_suite
from src.evals.targets import get_target

DEFAULT_DATASET = Path("datasets/golden.jsonl")
OUT_DIR = Path("reports")


def _print_run(result, threshold: float) -> None:
    print(f"\ntarget      {result.target}")
    print(f"cases       {result.total}")
    print(f"passed      {result.passed}")
    print(f"failed      {result.failed}")
    print(f"pass rate   {result.pass_rate:.1%}  (threshold {threshold:.0%})")
    print("\nby tag:")
    for tag, v in sorted(result.by_tag.items()):
        print(f"  {tag:<12} {v['passed']}/{v['total']}  {v['pass_rate']:.0%}")

    failures = [c for c in result.cases if not c["passed"]]
    if failures:
        print("\nfailures:")
        for c in failures:
            reasons = [
                f"{k}: {v['detail']}" for k, v in c["checks"].items() if not v["passed"]
            ] or [c["error"]]
            print(f"  {c['id']:<12} {reasons[0]}")


def _print_comparison(cmp_result) -> None:
    print(f"\nbaseline    {cmp_result.baseline}  {cmp_result.baseline_rate:.1%}")
    print(f"candidate   {cmp_result.candidate}  {cmp_result.candidate_rate:.1%}")
    print(f"delta       {cmp_result.delta * 100:+.1f}pp")
    print(f"verdict     {cmp_result.verdict}")

    print("\nby tag:")
    for tag, v in sorted(cmp_result.by_tag.items()):
        print(
            f"  {tag:<12} {v['baseline_rate']:.0%} -> {v['candidate_rate']:.0%}"
            f"  ({v['delta'] * 100:+.0f}pp)"
        )

    if cmp_result.fixed:
        print(f"\nfixed ({len(cmp_result.fixed)}):")
        for cid in cmp_result.fixed:
            print(f"  + {cid}")

    if cmp_result.regressions:
        print(f"\nREGRESSIONS ({len(cmp_result.regressions)}):")
        by_id = {c["id"]: c for c in cmp_result.cases}
        for cid in cmp_result.regressions:
            print(f"  - {cid:<12} {by_id[cid]['candidate_detail'][:70]}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the LLM eval suite.")
    parser.add_argument("--target", default="stub", help="stub | stub-v2 | gemini")
    parser.add_argument(
        "--against",
        default=None,
        metavar="BASELINE",
        help="compare --target against this baseline target instead of gating",
    )
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument(
        "--threshold", type=float, default=0.70,
        help="minimum pass rate; below this the run fails (single-run mode only)",
    )
    parser.add_argument("--out", type=Path, default=OUT_DIR)
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)

    # ---- comparison mode ---------------------------------------------------
    if args.against:
        baseline = run_suite(get_target(args.against), args.dataset)
        candidate = run_suite(get_target(args.target), args.dataset)
        result = compare(baseline, candidate)

        (args.out / "comparison.json").write_text(
            json.dumps(result.to_dict(), indent=2), encoding="utf-8"
        )
        render_comparison(result, args.out / "comparison.html")

        _print_comparison(result)
        print(f"\nreport      {args.out / 'comparison.html'}")

        if result.regressions:
            print(
                f"\nFAILED: {len(result.regressions)} regression(s). "
                "A net gain does not offset a case that used to pass."
            )
            return 1
        print(f"\nOK: {result.verdict.lower()}, no regressions")
        return 0

    # ---- single-run mode ---------------------------------------------------
    result = run_suite(get_target(args.target), args.dataset)

    (args.out / "results.json").write_text(
        json.dumps(result.to_dict(), indent=2), encoding="utf-8"
    )
    render(result, args.threshold, args.out / "index.html")

    _print_run(result, args.threshold)
    print(f"\nreport      {args.out / 'index.html'}")

    if result.pass_rate < args.threshold:
        print(f"\nGATE FAILED: {result.pass_rate:.1%} < {args.threshold:.0%}")
        return 1

    print("\nGATE PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
