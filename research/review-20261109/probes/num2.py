import math
import sys


def show(label: str, f) -> None:
    try:
        print(label, f())
    except Exception as e:
        print(label, type(e).__name__, e)


def floats(args: list[str]) -> None:
    one = len(args) + 1
    f1 = float(one)
    vals = [0.1, 1e16, 1e-5, 1e22, 1e21, 1.5e-7, 123456789012345680.0, 9007199254740993.0, 5e-324, 1.7976931348623157e308,
            0.30000000000000004, 1 / 3, 2 / 3, 100.0, 1e15, 9999999999999998.0, 1e-4, 0.0001234, 123456.789e3, -1e-320, 2.5e-10, 4.35, 0.1 + 0.2]
    for v in vals:
        x = v * f1
        print(repr(x), str(x), f"{x}", f"{x:g}", f"{x:.3g}", f"{x:e}", f"{x:.0f}"[:40], f"{x:10.4f}"[:40], f"{x:.3e}", f"{x:G}", f"{x:%}"[:50], f"{x:,}", f"{x:_.1f}"[:60], "%r %s %g %.2f %e" % (x, x, x, x, x) if abs(x) < 1e30 else "")
    for v in [math.inf, -math.inf, math.nan]:
        x = v * f1
        print(repr(x), str(x), f"{x:g}", f"{x:f}", f"{x:e}", f"{x:10}", f"{x:<10}|", f"{x:+}", f"{x:010}", f"{x:.2%}", f"{x:,}", "%f %e %g %s %r %5.1f|%-8g|%+g" % (x, x, x, x, x, x, x, x))
    show("fmt int", lambda: [f"{255 * one:x}", f"{255 * one:#X}", f"{255 * one:#010b}", f"{255 * one:o}", f"{-255 * one:+d}", f"{255 * one: d}", f"{255 * one:08d}", f"{-255 * one:08d}", f"{255 * one:<8d}|", f"{255 * one:^8d}|", f"{255 * one:>8d}|", f"{255 * one:*^9d}", f"{1234567 * one:,}", f"{1234567 * one:_}", f"{1234567 * one:_x}", f"{-1234567 * one:012,}", f"{65 * one:c}", f"{12 * one:e}", f"{12 * one:.2f}", f"{12 * one:%}", f"{12 * one:g}", f"{0 * one:b}", f"{-1 * one:b}", f"{-1 * one:x}", f"{-(2**63) * one:x}", f"{one:=+5d}", f"{-one:=5d}", f"{one:05}", f"{one:n}"])
    show("fmt int prec", lambda: f"{10 * one:.2}")
    show("fmt int ,x", lambda: f"{10 * one:,x}")
    show("fmt int c range", lambda: f"{-1 * one:c}")
    show("fmt int c big", lambda: f"{0x110000 * one:c}")
    show("fmt int c 0x10ffff", lambda: len(f"{0x10ffff * one:c}"))
    show("fmt str", lambda: [f"{'ab':5}|", f"{'ab':>5}|", f"{'ab':^5}|", f"{'ab':*<5}|", f"{'abcdef':.3}|", f"{'abcdef':5.3}|", f"{'é':>3}|", f"{'日本':^6}|", f"{'ab'!r:>6}|", f"{'ab'!a}", f"{'é'!a}", f"{'ab'!s:.1}"])
    show("fmt str =", lambda: f"{'ab':=5}")
    show("fmt str d", lambda: f"{'ab':d}")
    show("fmt str ,", lambda: f"{'ab':,}")
    show("fmt str +", lambda: f"{'ab':+}")
    show("fmt str 0", lambda: f"{'ab':05}")
    show("fmt str #", lambda: f"{'ab':#}")
    show("fmt float", lambda: [f"{0.5 * f1:.0f}", f"{1.5 * f1:.0f}", f"{2.5 * f1:.0f}", f"{-0.5 * f1:.0f}", f"{0.125 * f1:.2f}", f"{0.375 * f1:.2f}", f"{2.675 * f1:.2f}", f"{1e21 * f1:f}", f"{1e-7 * f1:.3g}", f"{123456789.0 * f1:g}", f"{0.000012345 * f1:g}", f"{1234567.891 * f1:,.2f}", f"{-0.0 * f1:+.1f}", f"{1.0 * f1:.0e}", f"{1.0 * f1:#.0e}", f"{1.0 * f1:#.0f}", f"{1.0 * f1:#g}", f"{1.0 * f1:g}", f"{100000.0 * f1:g}", f"{1000000.0 * f1:g}", f"{1e-5 * f1:g}", f"{0.0001 * f1:g}", f"{123.456 * f1:10.2e}|", f"{123.456 * f1:<12.2f}|", f"{123.456 * f1:^12.2f}|", f"{123.456 * f1:012.2f}|", f"{-123.456 * f1:012.2f}|", f"{123.456 * f1:+012.2f}|", f"{123.456 * f1: 012.2f}|", f"{123.456 * f1:=+12.2f}|", f"{123.456 * f1:x>12.2f}|", f"{1e10 * f1:,}", f"{12345.678 * f1:_.2f}", f"{0.5 * f1:%}", f"{0.12345 * f1:.1%}", f"{1.0 * f1:5.0%}|", f"{1e100 * f1:.3}", f"{1e100 * f1:n}", f"{3.0 * f1}", f"{3.0 * f1:}", f"{3.0 * f1!r}", f"{3.14159 * f1:.3}", f"{31415.9 * f1:.3}", f"{0.00031415 * f1:.3}", f"{1e16 * f1:.17g}", f"{0.1 * f1:.17g}", f"{0.1 * f1:.20f}", f"{0.1 * f1:.55f}", f"{1.0 * f1:.100f}"[:20], f"{5e-324 * f1:.3e}", f"{5e-324 * f1:g}", f"{1.7976931348623157e308 * f1:f}"[:30]])
    show("fmt float d", lambda: f"{1.5 * f1:d}")
    show("fmt float x", lambda: f"{1.5 * f1:x}")
    show("fmt float c", lambda: f"{1.5 * f1:c}")
    show("fmt float _", lambda: f"{1e10 * f1:_}")
    show("fmt float ,_", lambda: f"{1e10 * f1:,_}")
    show("fmt float z", lambda: [f"{-0.0001 * f1:z.2f}", f"{-0.0 * f1:z}", f"{-0.0 * f1:z.0f}", f"{0.0001 * f1:z.1e}"])
    show("fmt bool", lambda: [f"{True}", f"{True:d}", f"{True:5}|", f"{True!r:>6}", f"{True:x}", f"{True:.1f}", f"{False:>7}|", f"{True:^7}|"])
    show("fmt none", lambda: [f"{None}", f"{None!r}", f"{None!s:>6}"])
    show("fmt list", lambda: [f"{[1, 2]}", f"{[1, 'a', 2.0]!r:>20}", f"{(1,)}", f"{ {1: 'a'} }", f"{[1.0, -0.0, 1e100, float('nan')]}", f"{{'a': [None, True]}}"])
    show("pct", lambda: ["%5.2f%%" % (3.14159 * f1), "%-5d|" % (3 * one), "%+d" % (3 * one), "%05d" % (-3 * one), "%x" % (-255 * one), "%c" % (65 * one), "%c" % "a", "%r" % "a", "%s" % (one,), "%.3s" % "abcdef", "%10.4g|" % (3.14159 * f1), "%e" % (0 * one), "% d" % (5 * one), "%#x" % (255 * one), "%#o" % (8 * one), "%5s|%-5s|" % ("a", "b"), "%d" % (3.99 * f1), "%d" % (-3.99 * f1), "%i" % (one), "%u" % (-one), "%X" % (255 * one), "%5c|" % "x", "%%", "%s %s" % (1.0 * f1, None), "%s" % [1, "a"], "%r" % (1.5 * f1), "%a" % "é", "%.0f" % (0.5 * f1), "%.0f" % (1.5 * f1), "%#.0f" % (1.0 * f1), "%g" % (1e-5 * f1), "%g" % (123456789.0 * f1), "%G" % (1e-10 * f1), "%010.3f" % (-3.14159 * f1), "%+.2e" % (12345.678 * f1), "%5d%%" % (50 * one), "%x" % True, "%d" % True, "%s" % True, "%5.1f" % one, "%.2f" % one, "%e" % one, "%g" % one])
    show("pct d float inf", lambda: "%d" % (math.inf * f1))
    show("pct d float nan", lambda: "%d" % (math.nan * f1))
    show("pct d big float", lambda: "%d" % (1e30 * f1))
    show("pct c 256", lambda: "%c" % (0x110000 * one))
    show("pct c neg", lambda: "%c" % (-one))
    show("pct c str2", lambda: "%c" % ("ab" * one))
    show("format()", lambda: [format(255 * one, "x"), format(1.5 * f1, ".3f"), format("a", ">3"), format(one), format(1.5 * f1), format(True), format(one, ""), format(1e100 * f1, "")])
    show("float()", lambda: [float("1_000.5"), float(" 1.5 \n"), float("infinity"), float("-Inf"), float("nan"), float("-nan"), float("+1e3"), float(".5"), float("5."), float("1e-400"), float("1E5"), float("٣.٥")])
    show("float('1e400')", lambda: float("1e400"))
    show("float('')", lambda: float(""))
    show("float('1_')", lambda: float("1_"))
    show("float('1__0')", lambda: float("1__0"))
    show("float('1e')", lambda: float("1e"))
    show("float('.')", lambda: float("."))
    show("float('1 2')", lambda: float("1 2"))
    show("float('inf ')", lambda: float(" inf "))
    show("float('in')", lambda: float("in"))
    show("float('0x1p3')", lambda: float("0x1p3"))
    show("float('1e+')", lambda: float("1e+"))
    show("float('--1')", lambda: float("--1"))
    show("float('1.e5')", lambda: float("1.e5"))
    show("float('_1.5')", lambda: float("_1.5"))
    show("float('1._5')", lambda: float("1._5"))
    show("float('1_.5')", lambda: float("1_.5"))
    show("float('1e1_0')", lambda: float("1e1_0"))
    show("float('1e_10')", lambda: float("1e_10"))
    show("float.hex", lambda: [(1.0 * f1).hex(), (0.1 * f1).hex(), (-0.0 * f1).hex(), (5e-324 * f1).hex(), (math.inf * f1).hex(), (math.nan * f1).hex()])
    show("float.is_integer", lambda: [(1.0 * f1).is_integer(), (1.5 * f1).is_integer(), (math.inf * f1).is_integer(), (math.nan * f1).is_integer(), (1e300 * f1).is_integer()])
    show("math fns", lambda: [math.sqrt(2.0 * f1), math.exp(1.0 * f1), math.log(10.0 * f1), math.log2(8.0 * f1), math.log10(1000.0 * f1), math.log(8.0 * f1, 2.0), math.sin(1.0 * f1), math.cos(1.0 * f1), math.tan(1.0 * f1), math.atan2(1.0 * f1, -1.0), math.hypot(3.0 * f1, 4.0), math.fabs(-1.5 * f1), math.fmod(-7.5 * f1, 2.0), math.ldexp(1.0 * f1, 10), math.pow(2.0 * f1, 0.5), math.degrees(math.pi * f1), math.radians(180.0 * f1), math.expm1(1e-10 * f1), math.log1p(1e-10 * f1), math.erf(0.5 * f1), math.gamma(5.5 * f1), math.lgamma(5.5 * f1), math.cbrt(27.0 * f1), math.exp2(10.0 * f1)])
    show("modf frexp", lambda: [str(math.modf(-1.5 * f1)), str(math.frexp(8.0 * f1)), str(math.modf(math.inf * f1)), str(math.frexp(0.0 * f1)), str(math.modf(-0.0 * f1))])
    show("math.sqrt(-1)", lambda: math.sqrt(-1.0 * f1))
    show("math.log(0)", lambda: math.log(0.0 * f1))
    show("math.log(-1)", lambda: math.log(-1.0 * f1))
    show("math.exp(1000)", lambda: math.exp(1000.0 * f1))
    show("math.pow(0,-1)", lambda: math.pow(0.0 * f1, -1.0))
    show("math.pow(-1,0.5)", lambda: math.pow(-1.0 * f1, 0.5))
    show("math.pow(10,400)", lambda: math.pow(10.0 * f1, 400.0))
    show("math.fmod(1,0)", lambda: math.fmod(1.0 * f1, 0.0))
    show("math.acos(2)", lambda: math.acos(2.0 * f1))
    show("math.cosh(1000)", lambda: math.cosh(1000.0 * f1))
    show("math.ldexp big", lambda: math.ldexp(1.0 * f1, 2000))
    show("math.gamma(0)", lambda: math.gamma(0.0 * f1))
    show("math.gamma(-1)", lambda: math.gamma(-1.0 * f1))
    show("math.gamma(200)", lambda: math.gamma(200.0 * f1))
    show("math.log int", lambda: [math.log(one * 8, 2), math.log2(one * 1024), math.log10(one * 10**15), math.sqrt(one * 16), math.log(mx_like(one))])
    show("math.fsum", lambda: [math.fsum([0.1 * f1] * 10), sum([0.1 * f1] * 10), math.fsum([1e100 * f1, 1.0, -1e100]), sum([1e100 * f1, 1.0, -1e100]), sum([0.1 * f1, 0.2, 0.3]), sum([1e16 * f1, 1.0, 1.0]), sum([1.0 * f1, 1e100, 1.0, -1e100]) ])
    show("sum mixed", lambda: [str(sum([one, 2, 3])), str(sum([one, 2, 3], 0.5)), str(sum([0.5 * f1], 1)), str(sum([one], 0.0)), str(sum(range(10 * one))), str(sum(x * 0.1 for x in range(10 * one))), str(sum([math.inf * f1, -math.inf])), str(sum([1e308 * f1, 1e308, -1e308]))])
    show("math.prod", lambda: [str(math.prod([one, 2, 3])), str(math.prod([1.5 * f1, 2.0])), str(math.prod([one, 2], start=10)), str(math.prod([2**32 * one, 2**31 - 1, 2]))])
    show("math.prod ovf", lambda: math.prod([2**32 * one, 2**32]))
    show("math.dist", lambda: [str(math.dist([0.0 * f1, 0.0], [3.0, 4.0])), str(math.isclose(0.1 * f1 + 0.2, 0.3)), str(math.isclose(1e-10 * f1, 0.0)), str(math.isclose(1e-10 * f1, 0.0, abs_tol=1e-9)), str(math.nextafter(1.0 * f1, 2.0)), str(math.ulp(1.0 * f1)), str(math.remainder(5.0 * f1, 3.0)), str(math.copysign(3.0, -0.0 * f1))])
    show("isfinite", lambda: [math.isfinite(1.0 * f1), math.isnan(1.0 * f1), math.isinf(math.inf * f1), math.isfinite(math.nan * f1)])
    show("hash", lambda: [hash(one), hash(-one), hash(-2 * one), hash(2**61 - 1 + (one - 1)), hash(2**61 * one), hash(-(2**62) * 2 * one), hash(1.0 * f1), hash(1.5 * f1), hash(-1.0 * f1), hash(math.inf * f1), hash(-math.inf * f1), hash(0.1 * f1), hash(True), hash((one, 2)), hash((one,)), hash(()), hash((one, (2, 3)))])


def mx_like(one: int) -> int:
    return 2**63 - one


floats(sys.argv[1:])
