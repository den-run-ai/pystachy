# Documented deviation: there are no complex numbers. A negative float to a fractional
# power, which CPython answers with a complex number, raises ValueError instead.
x = -8.0
print(x ** 2.0, x ** 1.0)
print(x ** 0.5)
