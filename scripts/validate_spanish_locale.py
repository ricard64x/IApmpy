"""Validate that the Spanish locale matches the English message schema."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "locales"
VARIABLE = re.compile(r"\{([a-zA-Z_][a-zA-Z_0-9]*)\}")

def load(name: str):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))

def check(reference, translated, key="root"):
    if isinstance(reference, dict):
        assert isinstance(translated, dict), f"{key}: expected object"
        assert set(reference) == set(translated), f"{key}: translation keys differ: {set(reference)^set(translated)}"
        for child in reference:
            check(reference[child], translated[child], f"{key}.{child}")
        return
    if isinstance(reference, list):
        assert isinstance(translated, list), f"{key}: expected list"
        assert len(reference) == len(translated), f"{key}: array length mismatch"
        for i, (ref, value) in enumerate(zip(reference, translated)):
            check(ref, value, f"{key}[{i}]")
        return
    assert isinstance(reference, str) and isinstance(translated, str), f"{key}: expected string"
    assert translated.strip(), f"{key}: empty translation"
    assert sorted(VARIABLE.findall(reference)) == sorted(VARIABLE.findall(translated)), (
        f"{key}: interpolation variables mismatch"
    )

if __name__ == "__main__":
    languages = load("languages.json")
    assert languages["es"]["label"] == "Español"
    check(load("en.json"), load("es.json"))
    print("Spanish locale validated: keys, arrays and interpolation variables match English.")
