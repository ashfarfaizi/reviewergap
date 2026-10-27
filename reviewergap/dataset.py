"""Generate arithmetic/algebra word problems with step-by-step worked solutions.

Each problem is produced TWICE:
  - a clean solution (correct final answer, correct steps)
  - a corrupted solution: exactly one planted error of a known TYPE at a known STEP.

Because we build the solutions ourselves, we know the ground truth perfectly:
whether a solution is flawed, where the flaw is, and what kind it is. That lets
us score a reviewer honestly without trusting any model to label the data.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field, asdict

ERROR_TYPES = [
    "arithmetic_slip",    # a single step computes the wrong number
    "copy_error",         # a number is carried over wrong to the next step
    "wrong_operation",    # +/-/x/div swapped in one step
    "dropped_term",       # a term silently disappears
    "plausible_but_off",  # final answer is close to correct (hard to catch)
]


@dataclass
class Solution:
    problem_id: str
    question: str
    steps: list[str]
    final_answer: str
    is_flawed: bool
    error_type: str | None = None      # None when clean
    error_step: int | None = None      # 1-indexed step that contains the flaw
    correct_answer: str = ""           # the true answer regardless of flaw
    meta: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    def render(self) -> str:
        lines = [f"Problem: {self.question}", "", "Proposed solution:"]
        for i, s in enumerate(self.steps, 1):
            lines.append(f"Step {i}: {s}")
        lines.append(f"Final answer: {self.final_answer}")
        return "\n".join(lines)


def _money(x: float) -> str:
    return f"{x:,.2f}"


class ProblemFactory:
    """Each method returns (steps, final_answer, correct_answer_value)."""

    def __init__(self, rng: random.Random):
        self.rng = rng

    def shopping(self):
        price = self.rng.randint(12, 90)
        qty = self.rng.randint(3, 9)
        discount = self.rng.choice([0, 5, 10, 15])
        q = (f"A shop sells a widget for {price} rupees. A customer buys {qty} widgets "
             f"and gets a {discount}% discount on the total. How much do they pay?")
        subtotal = price * qty
        disc_amount = subtotal * discount / 100
        total = subtotal - disc_amount
        steps = [
            f"Subtotal = {price} x {qty} = {subtotal}",
            f"Discount = {discount}% of {subtotal} = {_money(disc_amount)}",
            f"Total = {subtotal} - {_money(disc_amount)} = {_money(total)}",
        ]
        return steps, _money(total), total

    def interest(self):
        p = self.rng.randint(1000, 9000)
        r = self.rng.choice([4, 5, 6, 8, 10])
        t = self.rng.randint(2, 5)
        q = (f"A sum of {p} rupees is invested at {r}% simple interest per year "
             f"for {t} years. What is the total amount at the end?")
        interest = p * r * t / 100
        total = p + interest
        steps = [
            f"Interest = (P x R x T) / 100 = ({p} x {r} x {t}) / 100 = {_money(interest)}",
            f"Total amount = Principal + Interest = {p} + {_money(interest)} = {_money(total)}",
        ]
        return steps, _money(total), total, q

    def speed(self):
        d1 = self.rng.randint(60, 200)
        d2 = self.rng.randint(60, 200)
        h = self.rng.randint(2, 6)
        q = (f"A car travels {d1} km in the morning and {d2} km in the afternoon, "
             f"over a total of {h} hours of driving. What is its average speed in km/h?")
        total_d = d1 + d2
        speed = total_d / h
        steps = [
            f"Total distance = {d1} + {d2} = {total_d} km",
            f"Average speed = distance / time = {total_d} / {h} = {_money(speed)} km/h",
        ]
        return steps, f"{_money(speed)} km/h", speed, q

    def mixture(self):
        a = self.rng.randint(2, 8)
        b = self.rng.randint(2, 8)
        pa = self.rng.randint(20, 60)
        pb = self.rng.randint(20, 60)
        q = (f"{a} kg of rice at {pa} rupees/kg is mixed with {b} kg of rice at "
             f"{pb} rupees/kg. What is the cost per kg of the mixture?")
        cost = a * pa + b * pb
        wt = a + b
        rate = cost / wt
        steps = [
            f"Total cost = {a} x {pa} + {b} x {pb} = {a*pa} + {b*pb} = {cost}",
            f"Total weight = {a} + {b} = {wt} kg",
            f"Cost per kg = {cost} / {wt} = {_money(rate)}",
        ]
        return steps, _money(rate), rate, q


def _corrupt(steps: list[str], error_type: str, rng: random.Random) -> tuple[list[str], int]:
    """Return corrupted steps and the 1-indexed step that holds the planted flaw."""
    steps = list(steps)
    # choose a step that contains an '=' with a number to the right
    idx = rng.randrange(len(steps))
    import re
    nums = re.findall(r"[-+]?\d[\d,]*\.?\d*", steps[idx])
    if not nums:
        idx = 0
        nums = re.findall(r"[-+]?\d[\d,]*\.?\d*", steps[idx])

    def bump(s: str) -> str:
        last = nums[-1]
        val = float(last.replace(",", ""))
        if error_type == "plausible_but_off":
            delta = max(1.0, round(abs(val) * 0.03, 2))
        else:
            delta = rng.choice([1, 2, 3, 10, 7])
        newval = val + (delta if rng.random() < 0.5 else -delta)
        if "." in last or error_type == "plausible_but_off":
            rep = f"{newval:,.2f}"
        else:
            rep = f"{int(newval):,}"
        # replace only the final occurrence
        head, _, tail = s.rpartition(last)
        return head + rep + tail

    steps[idx] = bump(steps[idx])
    return steps, idx + 1


def generate(n: int = 200, seed: int = 7, flawed_fraction: float = 0.5) -> list[Solution]:
    rng = random.Random(seed)
    factory = ProblemFactory(rng)
    builders = [factory.interest, factory.speed, factory.mixture]
    # shopping returns 3-tuple with embedded question; normalise all to (steps, ans, val, q)
    out: list[Solution] = []
    for i in range(n):
        b = rng.choice(builders)
        res = b()
        if len(res) == 4:
            steps, ans, val, q = res
        else:  # pragma: no cover
            steps, ans, val = res
            q = ""
        pid = f"p{i:04d}"
        flawed = rng.random() < flawed_fraction
        if flawed:
            etype = rng.choice(ERROR_TYPES)
            csteps, estep = _corrupt(steps, etype, rng)
            # final answer should reflect the corrupted chain: just perturb displayed answer too
            bad_ans = ans
            import re
            m = re.findall(r"[-+]?\d[\d,]*\.?\d*", ans)
            if m:
                v = float(m[-1].replace(",", ""))
                nv = v + rng.choice([1, 2, 5, 0.5])
                bad_ans = ans.replace(m[-1], f"{nv:,.2f}" if "." in m[-1] else f"{int(nv):,}")
            out.append(Solution(pid, q, csteps, bad_ans, True, etype, estep,
                                correct_answer=ans, meta={"builder": b.__name__}))
        else:
            out.append(Solution(pid, q, steps, ans, False, None, None,
                                correct_answer=ans, meta={"builder": b.__name__}))
    return out
