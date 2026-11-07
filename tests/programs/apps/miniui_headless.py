"""Exercise the real widget core without importing FFI or a display backend."""
from miniui import UI, Input, Rect


def buttons() -> None:
    ui = UI(240, 200)
    ui.begin(Input(20, 20, True, True))
    assert not ui.button("a", "Same label")
    ui.end()
    assert ui.active == "a"
    ui.begin(Input(239, 199, False, False, True))
    assert not ui.button("a", "Same label")
    ui.end()
    assert ui.active == ""
    ui.begin(Input(20, 20, False, True, True))
    assert ui.button("a", "Same label")
    assert not ui.button("b", "Same label")
    ui.end()
    ui.begin(Input(20, 20, False, False, True))
    assert not ui.button("a", "Same label")
    ui.end()
    ui.begin(Input(20, 20, False, True, True))
    assert not ui.button("a", "Disabled", False)
    ui.end()
    assert ui.focus == ""
    print("buttons: capture, release, fast click, disabled, distinct IDs")


def keyboard() -> None:
    ui = UI(240, 200)
    ui.begin(Input())
    ui.button("a", "First")
    ui.button("b", "Second")
    ui.end()
    events = Input()
    events.tab = True
    ui.begin(events)
    ui.button("a", "First")
    ui.button("b", "Second")
    ui.end()
    assert ui.focus == "a"
    events = Input()
    events.enter = True
    ui.begin(events)
    assert ui.button("a", "First")
    assert not ui.button("b", "Second")
    ui.end()
    events = Input()
    events.tab = True
    events.shift = True
    ui.begin(events)
    ui.button("a", "First")
    ui.button("b", "Second")
    ui.end()
    assert ui.focus == "b"
    ui.begin(Input())
    ui.button("a", "First")
    ui.end()
    assert ui.focus == ""
    other = UI(240, 200)
    assert other.focus == ""
    print("keyboard: tab, reverse wrap, enter, removed focus, isolated contexts")


def checkbox_and_identity() -> None:
    ui = UI(240, 200)
    ui.begin(Input(20, 20, True, True))
    value = ui.checkbox("check", "Enabled", False)
    ui.end()
    assert not value
    ui.begin(Input(20, 20, False, False, True))
    value = ui.checkbox("check", "Enabled", value)
    ui.end()
    assert value
    ui.begin(Input(20, 20, True, True))
    ui.row([0, 0])
    ui.button("a", "A")
    ui.button("b", "B")
    ui.end()
    ui.begin(Input(20, 20, False, False, True))
    ui.row([0, 0])
    assert not ui.button("b", "B")
    assert not ui.button("a", "A")
    ui.end()
    print("checkbox and identity: release-only toggle; IDs survive reordered layout")


def sliders() -> None:
    ui = UI(240, 200)
    ui.begin(Input(120, 20, True, True))
    value = ui.slider("speed", 0.0, 0.0, 1.0)
    ui.end()
    assert value == 0.5
    ui.begin(Input(500, 500, True))
    value = ui.slider("speed", value, 0.0, 1.0)
    ui.end()
    assert value == 1.0
    ui.begin(Input(-100, 20, False, False, True))
    value = ui.slider("speed", value, 0.0, 1.0)
    ui.end()
    assert value == 0.0 and ui.active == ""
    events = Input()
    events.right = True
    ui.begin(events)
    value = ui.slider("speed", value, 0.0, 1.0)
    ui.end()
    assert value == 0.01
    ui.begin(Input(20, 20, True, True))
    assert ui.slider("same", 10.0, 2.0, 2.0) == 2.0
    assert ui.slider("disabled", 0.3, 0.0, 1.0, False) == 0.3
    ui.end()
    print("sliders: capture, clamp, keyboard step, equal bounds, disabled")


