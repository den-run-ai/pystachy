# bytearray as a class object: type(b), and the class kept in a variable and called, which makes its
# objects as bytearray(...) does (lib's _new, through Gen.class_new)
def main() -> None:
    b = bytearray(b"ab")
    t = type(b)
    print(t is bytearray, t.__name__, type(b).__name__, isinstance(b, bytearray))
    k = bytearray
    print(k(b"xy"), k(2), k is bytearray)
    r = range(3)
    print(type(r) is range, type(r).__name__)


main()
