# Documented deviation: a float to a float power is a float. A negative float to a fractional
# power, which CPython answers with a complex number, raises ValueError instead (complex(x) ** y
# gives CPython's result).
x = -8.0
print(x ** 2.0, x ** 1.0)
print(x ** 0.5)
