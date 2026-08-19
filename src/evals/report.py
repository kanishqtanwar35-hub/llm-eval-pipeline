"""Render the run as a self-contained HTML page.

Self-contained matters: GitHub Pages serves it directly, and the artifact
downloads from Actions open in a browser with no build step.
"""

import html
from pathlib import Path

from src.evals.runner import RunResult

TEMPLATE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Eval report — {target}</title>
<style>
  :root {{ --bg:#fbfbfa; --fg:#16211f; --muted:#6b7a76; --line:#e2e6e3;
           --ok:#2c6b4b; --bad:#8a362f; --card:#fff; }}
  @media (prefers-color-scheme: dark) {{
    :root {{ --bg:#0e1615; --fg:#e7ede9; --muted:#8fa39d; --line:#25332f;
             --ok:#63c08d; --bad:#e27a70; --card:#141f1d; }}
  }}
  body {{ background:var(--bg); color:var(--fg); margin:0; padding:2rem 1rem 4rem;
          font:16px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif; }}
  .wrap {{ max-width:1000px; margin:0 auto; }}
  h1 {{ font-size:1.6rem; margin:0 0 .25rem; }}
  .sub {{ color:var(--muted); margin:0 0 2rem; font-size:.9rem; }}
  .tiles {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(130px,1fr));
            gap:1px; background:var(--line); border:1px solid var(--line); margin-bottom:2rem; }}
  .tile {{ background:var(--card); padding:1rem; }}
  .tile .n {{ font-size:1.8rem; font-variant-numeric:tabular-nums; line-height:1; }}
  .tile .l {{ color:var(--muted); font-size:.78rem; margin-top:.3rem; }}
  h2 {{ font-size:1.05rem; border-bottom:2px solid var(--fg); padding-bottom:.4rem; }}
  table {{ width:100%; border-collapse:collapse; font-size:.86rem; }}
  th,td {{ text-align:left; padding:.5rem .6rem; border-bottom:1px solid var(--line);
           vertical-align:top; }}
  th {{ color:var(--muted); font-weight:600; font-size:.75rem;
        text-transform:uppercase; letter-spacing:.06em; }}
  .pass {{ color:var(--ok); font-weight:600; }}
  .fail {{ color:var(--bad); font-weight:600; }}
  code {{ font:.82rem ui-monospace,Menlo,Consolas,monospace; word-break:break-word; }}
  .scroll {{ overflow-x:auto; }}
  details {{ margin-top:.3rem; }}
  summary {{ cursor:pointer; color:var(--muted); font-size:.8rem; }}
</style></head><body><div class="wrap">
<h1>Eval report</h1>
<p class="sub">target <code>{target}</code> &middot; {total} cases &middot; {duration}s</p>

<div class="tiles">
  <div class="tile"><div class="n">{pass_rate}%</div><div class="l">Pass rate</div></div>
  <div class="tile"><div class="n pass">{passed}</div><div class="l">Passed</div></div>
  <div class="tile"><div class="n fail">{failed}</div><div class="l">Failed</div></div>
  <div class="tile"><div class="n">{threshold}%</div><div class="l">Gate threshold</div></div>
  <div class="tile"><div class="n {gate_class}">{gate}</div><div class="l">Result</div></div>
</div>

<h2>By tag</h2>
<div class="scroll"><table>
<tr><th>Tag</th><th>Passed</th><th>Total</th><th>Rate</th></tr>
{tag_rows}
</table></div>

<h2>Cases</h2>
<div class="scroll"><table>
<tr><th>ID</th><th>Result</th><th>Input</th><th>Output &amp; checks</th><th>ms</th></tr>
{case_rows}
</table></div>
</div></body></html>
"""


COMPARE_TEMPLATE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{candidate} vs {baseline}</title>
<style>
  :root {{ --bg:#fbfbfa; --fg:#16211f; --muted:#6b7a76; --line:#e2e6e3;
           --ok:#2c6b4b; --bad:#8a362f; --warn:#8a5d14; --card:#fff; }}
  @media (prefers-color-scheme: dark) {{
    :root {{ --bg:#0e1615; --fg:#e7ede9; --muted:#8fa39d; --line:#25332f;
             --ok:#63c08d; --bad:#e27a70; --warn:#d7a54a; --card:#141f1d; }}
  }}
  body {{ background:var(--bg); color:var(--fg); margin:0; padding:2rem 1rem 4rem;
          font:16px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif; }}
  .wrap {{ max-width:1000px; margin:0 auto; }}
  h1 {{ font-size:1.5rem; margin:0 0 .2rem; }}
  .sub {{ color:var(--muted); margin:0 0 2rem; font-size:.88rem; }}
  .tiles {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(140px,1fr));
            gap:1px; background:var(--line); border:1px solid var(--line); margin-bottom:2rem; }}
  .tile {{ background:var(--card); padding:1rem; }}
  .tile .n {{ font-size:1.7rem; font-variant-numeric:tabular-nums; line-height:1; }}
  .tile .l {{ color:var(--muted); font-size:.76rem; margin-top:.3rem; }}
  h2 {{ font-size:1.02rem; border-bottom:2px solid var(--fg); padding-bottom:.4rem;
        margin-top:2rem; }}
  table {{ width:100%; border-collapse:collapse; font-size:.85rem; }}
  th,td {{ text-align:left; padding:.5rem .6rem; border-bottom:1px solid var(--line);
           vertical-align:top; }}
  th {{ color:var(--muted); font-weight:600; font-size:.72rem;
        text-transform:uppercase; letter-spacing:.06em; }}
  .good {{ color:var(--ok); font-weight:600; }}
  .bad {{ color:var(--bad); font-weight:600; }}
  .warn {{ color:var(--warn); font-weight:600; }}
  code {{ font:.8rem ui-monospace,Menlo,Consolas,monospace; word-break:break-word; }}
  .scroll {{ overflow-x:auto; }}
  tr.regression td {{ background:color-mix(in srgb, var(--bad) 8%, transparent); }}
  tr.fixed td {{ background:color-mix(in srgb, var(--ok) 8%, transparent); }}
</style></head><body><div class="wrap">
<h1>{candidate} vs {baseline}</h1>
<p class="sub">{total} shared cases &middot; verdict <b class="{verdict_class}">{verdict}</b></p>

<div class="tiles">
  <div class="tile"><div class="n">{baseline_rate}%</div><div class="l">Baseline</div></div>
  <div class="tile"><div class="n">{candidate_rate}%</div><div class="l">Candidate</div></div>
  <div class="tile"><div class="n {delta_class}">{delta_sign}{delta}pp</div><div class="l">Delta</div></div>
  <div class="tile"><div class="n good">{n_fixed}</div><div class="l">Fixed</div></div>
  <div class="tile"><div class="n bad">{n_regressions}</div><div class="l">Regressions</div></div>
</div>

{regression_banner}

<h2>By tag</h2>
<div class="scroll"><table>
<tr><th>Tag</th><th>Baseline</th><th>Candidate</th><th>Delta</th></tr>
{tag_rows}
</table></div>

<h2>Cases that changed</h2>
<div class="scroll"><table>
<tr><th>ID</th><th>Change</th><th>Tags</th><th>Why the candidate fails</th></tr>
{changed_rows}
</table></div>
</div></body></html>
"""


def render_comparison(comparison, out_path: Path) -> Path:
    tag_rows = "".join(
        f"<tr><td><code>{html.escape(tag)}</code></td>"
        f"<td>{v['baseline_rate'] * 100:.0f}%</td>"
        f"<td>{v['candidate_rate'] * 100:.0f}%</td>"
        f"<td class=\"{'good' if v['delta'] > 0 else 'bad' if v['delta'] < 0 else ''}\">"
        f"{v['delta'] * 100:+.0f}pp</td></tr>"
        for tag, v in sorted(comparison.by_tag.items())
    ) or "<tr><td colspan='4'>no tags</td></tr>"

    changed = [c for c in comparison.cases if c["outcome"] in ("fixed", "regression")]
    changed_rows = "".join(
        f"<tr class=\"{c['outcome']}\"><td><code>{html.escape(c['id'])}</code></td>"
        f"<td class=\"{'good' if c['outcome'] == 'fixed' else 'bad'}\">"
        f"{'FIXED' if c['outcome'] == 'fixed' else 'REGRESSION'}</td>"
        f"<td><code>{html.escape(', '.join(c['tags']))}</code></td>"
        f"<td>{html.escape(c['candidate_detail'][:160])}</td></tr>"
        for c in changed
    ) or "<tr><td colspan='4'>no cases changed outcome</td></tr>"

    if comparison.regressions:
        banner = (
            '<p class="bad" style="border:1px solid currentColor;padding:.8rem 1rem;'
            'margin:0 0 1rem">'
            f"{len(comparison.regressions)} case(s) that passed on the baseline now "
            "fail. Net improvement is not improvement — review these before shipping."
            "</p>"
        )
    else:
        banner = ""

    page = COMPARE_TEMPLATE.format(
        baseline=html.escape(comparison.baseline),
        candidate=html.escape(comparison.candidate),
        total=len(comparison.cases),
        verdict=comparison.verdict,
        verdict_class=(
            "bad" if comparison.verdict in ("REGRESSED", "WORSE")
            else "good" if comparison.verdict == "IMPROVED" else "warn"
        ),
        baseline_rate=f"{comparison.baseline_rate * 100:.0f}",
        candidate_rate=f"{comparison.candidate_rate * 100:.0f}",
        delta=f"{abs(comparison.delta) * 100:.0f}",
        delta_sign="+" if comparison.delta > 0 else "-" if comparison.delta < 0 else "",
        delta_class=(
            "good" if comparison.delta > 0 else "bad" if comparison.delta < 0 else ""
        ),
        n_fixed=len(comparison.fixed),
        n_regressions=len(comparison.regressions),
        regression_banner=banner,
        tag_rows=tag_rows,
        changed_rows=changed_rows,
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(page, encoding="utf-8")
    return out_path


def render(result: RunResult, threshold: float, out_path: Path) -> Path:
    tag_rows = "".join(
        f"<tr><td><code>{html.escape(tag)}</code></td><td>{v['passed']}</td>"
        f"<td>{v['total']}</td><td>{v['pass_rate'] * 100:.0f}%</td></tr>"
        for tag, v in sorted(result.by_tag.items())
    ) or "<tr><td colspan='4'>no tags</td></tr>"

    case_rows = []
    for c in result.cases:
        badge = ('<span class="pass">PASS</span>' if c["passed"]
                 else '<span class="fail">FAIL</span>')
        checks = "".join(
            f"<div>{'✓' if v['passed'] else '✗'} <code>{html.escape(k)}</code> — "
            f"{html.escape(str(v['detail']))}</div>"
            for k, v in c["checks"].items()
        )
        if c["error"]:
            checks += f"<div class='fail'>error: {html.escape(c['error'])}</div>"

        case_rows.append(
            f"<tr><td><code>{html.escape(c['id'])}</code></td><td>{badge}</td>"
            f"<td>{html.escape(c['input'][:90])}</td>"
            f"<td>{checks}<details><summary>output</summary>"
            f"<code>{html.escape(c['output'][:400])}</code></details></td>"
            f"<td>{c['latency_ms']}</td></tr>"
        )

    passed_gate = result.pass_rate >= threshold
    page = TEMPLATE.format(
        target=html.escape(result.target),
        total=result.total,
        duration=result.duration_s,
        pass_rate=f"{result.pass_rate * 100:.0f}",
        passed=result.passed,
        failed=result.failed,
        threshold=f"{threshold * 100:.0f}",
        gate="PASS" if passed_gate else "FAIL",
        gate_class="pass" if passed_gate else "fail",
        tag_rows=tag_rows,
        case_rows="".join(case_rows),
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(page, encoding="utf-8")
    return out_path
