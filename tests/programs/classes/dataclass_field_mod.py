import dataclasses
from dataclasses import dataclass, field


def default_tags() -> list[str]:
    return ["module"]


@dataclass(frozen=True, order=True)
class Entry:
    key: str
    rank: int = 0
    tags: list[str] = field(default_factory=default_tags, compare=False)
    note: str = dataclasses.field(default="", repr=False)


@dataclass
class Registry:
    entries: list[Entry] = field(default_factory=list)
    count: int = field(init=False, default=0)

    def add(self, e: Entry) -> None:
        self.entries.append(e)
        self.count += 1
