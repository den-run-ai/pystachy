"""Distinct recursive cycles raise, and comparison state remains reusable."""
type Value = int | list[Value]


def main() -> None:
    first: list[Value] = []
    second: list[Value] = []
    first.append(first)
    second.append(second)
    for _ in range(2):
        try:
            print(first == second)
        except RecursionError:
            print("cycle equality guarded")
        print(first, first == first)
        left: list[Value] = [[1], 2]
        right: list[Value] = [[1], 2]
        print(left, left == right)


main()
