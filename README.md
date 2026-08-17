# LLM evaluation pipeline

Automated evals for an LLM app, with a **regression gate** that fails CI when
quality drops. Runs on GitHub Actions' free tier. Needs no API key.

**Status:** verified running. 14/14 tests pass, suite executes, HTML report
generated, gate enforced.

```
target      stub
cases       10
passed      8
failed      2
pass rate   80.0%  (threshold 70%)

by tag:
  arithmetic   1/1  100%
  concision    1/2   50%
  factual      3/3  100%
  format       1/2   50%
  injection    1/1  100%
  safety       2/2  100%

failures:
  json-002     valid_json: not valid JSON: Expecting value: line 1 column 1
  len-002      max_words: 48 words (limit 35)

GATE PASSED
```

---

## Why this is the highest-value project on the list

Almost every junior portfolio has a RAG app or a chatbot. Almost none can answer
**"how do you know it works?"**

This is that answer. It is also the least glamorous project here, which is
precisely why so few people build it.

---

## Quickstart

```bash
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt

pytest -q                       # 14 tests — the harness tests itself
python run_evals.py             # stub target, no API key
```

Open `reports/index.html`.

Against a real model:

```bash
set GEMINI_API_KEY=your_key
python run_evals.py --target gemini --threshold 0.80
```

---

## How it works

```
datasets/golden.jsonl  ──►  runner  ──►  target (stub | gemini | your app)
                              │                    │
                              │◄───── output ──────┘
                              ▼
                        metrics.py checks
                              ▼
             results.json + index.html + exit code
```

A case passes only when **every** check on it passes. The run fails when the
overall pass rate falls below `--threshold`, and `run_evals.py` exits 1 — which
is what turns a report into a gate.

---

## The checks

| Check | Asserts |
|---|---|
| `contains` | Expected substring appears (case-insensitive) |
| `exact` | Output matches exactly |
| `regex` | Output matches `pattern` on the case |
| `valid_json` | Parses as JSON (markdown fences stripped) |
| `json_keys` | Same keys as expected, order and values ignored |
| `refuses` | Model declined — for safety and injection cases |
| `max_words` | Output within `max_words` |
| `no_pii` | No email, phone or card-shaped string |

All deterministic. No LLM judge, no network, no variance between runs. Prefer
these wherever possible — `"Paris" in output` cannot be wrong, and a judge can.

---

## The golden set

`datasets/golden.jsonl`, one case per line:

```json
{"id": "fact-001", "input": "What is the capital of France?",
 "expected": "Paris", "checks": ["contains"], "tags": ["factual"]}
```

Tags drive the per-tag breakdown. That matters: **"80% overall" hides that
safety is at 50%.** An aggregate number is the wrong unit for deciding whether
to ship.

Start with 10 cases. Add one every time you find a failure in the wild — that
converts each bug into a permanent regression test, and the suite grows to match
the ways your app actually breaks.

---

## The stub target

`StubTarget` is a deliberately imperfect fake model. It answers some cases
correctly and fails two on purpose — one returns prose where JSON was asked for,
one exceeds a word limit.

That is intentional. A harness that reports 100% is a harness that might not be
checking anything. `test_suite_runs_against_the_stub` asserts
`0 < passed < total` for exactly this reason.

It also means the whole suite runs in CI with no secrets, on every push.

---

## Evaluating your own app

`Target` is any callable `str -> str`:

```python
class MyRAGTarget:
    name = "my-rag"
    def __call__(self, prompt: str) -> str:
        return my_rag_system.answer(prompt)
```

Register it in `get_target()` and run. Point it at your own RAG service, a
prompt variant, or a different model, and you get a comparable number for each
against the same golden set.

---

## CI

`.github/workflows/evals.yml` runs on push, on PRs, and **nightly at 03:00**.

The nightly run is the one people forget. Providers update models underneath
you. A scheduled eval catches a regression you did not cause — and being able to
say "my nightly evals caught a provider-side model change" is a genuinely strong
interview line.

The report publishes to GitHub Pages on pushes to `main`. Setup:
Settings → Pages → Source: GitHub Actions.

---

## Limitations, stated plainly

- **No LLM-as-judge.** Deterministic checks cannot assess tone, helpfulness or
  factual nuance. A judge grader is the obvious next addition — but build the
  deterministic layer first, because it is free and it never lies.
- **10 cases is a starting point**, not a suite. Real coverage is 50–200.
- **`refuses` is keyword matching.** A model that declines in unusual phrasing
  is scored as complying. Broaden `REFUSAL_MARKERS` as you see real outputs.
- **No cost or latency budget.** `latency_ms` is recorded per case but not gated.
