"""Load the golden set.

JSONL, not CSV: cases contain nested fields and free text with commas, and
JSONL diffs cleanly in git so a reviewer can see exactly which case you added.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List


@dataclass
class Case:
    id: str
    input: str
    expected: str = ""
    checks: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    extra: Dict[str, Any] = field(default_factory=dict)


def load_cases(path: Path) -> List[Case]:
    cases: List[Case] = []
    seen = set()

    with open(path, "r", encoding="utf-8") as f:
        for lineno, raw in enumerate(f, start=1):
            raw = raw.strip()
            if not raw or raw.startswith("//"):
                continue
            try:
                obj = json.loads(raw)
            except json.JSONDecodeError as e:
                raise ValueError(f"{path}:{lineno} is not valid JSON: {e}") from e

            case_id = obj.pop("id", f"case-{lineno}")
            if case_id in seen:
                raise ValueError(f"{path}:{lineno} duplicate case id '{case_id}'")
            seen.add(case_id)

            cases.append(
                Case(
                    id=case_id,
                    input=obj.pop("input"),
                    expected=obj.pop("expected", ""),
                    checks=obj.pop("checks", []),
                    tags=obj.pop("tags", []),
                    extra=obj,          # max_words, json_keys, anything else
                )
            )

    if not cases:
        raise ValueError(f"{path} contains no cases")
    return cases
