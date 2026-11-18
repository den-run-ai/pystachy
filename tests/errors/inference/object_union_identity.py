# error: comparing closed union values requires narrowing with isinstance() first
# A boxed number has no identity to compare: == compares the members, and is None tests None.
class Meter:
    pass


def same(a: "int | Meter", b: "int | Meter") -> bool:
    return a is b


print(same(1, Meter()))
