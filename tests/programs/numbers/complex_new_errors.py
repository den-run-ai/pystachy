# complex()'s TypeErrors for a string with a second argument, raised when called after both
# arguments are evaluated (CPython's complex_new_impl), given by position or by keyword
def text(v: str, out: list[str]) -> str:
    out.append(v)
    return v


def num(v: int, out: list[str]) -> int:
    out.append(str(v))
    return v


seen: list[str] = []
for attempt in range(7):
    try:
        if attempt == 0:
            print(complex("1", 2))
        elif attempt == 1:
            print(complex(1, "2"))
        elif attempt == 2:
            print(complex("1", "2"))
        elif attempt == 3:
            print(complex(1j, "2"))
        elif attempt == 4:
            print(complex(real="1j", imag=2))
        elif attempt == 5:
            print(complex(imag=num(3, seen), real=text("x", seen)))
        else:
            print(complex(num(4, seen), text("y", seen)))
    except TypeError as error:
        print("TypeError", error)
print(seen)
print(complex(real=1, imag=2), complex(imag=2), complex(real="3+4j"), complex(imag=2.5, real=1j))
