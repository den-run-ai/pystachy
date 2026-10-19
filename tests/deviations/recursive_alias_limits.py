"""Fixed native recursion budgets differ from CPython; unwind state is reusable."""
type Value = int | list[Value]


def nested(depth: int) -> Value:
    value: Value = 1
    for _ in range(depth):
        value = [value]
    return value


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


main()
