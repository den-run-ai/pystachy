# The default factories of a dataclass run after the call's arguments, in field order, whether
# or not the field is an __init__ parameter (init=False) or keyword-only, then __post_init__;
# replace() runs those of the init=False fields again. A factory may be a lib generic class.
from collections import deque
from dataclasses import KW_ONLY, dataclass, field, replace

log: list[str] = []
n = 0


def next_id() -> int:
    global n
    n += 1
    log.append(f"id {n}")
    return n


def tags(tag: str) -> list[str]:
    log.append(tag)
    return [tag]


def arg(label: str, v: int) -> int:
    log.append("arg " + label)
    return v


def flush() -> list[str]:
    out = list(log)
    log.clear()
    return out


@dataclass
class Item:
    id: int = field(init=False, default_factory=next_id)
    stamp: int = field(default_factory=next_id)


print(Item(), flush())
print(Item(arg("stamp", 7)), flush())


@dataclass
class Record:
    n: int
    a: list[str] = field(default_factory=lambda: tags("a"), kw_only=True)
    b: list[str] = field(default_factory=lambda: tags("b"), init=False)
    c: list[str] = field(default_factory=lambda: tags("c"))
    _: KW_ONLY
    d: list[str] = field(default_factory=lambda: tags("d"))
    m: int = 0

    def __post_init__(self) -> None:
        log.append("post_init")


print(Record(arg("n", 1), m=arg("m", 2)), flush())
print(Record(arg("n", 1), ["ç"], a=["á"]), flush())


@dataclass
class Extended(Record):
    e: list[str] = field(default_factory=lambda: tags("e"), init=False)
    f: list[str] = field(default_factory=lambda: tags("f"), kw_only=True)


r = Extended(arg("n", 3), d=["δ"])
print(r, flush())
print(replace(r, n=arg("replace n", 4)), flush())


@dataclass(init=False)
class Manual(Item):
    def __init__(self) -> None:
        super().__init__(stamp=arg("super", 0))


print(Manual(), flush())


@dataclass
class Queue:
    pending: deque[int] = field(default_factory=deque)
    names: deque[str] = field(default_factory=lambda: deque(["x", "y"]))
    seen: set[int] = field(init=False, default_factory=set)


q = Queue()
q.pending.append(1)
q.seen.add(2)
print(len(q.pending), list(q.names), q.seen, len(Queue().pending))
