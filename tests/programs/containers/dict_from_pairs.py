# dict(pairs): a new dict of (key, value) pairs inserted in turn, as PyDict_MergeFromSeq2
# inserts them (a repeated key keeps its first position and takes the last value): from a list
# or tuple of 2-tuples, a list comprehension or generator expression, zip(), enumerate(),
# reversed(), map() and filter(). The pairs are taken at once, as list() takes them.
from typing import NamedTuple

pairs = [("a", 1), ("b", 2), ("a", 3)]
print(dict(pairs), dict([("x", 1.5)]), dict(((1, "one"), (2, "two"))))
print(dict(zip("abc", [1, 2, 3])), dict(zip([1, 2, 3], "ab")), dict(zip(["k"], [[1, 2]])))
print(dict(enumerate(["x", "y", "z"])), dict(enumerate(["h", "é"], 1)))
print(dict((k, len(k)) for k in ["aa", "b", "ccc"]), dict([(i, i * i) for i in range(4)]))
print(dict(map(lambda s: (s, s.upper()), ["p", "q"])), dict(reversed(pairs)), dict(filter(lambda kv: kv[1] > 1, pairs)))
ek: list[str] = []
ev: list[int] = []
empty = dict(zip(ek, ev))
print(empty, dict([(i, i) for i in range(0)]) == {})
typed: dict[str, float] = dict([("pi", 3.14), ("e", 2.71)])
print(typed)
keyed = dict([((1, "x"), None), ((2, "y"), 2.5)])
print(keyed, keyed[(2, "y")])
print(dict(zip(["日本", "café"], ["語", "été"])))


class KV(NamedTuple):
    k: str
    v: int


nts = [KV("n", 1), KV("m", 2)]
print(dict((p.k, p.v) for p in nts))


# arguments are evaluated before the dict is made, and a pair's key is hashed as it is inserted
def gen(tag: str, n: int) -> list[int]:
    print("eval", tag)
    return list(range(n))


print(dict(zip(gen("keys", 3), gen("values", 2))))
d = dict(pairs)
d["c"] = 4
del d["a"]
print(d, dict(d.items()), dict(sorted(d.items(), key=lambda kv: -kv[1])))
