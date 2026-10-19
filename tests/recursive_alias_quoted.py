# Quoted annotations name a recursive alias as unquoted ones do: parameters, results, locals and
# container element types.
type V = None | int | str | list[V] | dict[str, V]


def f(v: "V") -> "list[V]":
    out: "list[V]" = [v]
    return out


def g(d: "dict[str, V]") -> "V":
    return d


def depth(v: "V") -> int:
    best = 0
    if isinstance(v, list):
        best = 1
        for x in v:
            best = max(best, 1 + depth(x))
    elif isinstance(v, dict):
        best = 1
        for y in v.values():
            best = max(best, 1 + depth(y))
    return best


def main() -> None:
    r = f([1, None])
    nested: "V" = g({"a": r, "b": "s"})
    print(r, nested)
    print(depth(nested), depth(f(f(f(3)))))
    items: "list[V]" = []
    items.append(nested)
    items.append(items[0])
    print(items[0] == items[1])
    first = items[0]
    second = items[1]
    if isinstance(first, dict) and isinstance(second, dict):
        print(first is second, first["a"] == second["a"])


main()
