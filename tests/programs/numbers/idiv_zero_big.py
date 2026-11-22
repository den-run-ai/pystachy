# int / int beyond the exact range of floats: a zero dividend (whose bit length the rounding
# code must not take), signed zeros, operands around 2**53, 2**62 and the ends of the 64-bit
# range, divisors above 2**53; the last division is by zero
import sys

big = sys.maxsize
low = -big - 1
p53 = 2 ** 53
p60 = 2 ** 60
p62 = 2 ** 62
zero = 0
neg_zero = -zero
print(0 / (1 << 60), 0 / -(1 << 60), -0 / (1 << 60), -0 / -(1 << 60), 0 / big, 0 / low)
print(zero / p60, zero / -p60, neg_zero / p60, neg_zero / -p60, zero / (p53 + 1), zero / -(p53 + 1))
print(zero / big, zero / low, zero / 1, zero / -1, neg_zero / -1, zero / p53, zero / -p53)
print(1 / p60, -1 / p60, 1 / -p60, -1 / -p60, 1 / big, -1 / big, 1 / low, -1 / low)
print(low / 1, low / -1, low / low, low / big, big / low, big / big, big / -1, p62 / low)
ns = [0, -0, 1, -1, 2, 3, p53 - 1, p53, p53 + 1, p53 + 2, p53 + 3, -(p53 + 1), p62 - 1, p62, p62 + 1, -p62, big - 1, big, low + 1, low]
ds = [1, -1, 3, -7, p53 - 1, p53, p53 + 1, -(p53 + 1), p53 + 3, p60, -p60, p60 + 1, p62 + 3, -p62, big, low]
for n in ns:
    print(n, [n / d for d in ds])
for d in ds:
    print(d, [d / n for n in ns if n != 0])
# At 1.0, successive floats differ by 1024 / p62. Check both ties and their neighbors.
for offset in (511, 512, 513, 1535, 1536, 1537):
    n = p62 + offset
    print((n / p62).hex(), (-n / p62).hex(), (n / -p62).hex(), (-n / -p62).hex())
print(zero / zero)
