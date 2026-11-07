"""Small immediate-mode UI. No FFI, raylib, callbacks or dynamic Any.

Application state stays with the caller. Submit each interactive ID exactly once
per frame. Draw commands are valid until the next begin(); copy to retain them.
"""


class Rect:
    def __init__(self, x: int, y: int, w: int, h: int):
        self.x = x
        self.y = y
        self.w: int = max(0, w)
        self.h: int = max(0, h)

    def contains(self, x: int, y: int) -> bool:
        return self.x <= x < self.x + self.w and self.y <= y < self.y + self.h

    def intersect(self, other: "Rect") -> "Rect":
        x = max(self.x, other.x)
        y = max(self.y, other.y)
        return Rect(x, y, min(self.x + self.w, other.x + other.w) - x,
                    min(self.y + self.h, other.y + other.h) - y)


class Input:
    """Frame snapshot, not an ordered event stream; Escape/blur cancel the frame."""

    def __init__(self, x: int = 0, y: int = 0, down: bool = False,
                 pressed: bool = False, released: bool = False, text: str = ""):
        self.x = x
        self.y = y
        self.down = down
        self.pressed = pressed
        self.released = released
        self.text = text
        self.focused = True
        self.backspace = False
        self.delete = False
        self.left = False
        self.right = False
        self.home = False
        self.end = False
        self.tab = False
        self.shift = False
        self.enter = False
        self.space = False
        self.escape = False


class Command:
    def __init__(self, kind: int, rect: Rect, clip: Rect, color: int,
                 text: str = "", size: int = 18, caret: int = -1):
        self.kind = kind                 # 0: filled rectangle; 1: text
        self.rect = rect
        self.clip = clip
        self.color = color              # unsigned 0xRRGGBBAA
        self.text = text
        self.size = size
        self.caret = caret              # code-point index; -1 hides the caret


class Style:
    def __init__(self):
        self.padding = 10
        self.gap = 8
        self.height = 30
        self.font_size = 18
        self.background = 0x181C24FF
        self.panel = 0x242B36FF
        self.base = 0x333D4CFF
        self.hover = 0x45546AFF
        self.active = 0x245C84FF
        self.accent = 0x66C2FFFF
        self.text = 0xEEF2F6FF
        self.muted = 0x8993A2FF


