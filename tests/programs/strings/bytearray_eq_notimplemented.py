# bytearray == x and != x of an operand that is no bytes: bytearray's methods give way to x's own
# __eq__ (NotImplemented), as in CPython.
class AlwaysEq:
    def __eq__(self, other: object) -> bool:
        return True


class Plain:
    pass


x = AlwaysEq()
b = bytearray(b"a")
print(b == x, b != x, b == Plain(), b != Plain(), b == 3, b != "a")
print(b == b"a", b != b"a", b == bytearray(b"a"), b != bytearray(b"b"))
