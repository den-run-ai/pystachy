# is and is not where a closed union holds numbers or strs beside objects, lists or dicts, and
# no number or str of one operand can meet one of the other: an object, list or dict is the other
# operand by its pointer, and a number or str is never one.
class Sock:
    def __init__(self, fd: int) -> None:
        self.fd = fd


class Key:
    def __init__(self, obj: Sock | int) -> None:
        self.obj: Sock | int = obj


def same(k: Key, s: Sock) -> bool:
    return k.obj is s


def pick(n: int, s: Sock) -> Sock | str | None:
    if n == 0:
        return s
    if n == 1:
        return "text"
    return None


def rows(n: int, xs: list[int]) -> list[int] | str | float:
    if n == 0:
        return xs
    if n == 1:
        return "xs"
    return 1.5


a = Sock(3)
b = Sock(4)
keys = [Key(a), Key(7), Key(b)]
for k in keys:
    print(same(k, a), k.obj is not b, k.obj is b, a is k.obj, b is not k.obj)
for n in range(3):
    got = pick(n, a)
    print(got is a, got is not a, got is b, got is None, a is got)
mine = [1, 2]
other = [1, 2]
for n in range(3):
    held = rows(n, mine)
    print(held is mine, held is other, held is not mine, mine is held)
