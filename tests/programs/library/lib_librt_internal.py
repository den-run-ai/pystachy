# librt.internal, mypy's cache codec (lib/librt/internal.py here, librt 0.16.0's C extension in
# CPython): each value's bytes at the formats' boundaries, the values read back, extract_symbol's
# skip over nested cache objects, and the errors of truncated or invalid data, with the position
# a failed read leaves.
from librt.internal import (
    ReadBuffer,
    WriteBuffer,
    cache_version,
    extract_symbol,
    read_bool,
    read_bytes,
    read_float,
    read_int,
    read_str,
    read_tag,
    write_bool,
    write_bytes,
    write_float,
    write_int,
    write_str,
    write_tag,
)

INTS = [0, 1, -1, -10, -11, 117, 118, -100, -101, 16283, 16284, -10000, -10001, 536860911,
        536860912, 2147483648, -2147483648, 4611686018427400249, -9223372036854775807 - 1,
        9223372036854775807, 255, 256, 65536]
STRS = ["", "a", "héllo wörld", "\U0001f40d snake", "x" * 117, "y" * 118, "z" * 16283, "w" * 16284]
BLOBS = [b"", b"\x00\xff", bytes(range(256))]
FLOATS = [0.0, -0.0, 1.5, -2.25, 1e308, 5e-324, float("inf"), float("-inf"), 0.1]

for x in INTS:
    w = WriteBuffer()
    write_int(w, x)
    print(x, w.getvalue().hex())
for s in STRS:
    w = WriteBuffer()
    write_str(w, s)
    v = w.getvalue()
    print(len(s), len(v), v[:8].hex())
for b in BLOBS:
    w = WriteBuffer()
    write_bytes(w, b)
    print(len(b), w.getvalue()[:6].hex())
for f in FLOATS:
    w = WriteBuffer()
    write_float(w, f)
    print(f, w.getvalue().hex())

w = WriteBuffer()
for x in INTS:
    write_int(w, x)
for s in STRS:
    write_str(w, s)
for b in BLOBS:
    write_bytes(w, b)
for f in FLOATS:
    write_float(w, f)
write_bool(w, True)
write_bool(w, False)
for t in (0, 7, 254, 255):
    write_tag(w, t)
data = w.getvalue()
print(len(data), cache_version())
r = ReadBuffer(data)
print([read_int(r) for _ in INTS] == INTS, [read_str(r) for _ in STRS] == STRS)
print([read_bytes(r) for _ in BLOBS] == BLOBS, [read_float(r) for _ in FLOATS])
print(read_bool(r), read_bool(r), [read_tag(r) for _ in range(4)])

# A cache class's fields: everything up to its END_TAG (255), which extract_symbol returns
w = WriteBuffer()
write_tag(w, 4)
write_str(w, "name")
write_tag(w, 3)
write_int(w, 1000000000000)
write_tag(w, 20)
write_int(w, 3)
write_tag(w, 2)
write_tag(w, 1)
write_tag(w, 60)
write_tag(w, 6)
write_float(w, 2.5)
write_tag(w, 255)
write_tag(w, 80)
write_tag(w, 81)
write_str(w, "builtins.int")
write_tag(w, 80)
write_tag(w, 85)
write_tag(w, 80)
write_tag(w, 82)
write_tag(w, 5)
write_bytes(w, b"\x01\x02")
write_tag(w, 255)
write_tag(w, 30)
write_int(w, 2)
write_str(w, "k")
write_tag(w, 21)
write_int(w, 2)
write_int(w, 5)
write_int(w, -9223372036854775807)
write_str(w, "j")
write_tag(w, 22)
write_int(w, 1)
write_str(w, "s")
write_tag(w, 24)
write_int(w, 1)
write_tag(w, 7)
write_float(w, 1.0)
write_float(w, -1.0)
write_tag(w, 8)
write_str(w, "a")
write_str(w, "b")
write_tag(w, 255)
write_tag(w, 99)
r = ReadBuffer(w.getvalue())
sym = extract_symbol(r)
print(len(sym), sym[:12].hex(), sym[-6:].hex(), read_tag(r))

failures = [b"", b"\x0f", b"\x1e\x41", b"\x18\xff\xfe", b"\x02", b"\x0f\x03\x05", b"\x09\xff"]
for b in failures:
    for kind in range(7):
        r = ReadBuffer(b)
        try:
            if kind == 0:
                print(read_int(r), end=" ")
            elif kind == 1:
                print(repr(read_str(r)), end=" ")
            elif kind == 2:
                print(repr(read_bytes(r)), end=" ")
            elif kind == 3:
                print(read_bool(r), end=" ")
            elif kind == 4:
                print(read_float(r), end=" ")
            elif kind == 5:
                print(read_tag(r), end=" ")
            else:
                print(extract_symbol(r).hex(), end=" ")
        except ValueError as e:
            print(f"ValueError({e})", end=" ")
    print()
for b in [bytes([9, 255]), bytes([50, 255]), bytes([254]), bytes([80, 90]), bytes([4, 15])]:
    try:
        print(extract_symbol(ReadBuffer(b)).hex())
    except ValueError as e:
        print("ValueError", e)
r = ReadBuffer(b"\x1e\x41")
try:
    read_str(r)
except ValueError as e:
    print("ValueError", e, read_tag(r))
r = ReadBuffer(b"\x18\xff\xfe\x07")
try:
    read_str(r)
except UnicodeDecodeError as e:
    print("UnicodeDecodeError", e, read_tag(r))
# (classes nested 2000 deep: the extension recurses in C, the port keeps a stack)
deep = bytes([51] * 2000 + [255] * 2001 + [7])
r = ReadBuffer(deep)
print(len(extract_symbol(r)), read_tag(r))
