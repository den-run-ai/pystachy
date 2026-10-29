# pystachy: python-int
# Proven Any ints are read as typed operands; the wide result never becomes Any.
import provenints


def run() -> None:
    total = 2 ** 70
    for value in provenints.values():
        if isinstance(value, int):
            print("wide orders", total + value, value + total)
            total += value
            print("wide accumulator", total)
            print("wide bitwise", total & value, value & total, total | value, value | total, total ^ value, value ^ total)
        else:
            print("wide non-int", type(value).__name__, value)
    print("wide total", total)
