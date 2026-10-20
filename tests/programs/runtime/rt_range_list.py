# Pointer-free range-list buffers still support ordinary list mutation and copying.
def exercise(start: int, stop: int, step: int) -> None:
    xs = list(range(start, stop, step))
    copied = xs.copy()
    middle = xs[1:-1]
    print("range", xs, copied, middle)
    xs.append(99)
    xs.insert(0, -7)
    xs.extend(copied)
    xs.extend(xs)
    xs[0] = 13
    print("mutated", xs, copied, middle)
    xs.clear()
    xs.append(5)
    print("reused", xs)


exercise(0, 0, 1)
exercise(2, 11, 3)
exercise(7, -3, -3)

# Exercise a large-object buffer, then generic growth and a copied/sliced buffer.
large = list(range(2048))
large.append(2048)
copied_large = large.copy()
large[0] = -1
tail = large[-4:]
print("large", len(large), sum(large), copied_large[0], tail)
