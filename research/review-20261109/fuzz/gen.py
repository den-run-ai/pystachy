"""Random typed-program generator for differential testing (CPython vs Pystachy).

Each program defines a few functions over a fixed set of typed locals and prints state after
every top-level call; integer arithmetic is kept small (mod 9973) so 64-bit overflow never
decides the result. Statements are chosen to exercise the optimizer's passes: optional and
union locals, dict membership/update fusion, indexed list loops, char comparisons, tuple returns,
callbacks in loops, try/except around runtime errors, closures and generators.
"""
import random
import sys


class G:
    def __init__(self, seed: int) -> None:
        self.r = random.Random(seed)
        self.lines: list[str] = []
        self.ind = 1
        self.depth = 0
        self.loopvars = 0

    def emit(self, s: str) -> None:
        self.lines.append("    " * self.ind + s)

    # ---- expressions by type
    def iexpr(self, d: int = 0) -> str:
        r = self.r
        k = r.randrange(22 if d < 3 else 6)
        if k == 0:
            return str(r.choice([0, 1, 2, 3, 5, 7, -1, -3, 10, 97, 255, 1000]))
        if k in (1, 2):
            return r.choice(["a", "b", "c"])
        if k == 3:
            return f"len({self.lexpr(d + 1)})"
        if k == 4:
            return f"len({self.sexpr(d + 1)})"
        if k == 5:
            return f"len(d)"
        if k in (6, 7, 8):
            op = r.choice(["+", "-", "*"])
            return f"(({self.iexpr(d + 1)} {op} {self.iexpr(d + 1)}) % 9973)"
        if k == 9:
            op = r.choice(["//", "%"])
            return f"({self.iexpr(d + 1)} {op} {self.nz(d + 1)})"
        if k == 10:
            return f"({self.iexpr(d + 1)} if {self.bexpr(d + 1)} else {self.iexpr(d + 1)})"
        if k == 11:
            return f"xs[{self.iexpr(d + 1)} % len(xs)]" if r.random() < 0.7 else f"xs[{self.iexpr(d + 1)}]"
        if k == 12:
            return f"d.get({self.sexpr(d + 1)}, {self.iexpr(d + 1)})"
        if k == 13:
            return f"d[{self.sexpr(d + 1)}]"
        if k == 14:
            return f"(o if o is not None else {self.iexpr(d + 1)})"
        if k == 15:
            return f"min({self.iexpr(d + 1)}, {self.iexpr(d + 1)})" if r.random() < 0.5 else f"max({self.iexpr(d + 1)}, {self.iexpr(d + 1)})"
        if k == 16:
            return f"abs({self.iexpr(d + 1)})"
        if k == 17:
            return f"ord({self.sexpr(d + 1)}[{self.iexpr(d + 1)} % 3])" if r.random() < 0.5 else f"int({self.fexpr(d + 1)})"
        if k == 18:
            return f"pair({self.iexpr(d + 1)}, {self.iexpr(d + 1)})[{r.randrange(2)}]"
        if k == 19:
            return f"(u if isinstance(u, int) else len(u))"
        if k == 20:
            return f"sum({self.lexpr(d + 1)})"
        return f"({self.iexpr(d + 1)} & {self.iexpr(d + 1)})" if r.random() < 0.5 else f"({self.iexpr(d + 1)} ^ {self.iexpr(d + 1)})"

    def nz(self, d: int) -> str:
        return self.r.choice(["3", "7", "-4", "(abs(a) + 1)", "(b % 5 + 1)", "(c % 3)", self.iexpr(d)])

    def fexpr(self, d: int = 0) -> str:
        r = self.r
        k = r.randrange(9 if d < 3 else 3)
        if k == 0:
            return str(r.choice([0.0, 0.5, 1.5, -2.25, 3.0, 1e3, 0.1]))
        if k in (1, 2):
            return r.choice(["x", "y"])
        if k in (3, 4):
            op = r.choice(["+", "-", "*"])
            return f"({self.fexpr(d + 1)} {op} {self.fexpr(d + 1)})"
        if k == 5:
            return f"({self.fexpr(d + 1)} / ({self.fexpr(d + 1)} + 0.5))"
        if k == 6:
            return f"float({self.iexpr(d + 1)})"
        if k == 7:
            return f"({self.fexpr(d + 1)} if {self.bexpr(d + 1)} else {self.fexpr(d + 1)})"
        return f"(q if q is not None else {self.fexpr(d + 1)})"

    def sexpr(self, d: int = 0) -> str:
        r = self.r
        k = r.randrange(14 if d < 3 else 4)
        if k == 0:
            return repr(r.choice(["", "a", "b", "ab", "abc", "k1", "k2", "日", "x:y", "Hello", " pad "]))
        if k in (1, 2, 3):
            return r.choice(["s", "t"])
        if k == 4:
            return f"({self.sexpr(d + 1)} + {self.sexpr(d + 1)})[:12]"
        if k == 5:
            return f"str({self.iexpr(d + 1)})"
        if k == 6:
            return f"{self.sexpr(d + 1)}[{self.iexpr(d + 1)} % 3:{self.iexpr(d + 1)} % 7]"
        if k == 7:
            m = r.choice(["upper()", "lower()", "strip()", "replace('a', 'bb')[:12]", "title()", "zfill(4)", "rjust(5, '.')"])
            return f"{self.sexpr(d + 1)}.{m}"
        if k == 8:
            return f"({self.sexpr(d + 1)} if {self.bexpr(d + 1)} else {self.sexpr(d + 1)})"
        if k == 9:
            return f"f\"{{{self.iexpr(d + 1)}}}:{{{self.sexpr(d + 1)}!r}}\"[:14]"
        if k == 10:
            return f"ss[{self.iexpr(d + 1)} % len(ss)]"
        if k == 11:
            return f"(p if p is not None else {self.sexpr(d + 1)})"
        if k == 12:
            return f"(u if isinstance(u, str) else str(u))"
        return f"('k' + str({self.iexpr(d + 1)} % 4))"

    def bexpr(self, d: int = 0) -> str:
        r = self.r
        k = r.randrange(16 if d < 3 else 5)
        if k == 0:
            return r.choice(["True", "False", "flag"])
        if k in (1, 2):
            op = r.choice(["<", "<=", "==", "!=", ">", ">="])
            return f"({self.iexpr(d + 1)} {op} {self.iexpr(d + 1)})"
        if k == 3:
            op = r.choice(["==", "!=", "<"])
            return f"({self.sexpr(d + 1)} {op} {self.sexpr(d + 1)})"
        if k == 4:
            return f"({self.sexpr(d + 1)} in d)"
        if k == 5:
            return f"({self.iexpr(d + 1)} in xs)"
        if k == 6:
            return f"(o is None)" if r.random() < 0.5 else "(o is not None)"
        if k == 7:
            return f"(p is None)" if r.random() < 0.5 else "(q is not None)"
        if k == 8:
            return f"({self.bexpr(d + 1)} and {self.bexpr(d + 1)})"
        if k == 9:
            return f"({self.bexpr(d + 1)} or {self.bexpr(d + 1)})"
        if k == 10:
            return f"(not {self.bexpr(d + 1)})"
        if k == 11:
            return f"({self.fexpr(d + 1)} < {self.fexpr(d + 1)})"
        if k == 12:
            return f"({self.sexpr(d + 1)}[{self.iexpr(d + 1)} % 2:][:1] == {r.choice(repr('a'), ) if False else repr(r.choice('abk:'))})"
        if k == 13:
            return f"isinstance(u, {r.choice(['int', 'str'])})"
        if k == 14:
            return f"{self.sexpr(d + 1)}.startswith({self.sexpr(d + 1)})"
        return f"({self.sexpr(d + 1)} in {self.sexpr(d + 1)})"

    def lexpr(self, d: int = 0) -> str:
        r = self.r
        k = r.randrange(7 if d < 3 else 2)
        if k in (0, 1):
            return "xs"
        if k == 2:
            return f"[{self.iexpr(d + 1)}, {self.iexpr(d + 1)}]"
        if k == 3:
            return f"xs[{self.iexpr(d + 1)} % 4:{self.iexpr(d + 1)} % 9]"
        if k == 4:
            return f"[v * 2 % 9973 for v in {self.lexpr(d + 1)} if v % 3 != {r.randrange(3)}]"
        if k == 5:
            return f"sorted({self.lexpr(d + 1)})"
        return f"({self.lexpr(d + 1)} + {self.lexpr(d + 1)})[:8]"

    # ---- statements
    def stmt(self) -> None:
        r = self.r
        k = r.randrange(40 if self.depth < 3 else 18)
        if k < 3:
            self.emit(f"{r.choice(['a', 'b', 'c'])} = {self.iexpr()}")
        elif k == 3:
            self.emit(f"{r.choice(['a', 'b', 'c'])} {r.choice(['+=', '-=', '^='])} {self.iexpr(1)} % 100")
        elif k == 4:
            self.emit(f"{r.choice(['x', 'y'])} = {self.fexpr()}")
        elif k in (5, 6):
            self.emit(f"{r.choice(['s', 't'])} = {self.sexpr()}")
        elif k == 7:
            self.emit(f"s += {self.sexpr(1)}" if r.random() < 0.6 else f"s = (s + {self.sexpr(1)})[-10:]")
        elif k == 8:
            self.emit(f"o = {r.choice(['None', self.iexpr(1), 'None if ' + self.bexpr(1) + ' else ' + self.iexpr(1)])}")
        elif k == 9:
            self.emit(f"p = {r.choice(['None', self.sexpr(1), 'd_s.get(' + self.sexpr(1) + ')'])}")
        elif k == 10:
            self.emit(f"q = {r.choice(['None', self.fexpr(1)])}")
        elif k == 11:
            self.emit(f"u = {r.choice([self.iexpr(1), self.sexpr(1)])}")
        elif k == 12:
            self.emit(f"flag = {self.bexpr()}")
        elif k == 13:
            c = r.randrange(6)
            if c == 0:
                self.emit(f"xs.append({self.iexpr(1)})")
            elif c == 1:
                self.emit(f"xs[{self.iexpr(1)} % len(xs)] = {self.iexpr(1)}")
            elif c == 2:
                self.emit(f"if len(xs) > 3: xs.pop({r.choice(['', '0', '-2', self.iexpr(2) + ' % 3'])})")
            elif c == 3:
                self.emit(f"xs = {self.lexpr()} or [1]")
            elif c == 4:
                self.emit(f"xs[{self.iexpr(1)} % 3:{self.iexpr(1)} % 5] = {self.lexpr(1)}[:3]")
                self.emit("if not xs: xs = [4]")
            else:
                self.emit(r.choice(["xs.sort()", "xs.reverse()", "xs.insert(1, c % 50)", "xs = xs[:12] or [2]", "ss.append(s[:4])", "ss = ss[-5:]"]))
        elif k == 14:
            c = r.randrange(6)
            key = self.sexpr(1)
            if c == 0:
                self.emit(f"d[{key}] = {self.iexpr(1)}")
            elif c == 1:
                self.emit(f"k_ = {key}")
                self.emit(f"if k_ in d:")
                self.emit(f"    d[k_] += {self.iexpr(1)} % 50")
                self.emit(f"else:")
                self.emit(f"    d[k_] = {self.iexpr(1)}")
            elif c == 2:
                self.emit(f"d[{key}] = d.get({key}, 0) + 1")
            elif c == 3:
                self.emit(f"d.pop({key}, 0)")
            elif c == 4:
                self.emit(f"if len(d) > 6: d.pop(next(iter(d)))")
            else:
                self.emit(f"d_s[{key}] = {self.sexpr(1)}")
        elif k == 15:
            self.emit(f"out.append({r.choice([self.iexpr(), 'len(' + self.sexpr() + ')', 'int(' + self.bexpr() + ')'])})")
        elif k == 16:
            self.emit(f"a, b = b, a") if r.random() < 0.5 else self.emit(f"a, c = pair({self.iexpr(1)}, {self.iexpr(1)})")
        elif k == 17:
            self.emit(f"acc += apply(cb{r.randrange(3)}, {self.iexpr(1)}, {r.randrange(1, 5)})")
        elif k in (18, 19, 20, 21):
            self.emit(f"if {self.bexpr()}:")
            self.block()
            if r.random() < 0.5:
                self.emit("else:")
                self.block()
        elif k in (22, 23, 24):
            v = f"i{self.loopvars}"
            self.loopvars += 1
            c = r.randrange(5)
            if c == 0:
                self.emit(f"for {v} in range({r.randrange(1, 5)}):")
            elif c == 1:
                self.emit(f"for {v} in range(len(xs)):")
                self.ind += 1
                self.emit(f"acc += xs[{v}] if {v} < len(xs) else -1")
                self.ind -= 1
            elif c == 2:
                self.emit(f"for {v}, e_ in enumerate(list(xs)):")
                self.ind += 1
                self.emit(f"acc += e_ * {v} % 97")
                self.ind -= 1
            elif c == 3:
                self.emit(f"for ch_ in {self.sexpr(1)}:")
                self.ind += 1
                self.emit(f"if ch_ == {repr(r.choice('abk: 日'))}:")
                self.emit(f"    acc += 1")
                self.emit(f"elif ch_ != 'b':")
                self.emit(f"    acc += 2")
                self.ind -= 1
            else:
                self.emit(f"for k2_, v2_ in list(d.items()):")
                self.ind += 1
                self.emit(f"acc += v2_ + len(k2_)")
                self.ind -= 1
            self.block(loop=True)
        elif k == 25:
            self.emit(f"w_ = {r.randrange(1, 6)}")
            self.emit(f"while w_ > 0:")
            self.ind += 1
            self.emit("w_ -= 1")
            self.ind -= 1
            self.block(loop=True)
        elif k in (26, 27, 28):
            self.emit("try:")
            self.block()
            exc = r.choice(["(KeyError, IndexError)", "ZeroDivisionError", "(ZeroDivisionError, KeyError, IndexError, ValueError)", "LookupError", "Exception"])
            self.emit(f"except {exc} as e_:")
            self.ind += 1
            self.emit(f"out.append(-{r.randrange(1, 9)})")
            self.emit(f"t = type(e_).__name__[:6]")
            self.ind -= 1
            if r.random() < 0.3:
                self.emit("finally:")
                self.ind += 1
                self.emit(f"acc += {r.randrange(1, 9)}")
                self.ind -= 1
        elif k == 29:
            self.emit(f"if o is not None:")
            self.ind += 1
            self.emit(f"o = o + {self.iexpr(1)} % 10")
            self.emit(f"acc += o")
            self.ind -= 1
        elif k == 30:
            self.emit(f"if p is not None and len(p) > {r.randrange(3)}:")
            self.ind += 1
            self.emit(f"t = p[{r.randrange(2)}].upper() + t[:5]")
            self.ind -= 1
        elif k == 31:
            self.emit(f"if isinstance(u, int):")
            self.ind += 1
            self.emit(f"u = (u * 3 + {self.iexpr(1)}) % 9973")
            self.ind -= 1
            self.emit("else:")
            self.ind += 1
            self.emit(f"u = (u + {self.sexpr(1)})[:9]")
            self.ind -= 1
        elif k == 32:
            self.emit(f"acc += sum(g_ for g_ in gen({self.iexpr(1)} % 6, {self.iexpr(1)} % 7 + 1))")
        elif k == 33:
            self.loopvars += 1
            fv = f"fn{self.loopvars}_"
            nv = f"n{self.loopvars}_"
            self.emit(f"{nv} = {self.iexpr(1)}")
            self.emit(f"{fv} = lambda z_: z_ * 2 + {nv} % 7")
            self.emit(f"acc += {fv}({self.iexpr(1)} % 100)")
        elif k == 34:
            self.emit(f"m_ = max(xs) if xs else 0")
            self.emit(f"acc += m_ - min(xs) + xs.count({self.iexpr(1)}) + (xs.index(m_) if m_ in xs else 0)")
        elif k == 35:
            self.emit(f"t = {r.choice(['\",\".join(ss)[:12]', '\"|\".join(str(v) for v in xs[:4])', 'repr(xs[:3])', 'str(d.get(s))', 'str(sorted(d.items())[:2])', 'f\"{x:.2f}/{a:>4}/{s!r:.6}\"'])}")
        elif k == 36:
            self.emit(f"if {self.bexpr()}:")
            self.ind += 1
            self.emit(r.choice(["return acc + a", "raise ValueError('v')", "out.append(99)"]))
            self.ind -= 1
        elif k == 37:
            self.emit(f"acc += rec({self.iexpr(1)} % 9)")
        elif k == 38:
            self.emit(f"y = x; x = {self.fexpr(1)} if y == y else 0.0")
        else:
            self.emit(f"assert {self.bexpr()} or True, s")

    def block(self, loop: bool = False) -> None:
        self.ind += 1
        self.depth += 1
        n = self.r.randrange(1, 4)
        for _ in range(n):
            self.stmt()
        if loop and self.r.random() < 0.3:
            self.emit(f"if {self.bexpr()}:")
            self.emit(f"    {self.r.choice(['break', 'continue'])}")
        self.depth -= 1
        self.ind -= 1

    def function(self, name: str) -> None:
        self.lines.append(f"def {name}(a: int, b: int, s: str, flag: bool) -> int:")
        self.ind = 1
        for line in ["c = 3", "x = 1.5", "y = -0.25", "t = 'tt'", "xs = [5, 3, 8, 1]", "ss = ['p', 'qq']", "d: dict[str, int] = {'k1': 1, 'ab': 2}",
                     "d_s: dict[str, str] = {'a': 'A'}", "o: int | None = None", "p: str | None = None", "q: float | None = None",
                     "u: int | str = 0", "out: list[int] = []", "acc = 0"]:
            self.emit(line)
        self.loopvars = 0
        for _ in range(self.r.randrange(6, 14)):
            self.stmt()
        self.emit("show(acc, a, b, c, x, y, s, t, xs, ss, d, d_s, o, p, q, u, out)")
        self.emit("return acc % 9973")
        self.lines.append("")

    def program(self, nfuncs: int = 3) -> str:
        head = '''import sys


def pair(m: int, n: int) -> tuple[int, int]:
    return (m + n) % 9973, (m - n) % 9973


def cb0(v: int) -> int:
    return v + 1


def cb1(v: int) -> int:
    return v * 2 % 9973


def cb2(v: int) -> int:
    if v % 5 == 0:
        raise KeyError("cb2")
    return v - 3


def apply(f, v: int, n: int) -> int:
    r = v
    for _ in range(n):
        r = f(r) % 9973
    return r


def gen(lo: int, hi: int):
    for g in range(lo, hi):
        if g % 4 == 3:
            continue
        yield g * g % 97


def rec(n: int) -> int:
    return 1 if n <= 0 else (n * rec(n - 1) + 1) % 9973


def show(acc: int, a: int, b: int, c: int, x: float, y: float, s: str, t: str, xs: list[int], ss: list[str], d: dict[str, int], d_s: dict[str, str], o: int | None, p: str | None, q: float | None, u: int | str, out: list[int]) -> None:
    print(acc, a, b, c, f"{x:.6g}", f"{y:.6g}", repr(s), repr(t), xs, ss, sorted(d.items()), sorted(d_s.items()), o, repr(p), "None" if q is None else f"{q:.6g}", repr(u), out)


'''
        for i in range(nfuncs):
            self.function(f"f{i}")
        main = ["def main() -> None:", "    args = [(1, 2, 'ab', True), (0, -5, '', False), (97, 3, 'k1', True), (-7, 1000, '日:x', False), (255, 0, 'Hello', True)]",
                "    for a, b, s, flag in args:"]
        for i in range(nfuncs):
            main += [f"        try:", f"            print('f{i}', f{i}(a, b, s, flag))", f"        except Exception as e:", f"            print('f{i}', 'raised', type(e).__name__, e)"]
        main += ["", "", "main()", ""]
        return head + "\n".join(self.lines) + "\n\n" + "\n".join(main)


if __name__ == "__main__":
    seed = int(sys.argv[1])
    print(G(seed).program())
