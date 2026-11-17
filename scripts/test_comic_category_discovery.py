#!/usr/bin/env python3
"""Offline tests for the manual comics category discovery model.

No API key, no DeepSeek request, no MotherDuck connection.

Usage: python scripts/test_comic_category_discovery.py   (exit 0 = every check passed)

It runs top-to-bottom on import, so execute it — do not `import` it for reuse.
"""
import importlib.util
import json
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
path = REPO_ROOT / "transformation_dbt/domain_data_products/models/comics/staging/stg_comics_categories.py"
spec = importlib.util.spec_from_file_location("category_model", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

names = ["Gaming", "Technology", "Science and mathematics", "Geek culture",
         "Everyday life", "Other / unclear"]
valid = {"categories": [{"name": name, "definition": f"Main topic is {name}."}
                         for name in names]}


class FakeLLM:
    def __init__(self, response=valid):
        self.calls = []
        self.response = response

    def invoke(self, messages):
        self.calls.append(messages)
        return self.response


frame = pd.DataFrame([
    {"num": 1, "year": "2005", "title": "OLD_MARKER", "alt": "TOOLTIP_MARKER",
     "transcript": "x" * 55000 + "END_MARKER"},
    {"num": 2, "year": "2026", "title": "NEW_MARKER", "alt": None,
     "transcript": None},
])
parts = list(module.comic_inputs(frame))
assert len(parts) > len(frame)  # long comic split into multiple parts
assert "END_MARKER" in "".join(parts)  # tail not truncated
assert "TOOLTIP_MARKER" in "".join(parts)
assert "NEW_MARKER" in "".join(parts)
assert all(len(batch) <= 24000 for batch in module.pack_batches(parts))
mock = FakeLLM()
result = module.discover(frame, mock)
assert list(result.columns) == ["category_id", "category_name", "definition"]
assert len(result) == 6
assert result.category_id.is_unique
assert len(mock.calls) > 2  # all comic batches plus final merge
assert "END_MARKER" in "\n".join(call[1][1] for call in mock.calls)

# Empty input and duplicate category names must fail, not save broken output.
for bad_frame, response in [
    (frame.iloc[:0], valid),
    (frame, {"categories": [valid["categories"][0]] * 6}),
]:
    try:
        module.discover(bad_frame, FakeLLM(response))
    except ValueError:
        pass
    else:
        raise AssertionError("Expected a validation error")

# Exercise hierarchical suggestion reduction with many large batches.
large_frame = pd.DataFrame([
    {"num": i, "year": "2024", "title": f"Comic {i}", "alt": "Tooltip",
     "transcript": "y" * 23000}
    for i in range(60)
])
large_response = {"categories": [{"name": name, "definition": "d" * 300}
                                  for name in names]}
large_mock = FakeLLM(large_response)
assert len(module.discover(large_frame, large_mock)) == 6
assert any("Merge these proposed" in call[1][1] for call in large_mock.calls)

# Over-long provider definitions must be trimmed, not abort the paid run
# (observed live on 2026-11-17: a 370-char definition failed Pydantic validation).
long_definition = (
    "Comics primarily about computers, software, programming, the internet, digital culture, "
    "or the tech industry. This includes topics like programming languages, file formats, "
    "software behavior, online platforms, and tech-related humor. Excludes gaming unless the "
    "primary focus is on the technology itself."
)
assert len(long_definition) > 300
assert len(module.fit_text(long_definition, 300)) <= 300
assert module.fit_text(long_definition, 300).endswith(".")
assert module.fit_text("  spaced\n\ttext  ", 300) == "spaced text"
long_response = {"categories": [{"name": name, "definition": long_definition}
                                for name in names]}
assert module.discover(frame.iloc[:2], FakeLLM(long_response)).definition.map(len).max() <= 300

# An 11-category merge answer must be capped, not abort the run
# (observed live on run #2 2026-11-17: `too_long` after 83 paid batches).
from types import SimpleNamespace


class RawOnlyLLM:
    """Mimics include_raw=True when the parsed half is None."""

    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def invoke(self, messages):
        self.calls.append(messages)
        return {"raw": SimpleNamespace(content=json.dumps(self.payload)),
                "parsed": None, "parsing_error": ValueError("too_long")}


extra = ["History", "Work", "Society", "Art", "Language"]
eleven = {"categories": [{"name": name, "definition": "One concise sentence."}
                         for name in names + extra]}
assert len(eleven["categories"]) == 11
capped = module.discover(frame.iloc[:2], RawOnlyLLM(eleven))
assert len(capped) == 10 and capped.category_id.is_unique
assert (capped.category_name == "Other / unclear").sum() == 1

# A missing fallback is restored; duplicates collapse to one row.
no_fallback = {"categories": [{"name": name, "definition": "One concise sentence."}
                              for name in names[:5]] + [{"name": "Gaming",
                                                         "definition": "Duplicate."}]}
restored = module.discover(frame.iloc[:2], FakeLLM(no_fallback))
assert len(restored) == 6 and (restored.category_name == "Other / unclear").sum() == 1

# Validate the actual installed LangChain wrapper WITHOUT invoking it.
from langchain_deepseek import ChatDeepSeek
wrapper = ChatDeepSeek(model="deepseek-chat", api_key="offline-test-not-a-real-key",
                      temperature=0).with_structured_output(
                          module.CategoryList, method="json_mode", include_raw=True)
assert wrapper is not None

print(json.dumps({"status": "PASS", "checks": [
    "Every comic included; long-text tail preserved", "Bounded batches",
    "Category-only output", "Empty input rejected", "Duplicate categories rejected",
    "Hierarchical merge exercised", "Installed ChatDeepSeek JSON wrapper constructed offline"
], "not_tested": ["Actual LLM output quality", "dbt compile", "MotherDuck execution"],
"api_calls": 0}, indent=2))