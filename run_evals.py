"""Entrypoint.

    python run_evals.py                          # stub target, no API key
    python run_evals.py --target gemini          # real model
    python run_evals.py --threshold 0.9          # stricter gate

Exits 1 when the pass rate falls below the threshold, which is what turns this
into a CI gate rather than a report nobody reads.
"""

import argparse
import json
import sys
from pathlib import Path

from src.evals.report import render
from src.evals.runner import run_suite
from src.evals.targets import get_target

DEFAULT_DATASET = Path("datasets/golden.jsonl")
OUT_DIR = Path("reports")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the LLM eval suite.")
    parser.add_argument("--target", default="stub", help="stub | gemini")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--threshold", type=float, default=0.70,
                        help="minimum pass rate; below this the run fails")
    parser.add_argument("--out", type=Path, default=OUT_DIR)
    args = parser.parse_args()

    target = get_target(args.target)
    result = run_suite(target, args.dataset)

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "results.json").write_text(
        json.dumps(result.to_dict(), indent=2), encoding="utf-8"
    )
    render(result, args.threshold, args.out / "index.html")

    print(f"\ntarget      {result.target}")
    print(f"cases       {result.total}")
    print(f"passed      {result.passed}")
    print(f"failed      {result.failed}")
    print(f"pass rate   {result.pass_rate:.1%}  (threshold {args.threshold:.0%})")
    print("\nby tag:")
    for tag, v in sorted(result.by_tag.items()):
        print(f"  {tag:<12} {v['passed']}/{v['total']}  {v['pass_rate']:.0%}")

    failures = [c for c in result.cases if not c["passed"]]
    if failures:
        print("\nfailures:")
        for c in failures:
            reasons = [f"{k}: {v['detail']}" for k, v in c["checks"].items()
                       if not v["passed"]] or [c["error"]]
            print(f"  {c['id']:<12} {reasons[0]}")

    print(f"\nreport      {args.out / 'index.html'}")

    if result.pass_rate < args.threshold:
        print(f"\nGATE FAILED: {result.pass_rate:.1%} < {args.threshold:.0%}")
        return 1

    print("\nGATE PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
