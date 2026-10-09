# a statement that is a conditional expression whose arms are a call returning None and None
def main() -> None:
    xs: list[int] = []
    for n in range(8):
        xs.append(n) if n < 5 else None
    print(xs)


main()
