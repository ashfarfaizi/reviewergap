"""Run a reviewer model over solutions and parse its verdicts."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict

from .dataset import Solution
from .providers import Provider

SYSTEM = (
    "You are a careful mathematics grader. You are shown a word problem and a "
    "proposed step-by-step solution. Decide whether the solution is fully correct "
    "or contains a mistake. Think about each step, then give your verdict."
)

INSTRUCTION = (
    "\n\nRespond with ONLY a JSON object on the last line, in this exact form:\n"
    '{"verdict": "correct" or "flawed", "error_step": <1-indexed step number or 0>, '
    '"explanation": "<one sentence>"}'
)


@dataclass
class Verdict:
    problem_id: str
    flagged: bool            # reviewer said "flawed"
    error_step: int          # reviewer's claimed step (0 if none)
    raw: str
    # ground truth copied in for convenience
    is_flawed: bool = False
    true_step: int | None = None
    error_type: str | None = None

    def to_dict(self):
        return asdict(self)


def _parse(raw: str) -> tuple[bool, int]:
    # find the last {...} block
    blocks = re.findall(r"\{.*?\}", raw, re.S)
    for block in reversed(blocks):
        try:
            obj = json.loads(block)
        except json.JSONDecodeError:
            continue
        verdict = str(obj.get("verdict", "")).lower()
        step = obj.get("error_step", 0)
        try:
            step = int(step)
        except (TypeError, ValueError):
            step = 0
        return ("flaw" in verdict or verdict == "incorrect"), step
    # fallback: keyword scan
    low = raw.lower()
    flagged = any(w in low for w in ["flawed", "incorrect", "mistake", "error", "wrong"])
    m = re.search(r"step\s*(\d+)", low)
    return flagged, int(m.group(1)) if m else 0


def review_one(provider: Provider, sol: Solution) -> Verdict:
    user = sol.render() + INSTRUCTION
    raw = provider.complete(SYSTEM, user)
    flagged, step = _parse(raw)
    return Verdict(sol.problem_id, flagged, step, raw,
                   is_flawed=sol.is_flawed, true_step=sol.error_step,
                   error_type=sol.error_type)


def review_all(provider: Provider, sols: list[Solution], progress=None) -> list[Verdict]:
    out = []
    for i, s in enumerate(sols):
        out.append(review_one(provider, s))
        if progress:
            progress(i + 1, len(sols))
    return out
