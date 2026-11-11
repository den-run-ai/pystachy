"""Backend-free widget state checks for original pytest and native execution."""
from miniui import Input, Rect, UI
import pytest


def test_rectangle_bounds_and_intersection():
    rectangle = Rect(10, 20, 5, 6)
    assert rectangle.contains(10, 20)
    assert not rectangle.contains(15, 20)
    overlap = rectangle.intersect(Rect(12, 18, 10, 5))
    assert (overlap.x, overlap.y, overlap.w, overlap.h) == (12, 20, 3, 3)
    assert rectangle.intersect(Rect(30, 40, 1, 1)).w == 0


@pytest.fixture
def ui() -> UI:
    return UI(200, 120)


def test_button_click_requires_press_and_release(ui: UI):
    ui.begin(Input(20, 20, True, True))
    assert not ui.button("run", "Run")
    assert ui.active == "run"
    ui.end()
    ui.begin(Input(20, 20, False, False, True))
    assert ui.button("run", "Run")
    ui.end()
    assert ui.active == ""


def test_frame_and_unique_id_contracts(ui: UI):
    with pytest.raises(RuntimeError, match="begin/end"):
        ui.button("run", "Run")
    ui.begin(Input())
    with pytest.raises(RuntimeError, match="previous frame"):
        ui.begin(Input())
    ui.button("same", "One")
    with pytest.raises(ValueError, match="unique"):
        ui.button("same", "Two")
    ui.end()


def test_escape_cancels_active_control(ui: UI):
    ui.begin(Input(20, 20, True, True))
    ui.button("run", "Run")
    ui.end()
    events = Input(20, 20, False, False, True)
    events.escape = True
    ui.begin(events)
    assert not ui.button("run", "Run")
    assert ui.focus == ""
    ui.end()
