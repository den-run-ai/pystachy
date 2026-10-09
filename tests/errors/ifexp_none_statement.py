# error: conditional expression has no value
# (CPython runs it: a statement that is a conditional expression whose arms are both None)
def main() -> None:
    xs: list[int] = []
    n = 3
    xs.append(n) if n < 5 else None
    print(xs)


main()
