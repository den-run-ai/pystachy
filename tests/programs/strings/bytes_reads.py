# bytes items, which compile to an inline read of the byte below the length and a runtime call
# otherwise: bytes from 0 to 255 (read unsigned), the bounds on both sides, negative indices,
# indices held in variables and computed, and the items of each kind of for loop and comprehension.
data = bytes(range(256))
probe = b"\x00\x7f\x80\xfe\xffA"
made = [probe, "é€".encode(), bytes([1, 200, 3]), probe[1:5], probe + b"z", b"ab" * 3, b""]

print([data[i] for i in range(0, 256, 15)], data[255], data[-1], data[-256])
for b in made:
    n = len(b)
    print(n, [b[i] for i in range(n)], [b[-i] for i in range(1, n + 1)])
    for i in [n - 1, n, -n, -n - 1, 2**62, -(2**62)]:
        try:
            print(" ", i, b[i])
        except IndexError as e:
            print(" ", i, "IndexError", e)

total = 0
for x in data:
    total = total * 7 + x & 0xFFFFFFFF
print(total)
for x in reversed(probe):
    total = total * 5 + x
print(total)
print([(i, x) for i, x in enumerate(probe)], list(zip(probe, probe[1:])), [x for x in probe if x > 127])
print(sum(x for x in data), max(probe), min(probe), list(probe), 255 in probe, 7 in probe)


def at(b: bytes, i: int) -> int:
    return b[i]


def hash_bytes(b: bytes) -> int:
    h = 5381
    for i in range(len(b)):
        h = (h * 33 + b[i]) & 0xFFFFFFFF
    return h


print(at(probe, 4), at(probe, -2), hash_bytes(data), hash_bytes(b""), hash_bytes(probe * 100))
try:
    print(at(b"", 0))
except IndexError as e:
    print("empty", e)
