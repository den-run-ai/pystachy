# a value of object that isinstance() narrows and that is then updated: an augmented assignment
# to a narrowed variable, a narrowed attribute (self.value, c.value) and a while loop's test store
# the new value as object again
class Counter:
    def __init__(self) -> None:
        self.value: object = 0

    def bump(self) -> None:
        v = self.value
        if isinstance(v, int):
            self.value = v + 1


def main() -> None:
    y: object = 5
    if isinstance(y, int):
        y += 1
    print(y)
    c = Counter()
    c.bump()
    c.bump()
    print(c.value)
    if isinstance(c.value, int):
        print(c.value * 3)
    s: object = "ab"
    if isinstance(s, str):
        s *= 2
    print(s)
    flag: object = False
    if isinstance(flag, bool) and not flag:
        print("false flag")
    n: object = 3
    while isinstance(n, int) and n > 0:
        n -= 1
    print(n)


main()
