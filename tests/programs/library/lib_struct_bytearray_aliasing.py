# struct reads a bytearray's buffer in place: bytes unpacked from it are copies even where the
# bytearray fills its buffer, and each read after a write of the same bytes sees the write.
import struct


def rw(buf: bytearray, n: int) -> int:
    t = 0
    for i in range(n):
        (a,) = struct.unpack_from("<I", buf, 0)
        struct.pack_into("<I", buf, 0, a + 1)
        (b,) = struct.unpack_from("<I", buf, 0)
        t += b * 3 + a
    return t


def steps(buf: bytearray) -> list[int]:
    (a,) = struct.unpack("<I", buf)
    buf[0] = 9
    (b,) = struct.unpack("<I", buf)
    struct.pack_into("<B", buf, 1, 7)
    (c,) = struct.unpack("<I", buf)
    buf[2:4] = b"\x01\x02"
    (d,) = struct.unpack("<I", buf)
    x = buf[1]
    struct.pack_into("<H", buf, 0, 0x0505)
    y = buf[1]
    (s,) = struct.unpack("4s", buf)
    buf.reverse()
    (e,) = struct.unpack(">I", buf)
    return [a, b, c, d, x, y, e, len(s), s[0]]


def grow(n: int) -> int:
    buf = bytearray()
    t = 0
    for i in range(n):
        buf += b"\x00\x00"
        struct.pack_into("<H", buf, -2, i)
        (v,) = struct.unpack_from("<H", buf, len(buf) - 2)
        (w,) = struct.unpack_from("<H", buf, 0)
        t += v - w
    return t


def main() -> None:
    print(rw(bytearray(4), 1000), rw(bytearray(b"\xff\xff\xff\x00"), 10))
    print(steps(bytearray(b"\x01\x02\x03\x04")))
    print(grow(500))
    w = bytearray(b"abcdefgh" * 4)
    (s32,) = struct.unpack("32s", w)
    (p,) = struct.unpack_from("31p", w, 1)
    w[0] = 33
    w[2] = 33
    print(s32[:4], p[:4], w[:4])


main()
