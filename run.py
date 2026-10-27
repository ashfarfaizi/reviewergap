#!/usr/bin/env python3
"""ReviewerGap command-line runner.

Examples
--------
Offline demo (no API key, runs in seconds):
    python run.py --reviewer mock --n 200

Compare a same-family reviewer against a different-family one:
    python run.py --reviewer gemini:gemini-3.5-flash-lite \\
                  --reviewer-b anthropic:claude-haiku-5-5 --n 150

Two mock reviewers with different blind spots (offline, shows the correlation idea):
    python run.py --reviewer mock:miss=0.15 --reviewer-b mock:miss=0.15,seed=99 --n 300
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from reviewergap import dataset, providers, reviewer, metrics, report


def _progress(i, n):
    if i != n and i % 25 != 0:
        return
    bar = int(30 * i / n)
    print(f"\r  [{'#'*bar}{'.'*(30-bar)}] {i}/{n}", end="", flush=True)
    if i == n:
        print()


def main(argv=None):
    ap = argparse.ArgumentParser(description="ReviewerGap: do AI reviewers catch the mistakes that matter?")
    ap.add_argument("--reviewer", default="mock", help="primary reviewer spec (see providers.build)")
    ap.add_argument("--reviewer-b", default=None, help="optional second reviewer for correlation analysis")
    ap.add_argument("--n", type=int, default=200, help="number of problems")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--flawed-fraction", type=float, default=0.5)
    ap.add_argument("--out", default="results", help="output directory")
    args = ap.parse_args(argv)

    os.makedirs(args.out, exist_ok=True)
    print(f"Generating {args.n} problems (seed={args.seed}, flawed={args.flawed_fraction:.0%}) ...")
    sols = dataset.generate(args.n, args.seed, args.flawed_fraction)
    with open(os.path.join(args.out, "dataset.jsonl"), "w") as f:
        for s in sols:
            f.write(json.dumps(s.to_dict()) + "\n")

    metrics_list = []
    verdicts_by_reviewer = {}

    for spec in [args.reviewer, args.reviewer_b]:
        if not spec:
            continue
        prov = providers.build(spec)
        print(f"Reviewing with {prov.name} ...")
        vs = reviewer.review_all(prov, sols, progress=_progress)
        verdicts_by_reviewer[prov.name] = vs
        m = metrics.score(vs, prov.name)
        metrics_list.append(m)
        with open(os.path.join(args.out, f"verdicts_{prov.name.replace(':','_').replace('/','_')}.jsonl"), "w") as f:
            for v in vs:
                f.write(json.dumps(v.to_dict()) + "\n")
        print(f"  detection={m.detection_rate:.0%}  false_alarms={m.false_positive_rate:.0%}  localisation={m.localisation_rate:.0%}")

    corr = None
    if len(verdicts_by_reviewer) == 2:
        a, b = list(verdicts_by_reviewer.values())
        corr = metrics.correlation(a, b)
        print(f"Miss correlation (phi) = {corr.get('miss_phi_correlation')}, "
              f"both miss = {corr.get('both_miss_rate')}, "
              f"combined = {corr.get('combined_detection_if_either_flags')}")

    config = {"reviewer": args.reviewer, "n": args.n, "seed": args.seed}
    if args.reviewer_b:
        config["reviewer_b"] = args.reviewer_b
    html = report.build_report(metrics_list, corr, config)
    report_path = os.path.join(args.out, "report.html")
    with open(report_path, "w") as f:
        f.write(html)
    with open(os.path.join(args.out, "metrics.json"), "w") as f:
        json.dump({"metrics": [m.to_dict() for m in metrics_list], "correlation": corr}, f, indent=2)

    print(f"\nDone. Open {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
