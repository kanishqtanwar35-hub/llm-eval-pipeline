# Code walkthrough — 03-llm-eval-pipeline

Five modules. Read in this order; each depends only on the ones above it.

```
dataset.py   load golden.jsonl -> [Case]
metrics.py   (output, case) -> (passed, detail)      pure functions
targets.py   the thing under test: str -> str
runner.py    for each case: call target, run checks, aggregate
report.py    RunResult -> self-contained HTML
run_evals.py CLI + the exit code that makes it a gate
```

---

## `dataset.py`

**JSONL, not CSV.** Cases contain free text with commas and nested fields, and
JSONL diffs one-line-per-case in git — a reviewer sees exactly which case you
added.

Two guards worth having:

- **Duplicate ids raise.** Copy-pasting a case and forgetting to rename the id
  silently overwrites results in any dict-keyed aggregation. `test_duplicate_ids_are_rejected`
  pins it.
- **Unknown fields land in `extra`.** `max_words`, `pattern`, and anything you
  invent later flow through without touching this file. That is why adding a new
  check requires editing only `metrics.py`.

Errors name the file *and line number*. When case 47 of 200 is malformed you
want to be told which one.

## `metrics.py` — the heart

Every check is a **pure function**: `(output, case) -> (bool, str)`. No network,
no model, no randomness.

That is what makes the eval suite testable — and an eval suite you have not
tested reports whatever it feels like. `tests/test_metrics.py` covers each check
in both directions, pass and fail. Ten of the fourteen tests are here.

Three checks worth studying:

**`check_json_keys`** compares *key sets*, not strings. A model returning
`{"age": 36, "name": "Ada"}` in a different order is correct; string equality
would mark it wrong. Getting this wrong makes your eval suite report failures
that are not failures, and then you stop trusting it.

**`check_valid_json`** strips markdown fences before parsing. Models wrap JSON
in ` ```json ` despite instructions. You can fight that in the prompt forever,
or handle it in three lines here.

**`check_refuses`** is a keyword match against `REFUSAL_MARKERS`. Deliberately
conservative, and its limits are stated in the README. Note the failure detail
is `"did NOT refuse — complied with the request"` rather than `False` — when a
safety case fails you want the report to say what happened, not just that it did.

`run_checks` catches exceptions per check and turns them into failures with the
message attached. One broken check must not abort the run.

## `targets.py`

A target is anything callable `str -> str`. That single-method interface is the
seam: your RAG app, a raw model, a prompt variant, all plug in identically.

**`StubTarget` is deliberately imperfect.** It fails `json-002` (returns prose
where JSON was requested) and `len-002` (48 words against a 35-word limit) on
purpose. Two consequences:

1. The suite runs in CI with no secrets, on every push.
2. A harness reporting 100% might not be checking anything. The end-to-end test
   asserts `0 < passed < total`.

**`GeminiTarget`** is raw HTTP with 429 backoff. Note `temperature: 0.0` —
evaluating a nondeterministic system makes every regression ambiguous. And note
it returns `""` when `candidates` is empty, which is what a safety block looks
like; `candidates[0]` would raise `IndexError` and kill the run.

## `runner.py`

**A case passes only if every check on it passes.** One line —
`all(v["passed"] for v in checks.values())` — but it is a real decision. The
alternative (partial credit) produces scores that drift upward while the app
gets worse.

**The per-tag breakdown is the point.** An aggregate hides distribution: 80%
overall with safety at 50% is not a shippable system, and the single number does
not tell you that. `by_tag` makes it visible.

Errors are captured, not raised. One case that throws must not lose the other
nine results.

`latency_ms` is recorded per case. Not gated yet — an obvious next feature.

## `report.py`

Self-contained HTML with inlined CSS and no external requests, so it works as a
Pages deploy and as a downloaded Actions artifact.

Everything user-controlled goes through `html.escape`. Model output rendered raw
into a page is an XSS vector, and "it's just my eval report" is how that habit
forms.

Theme-aware via `prefers-color-scheme`, tabular numerals so the columns line up.
Small things, but a report someone actually reads is worth more than one they
skim.

## `run_evals.py`

```python
if result.pass_rate < args.threshold:
    print(f"GATE FAILED: {result.pass_rate:.1%} < {args.threshold:.0%}")
    return 1
```

**That exit code is the whole project.** A report nobody reads changes nothing;
a build that goes red changes behaviour. Same idea as project 01's `min_score`,
applied to an LLM app.

The failure list prints the first failing check per case, so the CI log alone
tells you what broke — without downloading the artifact.

---

## The `--threshold` question

Same rule as project 01's `min_score`: run once, read the number, set the
threshold just below it. Then raise it as you improve.

Set it too high and you disable your own CI within a week. Set it thoughtfully
and it protects you for years.

---

## Next additions, in order

1. **An LLM-as-judge grader** for tone and helpfulness — the things regex
   cannot see. Two judges and a tiebreak beat one judge.
2. **A latency budget.** `latency_ms` is already recorded; gate the p95.
3. **A cost budget.** Track tokens per case, fail if a prompt change doubles
   spend.
4. **Compare two targets in one run** and diff them. That turns "I think the new
   prompt is better" into a number.
