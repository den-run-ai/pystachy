# pystachy: python-int
# listguard where lists may hold promoting ints: reads past the test before the loop are
# unchecked, and item assignments keep their checks, as a list's identity companion needs them
def scale(a: list[int], out: list[int], k: int) -> None:
    for i in range(len(a)):
        out[i] = a[i] * k


def total(a: list[int], n: int) -> int:
    s = 0
    for i in range(n):
        s += a[i] + a[i + 1]
    return s


def main() -> None:
    a = [2 ** 62, 3, -(2 ** 63), 2 ** 70, 5]
    out = [0] * 5
    scale(a, out, 2 ** 10)
    print(out)
    print(total(a, 4))
    try:
        total(a, 5)
    except IndexError as e:
        print("long", e)
    short = [0] * 3
    try:
        scale(a, short, 3)
    except IndexError as e:
        print("short", e, short)


main()
