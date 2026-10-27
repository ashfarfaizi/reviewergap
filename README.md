# ReviewerGap

**Do AI reviewers catch the mistakes that matter?**

A small, self-contained study of *scalable oversight*: when one language model is used
to check another model's work, which errors does it reliably catch, which does it miss,
and do two different reviewers fail on the *same* problems?

This matters because a growing number of AI safety proposals — AI graders, debate,
automated red-teaming, "AI checking AI" — assume the checker works. ReviewerGap measures
whether it does, on a task where the ground truth is known exactly.

---

## Why this design is honest

The hard part of evaluating a reviewer is knowing the right answer yourself. ReviewerGap
sidesteps that: it **generates** maths word-problems together with their worked solutions,
so it knows at creation time whether a solution is correct, and if not, **which step** is
wrong and **what kind** of error it is. Every metric is scored against that ground truth,
not against another model's opinion. There is no human grading and nothing to trust.

Each problem is produced in two versions:

- a **clean** solution (correct), and
- a **flawed** solution with exactly one planted error of a known type at a known step.

Five error types, from blatant to subtle:

| Type | What it is |
|---|---|
| `arithmetic_slip` | one step computes the wrong number |
| `copy_error` | a number is carried to the next step wrong |
| `wrong_operation` | +/−/×/÷ swapped in one step |
| `dropped_term` | a term silently disappears |
| `plausible_but_off` | the answer is only ~3% off — the kind that's easy to miss |

## What it measures

- **Detection rate** — of flawed solutions, how many the reviewer flagged (recall).
- **False-alarm rate** — of clean solutions, how many it wrongly flagged.
- **Localisation** — when it flags a real error, does it point at the right step?
- **Detection by error type** — which mistakes slip through most often.
- **Miss correlation** — given two reviewers, how often do they miss the *same* error?
  If that correlation is high, stacking two reviewers buys far less safety than their
  individual numbers suggest. This is the result worth writing up.

## Run it

No dependencies beyond the Python standard library. Works fully offline with a built-in
mock reviewer, so you can see the whole pipeline before spending a cent on API calls.

```bash
# Offline demo (seconds, no API key):
python run.py --reviewer mock --n 200

# Two reviewers with independent blind spots, to see the correlation analysis:
python run.py --reviewer "mock:miss=0.12" --reviewer-b "mock:miss=0.12,seed=99" --n 300
```

Then open `results/report.html`.

### With real models

Set the API key for whichever provider you use, then name it as the reviewer. Gemini has
a free tier, so this costs nothing to start.

```bash
export GEMINI_API_KEY=...        # free key from aistudio.google.com/apikey
python run.py --reviewer gemini:gemini-3.5-flash-lite --n 150
```

**The headline experiment** — same model family vs. a different one as the reviewer:

```bash
export GEMINI_API_KEY=...
export ANTHROPIC_API_KEY=...
python run.py \
  --reviewer   gemini:gemini-3.5-flash-lite \
  --reviewer-b anthropic:claude-haiku-5-5 \
  --n 150
```

If the two reviewers' misses are **uncorrelated**, a cross-family check is a cheap, real
improvement to oversight. If they're **correlated**, that's an important warning. Either
way you have a finding.

Any OpenAI-compatible endpoint (DeepSeek, Qwen, Together, …) works too:
`--reviewer "openai:MODEL@https://api.your-provider.com/v1"` with `OPENAI_API_KEY` set.

## Outputs (`results/`)

- `report.html` — a shareable, self-contained report with charts (open in any browser).
- `metrics.json` — every number, for your own plots.
- `dataset.jsonl` — the problems and their ground-truth labels.
- `verdicts_*.jsonl` — each reviewer's raw output and parsed verdict, per problem.

## Tests

```bash
pip install pytest
pytest -q
```

The tests check that the dataset labels are internally consistent and deterministic, that
verdict parsing survives messy model output, and that the metrics behave sensibly.

## What this is and isn't

- It **is** a clean, reproducible harness for one real oversight question, built to be
  extended (new task domains, new error types, new reviewers, majority-vote reviewers).
- It is **not** a claim that these specific numbers are the final word. The mock reviewer
  exists only so the plumbing runs offline; the findings that matter come from real models.

## Ideas to extend it

- Add code-review tasks (functions with planted bugs and hidden unit tests as ground truth).
- Add a **self-review** condition: does a model catch its *own* mistakes less often?
- Add a **debate** or **best-of-k reviewers** condition and see where returns flatten.
- Hide vs. show the solver's reasoning to the reviewer, and measure the difference.

See `WRITEUP_TEMPLATE.md` for a structure to turn a run into a short post or paper.
