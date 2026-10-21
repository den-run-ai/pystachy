# A function compiled in the middle of another's compile is compiled as it would be on its own
# (#822): put(dict) is compiled while put(Box)'s key display (i, ...) is being compiled, a key
# that put(Box) may make in its frame. put(dict) stores its key in the dict, which keeps it after
# put returns, so that key is not made in put's frame.
class Box:
    def __init__(self):
        self.last = 0

    def __setitem__(self, k: tuple[int, int], v: int) -> None:
        self.last = k[0] + k[1] + v


def put(o, i: int, d: dict[tuple[int, int], int]) -> int:
    o[(i, put(d, i - 1, d) if i else 0)] = 7
    return i


def probe2(m: dict[tuple[int, int], int], i: int) -> int:
    return 1 if (i, i + 1) in m else 0


def probe1(m: dict[tuple[int, int], int]) -> int:
    return probe2(m, 41) + probe2(m, 43)


d: dict[tuple[int, int], int] = {}
b = Box()
put(b, 1, d)
print(b.last)
print(probe1(d))
print(d)
print((0, 0) in d)
