# decimal arithmetic, comparison, quantizing and conversion over a grid of operands, in several
# precisions and all eight rounding modes: each operation's results are folded into a digest,
# which CPython's decimal must reproduce exactly (a raised signal counts by its class and text).
from decimal import (ROUND_05UP, ROUND_CEILING, ROUND_DOWN, ROUND_FLOOR, ROUND_HALF_DOWN, ROUND_HALF_EVEN, ROUND_HALF_UP, ROUND_UP,
                     Decimal, DecimalException, getcontext)

ROUNDINGS = [ROUND_CEILING, ROUND_FLOOR, ROUND_UP, ROUND_DOWN, ROUND_HALF_UP, ROUND_HALF_DOWN, ROUND_HALF_EVEN, ROUND_05UP]
TEXTS = ["0", "-0", "0E+3", "0.00", "1", "-1", "1.0", "2", "3", "-7", "10", "0.1", "0.5", "-0.5", "1.5", "2.5", "0.25", "0.125",
         "9.99", "0.001", "1E-7", "1E+7", "123.456", "-987.654321", "99999", "0.99999", "1.00001", "3.14159265358979323846",
         "2.71828182845904523536", "12345678901234567890", "0.000012345678901234567890", "999999999999999999999999999999",
         "1E-20", "5E+20", "0.3333333333333333333333333333", "6.67E-11", "-299792458", "1.05", "17.5", "0.07", "45", "50", "55"]
SPECIAL = ["Infinity", "-Infinity", "NaN"]


def fold(digest: int, text: str) -> int:
    for ch in text:
        digest = (digest * 1000003 + ord(ch)) % 2147483647
    return (digest * 31 + 7) % 2147483647


class Tally:
    def __init__(self, name: str) -> None:
        self.name = name
        self.digest = 0
        self.count = 0
        self.raised = 0

    def add(self, text: str) -> None:
        self.digest = fold(self.digest, text)
        self.count += 1

    def fail(self, error: Exception) -> None:
        self.digest = fold(self.digest, type(error).__name__ + ": " + str(error))
        self.count += 1
        self.raised += 1

    def show(self) -> None:
        print(f"  {self.name:12} {self.count:6} results, {self.raised:4} raised, digest {self.digest}")


