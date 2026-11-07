"""Display-free ABI probe; use check_backend.py, not the real graphics library."""
from ffi import extern, c_int, c_uint
from miniui import UI, Rect, Input, Command
from raylib_backend import Window
from demo import main as demo_main


@extern("libminiui.so", "mock_events")
def events(x: c_int, y: c_int, mouse: c_int, keys: c_int, focused: c_int) -> None: ...


@extern("libminiui.so", "mock_stats")
def stats(index: c_int) -> c_int: ...


@extern("libminiui.so", "mock_color")
def last_color() -> c_uint: ...


@extern("libminiui.so", "mock_title_copy")
def title_copy() -> c_int: ...


@extern("libminiui.so", "mock_reset")
def reset() -> None: ...


@extern("libminiui.so", "mock_limit_frames")
def limit_frames(frames: c_int) -> None: ...


@extern("libminiui.so", "mock_trace")
def trace(index: c_int, field: c_int) -> c_int: ...


@extern("libminiui.so", "mock_trace_color")
def trace_color(index: c_int) -> c_uint: ...


@extern("libminiui.so", "mock_text_equals")
def text_equals(index: c_int, text: str) -> c_int: ...


def check_draw(index: int, kind: int, x: int, y: int, w: int, h: int,
               clip: Rect, color: int) -> None:
    expected = [kind, x, y, w, h, clip.x, clip.y, clip.w, clip.h]
    for field in range(len(expected)):
        assert trace(index, field) == expected[field]
    assert trace_color(index) == color


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
assert stats(5) == 0 and stats(6) == 1 and last_color() == 0xFEDCBA98

# Adjacent rectangles share their container clip, including overlapping geometry.
# Changing clip still preserves submission order. Text/caret keep narrow bounds.
reset()
ui.begin(Input())
root_clip = ui.clip
nested_clip = Rect(30, 30, 30, 30)
text_clip = Rect(32, 34, 16, 18)
ui.rectangle(Rect(0, 0, 40, 40), 0xFEDCBA98)
ui.rectangle(Rect(20, 20, 40, 40), 0xFF000080)
ui.rectangle(Rect(-100, -100, 10, 10), 0xFFFFFFFF)
ui.rectangle(Rect(10, 10, 0, 10), 0xFFFFFFFF)
ui.clip = nested_clip
ui.rectangle(Rect(20, 20, 40, 40), 0x00FF0080)
ui.commands.append(Command(1, text_clip, nested_clip, 0xFFFFFFFF, "abcdef", 18, 6))
ui.commands.append(Command(1, text_clip, nested_clip, 0xFFFFFFFF, "next", 18))
ui.clip = root_clip
ui.rectangle(Rect(10, 10, 5, 5), 0x12345678)
ui.end()
window.draw(ui)
assert stats(0) == 1 and stats(1) == 1 and stats(5) == 0
assert stats(2) == 5 and stats(3) == 2 and stats(8) == 7
assert stats(4) == 4 and stats(6) == 1 and stats(7) == 1
check_draw(0, 1, 0, 0, 40, 40, root_clip, 0xFEDCBA98)
check_draw(1, 1, 20, 20, 40, 40, root_clip, 0xFF000080)
check_draw(2, 1, 20, 20, 40, 40, nested_clip, 0x00FF0080)
check_draw(3, 2, -8, 34, 18, 0, text_clip, 0xFFFFFFFF)
assert text_equals(3, "abcdef") == 1
check_draw(4, 1, 46, 34, 1, 18, text_clip, 0xFFFFFFFF)
check_draw(5, 2, 32, 34, 18, 0, text_clip, 0xFFFFFFFF)
assert text_equals(5, "next") == 1
check_draw(6, 1, 10, 10, 5, 5, root_clip, 0x12345678)

reset()
ui.begin(Input())
for i in range(150):
    ui.rectangle(Rect(20 + i, 100, 3, 3), 0x66C2FFFF)
ui.end()
window.draw(ui)
assert stats(2) == 150 and stats(4) == 1 and stats(6) == 1
assert stats(5) == 0 and stats(8) == 150
for i in range(150):
    check_draw(i, 1, 20 + i, 100, 3, 3, root_clip, 0x66C2FFFF)

# Empty and fully culled frames still clear/end, without entering scissor mode.
for empty in (True, False):
    reset()
    ui.begin(Input())
    if not empty:
        ui.rectangle(Rect(500, 500, 10, 10), 0xFFFFFFFF)
    ui.end()
    window.draw(ui)
    assert stats(0) == 1 and stats(1) == 1 and stats(5) == 0
    assert stats(4) == 0 and stats(6) == 0 and stats(8) == 0

reset()
# Drawing errors must still pair BeginDrawing/EndDrawing.
ui.begin(window.poll())
ui.rectangle(Rect(10, 10, 20, 20), -1)
ui.end()
try:
    window.draw(ui)
except OverflowError:
    failed += 1
assert failed == 2 and stats(0) == 1 and stats(1) == 1
assert stats(4) == 1 and stats(6) == 1 and stats(5) == 0
# A failed frame must not leave stale clip state in the next clear/draw/end.
reset()
ui.begin(Input())
ui.rectangle(Rect(10, 10, 5, 5), 0xFFFFFFFF)
ui.end()
window.draw(ui)
assert stats(0) == 1 and stats(1) == 1 and stats(5) == 0
assert stats(4) == 1 and stats(6) == 1
window.close()
window.close()
assert not window.open() and window.dt() == 0.0
try:
    window.poll()
except RuntimeError:
    failed += 1
assert failed == 3
assert title_copy() == 1
print("miniui backend: scalar ABI, input, RGBA, clip batching/order, caret, cleanup passed")

# Exercise the actual demo's first frame for reproducible submission counts.
reset()
events(0, 0, 0, 0, 1)
limit_frames(1)
demo_main()
assert stats(0) == 1 and stats(1) == 1 and stats(5) == 0
assert stats(2) == 159 and stats(3) == 8 and stats(8) == 167
assert stats(4) == 15 and stats(6) == 1 and stats(7) == 0
calls = stats(0) + stats(1) + stats(2) + stats(3) + stats(4) + stats(7)
print("miniui demo rendering:", stats(8), "draws,", stats(4), "clips,", calls, "FFI calls")
