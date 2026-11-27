"""Animation classification and metadata (backlog MF.2, ADR-0011)."""

import functools

import pytest
from conftest import capture_scene
from manim import (
    UP,
    AnimationGroup,
    ChangeSpeed,
    Circle,
    Circumscribe,
    Create,
    FadeIn,
    GrowFromCenter,
    LaggedStart,
    MoveAlongPath,
    Rotate,
    Square,
    Transform,
    TransformMatchingShapes,
    UpdateFromAlphaFunc,
    Wait,
    Write,
    rate_functions,
)
from manim.animation.animation import Animation

from manim_stage.catalog import (
    CATEGORY_LABELS,
    animation_category,
    animation_info,
    rate_func_name,
    sample_rate_func,
)


class MyFade(FadeIn):
    pass


class Custom(Animation):
    pass


@pytest.mark.parametrize(
    "cls, cat",
    [
        (Create, "creation"), (Write, "creation"), (FadeIn, "fading"), (MyFade, "fading"),
        (Transform, "transform"), (TransformMatchingShapes, "transform"),
        (Circumscribe, "indication"), (MoveAlongPath, "movement"), (Rotate, "rotation"),
        (GrowFromCenter, "growing"), (AnimationGroup, "composition"),
        (LaggedStart, "composition"), (ChangeSpeed, "speedmodifier"),
        (UpdateFromAlphaFunc, "updaters"), (Wait, "wait"), (Custom, "custom"),
    ],
)  # fmt: skip
def test_category_follows_manim_modules(cls, cat):
    assert animation_category(cls) == cat
    assert cat in CATEGORY_LABELS


def test_animate_build_records_method_chain():
    anim = Square().animate.shift(UP).scale(2).build()
    info = animation_info(anim)
    assert info["class"] == ".animate" and info["category"] == "animate"
    assert info["methods"] == ["shift", "scale"]
    assert info["mobject"] == "Square"


def test_rate_function_name_and_curve():
    info = animation_info(FadeIn(Circle(), run_time=2, rate_func=rate_functions.there_and_back))
    assert info["rate_func"] == "there_and_back" and info["rate_func_builtin"]
    curve = info["rate_curve"]
    assert len(curve) == 33 and curve[0] == 0 and curve[16] == pytest.approx(1, abs=1e-3)
    assert info["run_time"] == 2.0 and info["mobject"] == "Circle"
    assert info.get("introducer") is True


def test_custom_and_partial_rate_funcs():
    def ease(t):
        return t * t

    assert rate_func_name(ease) == "ease"
    assert rate_func_name(lambda t: t) == "<lambda>"
    assert rate_func_name(functools.partial(rate_functions.squish_rate_func)) == (
        "squish_rate_func")  # fmt: skip

    def broken(t):
        raise ValueError

    assert sample_rate_func(broken) is None


def test_lag_ratio_and_named_mobject():
    sq = Square(name="pivot")
    info = animation_info(LaggedStart(FadeIn(sq), FadeIn(Circle()), lag_ratio=0.25))
    assert info["lag_ratio"] == 0.25
    assert animation_info(FadeIn(sq))["mobject_name"] == "pivot"


def test_capture_attaches_animation_info():
    tl = capture_scene("Nested", 15)
    play = tl.events[0]
    assert play.kind == "play"
    assert [a["class"] for a in play.meta["animations"]] == ["AnimationGroup"]
    children = [e for e in tl.events if e.kind == "animation"]
    assert children and all(e.meta["animation"]["class"] for e in children)
    fades = [e for e in children if e.meta["animation"]["class"] == "FadeIn"]
    assert {e.meta["animation"]["category"] for e in fades} == {"fading"}
    assert {e.meta["animation"]["mobject"] for e in fades} == {"Square", "Circle", "Triangle"}
