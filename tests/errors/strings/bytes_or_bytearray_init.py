# error: bytes in a closed union is not supported (use scalar, list/dict or native class/file types)
# (an ordinary class's __init__ types its fields from its parameters, so it takes no parameter
# that each call types: bytes | bytearray is a function's or a method's other than __init__'s)
class Reader:
    def __init__(self, data: bytes | bytearray) -> None:
        self.n = len(data)


print(Reader(b"abc").n)
