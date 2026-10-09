# Templates whose return None comes before a return of an object: the None returns are
# placeholders until the function's end shows that it returns an object (or nothing).
class Box:
    def __init__(self, v: int) -> None:
        self.v = v


def pick(flag, v):
    if not flag:
        return None
    return Box(v)


def find(xs, k):
    for x in xs:
        if x.v > k:
            return None
        if x.v == k:
            return x
    return None


def log(msg, n):
    if n == 0:
        return None
    print(msg, n)


b = pick(True, 3)
if b is not None:
    print(b.v)
print(pick(False, 4) is None)
boxes = [Box(1), Box(5), Box(9)]
f = find(boxes, 5)
print(f is not None and f.v == 5, find(boxes, 4) is None, find(boxes, 10) is None)
log("n =", 0)
log("n =", 2)
