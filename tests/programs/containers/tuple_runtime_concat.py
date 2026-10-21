# Runtime-length tuples concatenate: with each other, with fixed tuples on either side and in place
# (+=), into a new tuple, or the other operand itself where one is empty, as CPython's tupleconcat
# gives it; items of a type and of that type or None make a tuple of the latter
Key = tuple[str, ...]


def join(a: Key, b: Key) -> Key:
    return a + b


def parts(s: str) -> Key:
    key: Key = ()
    for p in s.split("."):
        key += (p,)
    return key


def prefixes(header: Key, key: Key) -> list[Key]:
    # as tomllib's key_value_rule makes the tables a dotted key passes through
    return [header + key[:i] for i in range(1, len(key))]


k = parts("a.b.c")
print(k, len(k), join(k, ("d",)), join((), k), join(k, ()))
print(("x",) + k, k + ("y", "z"), k[:1] + k[2:], k + k[1:], k + k + k)
e: Key = ()
print(e + e, e + k is k, k + e is k, k + () is k, () + k is k, len(e + e))
print(prefixes(("tool",), ("poetry", "group", "dev")), prefixes((), ("a",)))
nums: tuple[int, ...] = tuple([1, 2])
more: tuple[int, ...] = tuple([3])
print(nums + more, nums + (4, 5), (0,) + nums, sum(nums + more), max(nums + more))
opt: tuple[int | None, ...] = (None, 1)
print(opt + nums, nums + opt, opt + (None,))
fl: tuple[float, ...] = (1.5,)
print(fl + (2.5,), fl + fl, (fl + fl)[1], (fl + fl)[-1:])
flags: tuple[bool, ...] = (True,)
print(flags + (False,), flags + flags)
acc: Key = ()
for i in range(40):
    acc += (str(i),)
    if i % 2 == 0:
        acc = acc + acc[-1:]
print(len(acc), acc[:5], acc[-3:], acc.count("38"), acc.index("10"))
t = parts("x.y") + parts("z")
u = t
t += ("w",)
print(t, u, t is u, t == ("x", "y", "z", "w"), u < t)
for s in parts("p.q") + ("r",):
    print(s, end=" ")
print()
