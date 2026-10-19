# A callback that raises is reported as CPython reports an exception it ignores (the report's last
# line is the exception's), and the other callbacks and the program go on.
from _weakref import ref


class Item:
    def __init__(self, value: int):
        self.value = value


calls: list[int] = [0]


def boom(r: ref[Item]) -> None:
    calls[0] += 1
    raise ValueError("boom")


def create() -> tuple[list[ref[Item]], list[Item]]:
    owners = [Item(i) for i in range(256)]
    return [ref(item, boom) for item in owners], owners


def churn() -> None:
    for i in range(1024):
        text = str(i) * 65536
        assert len(text) >= 65536


refs, owners = create()
owners.clear()
churn()
items = [r() for r in refs]  # (holding the live referents, so that each None has called back)
dead = items.count(None)
print(dead > 0, calls[0] == dead)
