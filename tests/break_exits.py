# After a while True loop, a variable is assigned only if every break leaves it assigned: names
# assigned or deleted next to a break, at breaks of nested loops' else blocks and of loops nested
# in branches


def all_assign(x: int) -> int:
    while True:
        if x == 0:
            v = 10
            break
        if x == 3:
            v = 30
            break
        x -= 1
    return v


def dropped(x: int) -> int:
    w = 5
    while True:
        if x == 2:
            del w
            break
        if x > 5:
            break
        x += 1
    return w


def scan(xs: list[int]) -> int:
    i = 0
    while True:
        for v in xs:
            if v == i:
                break
        else:
            found = i
            break
        i += 1
    return found


def nested(n: int) -> int:
    while True:
        t = n
        if n > 2:
            while True:
                if n == 7:
                    u = 1
                    break
                n += 1
            if u > 0:
                k = t + u
                break
        n += 3
    return k + t


def exits(x: int) -> int:
    while True:
        w0 = x
        if x == 0:
            v0 = w0
            break
        w1 = x
        if x == 1:
            v1 = w1
            break
        w2 = x
        if x == 2:
            v0 = w2
            v2 = w2
            break
        x += 1
    return v0 + w2


print(all_assign(5), all_assign(2), dropped(7), scan([0, 1, 2]), scan([1, 0, 4, 2]), nested(0), nested(5))
print(exits(1))
