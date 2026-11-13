# complex numbers: literals, complex(), arithmetic with ints and floats in either order, repr's
# signed zeros, equality, hash, truth and the parts (lib/_pystachy_complex.py)
a = 1 + 2j
b = complex(3, -4)
print(a, b, a + b, a - b, a * b, a / b)
print(-a, +a, abs(b), a.real, a.imag, a.conjugate())
print(a == 1 + 2j, a != b, a == 1, complex(2, 0) == 2, complex(2, 0) == 2.0, 3 != complex(3.0, 0.0))
print(1j, -1j, 0j, -0j, complex(), complex(1.5), complex(b), complex(True, False))
print(2 ** a, a ** 2, a ** 0.5, 1 / a, 2.5 - a, True + 1j, 2.5 * 1j, 1j * 1j)
print(hash(complex(3, 0)) == hash(3), hash(1.5 + 2.5j), hash(complex(-1, 0)), bool(0j), bool(a), not complex(0.0, -0.0))
print(complex(1j, 2), complex(1, 2j), complex(1j, 2j), complex(1, -0.0), complex(imag=2), complex(real=1.5, imag=-2))
print(complex(-0.0, -0.0), complex(0.0, -0.0), complex(-0.0, 1.0), 1e16 + 1e-5j, complex(1e15, 0.0))
print(complex(-0.0, 0.0) + 0, complex(1.0, -0.0) + 1, 1.0 - complex(0.0, 0.0), complex(1.0, 0.0).conjugate())
print(complex(2.0 ** 53, 0.0) == 2 ** 53 + 1, complex(1.0, 0.0) == True, 1j == None, 1j != "1j", 1j == [1j])
x = 3 - 4j
x += 1
x *= 1j
x -= 2.5
x /= 2
x **= 2
print(x, type(x).__name__, isinstance(x, complex), isinstance(1, complex), isinstance(1.0, complex))
