# bytearray as a class object: type(b) and the class kept in a variable, with CPython's name,
# module and repr, and called, which makes its objects as bytearray(...) does (lib's _new, through
# Gen.class_new)
def main() -> None:
    b = bytearray(b"ab")
    k = bytearray
    t = type(b)
    print(t, k, repr(t), str(k), t.__module__, t.__qualname__, k == t, k is t)
    ks = [k, t]
    print(ks[0](1), ks[1] is bytearray)


main()
