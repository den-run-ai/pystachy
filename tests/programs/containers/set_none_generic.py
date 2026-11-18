# None-element sets and None keys through functions, fields, tuples, nested containers and a
# generic class whose type variable is bound to None (mypyc's AnalysisResult[None])
from typing import Generic, TypeVar

T = TypeVar("T")


class Result(Generic[T]):
    def __init__(self, before: dict[tuple[str, int], set[T]], after: dict[tuple[str, int], set[T]]) -> None:
        self.before = before
        self.after = after


class Holder:
    def __init__(self) -> None:
        self.flags: set[None] = set()
        self.names: set[str | None] = {None}
        self.by_file: dict[str | None, list[str]] = {}

    def mark(self) -> None:
        self.flags.add(None)
        self.names.add("n")
        self.by_file.setdefault(None, []).append("m")


def run(steps: list[bool]) -> Result[None]:
    before: dict[tuple[str, int], set[None]] = {}
    after: dict[tuple[str, int], set[None]] = {}
    cur: set[None] = set()
    for i in range(len(steps)):
        before["b", i] = set(cur)
        if steps[i]:
            cur = cur | {None}
        after["b", i] = cur.copy()
    return Result(before, after)


def merge(a: set[None], b: set[None] | None) -> set[None]:
    if b is None:
        return a
    return a | b


def group(messages: list[tuple[str | None, str]]) -> dict[str | None, list[str]]:
    out: dict[str | None, list[str]] = {}
    for path, text in messages:
        if path not in out:
            out[path] = []
        out[path].append(text)
    return out


def count(d: dict[str | None, list[str]], key: str | None) -> int:
    return len(d[key]) if key in d else -1


r = run([False, True, False])
for i in range(3):
    print(i, bool(r.before["b", i]), bool(r.after["b", i]), len(r.after["b", i]), r.after["b", i])
dirty = False
for key in r.after:
    if r.after[key] and not r.before[key]:
        dirty = True
print(dirty, r.before == r.after, r.after == r.after)
h = Holder()
print(h.flags, len(h.names), h.by_file)
h.mark()
h.mark()
print(h.flags, len(h.names), None in h.names, "n" in h.names, h.by_file)
print(merge(set(), None), merge({None}, None), merge(set(), {None}), merge(set(), set()))
g = group([(None, "a"), ("x.py", "b"), (None, "c"), ("y.py", "d")])
print(g, count(g, None), count(g, "x.py"), count(g, "z.py"))
pair: tuple[set[None], set[None]] = ({None}, set())
gen, kill = pair
print(gen, kill, bool(gen), bool(kill), gen == kill, pair)
nested: list[set[None]] = [set(), {None}]
print(nested, [len(s) for s in nested], nested[1] == {None}, nested == [set(), {None}])
table: dict[str, set[str | None]] = {"a": {None}, "b": {"q"}}
print(table["a"], table["b"], None in table["a"], None in table["b"], table == {"a": {None}, "b": {"q"}})
opt: set[None] | None = None
print(opt is None, opt)
opt = {None}
print(opt is None, opt, len(opt))
