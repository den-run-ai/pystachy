# complex numbers: literals, complex(), real and imag, repr and str, comparisons, hashing, and
# complex numbers as dict keys, set elements and items of lists and tuples


class ComplexExpr:
    def __init__(self, value: complex) -> None:
        self.value = value


class Var:
    def __init__(self) -> None:
        self.final_value: complex | None = None


def parts(z: complex) -> list[float]:
    return [z.real, z.imag]


def twice(z: complex) -> complex:
    return z + z


def index(table: dict[complex, int], value: complex) -> int:
    if value not in table:
        table[value] = len(table)
    return table[value]


z = complex(1.0, 2.0)
w = 3j
print(z, w, repr(z), str(w), f"{z} {w!r}", "%s %r" % (z, w), [z, w], (z, 1), {"k": z})
print(z.real, z.imag, w.real, w.imag, parts(twice(z)), type(z).__name__, type(z.real).__name__)
print(1j, 0j, -1j, 2.5j, 1e3j, 1_0j, .5j, 1e400j, -0j, 0j * -1)
print(complex(), complex(3), complex(2.5), complex(True), complex(1, 2), complex(1.5, -0.0), complex(-0.0, 0.0), complex(-0.0, -0.0))
print(complex(real=4), complex(imag=5), complex(real=1, imag=2), complex(imag=2, real=1), complex(z), complex(z) is z)
print(complex(z, w), complex(1, w), complex(z, 4), complex(z, z), complex(w, w))
print(complex(float("inf"), 1), complex(1, float("-inf")), complex(float("nan"), float("nan")), complex(float("inf"), float("nan")))
print(complex(0.0, float("inf")), complex(-0.0, float("nan")), complex(1e16, 1e-5), complex(1.5e300, -2.5e-300), complex(123456789.125, 0.1))
print(z == complex(1, 2), z != complex(1, 2), z == w, z != w, z == z, complex(2, 0) == 2, complex(2, 0) == 2.0, complex(2, 1) == 2, 2 == complex(2, 0), 2.0 != complex(2, 0))
print(complex(1, 0) == True, complex(0, 0) == False, 9007199254740993 == complex(9007199254740992.0, 0), complex(9007199254740992.0, 0) == 9007199254740992)
nan = complex(float("nan"), 0)
print(nan == nan, nan != nan, [nan] == [nan], nan in [nan])
print(bool(z), bool(0j), bool(complex(0, 1)), bool(complex(-0.0, -0.0)), not z, "yes" if w else "no")
print(hash(complex(1.5, 0)) == hash(1.5), hash(complex(3, 0)) == hash(3), hash(complex(0, 0)), hash(complex(1, 2)), hash(complex(-1, -2)), hash(complex(0, 1)))
print(hash(complex(1e300, 1e300)), hash(complex(-1.5, 2.25)), hash(complex(2.0 ** 61 - 1, 3)), hash(complex(-1, 0)), hash(complex(-2, 0)), hash(complex(float("inf"), float("-inf"))))
print(hash(z) == hash(complex(1, 2)), hash(z) == hash(1.0) + 1000003 * hash(2.0))
table: dict[complex, int] = {}
print(index(table, 1j), index(table, complex(0, 1)), index(table, 2j), index(table, complex(0.0, 2.0)), index(table, 0j), index(table, -0j), table)
table[complex(5, 0)] = 50
print(table[complex(5, 0)], complex(5, 0) in table, complex(5, 1) in table, table.get(complex(9, 9)), len(table))
s = {1j, complex(0, 1), 2 + 0j, 2 + 0j}
print(len(s), 1j in s, complex(2, 0) in s, 3j in s, sorted([x.imag for x in s]))
xs: list[complex] = [3j, 1 + 1j]
xs.append(complex(2))
print(xs, xs.index(complex(2, 0)), xs.count(3j), 3j in xs, 4j in xs, xs == [3j, (1 + 1j), (2 + 0j)], xs[0] is xs[0])
e = ComplexExpr(complex(1.5, -2.0))
print(e.value, parts(e.value), isinstance(e.value, complex), isinstance(e, ComplexExpr))
v = Var()
print(v.final_value, v.final_value is None)
v.final_value = complex(3, 4)
print(v.final_value, v.final_value is None, abs(v.final_value) if v.final_value is not None else -1.0)
print(isinstance(z, complex), isinstance(1.0, complex), isinstance(1, complex), isinstance("1j", complex), isinstance(z, (int, float)), isinstance(z, (int, float, complex)), isinstance(z, float))
print(z.conjugate(), w.conjugate(), complex(1, -0.0).conjugate(), z.conjugate().conjugate() == z, abs(complex(3, 4)), abs(-5j), abs(0j))
maybe: complex | None = None
print(maybe, maybe is None)
maybe = w
print(maybe, maybe is not None and maybe.imag == 3.0)
pair: tuple[complex, str] = (1j, "i")
print(pair, pair[0] * pair[0], pair == (1j, "i"))
