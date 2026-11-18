# A class object that may be None is a dict key and a set element, as a str that may be None is:
# None hashes and compares as itself beside the class objects, which compare by identity
class A:
    pass


class B(A):
    pass


def pick(flag: int) -> type[A] | None:
    if flag == 0:
        return None
    return A if flag == 1 else B


d: dict[type[A] | None, int] = {}
for i in range(3):
    d[pick(i)] = i
print(len(d), d[None], d[A], d[B], None in d, pick(2) in d)
s = {pick(0), pick(1), pick(2), pick(1)}
print(len(s), None in s, A in s, B in s)
print(sorted(["-" if k is None else k.__name__ for k in d]))
