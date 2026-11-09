"""Union-context expression fuzz: every generated expression has one natural scalar type (int, str,
float or bool) and is stored where a closed union is expected (return, annotated local, field,
dict value, list item, tuple item, call argument). All programs are valid typed Python, so a
compile-time rejection is a typing gap and an output difference a miscompile."""
import random
import sys


class G:
    def __init__(self, seed: int) -> None:
        self.r = random.Random(seed)

    def i(self, d: int = 0) -> str:
        r = self.r
        k = r.randrange(20 if d < 3 else 4)
        if k == 0:
            return str(r.choice([0, 1, 2, 3, 7, -1, -4, 10, 255]))
        if k in (1, 2, 3):
            return r.choice(["a", "b", "n"])
        if k in (4, 5):
            return f"({self.i(d + 1)} {r.choice(['+', '-', '*'])} {self.i(d + 1)})"
        if k == 6:
            return f"({self.i(d + 1)} {r.choice(['//', '%'])} ({self.i(d + 1)} % 5 + 6))"
        if k == 7:
            return f"({self.i(d + 1)} if {self.b(d + 1)} else {self.i(d + 1)})"
        if k == 8:
            return f"({self.i(d + 1)} or {self.i(d + 1)})"
        if k == 9:
            return f"({self.i(d + 1)} and {self.i(d + 1)})"
        if k == 10:
            return f"len({self.s(d + 1)})"
        if k == 11:
            return f"xs[{self.i(d + 1)} % 3]"
        if k == 12:
            return f"d.get({self.s(d + 1)}, {self.i(d + 1)})"
        if k == 13:
            return f"{r.choice(['abs', 'int', '-'])}({self.i(d + 1)})"
        if k == 14:
            return f"{r.choice(['min', 'max'])}({self.i(d + 1)}, {self.i(d + 1)})"
        if k == 15:
            return f"(o if o is not None else {self.i(d + 1)})"
        if k == 16:
            return f"({self.i(d + 1)} {r.choice(['&', '|', '^'])} {self.i(d + 1)})"
        if k == 17:
            return f"(y := {self.i(d + 1)})"
        if k == 18:
            return f"twice({self.i(d + 1)})"
        return f"sum([{self.i(d + 1)}, {self.i(d + 1)}])"

    def s(self, d: int = 0) -> str:
        r = self.r
        k = r.randrange(14 if d < 3 else 4)
        if k == 0:
            return repr(r.choice(["", "a", "ab", "k", "xyz"]))
        if k in (1, 2, 3):
            return r.choice(["s", "t"])
        if k == 4:
            return f"({self.s(d + 1)} + {self.s(d + 1)})"
        if k == 5:
            return f"({self.s(d + 1)} if {self.b(d + 1)} else {self.s(d + 1)})"
        if k == 6:
            return f"({self.s(d + 1)} or {self.s(d + 1)})"
        if k == 7:
            return f"str({self.i(d + 1)})"
        if k == 8:
            return f"{self.s(d + 1)}.{r.choice(['upper()', 'strip()', 'lower()'])}"
        if k == 9:
            return f"({self.s(d + 1)} * ({self.i(d + 1)} % 3))"
        if k == 10:
            return f"f\"{{{self.i(d + 1)}}}-{{{self.s(d + 1)}}}\""
        if k == 11:
            return f"{self.s(d + 1)}[:2]"
        if k == 12:
            return f"(p if p is not None else {self.s(d + 1)})"
        return f"ss[{self.i(d + 1)} % 2]"

    def f(self, d: int = 0) -> str:
        r = self.r
        k = r.randrange(9 if d < 3 else 3)
        if k == 0:
            return str(r.choice([0.0, 0.5, 1.5, -2.25]))
        if k in (1, 2):
            return r.choice(["x", "z"])
        if k in (3, 4):
            return f"({self.f(d + 1)} {r.choice(['+', '-', '*'])} {self.f(d + 1)})"
        if k == 5:
            return f"({self.f(d + 1)} if {self.b(d + 1)} else {self.f(d + 1)})"
        if k == 6:
            return f"({self.i(d + 1)} / 4)"
        if k == 7:
            return f"float({self.i(d + 1)})"
        return f"({self.f(d + 1)} or {self.f(d + 1)})"

    def b(self, d: int = 0) -> str:
        r = self.r
        k = r.randrange(10 if d < 3 else 3)
        if k == 0:
            return r.choice(["flag", "True", "False"])
        if k in (1, 2):
            return f"({self.i(d + 1)} {r.choice(['<', '==', '>=', '!='])} {self.i(d + 1)})"
        if k == 3:
            return f"({self.s(d + 1)} {r.choice(['==', '!=', '<'])} {self.s(d + 1)})"
        if k == 4:
            return f"({self.b(d + 1)} {r.choice(['and', 'or'])} {self.b(d + 1)})"
        if k == 5:
            return f"(not {self.b(d + 1)})"
        if k == 6:
            return f"({self.s(d + 1)} in d)"
        if k == 7:
            return f"({self.i(d + 1)} in xs)"
        if k == 8:
            return "(o is None)"
        return f"({self.b(d + 1)} if {self.b(d + 1)} else {self.b(d + 1)})"

    def expr(self, t: str) -> str:
        return {"int": self.i, "str": self.s, "float": self.f, "bool": self.b}[t]()

    def program(self, nfuncs: int = 6) -> str:
        r = self.r
        unions = [("int | str", ["int", "str"]), ("int | float", ["int", "float"]), ("str | float", ["str", "float"]), ("int | str | None", ["int", "str"]),
                  ("int | float | str", ["int", "float", "str"]), ("bool | str", ["bool", "str"]), ("int | bool | str", ["int", "bool", "str"])]
        out = ["import sys", "", "", "def twice(v: int) -> int:", "    return v * 2", "", "",
               "class Box:", "    def __init__(self, u: int | str) -> None:", "        self.u: int | str = u", "", ""]
        calls = []
        for k in range(nfuncs):
            ut, members = r.choice(unions)
            name = f"f{k}"
            body = [f"def {name}(a: int, b: int, s: str, flag: bool) -> {ut}:",
                    "    n = 3", "    y = 0", "    x = 1.5", "    z = -0.25", "    t = 'tt'", "    xs = [5, 3, 8]", "    ss = ['p', 'qq']",
                    "    d: dict[str, int] = {'k': 1, 'ab': 2}", "    o: int | None = a if a > 0 else None", "    p: str | None = s if s else None"]
            forms = r.sample(range(8), 4)
            for form in forms:
                t = r.choice(members)
                e = self.expr(t)
                if form == 0:
                    body += [f"    u{form}: {ut} = {e}", f"    show(u{form})"]
                elif form == 1:
                    t2 = r.choice(members)
                    body += [f"    u{form}: {ut} = {self.expr(t2)}", f"    u{form} = {e}", f"    show(u{form})"]
                elif form == 2:
                    body += [f"    dv{form}: dict[str, {ut}] = {{}}", f"    dv{form}['k'] = {e}", f"    dv{form}[{self.s(2)}] = {self.expr(r.choice(members))}", f"    show(len(dv{form}))", f"    show(dv{form}['k'])"]
                elif form == 3:
                    body += [f"    lv{form}: list[{ut}] = [{e}, {self.expr(r.choice(members))}]", f"    lv{form}.append({self.expr(r.choice(members))})", f"    for item{form} in lv{form}:", f"        show(item{form})"]
                elif form == 4:
                    body += [f"    show({e})"]
                elif form == 5 and "int" in members and "str" in members and "None" not in ut and ut == "int | str":
                    body += [f"    bx{form} = Box({self.expr(r.choice(['int', 'str']))})", f"    bx{form}.u = {self.expr(r.choice(['int', 'str']))}", f"    show(bx{form}.u)"]
                elif form == 6:
                    body += [f"    tv{form}: tuple[{ut}, int] = ({e}, {self.i(2)})", f"    show(tv{form}[0])", f"    show(tv{form}[1])"]
                else:
                    body += [f"    if {self.b(1)}:", f"        return {e}"]
            body += [f"    return {self.expr(r.choice(members))}", "", ""]
            out += body
            calls.append(name)
        out += ["def show(v: int | float | str | bool | None) -> None:", "    print(repr(v), type(v).__name__)", "", "",
                "def main() -> None:", "    args = [(1, 2, 'ab', True), (0, -5, '', False), (7, 3, 'k', True), (-7, 100, 'xyz', False)]", "    for a, b, s, flag in args:"]
        for name in calls:
            out += ["        try:", f"            r = {name}(a, b, s, flag)", f"            print('{name}', repr(r), type(r).__name__)",
                    "        except Exception as e:", f"            print('{name}', 'raised', type(e).__name__, e)"]
        out += ["", "", "main()", ""]
        return "\n".join(out)


if __name__ == "__main__":
    print(G(int(sys.argv[1])).program())
