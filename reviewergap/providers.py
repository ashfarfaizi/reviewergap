"""Model providers behind one small interface.

Every provider implements complete(system, user) -> str. The MockProvider needs
no API key and no network, so the whole pipeline runs offline for testing and
demos. Real providers read their key from an environment variable.
"""
from __future__ import annotations

import json
import os
import re
import urllib.request


class Provider:
    name = "base"

    def complete(self, system: str, user: str) -> str:
        raise NotImplementedError


class MockProvider(Provider):
    """A deterministic, offline stand-in for a reviewer model.

    It is intentionally imperfect, so results look realistic. It recomputes each
    'X op Y = Z' step and flags the first arithmetic mismatch it finds, but it
    only catches errors above a tolerance, so small 'plausible_but_off' slips
    usually slip past, exactly the blind spot the study is about. A tunable miss
    rate adds noise so same-vs-different reviewer comparisons are non-trivial.
    """
    def __init__(self, name="mock", miss_rate=0.15, tol=0.5, seed=0):
        self.name = name
        self.miss_rate = miss_rate
        self.tol = tol
        import random
        self.rng = random.Random(seed)

    def complete(self, system: str, user: str) -> str:
        steps = re.findall(r"Step (\d+): (.+)", user)
        verdict_step = 0
        # Only evaluate a well-formed "a op b = c" at the END of a step. Steps with
        # chained operations (e.g. "(P x R x T)/100 = ...") are skipped rather than
        # guessed at -- a deliberate blind spot that keeps false positives near zero.
        end_expr = re.compile(
            r"([-+]?\d[\d,]*\.?\d*)\s*([x*/+\-])\s*([-+]?\d[\d,]*\.?\d*)\s*=\s*([-+]?\d[\d,]*\.?\d*)\s*$")
        for num, text in steps:
            m = end_expr.search(text.strip())
            if not m:
                continue
            ga, op, gb, gc = m.groups()
            a, b, claimed = (float(x.replace(",", "")) for x in (ga, gb, gc))
            try:
                real = {"x": a*b, "*": a*b, "/": a/b, "+": a+b, "-": a-b}[op]
            except ZeroDivisionError:
                continue
            if abs(real - claimed) > self.tol and self.rng.random() > self.miss_rate:
                verdict_step = int(num)
                break
        if verdict_step:
            return json.dumps({"verdict": "flawed", "error_step": verdict_step,
                               "explanation": f"Step {verdict_step} does not compute correctly."})
        return json.dumps({"verdict": "correct", "error_step": 0,
                           "explanation": "All steps check out."})


class _HTTPProvider(Provider):
    def _post(self, url, headers, payload):
        data = json.dumps(payload).encode()
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read().decode())


class AnthropicProvider(_HTTPProvider):
    def __init__(self, model="claude-sonnet-5-5", name=None):
        self.model = model
        self.name = name or f"anthropic:{model}"
        self.key = os.environ.get("ANTHROPIC_API_KEY", "")
        self.base = os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com").rstrip("/")

    def complete(self, system, user):
        body = {"model": self.model, "max_tokens": 1024, "system": system,
                "messages": [{"role": "user", "content": user}]}
        out = self._post(f"{self.base}/v1/messages",
                         {"x-api-key": self.key, "anthropic-version": "2023-06-01",
                          "content-type": "application/json"}, body)
        return "".join(b.get("text", "") for b in out.get("content", []))


class GeminiProvider(_HTTPProvider):
    def __init__(self, model="gemini-3.5-flash-lite", name=None):
        self.model = model
        self.name = name or f"gemini:{model}"
        self.key = os.environ.get("GEMINI_API_KEY", os.environ.get("GOOGLE_API_KEY", ""))

    def complete(self, system, user):
        url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
               f"{self.model}:generateContent?key={self.key}")
        body = {"systemInstruction": {"parts": [{"text": system}]},
                "contents": [{"role": "user", "parts": [{"text": user}]}]}
        out = self._post(url, {"content-type": "application/json"}, body)
        return "".join(p.get("text", "")
                       for p in out["candidates"][0]["content"]["parts"])


class OpenAICompatibleProvider(_HTTPProvider):
    """Works with OpenAI, DeepSeek, Qwen, Together, etc. via base_url + key env."""
    def __init__(self, model, base_url, key_env, name=None):
        self.model = model
        self.base = base_url.rstrip("/")
        self.key = os.environ.get(key_env, "")
        self.name = name or f"openai:{model}"

    def complete(self, system, user):
        body = {"model": self.model,
                "messages": [{"role": "system", "content": system},
                             {"role": "user", "content": user}]}
        out = self._post(f"{self.base}/chat/completions",
                         {"Authorization": f"Bearer {self.key}",
                          "content-type": "application/json"}, body)
        return out["choices"][0]["message"]["content"]


def build(spec: str) -> Provider:
    """spec examples: mock, mock:miss=0.3, anthropic:claude-sonnet-5-5, gemini:gemini-3.5-flash-lite"""
    kind, _, rest = spec.partition(":")
    if kind == "mock":
        kw = {}
        for part in rest.split(","):
            if "=" in part:
                k, v = part.split("=")
                kw[k] = float(v) if k in {"miss", "tol"} else v
        return MockProvider(name=spec, miss_rate=kw.get("miss", 0.15),
                            tol=kw.get("tol", 0.5), seed=int(kw.get("seed", 0)))
    if kind == "anthropic":
        return AnthropicProvider(model=rest or "claude-sonnet-5-5")
    if kind == "gemini":
        return GeminiProvider(model=rest or "gemini-3.5-flash-lite")
    if kind == "openai":
        model, _, base = rest.partition("@")
        return OpenAICompatibleProvider(model=model, base_url=base or "https://api.openai.com/v1",
                                        key_env="OPENAI_API_KEY")
    raise ValueError(f"unknown provider spec: {spec}")
