# struct on bytes and on a bytearray, and hashlib on both: the best of ROUNDS runs of each
import hashlib
import struct
import sys
import time


def read_bytes(data: bytes, n: int) -> int:
    t = 0
    for i in range(n):
        a, b = struct.unpack_from("<IH", data, i * 6)
        t += a + b
    return t


def read_array(data: bytearray, n: int) -> int:
    t = 0
    for i in range(n):
        a, b = struct.unpack_from("<IH", data, i * 6)
        t += a + b
    return t


def read_copy(data: bytearray, n: int) -> int:
    # (what a bytearray needed before: its bytes copied for each call)
    t = 0
    for i in range(n):
        a, b = struct.unpack_from("<IH", bytes(data[i * 6:i * 6 + 6]), 0)
        t += a + b
    return t


def write_into(n: int) -> bytearray:
    buf = bytearray(n * 6)
    for i in range(n):
        struct.pack_into("<IH", buf, i * 6, i, i & 0xFFFF)
    return buf


def write_slices(n: int) -> bytearray:
    buf = bytearray(n * 6)
    for i in range(n):
        buf[i * 6:i * 6 + 6] = struct.pack("<IH", i, i & 0xFFFF)
    return buf


def write_join(n: int) -> bytes:
    parts: list[bytes] = []
    for i in range(n):
        parts.append(struct.pack("<IH", i, i & 0xFFFF))
    return b"".join(parts)


def main() -> None:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 200000
    rounds = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    names = ["write_into", "write_slices", "write_join", "read_bytes", "read_array", "read_copy", "sha256_bytes", "sha256_array"]
    best = [1e9] * len(names)
    sums: list[int] = [0] * len(names)
    digests: list[str] = [""] * len(names)
    for _ in range(rounds):
        t0 = time.perf_counter()
        a = write_into(n)
        t1 = time.perf_counter()
        b = write_slices(n)
        t2 = time.perf_counter()
        c = write_join(n)
        t3 = time.perf_counter()
        sums[3] = read_bytes(c, n)
        t4 = time.perf_counter()
        sums[4] = read_array(a, n)
        t5 = time.perf_counter()
        sums[5] = read_copy(a, n)
        t6 = time.perf_counter()
        digests[6] = hashlib.sha256(c).hexdigest()
        t7 = time.perf_counter()
        digests[7] = hashlib.sha256(a).hexdigest()
        t8 = time.perf_counter()
        ts = [t1 - t0, t2 - t1, t3 - t2, t4 - t3, t5 - t4, t6 - t5, t7 - t6, t8 - t7]
        for i in range(len(ts)):
            best[i] = min(best[i], ts[i])
        if not (a == b and bytes(a) == c):
            print("MISMATCH")
    print(n, sums[3], sums[4], sums[5], digests[6] == digests[7], digests[6][:16])
    for i in range(len(names)):
        print("%-13s %8.2f ms" % (names[i], best[i] * 1000))


main()
