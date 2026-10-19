# A for loop over a bytes tests its index against the length, which no bytes changes in place, then
# reads the item inline (statements.gen_seq_item): bytes_loop.calls pins that these loops call no
# pys_bytes_get. An indexed read b[i] reads inline below the length and calls pys_bytes_get otherwise
# (Gen.bytes_read), so that call stays in at(). PYSTACHY_OPT=-listget and -listfast restore the calls.
def total(b: bytes) -> int:
    t = 0
    for x in b:
        t += x
    return t


def pairs(a: bytes, b: bytes) -> int:
    n = 0
    for x, y in zip(a, b):
        n += x ^ y
    return n


def backwards(b: bytes) -> int:
    t = 0
    for x in reversed(b):
        t = t * 3 + x
    return t


def at(b: bytes, i: int) -> int:
    return b[i]


print(total(b"abc"), pairs(b"ab", b"ba"), backwards(b"\x01\x02"), at(b"xyz", -1))
