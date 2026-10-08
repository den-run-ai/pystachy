from dataclasses import dataclass


@dataclass
class Task:
    prio: int
    name: str

    def __lt__(self, other: "Task") -> bool:
        return self.prio < other.prio


a = (Task(1, "write"), 2)
b = (Task(1, "read"), 1)
print(a < b, b < a)
print(sorted([a, b]))


@dataclass
class P:
    x: int


p = P(1)
print([p] <= [p], (1, P(2)) < (1, P(3)) if False else (1, P(2)) == (1, P(2)))
print(sorted([(1, p), (1, p)]))
