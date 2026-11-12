"""Bounded builtin slice values: raw int/bool/None fields and indices()."""


class slice:
    __slots__ = ("start", "stop", "step")

    def __init__(self, start: int | bool | None, stop: int | bool | None, step: int | bool | None) -> None:
        self.start = start
        self.stop = stop
        self.step = step

    def __repr__(self) -> str:
        return f"slice({self.start!r}, {self.stop!r}, {self.step!r})"

    def __eq__(self, other: "slice") -> bool:
        if other is None:
            return False
        return self.start == other.start and self.stop == other.stop and self.step == other.step

    def indices(self, length: int) -> tuple[int, int, int]:
        if length < 0:
            raise ValueError("length should not be negative")
        step0 = _index(self.step)
        step = 1 if step0 is None else step0
        if step == 0:
            raise ValueError("slice step cannot be zero")
        lower = -1 if step < 0 else 0
        upper = length - 1 if step < 0 else length
        start0 = _index(self.start)
        stop0 = _index(self.stop)
        start = (upper if step < 0 else lower) if start0 is None else _clamp(start0, length, lower, upper)
        stop = (lower if step < 0 else upper) if stop0 is None else _clamp(stop0, length, lower, upper)
        return start, stop, step


def _index(value: int | bool | None) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return 1 if value else 0
    return value


def _clamp(value: int, length: int, lower: int, upper: int) -> int:
    if value < 0:
        value += length
        return lower if value < lower else value
    return upper if value > upper else value
