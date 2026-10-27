# ReviewerGap: do AI reviewers catch the mistakes that matter?

*Draft write-up. Replace the bracketed parts with your own numbers from `results/metrics.json`.
Keep it short and honest — a good oversight result with clear limitations beats an
over-claimed one.*

## One-paragraph summary

A lot of AI safety plans rely on using one model to check another: AI graders, debate,
automated red-teaming. These assume the checker is reliable. I built a small harness that
tests that assumption on a task with perfectly known ground truth, and found that
[MODEL] caught only [XX]% of planted errors, missed the subtle near-correct ones most
often, and — more importantly — a second reviewer from [same / a different] model family
missed [largely the same / mostly different] problems (miss correlation φ = [0.XX]). That
last number decides whether stacking reviewers actually helps.

## Setup

- **Task:** [N] arithmetic/algebra word problems, each with a step-by-step solution.
  Half are correct; half contain exactly one planted error of a known type at a known step.
- **Ground truth:** labels are generated with the problems, so no human or model grading
  is involved.
- **Reviewer(s):** [model name(s)], prompted to judge each solution and name the faulty step.
- **Metrics:** detection rate (recall on flawed), false-alarm rate (on clean),
  localisation (right step), and miss correlation between two reviewers.

## Results

| Reviewer | Detection | False alarms | Right step |
|---|---|---|---|
| [model A] | [XX]% | [X]% | [XX]% |
| [model B] | [XX]% | [X]% | [XX]% |

**Detection by error type (model A):**

| arithmetic_slip | copy_error | wrong_operation | dropped_term | plausible_but_off |
|---|---|---|---|---|
| [XX]% | [XX]% | [XX]% | [XX]% | **[XX]%** |

**Two-reviewer analysis (the main result):**

- Both reviewers missed the error on [XX]% of flawed problems.
- Accepting *either* reviewer's flag raised detection to [XX]% (vs [XX]% for one alone).
- Miss correlation φ = [0.XX].

## What I take from this

1. [e.g. "The reviewer is good at blatant arithmetic errors but weak on near-correct
   answers — exactly the errors most likely to matter in high-stakes settings."]
2. [e.g. "Same-family reviewers' misses are strongly correlated, so a second same-family
   check adds little. A cross-family reviewer helped more / didn't help."]
3. [Your honest caveat — small task domain, one difficulty level, prompt-sensitive, etc.]

## Limitations

- Single, narrow task domain (arithmetic word problems). Findings may not transfer to code
  or natural-language reasoning.
- One prompt per reviewer; results are known to be prompt-sensitive.
- Planted errors are synthetic and may be easier or harder than naturally occurring ones.

## Next steps

- [Add code-review tasks / self-review condition / debate / best-of-k reviewers.]
- [Scale to more models and a larger N.]

*Code and data: attached. Everything is reproducible with a single command.*
