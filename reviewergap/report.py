"""Self-contained HTML report with inline SVG charts (no libraries, no network)."""
from __future__ import annotations

import html
from .metrics import Metrics

CSS = """
:root{--bg:#fbfaf7;--fg:#1c1b19;--muted:#6b6862;--card:#fff;--line:#e6e2d8;
--bar:#3b6ea5;--bar2:#c2714a;--accent:#2f7d5b;--warn:#b4472e}
@media(prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#1a1915;--fg:#ece9e2;
--muted:#9c988e;--card:#232019;--line:#34302a;--bar:#6fa3d6;--bar2:#e0996f}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);
font:16px/1.55 ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
.wrap{max-width:860px;margin:0 auto;padding:32px 16px 80px}
h1{font-size:28px;margin:0 0 4px}h2{font-size:19px;margin:34px 0 10px;border-bottom:1px solid var(--line);padding-bottom:6px}
.sub{color:var(--muted);margin:0 0 20px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:18px 20px;margin:14px 0}
table{border-collapse:collapse;width:100%;font-size:14px}th,td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line)}
th{color:var(--muted);font-weight:600}td.num{text-align:right;font-variant-numeric:tabular-nums}
.kpi{display:flex;gap:14px;flex-wrap:wrap}.kpi .box{flex:1;min-width:150px;background:var(--card);
border:1px solid var(--line);border-radius:12px;padding:14px 16px}
.kpi .v{font-size:26px;font-weight:700}.kpi .l{color:var(--muted);font-size:13px}
.take{background:var(--card);border-left:4px solid var(--accent);border-radius:8px;padding:14px 18px;margin:16px 0}
.foot{color:var(--muted);font-size:13px;margin-top:40px}
"""


def _bars(title, labels, series, maxv=1.0):
    """Grouped horizontal bar chart as SVG. series = [(name,color,values)]."""
    row_h, gap, pad_l, w = 26, 14, 180, 640
    n = len(labels)
    bar_h = (row_h - 4) / max(1, len(series))
    h = pad_l and (n * (row_h * len(series) + gap) + 40)
    rows = []
    y = 20
    for i, lab in enumerate(labels):
        for j, (sname, color, vals) in enumerate(series):
            v = vals[i] if i < len(vals) else 0
            bw = (w - pad_l - 60) * (v / maxv if maxv else 0)
            yy = y + j * bar_h
            rows.append(f'<rect x="{pad_l}" y="{yy:.1f}" width="{bw:.1f}" height="{bar_h-2:.1f}" fill="{color}" rx="2"/>')
            rows.append(f'<text x="{pad_l+bw+6:.1f}" y="{yy+bar_h-4:.1f}" font-size="12" fill="currentColor">{v:.0%}</text>')
        rows.append(f'<text x="{pad_l-8}" y="{y+bar_h:.1f}" font-size="12" text-anchor="end" fill="currentColor">{html.escape(lab)}</text>')
        y += bar_h * len(series) + gap
    legend = ""
    lx = pad_l
    for sname, color, _ in series:
        legend += f'<rect x="{lx}" y="{y}" width="12" height="12" fill="{color}" rx="2"/><text x="{lx+16}" y="{y+11}" font-size="12" fill="currentColor">{html.escape(sname)}</text>'
        lx += 150
    total_h = y + 28
    return (f'<svg viewBox="0 0 {w} {total_h}" width="100%" role="img" aria-label="{html.escape(title)}">'
            + "".join(rows) + legend + "</svg>")


def build_report(metrics_list: list[Metrics], corr: dict | None,
                 config: dict) -> str:
    primary = metrics_list[0]
    kpis = f"""
    <div class="kpi">
      <div class="box"><div class="v">{primary.detection_rate:.0%}</div><div class="l">errors caught ({primary.reviewer})</div></div>
      <div class="box"><div class="v">{primary.false_positive_rate:.0%}</div><div class="l">false alarms on clean work</div></div>
      <div class="box"><div class="v">{primary.localisation_rate:.0%}</div><div class="l">caught at the right step</div></div>
      <div class="box"><div class="v">{primary.n}</div><div class="l">problems graded</div></div>
    </div>"""

    # detection by error type, one bar series per reviewer
    all_types = sorted({t for m in metrics_list for t in m.by_error_type})
    series = []
    palette = ["var(--bar)", "var(--bar2)", "var(--accent)"]
    for k, m in enumerate(metrics_list):
        series.append((m.reviewer, palette[k % len(palette)],
                       [m.by_error_type.get(t, 0) for t in all_types]))
    chart = _bars("Detection rate by error type", all_types, series) if all_types else ""

    # overall comparison table
    rows = ""
    for m in metrics_list:
        rows += (f"<tr><td>{html.escape(m.reviewer)}</td>"
                 f"<td class='num'>{m.detection_rate:.0%}</td>"
                 f"<td class='num'>{m.false_positive_rate:.0%}</td>"
                 f"<td class='num'>{m.localisation_rate:.0%}</td></tr>")

    corr_html = ""
    if corr and corr.get("n_flawed_shared"):
        corr_html = f"""
        <h2>Do two reviewers miss the same errors?</h2>
        <div class="card">
          <p>Comparing the two reviewers on the {corr['n_flawed_shared']} flawed problems they both saw:</p>
          <table>
            <tr><th>Both reviewers missed the error</th><td class="num">{corr['both_miss_rate']:.0%}</td></tr>
            <tr><th>Caught if we accept EITHER reviewer's flag</th><td class="num">{corr['combined_detection_if_either_flags']:.0%}</td></tr>
            <tr><th>Correlation of their misses (phi)</th><td class="num">{corr['miss_phi_correlation']:+.2f}</td></tr>
          </table>
          <p class="sub" style="margin-top:12px">A high positive correlation means the two reviewers tend to be blind to the
          same mistakes, so stacking them buys less safety than their individual numbers suggest.</p>
        </div>"""

    takeaway = (f"Across {primary.n} graded solutions, the primary reviewer caught "
                f"{primary.detection_rate:.0%} of planted errors but flagged "
                f"{primary.false_positive_rate:.0%} of correct solutions. The hardest errors to "
                f"catch were the subtle, near-correct ones — the category most likely to matter.")

    cfg = " · ".join(f"{k}={v}" for k, v in config.items())

    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ReviewerGap Results</title><style>{CSS}</style></head><body><div class="wrap">
<h1>ReviewerGap</h1>
<p class="sub">Do AI reviewers catch the mistakes that matter? &nbsp;|&nbsp; {html.escape(cfg)}</p>
<div class="take"><strong>Takeaway.</strong> {takeaway}</div>
{kpis}
<h2>Detection by error type</h2>
<div class="card">{chart or '<p class="sub">No flawed problems in this run.</p>'}</div>
<h2>Reviewer comparison</h2>
<div class="card"><table>
<tr><th>Reviewer</th><th class="num">Detection</th><th class="num">False alarms</th><th class="num">Right step</th></tr>
{rows}</table></div>
{corr_html}
<p class="foot">Generated by ReviewerGap. All problems and errors are synthetic and
labelled at generation time; metrics are computed against that ground truth. No
human grading is involved.</p>
</div></body></html>"""
