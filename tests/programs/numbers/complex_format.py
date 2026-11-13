# format() and f-strings of complex numbers: format_complex_internal's parts (a float's format,
# the imaginary part with its sign), repr's digits for no type, and its ValueErrors
inf = float("inf")
nan = inf - inf
specs = ["", ".2f", ">20", "<20", "^20", "*^20.3f", "+", " ", "-", "+.2e", "z.1f", "#", "#.0f", ".3", "10", ".0", "g",
         "G", "E", "n", ",.2f", "_.1f", "%", "d", "x", "010", "0>10", "=10", "+=10", "z", " .2g", ",", "_", "#,", "z.0f",
         "+z.0e", ",.3", "_g", ",d", "_x", ".", "1.2.3", "ab", ",_", "_,", "١٢", " ^9.1F"]
vals = [1.5 - 2.25j, 1j, complex(-0.0, -0.0), complex(1e20, 1e-20), complex(nan, -inf), 12345.678 + 9876.5j,
        complex(-0.0, 1.0), complex(-0.004, 0.0), complex(1e16, -123456789.0)]
for spec in specs:
    for v in vals:
        try:
            r = repr(format(v, spec))
        except ValueError as e:
            r = "ValueError: " + str(e)
        print(repr(spec), repr(v), r)
x = 3 - 4j
print(f"{x:>12.3f}|{x:+}|{x!r:>10}|{x}|{str(x)}")
