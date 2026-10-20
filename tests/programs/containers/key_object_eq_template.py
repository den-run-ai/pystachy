# Objects sorted, or taken by min() and max(), with a key object from a parameter or a field
# (one that could be None): the keyed call compares only the keys, so the items' own untyped
# __eq__ and __lt__ (which return NotImplemented, which is not supported here) are never
# compiled, as before #506.


class Task:
    def __init__(self, name: str, prio: int) -> None:
        self.name = name
        self.prio = prio

    def __eq__(self, other):
        if not isinstance(other, Task):
            return NotImplemented
        return self.name == other.name


class ByPrio:
    def __call__(self, t: Task) -> int:
        return t.prio


def schedule(tasks: list[Task], key: ByPrio) -> list[str]:
    return [t.name for t in sorted(tasks, key=key)]


class Version:
    def __init__(self, major: int, minor: int) -> None:
        self.major = major
        self.minor = minor

    def __lt__(self, other):
        if not isinstance(other, Version):
            return NotImplemented
        return (self.major, self.minor) < (other.major, other.minor)


class ByMinor:
    def __call__(self, v: Version) -> int:
        return v.minor


def newest(vs: list[Version], key: ByMinor) -> int:
    vs.sort(key=key)
    return max(vs, key=key).minor + min(vs[0], vs[1], key=key).minor


class Board:
    def __init__(self) -> None:
        self.key = ByPrio()
        self.tasks = [Task("c", 3), Task("a", 1), Task("b", 2)]

    def order(self) -> list[str]:
        self.tasks.sort(key=self.key)
        return [t.name for t in self.tasks]

    def first(self) -> str:
        return min(self.tasks, key=self.key).name + max(self.tasks[0], self.tasks[2], key=self.key).name


print(schedule([Task("b", 2), Task("a", 1)], ByPrio()))
print(newest([Version(1, 4), Version(2, 1), Version(1, 9)], ByMinor()))
b = Board()
print(b.order(), b.first())
