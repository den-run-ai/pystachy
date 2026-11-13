# error: from_bytes through a class object that may be any class's (type[object]) is not supported: a builtin class
# int has a from_bytes of its own, which the class object may be: no missing attribute, and not
# compiled through any class's class object.
class A:
    @staticmethod
    def from_bytes(data: bytes, byteorder: str) -> int:
        return 7


def call(k: type) -> int:
    return k.from_bytes(b"\x01", "big")


print(call(A))
