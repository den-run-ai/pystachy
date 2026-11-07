"""Display-free ABI probe; use check_backend.py, not the real graphics library."""
from ffi import extern, c_int, c_uint
from miniui import UI, Rect
from raylib_backend import Window


@extern("./build/miniui/libminiui.so", "mock_events")
def events(x: c_int, y: c_int, mouse: c_int, keys: c_int, focused: c_int) -> None: ...


@extern("./build/miniui/libminiui.so", "mock_stats")
def stats(index: c_int) -> c_int: ...


@extern("./build/miniui/libminiui.so", "mock_color")
def last_color() -> c_uint: ...


@extern("./build/miniui/libminiui.so", "mock_title_copy")
def title_copy() -> c_int: ...


assert title_copy() == 1
window = Window(240, 200, "miniui ABI probe")
assert window.open() and window.dt() == 0.03125
failed = 0
try:
    Window(240, 200, "second window")
except RuntimeError:
    failed += 1
assert failed == 1

events(17, 19, 7, 2047, 1)
value = window.poll()
assert value.x == 17 and value.y == 19
assert value.down and value.pressed and value.released and value.focused
assert value.backspace and value.delete and value.left and value.right
assert value.home and value.end and value.tab and value.shift
assert value.enter and value.space and value.escape
assert value.text == "é🙂"
events(20, 20, 6, 0, 1)
ui = UI(240, 200)
ui.begin(window.poll())
assert ui.textbox("text", "test") == "testé🙂"
ui.rectangle(Rect(15, 120, 20, 20), 0xFEDCBA98)
ui.end()
window.draw(ui)
assert stats(0) == 1 and stats(1) == 1
assert stats(2) >= 3 and stats(3) == 1 and stats(4) >= 3
assert stats(5) == 0 and last_color() == 0xFEDCBA98
# Drawing errors must still pair BeginDrawing/EndDrawing.
ui.begin(window.poll())
ui.rectangle(Rect(10, 10, 20, 20), -1)
ui.end()
try:
    window.draw(ui)
except OverflowError:
    failed += 1
assert failed == 2 and stats(0) == 2 and stats(1) == 2
window.close()
window.close()
assert not window.open() and window.dt() == 0.0
try:
    window.poll()
except RuntimeError:
    failed += 1
assert failed == 3
assert title_copy() == 1
print("miniui backend: scalar ABI, input, RGBA, title ownership, cleanup passed")
