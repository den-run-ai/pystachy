"""Static and class methods of a module's classes, and a class Pystachy cannot compile, unused."""
import os


class Length:
    factors: dict[str, float] = {"m": 1.0, "cm": 0.01, "km": 1000.0}

    def __init__(self, path: str, meters: float = 0.0, *, unit: str = "m") -> None:
        self.path = os.fspath(path)
        self.meters = meters
        self.unit = unit

    @classmethod
    def parse(cls, path: str, text: str | None = None, *, strict: bool = True) -> "Length":
        if text is None:
            text = "0m"
        unit = text.lstrip("0123456789.")
        if not cls.known(unit) and not strict:
            text = text[: len(text) - len(unit)] + "m"
            unit = "m"
        return cls(path=path, meters=float(text[: len(text) - len(unit)]) * cls.factors[unit], unit=unit)

    @staticmethod
    def known(unit: str) -> bool:
        return unit in Length.factors

    def __repr__(self) -> str:
        return f"Length({self.path!r}, {self.meters}, {self.unit})"


class Prop:
    def __init__(self) -> None:
        self.x = 1

    @property
    def double(self) -> int:
        return self.x * 2
