# z.__init__(...) of a complex number is object.__init__, which leaves it as complex_new made it:
# any arguments are evaluated and ignored, also by keyword and on None, so aliases, dict keys and
# the hash keep their value
def note(v: float, seen: list[str]) -> float:
    seen.append(str(v))
    return v


def get(flag: bool) -> complex | None:
    return 1j if flag else None


z = 1 + 2j
alias = z
table = {z: "k"}
before = hash(z)
seen: list[str] = []
print(z.__init__(note(3.0, seen), imag=note(4.0, seen)), z.__init__(), z.__init__(5.0, 6.0))
print(z, alias, table, z in table, hash(z) == before, seen)
x = get(False)
x.__init__(7.0)
y = get(True)
print(x, y.__init__(real=1.0), y)