def text_editing() -> None:
    ui = UI(240, 200)
    ui.begin(Input(20, 20, False, True, True))
    value = ui.textbox("text", "A")
    ui.end()
    ui.begin(Input(text="é🙂"))
    value = ui.textbox("text", value)
    ui.end()
    assert value == "Aé🙂" and ui.cursor == 3
    events = Input()
    events.backspace = True
    ui.begin(events)
    value = ui.textbox("text", value)
    ui.end()
    assert value == "Aé"
    events = Input(text="Z")
    events.home = True
    ui.begin(events)
    value = ui.textbox("text", value)
    ui.end()
    assert value == "ZAé" and ui.cursor == 1
    events = Input()
    events.delete = True
    ui.begin(events)
    value = ui.textbox("text", value)
    ui.end()
    assert value == "Zé"
    events = Input(text="\x00\n\tQRS")
    events.end = True
    ui.begin(events)
    value = ui.textbox("text", value, 4)
    ui.end()
    assert value == "ZéQR"
    ui.begin(Input())
    value = ui.textbox("text", "x", 4)
    ui.end()
    assert value == "x" and ui.cursor == 1
    events = Input()
    events.enter = True
    ui.begin(events)
    assert ui.textbox("text", value) == "x"
    ui.end()
    assert ui.focus == ""
    ui.begin(Input(text="ignored"))
    assert ui.textbox("text", value) == "x"
    ui.end()
    print("text: Unicode code points, insertion, deletion, capacity, commit")


def focus_loss() -> None:
    ui = UI(240, 200)
    ui.begin(Input(20, 20, True, True))
    ui.slider("drag", 0.0, 0.0, 1.0)
    ui.end()
    events = Input(200, 20, True)
    events.focused = False
    ui.begin(events)
    assert ui.slider("drag", 0.3, 0.0, 1.0) == 0.3
    ui.end()
    assert ui.active == "" and ui.focus == ""
    ui.begin(Input(20, 20, True, True))
    ui.button("gone", "Temporary")
    ui.end()
    ui.begin(Input(20, 20, True))
    ui.label("Gone")
    ui.end()
    assert ui.active == "" and ui.focus == ""
    ui.begin(Input(20, 20, True, True))
    ui.button("cancel", "Cancel")
    ui.end()
    events = Input(20, 20, True)
    events.escape = True
    ui.begin(events)
    ui.button("cancel", "Cancel")
    ui.end()
    assert ui.active == "" and ui.focus == ""
    print("focus loss: window blur, disappearing control, escape cancellation")


def layout_and_drawing() -> None:
    ui = UI(240, 90)
    ui.begin(Input(20, 86, False, True, True))
    ui.row([40, 0, 0])
    ui.label("one")
    ui.label("two")
    ui.label("three")
    assert ui.widths == [40, 82, 82]
    ui.row([0])
    ui.panel("section")
    assert not ui.button("clipped", "Outside content")
    ui.progress(2.0)
    ui.rectangle(Rect(-20, -20, 60, 60), 0x11223344)
    ui.end()
    assert len(ui.commands) > 7
    assert ui.commands[-1].color == 0x11223344
    clip = ui.commands[-1].rect.intersect(ui.commands[-1].clip)
    assert clip.x == 10 and clip.y == 10 and clip.w == 30 and clip.h == 30
    assert not Rect(0, 0, 10, 10).contains(10, 5)
    assert Rect(0, 0, 0, 10).intersect(Rect(1, 1, 10, 10)).w == 0
    print("drawing: flexible rows, clipping, progress, rectangle, RGBA")


def invalid_usage() -> None:
    ui = UI(240, 200)
    failed = 0
    try:
        ui.button("a", "No frame")
    except RuntimeError:
        failed += 1
    ui.begin(Input())
    try:
        ui.begin(Input())
    except RuntimeError:
        failed += 1
    ui.button("a", "One")
    try:
        ui.button("a", "Duplicate")
    except ValueError:
        failed += 1
    try:
        ui.button("", "Empty")
    except ValueError:
        failed += 1
    try:
        ui.row([500])
    except ValueError:
        failed += 1
    try:
        ui.row([-1])
    except ValueError:
        failed += 1
    try:
        ui.slider("bad", 0.0, 1.0, 0.0)
    except ValueError:
        failed += 1
    try:
        ui.slider("nan", float("nan"), 0.0, 1.0)
    except ValueError:
        failed += 1
    try:
        ui.progress(float("inf"))
    except ValueError:
        failed += 1
    try:
        ui.textbox("badtext", "nul\x00")
    except ValueError:
        failed += 1
    ui.end()
    try:
        ui.end()
    except RuntimeError:
        failed += 1
    assert failed == 11
    print("validation: lifecycle, IDs, layout, finite values, NUL")


buttons()
keyboard()
checkbox_and_identity()
sliders()
text_editing()
focus_loss()
layout_and_drawing()
invalid_usage()
print("miniui: 8 headless scenarios passed")
