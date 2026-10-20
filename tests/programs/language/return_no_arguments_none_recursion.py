remaining = 3


def direct():
    global remaining
    if remaining == 0:
        return None
    remaining -= 1
    return direct()


print(direct(), remaining)
remaining = 4


def first():
    return second()


def second():
    global remaining
    if remaining == 0:
        return None
    remaining -= 1
    return first()


print(first(), remaining)


class Counter:
    def __init__(self, n: int) -> None:
        self.n = n

    def run(self):
        if self.n == 0:
            return None
        self.n -= 1
        return self.run()


c = Counter(5)
print(c.run(), c.n)
