# the shape of mypyc's dataflow engine: a generic run over gen and kill sets that visitors return
# as AbstractSet pairs, a shared empty pair of frozensets among them
from collections.abc import Set as AbstractSet
from typing import Any, Generic, TypeVar

T = TypeVar("T")
AnalysisDict = dict[tuple[int, int], set[T]]
GenAndKill = tuple[AbstractSet[T], AbstractSet[T]]
_EMPTY: tuple[frozenset[Any], frozenset[Any]] = (frozenset(), frozenset())
NoneGenAndKill = GenAndKill[None]
CLEAN: NoneGenAndKill = (set(), set())
DIRTY: NoneGenAndKill = ({None}, {None})


class AnalysisResult(Generic[T]):
    def __init__(self, before: AnalysisDict[T], after: AnalysisDict[T]) -> None:
        self.before = before
        self.after = after

    def __str__(self) -> str:
        return f"before: {self.before}\nafter: {self.after}\n"


def defined(op: int) -> GenAndKill[str]:
    if op % 3 == 0:
        return {"r" + str(op)}, set()
    if op % 3 == 1:
        return set(), {"r" + str(op - 1)}
    return _EMPTY


def leaks(op: int) -> NoneGenAndKill:
    return DIRTY if op == 4 else CLEAN


def run_strs(ops: list[list[int]]) -> AnalysisResult[str]:
    before: AnalysisDict[str] = {}
    after: AnalysisDict[str] = {}
    cur: set[str] = set()
    for b in range(len(ops)):
        gen: set[str] = set()
        kill: set[str] = set()
        for op in ops[b]:
            opgen, opkill = defined(op)
            if opkill:
                gen -= opkill
            if opgen:
                gen |= opgen
                kill -= opgen
            if opkill:
                kill |= opkill
        for i in range(len(ops[b])):
            before[b, i] = set(cur)
            opgen, opkill = defined(ops[b][i])
            cur = (cur - opkill) | opgen
            after[b, i] = set(cur)
        print(b, sorted(gen), sorted(kill))
    return AnalysisResult(before, after)


def run_none(ops: list[int]) -> AnalysisResult[None]:
    before: AnalysisDict[None] = {}
    after: AnalysisDict[None] = {}
    cur: set[None] = set()
    for i in range(len(ops)):
        before[0, i] = set(cur)
        opgen, opkill = leaks(ops[i])
        new_after = (cur - opkill) | opgen
        if new_after != cur:
            cur = new_after
        after[0, i] = set(cur)
    return AnalysisResult(before, after)


r = run_strs([[0, 3, 4, 2], [1, 6, 5, 7]])
for key in sorted(r.after):
    print(key, sorted(r.before[key]), sorted(r.after[key]))
d = run_none([1, 2, 4, 5])
print(d)
print([bool(d.after[0, i]) and not bool(d.before[0, i]) for i in range(4)])
