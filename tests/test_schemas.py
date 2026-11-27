"""Schemas in docs/schemas match what the code emits (spec §8)."""

import json
import subprocess
import sys
from pathlib import Path

import pytest
from conftest import SCENES, capture_scene
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

SCHEMAS = Path(__file__).resolve().parent.parent / "docs" / "schemas"


def _load():
    docs = {p.name: json.loads(p.read_text(encoding="utf-8")) for p in SCHEMAS.glob("*.json")}
    registry = Registry().with_resources(
        (d["$id"], Resource.from_contents(d)) for d in docs.values()
    )
    return docs, registry


DOCS, REGISTRY = _load()


def validator(name: str) -> Draft202012Validator:
    return Draft202012Validator(DOCS[name], registry=REGISTRY)


@pytest.mark.parametrize("name", sorted(DOCS))
def test_schema_is_valid(name):
    Draft202012Validator.check_schema(DOCS[name])


def test_captured_timeline_matches_schema():
    tl = capture_scene("Lesson", 15).to_dict()
    validator("timeline.schema.json").validate(tl)
    for e in tl["events"]:
        assert e["end_frame"] >= e["start_frame"]  # not expressible in JSON Schema


def runner_lines(scene: str, *extra: str) -> list[dict]:
    proc = subprocess.run(
        [sys.executable, "-m", "manim_stage.runner", str(SCENES / "timing.py"), scene,
         "--fps", "10", "--width", "160", "--height", "90", *extra],
        capture_output=True, text=True, encoding="utf-8",
    )  # fmt: skip
    return [json.loads(line) for line in proc.stdout.splitlines()]


def test_runner_messages_match_schema(tmp_path):
    msgs = runner_lines("MixedRunTimes", "--cache-dir", str(tmp_path))
    msgs += runner_lines("Broken")
    msgs += runner_lines("--list")
    v = validator("runner-message.schema.json")
    for m in msgs:
        v.validate(m)
    assert {m["type"] for m in msgs} == {"hello", "scenes", "timeline", "frame", "done", "error"}


@pytest.mark.parametrize(
    "example, schema",
    [
        ("cues.json", "cues.schema.json"),
        ("project.json", "project.schema.json"),
        ("editable-property.json", "editable-property.schema.json"),
        ("audio.json", "audio.schema.json"),
    ],
)
def test_draft_examples_validate(example, schema):
    doc = json.loads((SCHEMAS / "examples" / example).read_text(encoding="utf-8"))
    validator(schema).validate(doc)


@pytest.mark.parametrize(
    "bad", ["/etc/passwd", "C:/x.py", "../x.py", "a/../../x.py", "a\\b.py", ".."]
)
def test_project_paths_reject_traversal(bad):
    doc = json.loads((SCHEMAS / "examples" / "project.json").read_text(encoding="utf-8"))
    doc["scenes"][0]["file"] = bad
    assert not validator("project.schema.json").is_valid(doc)


@pytest.mark.parametrize("good", ["a.py", "lessons/b.py", "x/..y/c.py", ".manim-stage/cues.json"])
def test_project_paths_accept_relative(good):
    doc = json.loads((SCHEMAS / "examples" / "project.json").read_text(encoding="utf-8"))
    doc["scenes"][0]["file"] = good
    assert validator("project.schema.json").is_valid(doc)
