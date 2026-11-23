# A recursive alias may hold one tuple type as a leaf: isinstance(v, tuple) narrows to it.
type Pt = int | str | tuple[int, int] | list[Pt] | dict[str, Pt]
type Row = None | str | tuple[str, ...] | list[Row]


def spans(v: Pt) -> int:
    if isinstance(v, tuple):
        return v[1] - v[0]
    if isinstance(v, list):
        return sum([spans(x) for x in v])
    if isinstance(v, dict):
        return sum([spans(x) for x in v.values()])
    return 0


def cells(v: Row) -> int:
    if v is None or isinstance(v, str):
        return 0
    if isinstance(v, tuple):
        return len(v)
    return sum([cells(x) for x in v])


def main() -> None:
    p: Pt = {"a": (1, 4), "b": [(2, 9), 5, "s"], "c": 3}
    print(p, spans(p), len(p))
    print(p == {"a": (1, 4), "b": [(2, 9), 5, "s"], "c": 3}, p == {"a": (1, 5)})
    q: list[Pt] = [(0, 1), [(1, 3)], "x"]
    q.append((5, 8))
    print(q, spans(q), (5, 8) in q)
    r: Row = [("a", "b"), None, [("c",), ()], "s"]
    print(r, cells(r), bool(r), repr(r))


main()
