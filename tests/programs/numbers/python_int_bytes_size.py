# pystachy: python-int
# bytes(n) accepts a runtime promoting int and checks its native size boundary
# before allocating (#1042). The boundary's OverflowError text follows the
# documented fixed-width conversion policy; compare the exception class here.
import sys

n = len(sys.argv) * 3
print(bytes(n), bytes(source=n), bytes(n - n), bytes(True), bytes(False))


def zeros(size: int) -> bytes:
    return bytes(size)


print(zeros(n), zeros(0))
for negative in [-n, -sys.maxsize - 1]:
    try:
        print(zeros(negative))
    except ValueError as error:
        print("ValueError:", error)

for large in [sys.maxsize + 1, -sys.maxsize - 2, 2 ** 100, -(2 ** 100)]:
    try:
        print(zeros(large))
    except OverflowError:
        print("OverflowError")

# A rejected size must not leave partial bytes state for a subsequent call.
print(zeros(n + 1), bytes([0, 65, 255]), bytes(range(n)), bytes(b"kept"))
