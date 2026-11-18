import struct
import sys


def read_bytes(data: bytes, n: int) -> int:
    t = 0
    for i in range(n):
        a, b = struct.unpack_from("<IH", data, i * 6)
        t += a + b
    return t


def main() -> None:
    n = int(sys.argv[1])
    parts: list[bytes] = []
    for i in range(n):
        parts.append(struct.pack("<IH", i, i & 0xFFFF))
    data = b"".join(parts)
    t = 0
    for _ in range(int(sys.argv[2])):
        t += read_bytes(data, n)
    print(t)


main()
