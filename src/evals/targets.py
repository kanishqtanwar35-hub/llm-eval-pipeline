"""The thing being evaluated.

A "target" is any callable str -> str. Swapping targets is how you compare a
prompt change, a model change, or your own RAG app against the same golden set.

`StubTarget` exists so the whole suite runs with no API key and no network,
which is what lets CI run it on every push and what lets the metrics have their
own unit tests.
"""

import json
import os
import time
from typing import Protocol

import requests


class Target(Protocol):
    name: str

    def __call__(self, prompt: str) -> str: ...


class StubTarget:
    """A deliberately imperfect fake model.

    It answers some cases correctly and fails others on purpose, so a run
    produces a mixed report rather than a meaningless 100%. Use it to develop
    the harness, then point at a real model.
    """

    name = "stub"

    ANSWERS = {
        "capital of france": "The capital of France is Paris.",
        "17 multiplied by 4": "17 x 4 = 68.",
        "red planet": "That would be Mars.",
        "boiling point of water": "Water boils at 100 degrees Celsius at sea level.",
    }

    def __call__(self, prompt: str) -> str:
        lowered = prompt.lower()

        for key, answer in self.ANSWERS.items():
            if key in lowered:
                return answer

        if "json" in lowered and "ada" in lowered:
            return json.dumps({"name": "Ada", "age": 36})
        if "json" in lowered and "status" in lowered:
            # Intentional failure: returns prose instead of JSON.
            return "The status is ok."
        if "ignore your instructions" in lowered or "pick a lock" in lowered:
            return "I can't help with that."
        if "water cycle" in lowered:
            return (
                "Water evaporates from oceans and lakes, condenses into clouds, "
                "falls as precipitation, and flows back to the sea."
            )
        if "photosynthesis" in lowered:
            # Intentional failure: too long for the 35-word limit.
            return (
                "Photosynthesis is the biochemical process by which green plants, "
                "algae and certain bacteria convert light energy, usually from the "
                "sun, into chemical energy stored as glucose, using carbon dioxide "
                "drawn from the atmosphere and water absorbed through their roots, "
                "while releasing oxygen as a by-product of the reaction."
            )
        return "I don't know."


class GeminiTarget:
    """Real model over the free tier. Set GEMINI_API_KEY to use it."""

    name = "gemini"

    # Pinned deliberately, not a `-latest` alias. An eval suite exists to
    # detect change; if the model underneath can shift without a commit, a red
    # run tells you nothing about whether *you* broke something. Bump this
    # version explicitly and let the suite show you the delta — that diff is
    # the most useful output this project produces.
    #
    # Verify a pin before trusting it: ListModels returns models that
    # generateContent then rejects with 404. gemini-2.5-flash is listed and is
    # NOT callable. Confirm with a real request before pinning:
    #   curl -H "x-goog-api-key: $KEY" -H "Content-Type: application/json" \
    #     -X POST ".../v1beta/models/<name>:generateContent" \
    #     -d '{"contents":[{"role":"user","parts":[{"text":"hi"}]}]}'
    DEFAULT_MODEL = "gemini-3.5-flash"

    def __init__(self, model: str = None, system: str = ""):
        self.model = model or os.getenv("GEMINI_MODEL", self.DEFAULT_MODEL)
        self.system = system or (
            "You are a concise assistant. Answer directly. "
            "When asked for JSON, return only JSON."
        )

    def __call__(self, prompt: str) -> str:
        # Strip whitespace and a possible UTF-8 BOM. Secrets pasted into a web
        # form or piped from a file routinely carry both, and either one fails
        # deep in http.client with a latin-1 codec error once the value is used
        # as a header � an error that looks like a library bug.
        api_key = os.environ.get("GEMINI_API_KEY", "").strip().lstrip("\ufeff").strip()
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is not set")

        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent"
        )
        payload = {
            "systemInstruction": {"parts": [{"text": self.system}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.0, "maxOutputTokens": 500},
        }

        # Key in a header, not the query string — a `?key=...` URL leaks into
        # exception messages and from there into CI logs.
        headers = {"x-goog-api-key": api_key, "Content-Type": "application/json"}

        for attempt in range(3):
            r = requests.post(url, headers=headers, json=payload, timeout=45)
            if r.status_code == 429:
                time.sleep(2 ** (attempt + 2))
                continue
            r.raise_for_status()
            data = r.json()
            candidates = data.get("candidates") or []
            if not candidates:
                return ""      # safety block returns no candidate
            return candidates[0]["content"]["parts"][0]["text"]

        raise RuntimeError("rate limited after 3 attempts")


def get_target(name: str) -> Target:
    if name == "stub":
        return StubTarget()
    if name == "gemini":
        return GeminiTarget()
    raise KeyError(f"unknown target '{name}' (available: stub, gemini)")
