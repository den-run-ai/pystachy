# complex numbers: CPython 3.13's IEEE special values and errors (runtime.c's ports of _Py_c_quot,
# complex_pow and _Py_c_abs): read at run time, so that no compile-time folding decides them
inf = float(input())
nan = inf - inf
huge = float(input())


def show(label: str, f) -> None:
    try:
        print(label, f())
    except ZeroDivisionError as e:
        print(label, "ZeroDivisionError:", e)
    except OverflowError as e:
        print(label, "OverflowError:", e)


zero = complex(0.0, 0.0)
show("div0", lambda: (1 + 2j) / zero)
show("rdiv0", lambda: 1 / zero)
show("fdiv0", lambda: 1.5 / zero)
show("pow0neg", lambda: zero ** -1)
show("pow0c", lambda: zero ** 1j)
show("pow00", lambda: zero ** 0)
show("powbig", lambda: complex(huge, huge) ** 2)
show("powovf", lambda: complex(huge * 1e108, 0.0) ** 1.5)
show("powneg", lambda: (1 + 2j) ** -2)
show("powc", lambda: 2 ** (1 + 1j))
show("powimag", lambda: (1j) ** (1j))
show("powreal", lambda: (-1) ** 0.5j)
show("abs", lambda: abs(complex(huge * 1e108, huge * 1e108)))
show("absovf", lambda: abs(complex(1.7e308, 1.7e308)))
show("absinfnan", lambda: abs(complex(inf, nan)))
show("absnan", lambda: abs(complex(nan, 1.0)))
show("quotinf", lambda: (1 + 1j) / complex(inf, inf))
show("prodinf", lambda: complex(inf, 0.0) * 2)
show("prodbig", lambda: complex(huge, huge) * complex(huge, huge))
show("reprs", lambda: [complex(nan, -inf), complex(1.0, -nan), complex(-inf, 0.0), complex(0.0, nan)])
show("eqnan", lambda: (complex(nan, 0.0) == complex(nan, 0.0), complex(nan, 0.0) != complex(nan, 0.0)))
