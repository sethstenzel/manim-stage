"""Introspected catalog (MF.1) and Library tab (MF.4)."""

import json

import manim
import pytest

from manim_stage import catalog as cat_mod


@pytest.fixture(scope="module")
def cat():
    return cat_mod.build_catalog()


def test_every_public_manim_name_is_catalogued_once(cat):
    """Coverage: ``from manim import *`` has no ``__all__``; every public name counts."""
    public = {n for n in dir(manim) if not n.startswith("_")}
    seen: dict[str, str] = {}
    for kind, entries in cat["kinds"].items():
        if kind == "manim_stage":
            continue
        for e in entries:
            if kind == "rate_functions" and e["snippet"].endswith(f"rate_functions.{e['name']})"):
                continue  # from manim.rate_functions, not star-exported
            assert e["name"] not in seen, f"{e['name']} in {seen.get(e['name'])} and {kind}"
            seen[e["name"]] = kind
    assert set(seen) == public
    json.dumps(cat)  # JSON-safe


def test_classification_and_metadata(cat):
    by = {(e["kind"], e["name"]): e for es in cat["kinds"].values() for e in es}
    assert by[("mobjects", "Circle")]["group"] == "geometry"
    assert (
        by[("mobjects", "MathTex")]["needs_latex"] and not by[("mobjects", "Text")]["needs_latex"]
    )
    assert by[("mobjects", "Sphere")]["three_d"]
    assert by[("animations", "FadeIn")]["group"] == "fading"
    assert by[("animations", "Transform")]["snippet"] == "self.play(Transform(mobject))"
    assert by[("scenes", "MovingCameraScene")]["snippet"].startswith(
        "class MyScene(MovingCameraScene)"
    )
    assert by[("colors", "BLUE")]["hex"].upper().startswith("#58C4DD")
    smooth = by[("rate_functions", "smooth")]
    assert smooth["curve"][0] == 0 and smooth["curve"][-1] == 1
    assert by[("rate_functions", "ease_in_sine")]["snippet"].endswith(
        "rate_functions.ease_in_sine)"
    )
    assert ("cameras", "MovingCamera") in by
    assert by[("manim_stage", "Array")]["snippet"] == "from manim_stage.edu import Array"
    assert "docs.manim.community" in by[("mobjects", "Circle")]["docs"]


def test_search_ranks_exact_names_first(cat):
    names = [e["name"] for e in cat_mod.search("fadein", cat)]
    assert names[0] == "FadeIn"
    assert {"FadeIn", "FadeOut"} <= {e["name"] for e in cat_mod.search("fade", cat)}


def test_cli_catalog(capsys):
    from manim_stage.cli import main

    assert main(["catalog", "smooth", "--kind", "rate_functions"]) == 0
    out = capsys.readouterr().out
    assert "smooth" in out and "entries" in out


def test_library_tab_search_and_copy(qtbot, tmp_path):
    from PySide6.QtGui import QGuiApplication

    from manim_stage.studio.ui.library_panel import LibraryPanel

    panel = LibraryPanel()
    qtbot.addWidget(panel)
    panel.show()
    assert panel.cat is not None  # built when shown
    panel.search.setText("ease_in_out_sine")
    e = panel.current()
    assert e and e["name"] == "ease_in_out_sine" and panel.curve.isVisibleTo(panel)
    panel.copy()
    assert "rate_functions.ease_in_out_sine" in QGuiApplication.clipboard().text()
    panel.search.setText("Circle")
    assert panel.current()["name"] == "Circle" and not panel.curve.isVisibleTo(panel)
    assert "Circle(" in panel.snippet.toPlainText()
    panel.search.setText("")
    assert panel.tree.topLevelItemCount() == len(cat_mod.KINDS)
