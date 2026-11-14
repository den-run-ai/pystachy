# pystachy: python-int
# Optional tuple keys retain the same promoting-int storage as nonoptional keys,
# including when set algebra reuses their existing pointers and stored hashes.
from fixed_optional_tuple_keys import add_fixed, contains_fixed, read_fixed, read_nested


def show(values: set[tuple[int, str] | None]) -> None:
    print(sorted(repr(value) for value in values))


def exercise(n: int) -> None:
    plain = {(n, "a"), (n + 1, "b")}
    optional: set[tuple[int, str] | None] = {None, (n, "a")}
    joined = plain | optional
    show(joined)
    show(optional | plain)
    show(plain & optional)
    show(optional & plain)
    show(plain - optional)
    show(optional - plain)
    show(plain ^ optional)
    print((n, "a") in joined, (n + 1, "b") in joined, (n + 2, "c") not in joined, None in joined)
    print(plain <= joined, joined >= optional, plain.isdisjoint(optional), optional.issubset(joined))
    show(optional.union(plain))
    show(optional.intersection(plain))
    show(optional.difference(plain))
    show(optional.symmetric_difference(plain))
    copied = joined.copy()
    copied.discard((n, "a"))
    copied.remove(None)
    show(copied)
    print(copied.pop(), len(copied), len(joined))
    optional.update(plain)
    optional.difference_update({None})
    optional.intersection_update(plain)
    optional.symmetric_difference_update({None})
    show(optional)
    print(frozenset(optional) == frozenset(joined))

    keyed: dict[tuple[int, str] | None, str] = {None: "none", (n, "a"): "a"}
    keyed[(n + 1, "b")] = "b"
    print(keyed, keyed[(n, "a")], keyed[None], keyed.get((n + 2, "c")), None in keyed)
    print(keyed.setdefault((n, "a"), "old"), keyed.setdefault((n + 2, "c"), "c"))
    print(list(keyed), list(keyed.items()), dict(keyed) == keyed)
    for key in keyed:
        print(key, key in keyed, keyed[key])
    print(keyed.popitem(), keyed.pop((n, "a")), keyed.pop(None), keyed.get(None, "gone"))
    del keyed[(n + 1, "b")]
    for key in [None, (n + 3, "missing")]:
        try:
            print(keyed[key])
        except KeyError as error:
            print("KeyError", error)

    nested: dict[tuple[tuple[int, int], str] | None, int] = {None: 0, ((n, -2 ** 63), "nested"): 1}
    print(nested, nested[((n, -2 ** 63), "nested")], ((n, -2 ** 63), "nested") in nested)
    print(list(nested.items()), nested.popitem())
    deep: dict[tuple[tuple[int, int] | None, str] | None, int] = {None: 0, (None, "empty"): 1, ((n, -2 ** 63), "nested"): 2}
    print(deep, deep[(None, "empty")], deep[((n, -2 ** 63), "nested")])
    values: list[tuple[int, str] | None] = [None, (n, "a")]
    print(values == values.copy(), values.count((n, "a")), values.index((n, "a")), (n, "a") in values, None in values)
    print(values[1] == (n, "a"), hash(values[1]) == hash((n, "a")))
    print(values, values[0], values[1], values.pop(), values)


for number in (2 ** 70, -2 ** 70, -2 ** 63, 0):
    exercise(number)

# Fixed-width modules store a real INT64_MIN tuple, which needs a fresh high-word
# layout before any optional container can read it as a promoting tuple.
mixed: set[tuple[int, str] | None] = {(2 ** 70, "wide")}
add_fixed(mixed)
show(mixed)
print(contains_fixed(mixed), (2 ** 70, "wide") in mixed, (-2 ** 63, "fixed") in mixed)
small: list[tuple[int, str] | None] = [None, (-2 ** 63, "fixed"), (1, "small")]
print(read_fixed(small, 0), read_fixed(small, 1), read_fixed(small, 2))
small_nested: list[tuple[tuple[int, int] | None, str] | None] = [None, (None, "empty"), ((-2 ** 63, 1), "fixed")]
print(read_nested(small_nested, 0), read_nested(small_nested, 1), read_nested(small_nested, 2))
lookups: dict[tuple[int, str] | None, str] = {None: "none", (1, "one"): "one"}
print(lookups[(True, "one")], (True, "one") in lookups, lookups[None])
