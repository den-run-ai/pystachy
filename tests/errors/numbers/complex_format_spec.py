# error: complex_format_spec.py:4: error: unsupported format string passed to complex.__format__
# (a format spec for a complex number is not supported: CPython prints 0.00+1.00j)
z = 1j
print(f"{z:.2f}")
