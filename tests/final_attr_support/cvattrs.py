from typing import ClassVar


class Counter:
    next_id: ClassVar[int] = 1
    names: ClassVar[dict[str, int]] = {}

    def __init__(self, name: str) -> None:
        self.id: int = Counter.next_id
        Counter.next_id += 1
        Counter.names[name] = self.id
