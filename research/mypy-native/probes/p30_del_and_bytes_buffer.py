# bytes building for the fixed-format cache (librt.internal WriteBuffer/ReadBuffer analogue)
class WriteBuffer:
    def __init__(self) -> None:
        self.parts: list[bytes] = []
    def write_int(self, v: int) -> None:
        self.parts.append(bytes([v & 0xFF, (v >> 8) & 0xFF]))
    def getvalue(self) -> bytes:
        return b"".join(self.parts)
w = WriteBuffer()
w.write_int(513)
b = w.getvalue()
print(len(b), b[0], b[1], b)
