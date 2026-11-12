from dataclasses import dataclass


@dataclass
class MethodPoint:
    x: int

    def __match_args__(self) -> tuple[str]:
        return ("x",)


@dataclass
class PropertyPoint:
    x: int

    @property
    def __match_args__(self) -> tuple[str]:
        raise ValueError("the instance property must not run")
