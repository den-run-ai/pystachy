# Comprehensions over a variable or field holding a fixed tuple whose items have different
# types, and over a **kwargs record's items() or values() of different types, compile item by
# item: list displays and str.join() of a generator expression or map(); so does tuple() of a
# generator expression over any fixed tuple, whose result is a fixed tuple. The tuple is
# evaluated once, first
def source(t):
    print("source")
    return t


row = (1, "two", 3.5, None, [4])
print([repr(x) for x in row], [str(x) for x in row][1])
print(", ".join(repr(x) for x in row), "|".join(map(str, row)), "-".join(str(x) for x in (1, 2)))
print(tuple(x * 2 for x in (1, "ab", 1.5)), tuple(str(x) for x in source((1, 2))), tuple(x for x in ()))
pair = ("é", 7)
items: list[str | int] = [x for x in pair]
print(tuple(map(repr, pair)), items, len(tuple(y for y in pair)))


def kwreprs(**kw):
    return ["%s=%r" % (k, v) for k, v in kw.items()], [repr(v) for v in kw.values()], ", ".join(f"{k}:{v}" for k, v in kw.items())


print(kwreprs(a=1, b="x", c=None))
print(kwreprs(a=1, b=2))
