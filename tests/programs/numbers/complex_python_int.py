# pystachy: python-int
# complex numbers with promoting ints: an int operand as its float (OverflowError past a float),
# and an int compared with the real part exactly
c = 1 + 2j
big = 2 ** 70
print(c + big, big * c, c == 2 ** 53 + 1, complex(big, 1), -c, c ** 2)
try:
    print(c + 2 ** 1100)
except OverflowError as e:
    print("OverflowError:", e)
n = 3
print(c * n, n - c, complex(n), complex(n) == n)
