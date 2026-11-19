# pystachy: python-int
# (k, v) in d.items() of a dict that holds promoting ints as its values looks k up once, calling
# its __hash__ and then __eq__ on the key found, and compares the value found with v, as
# CPython's dictitems_contains does; v and the values may pass 64 bits, as may int keys.
import sys

ONE = len(sys.argv) - 2  # (1, which the compiler does not know)
BIG = 2 ** 70 * ONE


class K:
    def __init__(self, v: int) -> None:
        self.v = v

    def __eq__(self, o: "K") -> bool:
        print("  eq", self.v, o.v)
        return self.v == o.v

    def __hash__(self) -> int:
        print("  hash", self.v)
        return self.v % 3


objs: dict[K, int] = {K(1): BIG, K(2): 2}
print("small value")
print((K(2), 2) in objs.items())
print("big value")
print((K(1), BIG) in objs.items())
print("other value")
print((K(2), 3) in objs.items(), (K(1), BIG + 1) not in objs.items())
print("missing key")
print((K(5), 2) in objs.items())
names: dict[str, int] = {"a": BIG, "b": 3}
print(("a", BIG) in names.items(), ("a", BIG + 1) in names.items(), ("b", 3) in names.items(), ("c", 3) in names.items())
ints: dict[int, int] = {BIG: 1, 5: 2}
print((BIG, 1) in ints.items(), (5, 2) in ints.items(), (6, 2) in ints.items(), (BIG, 2) in ints.items())
