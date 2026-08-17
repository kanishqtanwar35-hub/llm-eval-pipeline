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
