# pystachy: python-int
# a float or bool | None compared with a promoting int past 64 bits: by value, as CPython compares
# them (each tested for None first)
def main() -> None:
    big = 2 ** 70
    f: float | None = 2.5
    b: bool | None = True
    n: float | None = None
    print(f == big, big == f, f != big, f < big, big > f, b == big, n == big, n != big)
    g: float | None = float(2 ** 70)
    print(g == big, big == g, g == big + 1)


main()
