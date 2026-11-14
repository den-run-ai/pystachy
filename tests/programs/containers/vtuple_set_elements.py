# Runtime-length tuples as set and frozenset elements (#1460): equal tuples of any length, built
# any way, are one element, as in CPython


def ints(n: int) -> tuple[int, ...]:
    return tuple(range(n))


st: set[tuple[bool, ...]] = set()
st.add((True,))
st.add(tuple([True]))
st.add(())
st.add((False, True))
print(len(st), (True,) in st, (False,) in st, () in st, sorted(st))
st.discard(())
st.discard((True, True))
print(sorted(st), sorted({x for x in st if len(x) > 1}))
other: set[tuple[bool, ...]] = {(True,), (False, False)}
print(sorted(st | other), sorted(st & other), sorted(st - other))
fs = frozenset([ints(2), ints(2), ints(3), tuple([0, 1])])
print(len(fs), (0, 1) in fs, ints(0) in fs, sorted(fs))
ns: set[tuple[int, ...]] = {(1, 2), ()}
ns.remove((True, 2))
ns.discard((False,))
print(sorted(ns), (False,) in {(0,)})
names: set[tuple[str, ...]] = {tuple("ab"), ("a", "b"), tuple("abc"[:2])}
print(len(names), sorted(names))
