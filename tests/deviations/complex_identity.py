# Documented deviation: each imaginary literal makes a new complex number, where CPython shares a
# module's equal constants. x is y is False here, True in CPython; equality is CPython's.
x = 1j
y = 1j
z = x
print(x is z, x is y, x == y)
