# complex() of strings, as CPython's complex_from_string_inner reads them, and its TypeErrors
def parse(text: str) -> str:
    try:
        return repr(complex(text))
    except ValueError as error:
        return "ValueError: " + str(error)


good = ["1", "1j", "j", "+j", "-j", "J", "1+2j", "1-2j", " 1+2j ", "(1+2j)", "( 1+2j )", "\t(1+2j)\n", "1+j", "1-j", "-1-j",
        "1e3j", "1.5e-3+2.5E+2J", ".5j", "5.", "5.j", ".5+.5j", "inf", "infj", "-inf+nanj", "nan", "nanj", "NaN+InFj", "infinity",
        "+Infinity-INFINITYj", "1_0+2_0j", "1_000.000_1e1_0j", "1e1_0", "1e400", "-1e400j", "1e-400", "-0j", "-0-0j", "0.0", "+1",
        "999999999999999999999999999999", "1.0000000000000002+1e-320j", "١+٢j", "1 ", " 1j", "(1)", "(j)", "1e5",
        "0j", "00", "1E2", "+.5e1j", "-.0", "3+4J"]
bad = ["", " ", "()", "(", ")", "1+2", "1 + 2j", "1+ 2j", "1 +2j", "(1+2j", "1+2j)", "((1+2j))", "j1", "1jj", "1+2j3", "0x10", "1e", "1e+",
       "e5", "+", "-", "++1", "1+-2j", "1++2j", "--1", ".", ".j", "1\x00", "1j\x00", "1_", "_1", "1__0", "1e_1", "1._5", "1_.5", "1_j",
       "one", "1i", "1+2i", "1,2", "1j+2", "j+1", "1+2jj", "(1+2j)j", "1 j", "+ j", "infi", "nanana", "i", "1+", "1-", "1e5e5",
       "é", "1é", "1.2.3", "1+2.j.", "(1 +2j)", "1+2j (", "+-j"]
for text in good:
    print(repr(text), parse(text))
for text in bad:
    print(repr(text), parse(text))
print(complex("1.5+2.5j") == complex(1.5, 2.5), complex(" -j ") == -1j, complex("2") + complex("3j"), abs(complex("3-4j")))
print(complex("1e308") * 1, complex("4j").imag, complex(str(complex(1.25, -0.5))), complex(repr(-0j)), complex(str(complex(float("inf"), float("-inf")))))
for attempt in range(5):
    try:
        if attempt == 0:
            print(complex("1", 2))
        elif attempt == 1:
            print(complex(1, "2"))
        elif attempt == 2:
            print(complex("1", "2"))
        elif attempt == 3:
            print(complex(1j, "2"))
        else:
            print(complex(real="1j", imag=2))
    except TypeError as error:
        print("TypeError", error)
