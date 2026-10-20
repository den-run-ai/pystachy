from dataclasses import dataclass, field


def counted(label: str) -> int:
    print("default of", label)
    return len(label)


@dataclass(frozen=True)
class Event:
    name: str
    weight: int = counted("weight")
    notes: list[str] = field(default_factory=list, repr=False)


@dataclass(frozen=True)
class Timed(Event):
    seconds: float = 0.0
