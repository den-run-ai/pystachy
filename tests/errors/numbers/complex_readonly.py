# error: complex_readonly.py:4: error: readonly attribute
# (CPython's AttributeError: a complex number's real and imag cannot be assigned)
z = complex(1, 2)
z.real = 3.0
print(z)