class UI:
    def __init__(self, width: int, height: int):
        if width < 40 or height < 40:
            raise ValueError("UI dimensions must be at least 40")
        self.width = width
        self.height = height
        self.style = Style()
        self.commands: list[Command] = []
        self.active = ""
        self.focus = ""
        self.edit_id = ""
        self.cursor = 0
        self.input = Input()
        self.accept_input = True
        self.clip = Rect(0, 0, width, height)
        self.area = Rect(0, 0, width, height)
        self.ids: set[str] = set()
        self.order: list[str] = []
        self.widths: list[int] = []
        self.column = 0
        self.y = 0
        self.row_height = 30
        self.started = False

    def begin(self, events: Input) -> None:
        if self.started:
            raise RuntimeError("end the previous frame before begin")
        if self.style.padding < 0 or self.style.gap < 0 or self.style.height < 8:
            raise ValueError("invalid layout style")
        if self.style.font_size < 1:
            raise ValueError("font size must be positive")
        pad = self.style.padding
        if self.width - 2 * pad < 8 or self.height - 2 * pad < 8:
            raise ValueError("padding leaves no content area")
        self.input = events
        self.accept_input = events.focused and not events.escape
        if not self.accept_input:
            self.focus = ""
            self.active = ""
            self.edit_id = ""
        elif events.pressed:
            self.focus = ""
        elif events.tab and self.order:
            index = -1
            if self.focus in self.order:
                index = self.order.index(self.focus)
            if events.shift:
                index = len(self.order) if index < 0 else index
                index = (index - 1) % len(self.order)
            else:
                index = (index + 1) % len(self.order)
            self.focus = self.order[index]
        if not events.down and not events.released:
            self.active = ""
        self.commands = []
        self.ids.clear()
        self.order = []
        self.area = Rect(pad, pad, self.width - 2 * pad, self.height - 2 * pad)
        self.clip = self.area
        self.y = self.area.y
        self.column = 0
        self.widths = [self.area.w]
        self.row_height = self.style.height
        self.started = True

    def end(self) -> None:
        self._check_frame()
        if self.input.released or self.active not in self.order:
            self.active = ""
        if self.focus not in self.order:
            self.focus = ""
        if self.edit_id != self.focus:
            self.edit_id = ""
        self.started = False

    def _check_frame(self) -> None:
        if not self.started:
            raise RuntimeError("widgets require begin/end")

    def row(self, widths: list[int], height: int = 0) -> None:
        """Positive widths are pixels; zeros share remaining width equally."""
        self._check_frame()
        if not widths or height < 0:
            raise ValueError("row requires widths and a nonnegative height")
        fixed = 0
        flexible = 0
        for width in widths:
            if width < 0:
                raise ValueError("row widths must be nonnegative")
            fixed += width
            if width == 0:
                flexible += 1
        remaining = self.area.w - self.style.gap * (len(widths) - 1) - fixed
        if remaining < 0 or (flexible > 0 and remaining < flexible * 8):
            raise ValueError("row does not fit")
        resolved: list[int] = []
        for width in widths:
            if width == 0:
                width = remaining // flexible
                remaining -= width
                flexible -= 1
            if width < 8:
                raise ValueError("columns must be at least 8 pixels")
            resolved.append(width)
        if self.column:
            self.y += self.row_height + self.style.gap
        self.column = 0
        self.widths = resolved
        self.row_height = self.style.height if height == 0 else max(8, height)

    def _next(self) -> Rect:
        self._check_frame()
        if self.column == len(self.widths):
            self.column = 0
            self.y += self.row_height + self.style.gap
        x = self.area.x
        for i in range(self.column):
            x += self.widths[i] + self.style.gap
        rect = Rect(x, self.y, self.widths[self.column], self.row_height)
        self.column += 1
        return rect

    def _rect(self, rect: Rect, color: int) -> None:
        self.commands.append(Command(0, rect, self.clip, color))

    def _text(self, rect: Rect, text: str, color: int, caret: int = -1) -> None:
        if "\x00" in text:
            raise ValueError("text cannot contain NUL")
        inset = min(6, rect.w // 2)
        inner = Rect(rect.x + inset, rect.y + max(0, (rect.h - self.style.font_size) // 2),
                     max(0, rect.w - 2 * inset), self.style.font_size)
        self.commands.append(Command(1, inner, self.clip.intersect(rect), color,
                                     text, self.style.font_size, caret))

    def _control(self, key: str, rect: Rect, enabled: bool) -> bool:
        if not key or key in self.ids:
            raise ValueError("interactive IDs must be nonempty and unique per frame")
        self.ids.add(key)
        visible = self.clip.intersect(rect)
        if not enabled or visible.w == 0 or visible.h == 0:
            if self.active == key:
                self.active = ""
            if self.focus == key:
                self.focus = ""
            return False
        self.order.append(key)
        hot = self.accept_input and visible.contains(self.input.x, self.input.y)
        if hot and self.input.pressed and not self.active:
            self.active = key
            self.focus = key
        return hot

    def _clicked(self, key: str, hot: bool, enabled: bool) -> bool:
        if not enabled or not self.accept_input:
            return False
        mouse = self.active == key and self.input.released and hot
        keyboard = self.focus == key and (self.input.enter or self.input.space)
        return mouse or keyboard

    def _box(self, key: str, rect: Rect, hot: bool, enabled: bool) -> None:
        color = self.style.base
        if enabled:
            if self.active == key:
                color = self.style.active
            elif hot:
                color = self.style.hover
        self._rect(rect, color)
        if enabled and self.focus == key:
            self._rect(Rect(rect.x, rect.y + rect.h - 2, rect.w, 2), self.style.accent)

    def rectangle(self, rect: Rect, color: int) -> None:
        """Draw a clipped primitive without advancing layout."""
        self._check_frame()
        self._rect(rect, color)

    def label(self, text: str) -> None:
        self._text(self._next(), text, self.style.text)

    def panel(self, title: str) -> None:
        """A noninteractive section heading, not an OS window/container."""
        rect = self._next()
        self._rect(rect, self.style.panel)
        self._text(rect, title, self.style.text)

    def button(self, key: str, label: str, enabled: bool = True) -> bool:
        rect = self._next()
        hot = self._control(key, rect, enabled)
        self._box(key, rect, hot, enabled)
        self._text(rect, label, self.style.text if enabled else self.style.muted)
        return self._clicked(key, hot, enabled)

    def checkbox(self, key: str, label: str, value: bool, enabled: bool = True) -> bool:
        rect = self._next()
        hot = self._control(key, rect, enabled)
        if self._clicked(key, hot, enabled):
            value = not value
        size = min(rect.h, rect.w, 24)
        box = Rect(rect.x, rect.y + (rect.h - size) // 2, size, size)
        self._box(key, box, hot, enabled)
        if value:
            self._rect(Rect(box.x + 5, box.y + 5, max(0, size - 10), max(0, size - 10)),
                       self.style.accent if enabled else self.style.muted)
        self._text(Rect(rect.x + size, rect.y, max(0, rect.w - size), rect.h), label,
                   self.style.text if enabled else self.style.muted)
        return value

    def slider(self, key: str, value: float, low: float, high: float,
               enabled: bool = True) -> float:
        if not (-1e100 <= low <= high <= 1e100) or not (-1e100 <= value <= 1e100):
            raise ValueError("slider requires finite, ordered bounds and a finite value")
        rect = self._next()
        enabled = enabled and low < high
        hot = self._control(key, rect, enabled)
        value = max(low, min(high, value))
        span = max(1, rect.w - 8)
        if enabled and self.active == key and (self.input.down or self.input.released):
            fraction = max(0.0, min(1.0, (self.input.x - rect.x - 4) / float(span)))
            value = low + (high - low) * fraction
        if enabled and self.focus == key:
            step = (high - low) / 100.0
            if self.input.left:
                value -= step
            if self.input.right:
                value += step
            if self.input.home:
                value = low
            if self.input.end:
                value = high
        value = max(low, min(high, value))
        self._box(key, rect, hot, enabled)
        fraction = 0.0 if high == low else (value - low) / (high - low)
        self._rect(Rect(rect.x + int(fraction * span), rect.y + 2, 8, max(0, rect.h - 4)),
                   self.style.accent if enabled else self.style.muted)
        return value

    def progress(self, value: float) -> None:
        if not (-1e100 <= value <= 1e100):
            raise ValueError("progress requires a finite value")
        rect = self._next()
        self._rect(rect, self.style.base)
        self._rect(Rect(rect.x, rect.y, int(rect.w * max(0.0, min(1.0, value))), rect.h),
                   self.style.accent)

    def textbox(self, key: str, value: str, max_chars: int = 256,
                enabled: bool = True) -> str:
        if max_chars < 1 or "\x00" in value or "\n" in value or "\r" in value:
            raise ValueError("textbox requires single-line text and positive capacity")
        rect = self._next()
        hot = self._control(key, rect, enabled)
        value = value[:max_chars]
        caret = -1
        if enabled and self.focus == key:
            if self.edit_id != key or (hot and self.input.pressed):
                self.cursor = len(value)
            self.edit_id = key
            self.cursor = min(self.cursor, len(value))
            # Snapshot priority: navigation, deletion, text, then Enter.
            if self.input.home:
                self.cursor = 0
            if self.input.end:
                self.cursor = len(value)
            if self.input.left:
                self.cursor = max(0, self.cursor - 1)
            if self.input.right:
                self.cursor = min(len(value), self.cursor + 1)
            if self.input.backspace and self.cursor > 0:
                value = value[:self.cursor - 1] + value[self.cursor:]
                self.cursor -= 1
            if self.input.delete:
                value = value[:self.cursor] + value[self.cursor + 1:]
            inserted = ""
            for char in self.input.text:
                code = ord(char)
                if code >= 32 and code != 127 and not (0xD800 <= code <= 0xDFFF):
                    if len(inserted) < max_chars - len(value):
                        inserted += char
            value = value[:self.cursor] + inserted + value[self.cursor:]
            self.cursor += len(inserted)
            caret = self.cursor
            if self.input.enter:
                self.focus = ""
                caret = -1
        self._box(key, rect, hot, enabled)
        self._text(rect, value, self.style.text if enabled else self.style.muted, caret)
        return value
