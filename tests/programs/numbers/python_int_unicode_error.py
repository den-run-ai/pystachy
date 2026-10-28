# pystachy: python-int
# Unicode exception positions accept promoting ints that fit Py_ssize_t and reject the rest.
def decode(start: int, end: int) -> None:
    try:
        raise UnicodeDecodeError("utf-8", b"a\xff", start, end, "bad byte")
    except UnicodeError as error:
        print(str(error), repr(error))


def encode(start: int, end: int) -> None:
    error = UnicodeEncodeError("ascii", "aé", start, end, "bad character")
    print(str(error), repr(error))


decode(1, 2)
decode(-1, 0)
encode(1, 2)
encode(0, 2)
print(repr(UnicodeDecodeError("x", b"x", True, False, "bool arguments")))
for big in [2 ** 64, -(2 ** 64)]:
    try:
        decode(big, 1)
    except OverflowError as error:
        print("decode start:", error)
    try:
        decode(0, big)
    except OverflowError as error:
        print("decode end:", error)
    try:
        encode(big, 1)
    except OverflowError as error:
        print("encode start:", error)
    try:
        encode(0, big)
    except OverflowError as error:
        print("encode end:", error)
