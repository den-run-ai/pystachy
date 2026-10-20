# pow(a, b, m) reduces in 128 bits: -2**63 % -1 traps in 64-bit arithmetic, and CPython gives 0.
# The operands come from stdin too, so that no constant folding hides the runtime's arithmetic.
import sys

a = int(input())
m = int(input())
print(pow(a, 2, m), pow(a, 1, m), pow(a, 0, m), pow(a, 3, -m), pow(a, 5, a), pow(a, 7, 1000000007))
lo = -sys.maxsize - 1
hi = sys.maxsize
print(pow(lo, 2, -1), pow(lo, 3, 1), pow(lo, 2, lo), pow(lo, 3, hi), pow(hi, hi, lo), pow(-3, 3, lo))
print(pow(5, 3, -7), pow(-5, 3, 7), pow(-5, 3, -7), pow(2, 0, -1), pow(0, 0, 5), pow(lo + 1, hi, hi))
