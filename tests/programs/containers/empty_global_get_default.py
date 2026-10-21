# An empty global dict whose first use is d.get(k, []) or d.setdefault(k, []) in a function
# that returns it (the declared return type types the default) or assigns it to an annotated
# variable: a read in another function compiled first compiles that one, whatever their order.
D = {}
E = {}


def show() -> None:
    print(D, E)


def first(k: str) -> list[int]:
    return D.get(k, [])


def count(k: str) -> None:
    xs: list[int] = E.setdefault(k, [])
    xs.append(3)


print(first("a"))
count("b")
show()
