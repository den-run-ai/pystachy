# miniui prototype

An optional immediate-mode UI written in the Pystachy subset. The widget core has
no imports, no FFI, no CPython bridge and no dependency on raylib or raygui. This
is original project code, not a source translation of either upstream library.
Only the optional desktop backend uses raylib's C API (5.5 API surface).

## Scope

Six controls: label, button, checkbox, slider, progress bar and single-line
textbox. Section headings (`panel`), equal/fixed-width rows, clipping, stable IDs,
mouse capture and Tab/Shift-Tab keyboard focus are included. A rectangle primitive
supports the particle demo. The application owns all control values; no callbacks
or retained widget objects cross FFI.

`miniui.py`, `raylib_backend.py` and `raylib_adapter.c` contain the implementation.
Together with `demo.py` and `build_backend.sh`, they are under 1,000 physical lines,
including comments/blanks. Tests, this guide and the external raylib library are
excluded; the complete graphics stack is NOT under 1,000 lines.

## Run the desktop demo

Install raylib development files exposing a `raylib` pkg-config entry, version
5.5 or later, and use the normal Pystachy/LLVM source setup. From the repository
root (the adapter's library path is deliberately literal and relative):

```sh
examples/miniui/build_backend.sh
./pystachy run examples/miniui/demo.py
./pystachy build examples/miniui/demo.py -o build/miniui/demo
./build/miniui/demo
```

The adapter is loaded as `./build/miniui/libminiui.so`; retain that working directory
and library when deploying this prototype. It is not a single-file executable.
Dynamic raylib builds also need their raylib shared library available. Nothing is
downloaded, vendored or linked into ordinary Pystachy programs by this example.
The AOT design does not embed CPython. Linux is the intended first platform;
the Darwin build switch is experimental, not a macOS validation claim. Windows
packaging is not implemented. This is a single, fixed-size window, on the main
thread; close it with its titlebar. Always close it in `finally`.

The same demo can use the repository's CPython FFI twin:

```sh
PYTHONPATH=tools/rt_cpython python3 examples/miniui/demo.py
```

## Small API

```python
from miniui import UI
from raylib_backend import Window

ui = UI(640, 360)
window = Window(640, 360, "Controls")
speed = 0.5
try:
    while window.open():
        ui.begin(window.poll())
        ui.label("Simulation")
        ui.row([100, 0])  # fixed column; remaining width
        ui.label("Speed")
        speed = ui.slider("speed", speed, 0.0, 1.0)
        ui.row([0])
        if ui.button("reset", "Reset"):
            speed = 0.5
        ui.end()
        window.draw(ui)
finally:
    window.close()
```

Use unique, nonempty string IDs for interactive controls, independent of visible
labels or call order. Buttons activate on release inside after a press inside;
sliders retain capture while dragging outside. Removed/disabled controls lose
capture and focus. Tab uses the preceding frame's enabled control order (so the
first displayed frame establishes it). Enter/Space activate a focused button or
checkbox; arrows/Home/End adjust sliders. Escape and window blur cancel focus
and capture. Labels and progress bars do not take keyboard focus.

Text editing supports insertion, Left/Right/Home/End, Backspace/Delete and Enter
to leave editing. Clicking a textbox places the cursor at its end. Limits and
cursor movement count Unicode code points, not grapheme clusters. Unsupported
glyphs are still limited by raylib's default font. No selection, clipboard, IME,
undo, shaping or accessibility integration is promised. Caller text is clamped
to `max_chars`; NUL and multiline values are rejected. The backend measures and
clips text and scrolls it horizontally to keep the caret visible.

`panel` is a section heading, NOT a nested layout or native window. No scrolling,
menus, resize/DPI handling or multiwindow support is included. Custom rectangles
are clipped to the root content area and do not advance layout. Commands are
frame-local. Call `begin`, submit controls, `end`, then render. Work between frames
must stay bounded or the UI will not respond; there is no background event thread.

## Reproducible tests

The headless case is part of the ordinary corpus via its `.path` and `.out`:

```sh
PYTHONPATH=examples/miniui python3 tests/programs/apps/miniui_headless.py
make test FILES='tests/programs/apps/miniui_headless.py'
make test-py FILES='tests/programs/apps/miniui_headless.py'
```

The display-free backend test compiles the actual adapter against a deliberately
fake raylib, then exercises it through the repository's unchanged CPython FFI twin:

```sh
python3 examples/miniui/check_backend.py
python3 examples/miniui/check_backend.py --compiler ./pystachy
```

The second command also compares native JIT, AOT and program-only GC-stress
execution. A missing compiler does not count as a native pass. The fake backend
checks scalar widths, UTF-8 input, unsigned RGBA, retained title ownership and
cleanup; it does NOT validate real raylib headers, display creation, fonts or
rendering. Run the real demo separately on each supported platform.

Initial local evidence: all eight headless scenarios and the compiled mock-backend
probe passed on Linux with CPython 3.13.5. Its checked-in `.out` was recorded on
that interpreter; the repository-pinned 3.13.16 recording check is still required.
The session had no Pystachy executable/complete LLVM toolchain, raylib or network
clone access. Native compilation, real graphics, sanitizers and full repository
verification were not run locally. Keep this prototype draft until those checks
and review are complete.
