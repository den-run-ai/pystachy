# fieldtbaa (bytes_tbaa.tbaa): a program's loads of a bytes's length and of its bytes, and the loads
# and stores of a bytearray's buffer (lib/_pystachy_bytearray.py's primitives), carry the tags of
# "@str", a struct of their own beside the classes' and the lists' (Gen.str_tag): the length at
# offset 0, the bytes at 24. A bytes's bytes and a buffer's share one tag, so that LLVM keeps their
# order; the fields of Cursor and of the bytearray have tags of their own, which it tells apart.
class Cursor:
    def __init__(self, data: bytes) -> None:
        self.data = data
        self.pos = 0


def scan(c: Cursor) -> int:
    t = 0
    while c.pos < len(c.data):
        t += c.data[c.pos]
        c.pos += 1
    return t


def total(data: bytes) -> int:
    t = 0
    for x in data:
        t += x
    return t


def copy_into(b: bytearray, data: bytes) -> None:
    for i in range(len(data)):
        b[i] = data[i]


def main() -> None:
    b = bytearray(3)
    copy_into(b, b"xyz")
    b.append(1)
    print(scan(Cursor(b"abc")), total(b"xyz"), b[0], len(b))


main()
