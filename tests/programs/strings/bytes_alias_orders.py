# The orders that a wrong alias tag would change (Gen.str_tag): a bytearray's byte read after a
# write of it in one function, its length and buffer after a growth, the bytes of a bytes read
# beside stores of fields and list items, and a field kept across byte writes. Each value is
# computed at run time, so that no constant can stand in for a load.
import struct
import sys


class Tally:
    def __init__(self) -> None:
        self.count = 0
        self.last = -1


def read_modify_read(b: bytearray, n: int) -> int:
    t = 0
    for _ in range(n):
        x = b[0]
        b[0] = (x + 1) & 255
        t += b[0] * 3 + x
    return t


def read_after_write_at(b: bytearray, at: list[int], n: int) -> int:
    # (indices equal at run time that the compiler cannot prove equal: only the tags tell LLVM
    # whether the write may change what the second read reads)
    t = 0
    for k in range(n):
        i = at[k % 2]
        j = at[(k + 1) % 2]
        x = b[j]
        b[i] = (x + 1) & 255
        t += b[j] * 3 + x
    return t


def struct_read_after_write_at(b: bytearray, at: list[int], n: int) -> int:
    t = 0
    for k in range(n):
        (v,) = struct.unpack_from("<H", b, at[k % 2])
        struct.pack_into("<H", b, at[(k + 1) % 2], (v * 7 + k) & 0xFFFF)
        (w,) = struct.unpack_from("<H", b, at[k % 2])
        t += v + w * 5
    return t


def grow_and_read(n: int) -> int:
    b = bytearray()
    t = 0
    for i in range(n):
        b.append(i & 255)
        t += b[i] + len(b) + b[-1]
    return t


def field_between(data: bytes, tally: Tally) -> int:
    t = 0
    for i in range(len(data)):
        tally.count += 1
        tally.last = data[i]
        t += data[i] + tally.count
    return t


def list_between(data: bytes, out: list[int]) -> int:
    t = 0
    for i in range(len(data)):
        out[i % len(out)] = data[i] * 2
        t += out[i % len(out)] + data[i]
    return t


def field_across_writes(b: bytearray, tally: Tally, n: int) -> int:
    t = 0
    for i in range(n):
        tally.count += 2
        b[i % len(b)] = tally.count & 255
        t += tally.count + b[i % len(b)]
    return t


def struct_steps(b: bytearray, n: int) -> int:
    t = 0
    for i in range(n):
        (v,) = struct.unpack_from("<H", b, 0)
        struct.pack_into("<H", b, 0, (v * 7 + i) & 0xFFFF)
        (w,) = struct.unpack_from("<H", b, 0)
        b[1] = b[0]
        t += v + w * 5 + b[1]
    return t


def main() -> None:
    n = len(sys.argv) + 199  # (a run-time count)
    data = bytes([(i * 37 + 11) & 255 for i in range(n)])
    tally = Tally()
    print(read_modify_read(bytearray(b"\x05\x00"), n), grow_and_read(n))
    print(field_between(data, tally), tally.count, tally.last)
    print(list_between(data, [0, 0, 0]), field_across_writes(bytearray(5), tally, n), tally.count)
    print(struct_steps(bytearray(b"\x01\x02\x03"), n))
    zero = [n - n, n * 0]  # (two zeros)
    print(read_after_write_at(bytearray(b"\x05\x09"), zero, n), struct_read_after_write_at(bytearray(b"\x01\x02\x03"), zero, n))


main()
