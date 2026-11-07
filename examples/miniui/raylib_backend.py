"""Optional raylib adapter. Use the built run.sh to locate its shared library."""
from ffi import extern, c_int, c_uint
from miniui import Input, UI


@extern("libminiui.so", "miniui_init")
def _init(width: c_int, height: c_int, title: str) -> c_int: ...


@extern("libminiui.so", "miniui_close")
def _close() -> None: ...


@extern("libminiui.so", "miniui_open")
def _open() -> c_int: ...


@extern("libminiui.so", "miniui_focused")
def _focused() -> c_int: ...


@extern("libminiui.so", "miniui_mouse_x")
def _mouse_x() -> c_int: ...


@extern("libminiui.so", "miniui_mouse_y")
def _mouse_y() -> c_int: ...


@extern("libminiui.so", "miniui_mouse")
def _mouse() -> c_int: ...


@extern("libminiui.so", "miniui_keys")
def _keys() -> c_int: ...


@extern("libminiui.so", "miniui_character")
def _character() -> c_int: ...


@extern("libminiui.so", "miniui_dt")
def _dt() -> float: ...


@extern("libminiui.so", "miniui_begin")
def _begin(color: c_uint) -> None: ...


@extern("libminiui.so", "miniui_end")
def _end() -> None: ...


@extern("libminiui.so", "miniui_clip")
def _clip(x: c_int, y: c_int, w: c_int, h: c_int) -> None: ...


@extern("libminiui.so", "miniui_rect")
def _rect(x: c_int, y: c_int, w: c_int, h: c_int, color: c_uint) -> None: ...


@extern("libminiui.so", "miniui_text")
def _text(text: str, x: c_int, y: c_int, size: c_int, color: c_uint) -> None: ...


@extern("libminiui.so", "miniui_width")
def _width(text: str, size: c_int) -> c_int: ...


class Window:
    def __init__(self, width: int, height: int, title: str):
        self.closed = True
        if width < 40 or height < 40 or width > 32768 or height > 32768:
            raise ValueError("window dimensions must be in 40..32768")
        if _init(width, height, title) == 0:
            raise RuntimeError("raylib initialization failed or a window is already open")
        self.closed = False

    def open(self) -> bool:
        return not self.closed and _open() != 0

    def close(self) -> None:
        if not self.closed:
            _close()
            self.closed = True

    def dt(self) -> float:
        return 0.0 if self.closed else min(0.1, max(0.0, _dt()))

    def poll(self) -> Input:
        if self.closed:
            raise RuntimeError("window is closed")
        mouse = _mouse()
        keys = _keys()
        events = Input(_mouse_x(), _mouse_y(), bool(mouse & 1),
                       bool(mouse & 2), bool(mouse & 4))
        events.focused = _focused() != 0
        events.backspace = bool(keys & 1)
        events.delete = bool(keys & 2)
        events.left = bool(keys & 4)
        events.right = bool(keys & 8)
        events.home = bool(keys & 16)
        events.end = bool(keys & 32)
        events.tab = bool(keys & 64)
        events.shift = bool(keys & 128)
        events.enter = bool(keys & 256)
        events.space = bool(keys & 512)
        events.escape = bool(keys & 1024)
        code = _character()
        while code != 0:
            if 32 <= code <= 0x10FFFF and not (0xD800 <= code <= 0xDFFF):
                events.text += chr(code)
            code = _character()
        return events

    def draw(self, ui: UI) -> None:
        if self.closed or ui.started:
            raise RuntimeError("draw requires an open window and an ended UI frame")
        _begin(ui.style.background)
        last_x = last_y = last_w = last_h = -1
        try:
            for command in ui.commands:
                rect = command.rect
                clip = command.clip
                if (rect.w == 0 or rect.h == 0 or clip.w == 0 or clip.h == 0
                        or rect.x >= clip.x + clip.w or rect.x + rect.w <= clip.x
                        or rect.y >= clip.y + clip.h or rect.y + rect.h <= clip.y):
                    continue
                # Rectangles share the container clip; text still needs its own
                # bounds, including a horizontally scrolled textbox and caret.
                if command.kind != 0:
                    clip = clip.intersect(rect)
                if (clip.x != last_x or clip.y != last_y
                        or clip.w != last_w or clip.h != last_h):
                    _clip(clip.x, clip.y, clip.w, clip.h)
                    last_x, last_y, last_w, last_h = clip.x, clip.y, clip.w, clip.h
                if command.kind == 0:
                    _rect(rect.x, rect.y, rect.w, rect.h, command.color)
                else:
                    cursor = 0
                    offset = 0
                    if command.caret >= 0:
                        cursor = _width(command.text[:command.caret], command.size)
                        offset = max(0, cursor + 2 - rect.w)
                    _text(command.text, rect.x - offset, rect.y, command.size, command.color)
                    if command.caret >= 0:
                        _rect(rect.x + cursor - offset, rect.y, 1, rect.h, command.color)
        finally:
            _end()