def binary(values: list[Decimal]) -> None:
    names = ["add", "sub", "mul", "div", "floordiv", "mod", "divmod", "compare", "order", "max_min", "quantize", "remnear", "fma"]
    tallies = [Tally(name) for name in names]
    for a in values:
        for b in values:
            for index in range(len(names)):
                tally = tallies[index]
                try:
                    if index == 0:
                        tally.add(str(a + b))
                    elif index == 1:
                        tally.add(str(a - b))
                    elif index == 2:
                        tally.add(str(a * b))
                    elif index == 3:
                        tally.add(str(a / b))
                    elif index == 4:
                        tally.add(str(a // b))
                    elif index == 5:
                        tally.add(str(a % b))
                    elif index == 6:
                        q, r = divmod(a, b)
                        tally.add(str(q) + " " + str(r))
                    elif index == 7:
                        tally.add(str(a.compare(b)) + str(a == b) + str(a != b) + (str(hash(a) == hash(b)) if a == b else ""))
                    elif index == 8:
                        tally.add(str(a < b) + str(a <= b) + str(a > b) + str(a >= b))
                    elif index == 9:
                        tally.add(str(a.max(b)) + " " + str(a.min(b)) + " " + str(a.copy_sign(b)) + str(a.same_quantum(b)))
                    elif index == 10:
                        tally.add(str(a.quantize(b)))
                    elif index == 11:
                        tally.add(str(a.remainder_near(b)))
                    else:
                        tally.add(str(a.fma(b, a)))
                except (DecimalException, ZeroDivisionError) as error:
                    tally.fail(error)
    for tally in tallies:
        tally.show()


def unary(values: list[Decimal]) -> None:
    names = ["sign", "sqrt", "normalize", "integral", "int", "float", "round", "pow", "text", "mixed", "tuple", "scaleb"]
    tallies = [Tally(name) for name in names]
    for a in values:
        for index in range(len(names)):
            tally = tallies[index]
            try:
                if index == 0:
                    tally.add(str(-a) + " " + str(+a) + " " + str(abs(a)) + " " + str(a.copy_negate()) + str(bool(a)))
                elif index == 1:
                    tally.add(str(a.sqrt()))
                elif index == 2:
                    tally.add(str(a.normalize()) + " " + a.to_eng_string() + " " + str(a.adjusted()) + a.number_class())
                elif index == 3:
                    tally.add(" ".join([str(a.to_integral_value(mode)) for mode in ROUNDINGS]))
                elif index == 4:
                    if a.is_finite() and a.adjusted() < 18:
                        tally.add(str(int(a)) + " " + str(hash(a)))
                    if a.is_finite() and a.adjusted() < 9 and a == round(a, 9):
                        tally.add(str(a.as_integer_ratio()))
                elif index == 5:
                    if a.is_finite():
                        tally.add(repr(float(a)))
                elif index == 6:
                    if a.is_finite() and a.adjusted() < 15:
                        tally.add(str(round(a)) + " " + str(round(a, 2)) + " " + str(round(a, -1)))
                elif index == 7:
                    tally.add(" ".join([str(a ** n) for n in [-3, -1, 1, 2, 3, 10, 17]]))
                elif index == 8:
                    tally.add(repr(a) + f"{a:.3f}|{a:e}|{a:,.2f}|{a:+.4g}|{a:%}|{a:>30}|{a:020.5f}")
                elif index == 9:
                    tally.add(str(a + 3) + str(3 + a) + str(a - 3) + str(3 - a) + str(a * 3) + str(3 * a) + str(a / 3) + str(a == 3) + str(a < 3) + str(a > 0.5))
                elif index == 10:
                    t = a.as_tuple()
                    tally.add(str(t.sign) + str(t.digits) + str(t.exponent))
                else:
                    tally.add(str(a.scaleb(3)) + " " + str(a.scaleb(-3)) + " " + " ".join([str(a.quantize(Decimal("0.01"), rounding=mode)) for mode in ROUNDINGS]))
            except (DecimalException, ZeroDivisionError, ValueError, OverflowError) as error:
                tally.fail(error)
    for tally in tallies:
        tally.show()


def formats(values: list[Decimal]) -> None:
    specs = ["", "f", ".0f", ".2f", ".10f", "e", ".0e", ".3E", "g", ".0g", ".5g", "G", "%", ".1%", "n", ">20", "<20.3f", "^21", "=+15.2f",
             "+", " ", "015.3f", ",", ",.2f", "_", "020,.1f", "z.1f", "#.0f", ".10", "#g", "x>12.4", "012", "+.0e", "e<25.6E", "-", "08.3e",
             ".05f", "_.3f", "^+9.2e", "0,", "*=14,.1f", " .4G", "z", "#", ".1", ".2%", "030_.4f", "!^11.3"]
    tally = Tally("format")
    bad = Tally("format bad")
    for a in values:
        for spec in specs:
            tally.add(format(a, spec))
        for spec in ["x", ".", "0<5", "<05", ",n", "1.2.3", "ff", "5,5", "--", ".f1"]:
            try:
                bad.add(format(a, spec))
            except ValueError as error:
                bad.fail(error)
    tally.show()
    bad.show()


finite = [Decimal(text) for text in TEXTS]
everything = finite + [Decimal(text) for text in SPECIAL]
context = getcontext()
for prec, rounding in [(28, ROUND_HALF_EVEN), (9, ROUND_HALF_UP), (5, ROUND_DOWN), (1, ROUND_05UP), (50, ROUND_CEILING), (3, ROUND_FLOOR),
                       (16, ROUND_UP), (7, ROUND_HALF_DOWN)]:
    context.prec = prec
    context.rounding = rounding
    print(f"prec={prec} rounding={rounding}")
    binary(everything if prec == 28 else finite)
    unary(everything)
    formats(everything)
