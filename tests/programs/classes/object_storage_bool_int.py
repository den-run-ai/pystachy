# isinstance(x, int) narrows a value of object to int | bool, which is the int it is wherever
# CPython reads a bool as its int and the result is an int either way: an index, a slice bound,
# a repetition count, range(), hex(), %d, a list method's index, **, << and >>, and &, | and ^
# with an int; an int | bool that an annotation makes takes them too
def use(v: object) -> None:
    x: object = v
    if isinstance(x, int):
        xs = [10, 20, 30, 40]
        print(xs[x], xs[x:], xs[:x], "abcd"[x], list(range(x)), list(range(x, 4)), [0] * x, "ab" * x)
        print(x ** 2, 2 ** x, x & 3, x | 4, x ^ 1, 3 & x, x << 2, 1 << x, x >> 1, -x, abs(x))
        print("%d|%x|%5d|%.1f" % (x, x, x, x), hex(x), oct(x), bin(x), x.bit_length(), divmod(x, 2))
        ys = [1, 2, 3, 4]
        print(ys.pop(x), ys, x == 1, repr(x), str(x))


def main() -> None:
    for o in [3, True, 2, False]:
        use(o)
    flags: list[int | bool] = [1, True, False, 2]
    names = ["zero", "one", "two"]
    for f in flags:
        print(names[f], f << 1, f ** 3, f)


main()
