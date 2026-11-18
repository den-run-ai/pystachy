# struct reads a bytearray in place (unpack, unpack_from, iter_unpack) and pack_into() writes into
# one: the offset checked, the struct's bytes zeroed, then each item stored, as CPython does.
import struct

HEAD = struct.Struct("<HI")


def show(what: str, b: bytearray) -> None:
    print(what, b.hex(), len(b))


def main() -> None:
    b = bytearray(b"\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c")
    print(struct.unpack("<IHHI", b), struct.unpack_from("<H", b, 2), struct.unpack_from(">I", b, -4))
    print(struct.unpack_from("<2s?b", b), struct.unpack_from("<B", buffer=b, offset=1))
    print(list(struct.iter_unpack("<HB", b)), HEAD.unpack_from(b, 3), HEAD.unpack(b[:6]))
    b.append(13)
    b.extend(bytes(40))
    print(struct.unpack_from("<I", b, 9), len(list(struct.iter_unpack("<I", b[:52]))))
    out = bytearray(16)
    struct.pack_into("<IH", out, 0, 0x04030201, 0x0605)
    show("le", out)
    struct.pack_into(">hxb", out, 8, -2, 7)
    show("be", out)
    struct.pack_into("<3sx?", out, -5, b"ab", True)
    show("tail", out)
    struct.pack_into("@bi", out, 4, 1, 2)
    show("native", out)
    struct.pack_into("<d", out, 0, 1.5)
    show("float", out)
    struct.pack_into("", out, 16)
    HEAD.pack_into(out, 10, 0xFFFF, 0xFFFFFFFF)
    show("Struct", out)
    vals = (9, 8)
    struct.pack_into("<BB", out, 0, *vals)
    show("star", out)
    out = bytearray(b"\xff" * 8)
    try:
        struct.pack_into("<BxHB", out, 1, 1, 2, 256)
    except struct.error as e:
        print("error:", e)
    show("partial", out)
    for off in (5, -9, -3, 8):
        try:
            struct.pack_into("<I", out, off, 1)
        except struct.error as e:
            print("error:", e)
    for off in (9, -13):
        try:
            print(struct.unpack_from("<I", b, len(b) - 3 if off > 0 else -len(b) - 1))
        except struct.error as e:
            print("error:", e)
    try:
        struct.unpack("<I", bytearray(3))
    except struct.error as e:
        print("error:", e)
    try:
        list(struct.iter_unpack("<H", bytearray(3)))
    except struct.error as e:
        print("error:", e)
    grow = bytearray()
    for i in range(300):
        grow += bytes(4)
        struct.pack_into("<I", grow, i * 4, i * i)
    total = 0
    for i in range(300):
        total += struct.unpack_from("<I", grow, i * 4)[0]
    print(total, len(grow), grow[-4:])


main()
