# in, count() and index() of a tuple compare a complex number and an int, a float or a bool as ==
# does (PyObject_RichCompareBool): equal where the imaginary part is zero and the real parts are
z = complex(1, 0)
w = 2.5 + 0j
print(1 in (z,), z in (1,), 1.0 in (z, 2), z in (0, 1.0), True in (z,), z in (True,))
print(2.5 in (w,), w in (2, 2.5), 3 in (z, w), z in (2, 3), 1j in (1, 2), 1 in (1j,))
t = (1, z, 2.0, 3j)
print(t.count(1), t.count(z), t.index(z), t.index(2), t.count(2 + 0j), 3j in t, 3 in t)
ints = (0, 1, 2)
print(z in ints, ints.index(z), ints.count(z), complex(2.5) in ints, repr(z))
try:
    ints.index(1j)
except ValueError as e:
    print("ValueError", e)
