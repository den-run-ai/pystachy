"""Fixed native recursion budgets differ from CPython; unwind state is reusable."""
type Value = int | list[Value]
type Leaf = int | str | list[Leaf]


def nested(depth: int) -> Value:
    value: Value = 1
    for _ in range(depth):
        value = [value]
    return value


def leafed(depth: int, leaf: Leaf) -> Leaf:
    value: Leaf = leaf
    for _ in range(depth):
        value = [value]
    return value


def compare(left: Leaf, right: Leaf) -> None:
    try:
        print(left == right)
    except RecursionError:
        print("equality depth guarded")
    try:
        print(len(repr(left)))
    except RecursionError:
        print("repr depth guarded")


def main() -> None:
    left = nested(600)
    right = nested(600)
    for _ in range(2):
        try:
            repr(left)
            print("repr accepted")
        except RecursionError:
            print("repr depth guarded")
        try:
            print(left == right)
        except RecursionError:
            print("equality depth guarded")
        print(nested(3), nested(3) == nested(3))
    first: list[Value] = []
    second: list[Value] = []
    first.append(first)
    second.append(second)
    try:
        print(first == second)
    except RecursionError:
        print("cycle equality guarded")
    print(first, first == first)
    # Comparison and repr follow at most 512 recursive alias edges, whatever the leaf: the leaf of
    # a value nested 513 deep is the 513th edge away.
    for depth in [512, 513]:
        compare(leafed(depth, 1), leafed(depth, 1))
        compare(leafed(depth, "a"), leafed(depth, "a"))


main()
