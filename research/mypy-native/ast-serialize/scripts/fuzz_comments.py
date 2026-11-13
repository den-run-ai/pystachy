"""Random type comments, ignores and inline options, port vs extension."""
import random
import sys

sys.argv = [sys.argv[0]]
sys.path.insert(0, "/home/user/wt-astser/tools")
import ast_serialize_check as c  # noqa: E402

port = c.load()
import ast_serialize as rust  # noqa: E402

rng = random.Random(int(sys.argv[1]) if len(sys.argv) > 1 else 5)
ATOMS = ["int", "str", "List[int]", "Dict[str, 'x']", "None", "...", "a.b", "Tuple[()]", "x | y", "'T'",
         "Callable[[int], str]", "1", "-1", "f(x)", "[int]", "(int, str)", "", " ", "*int", "**str", "(", ")",
         "lambda: 1", "int, str", "é", "Literal['a']", "x[", "# x", "type: int", "ignore", "\\", "{'a': 1}"]


def typ(depth=0):
    k = rng.randrange(6)
    if depth > 2 or k < 3:
        return rng.choice(ATOMS)
    if k == 3:
        return f"{rng.choice(['List', 'Dict', 'x.y'])}[{typ(depth + 1)}, {typ(depth + 1)}]"
    if k == 4:
        return f"{typ(depth + 1)} | {typ(depth + 1)}"
    return "(" + ", ".join(rng.choice(["", "*", "**"]) + typ(depth + 1) for _ in range(rng.randint(0, 3))) + ")" + \
        rng.choice([" -> ", "->", " - > ", " "]) + typ(depth + 1)


def comment():
    k = rng.randrange(10)
    if k < 4:
        return "# type: " + typ()
    if k == 4:
        return "# type: ignore" + rng.choice(["", "[a]", "[a, b-c]", "[]", "[x y]", " [a]", "[a", "xyz", "  # x"])
    if k == 5:
        return "# mypy: ignore" + rng.choice(["", "[a]", "[bad code]"])
    if k == 6:
        return "#type:" + typ() + "  # type: ignore[c]"
    if k == 7:
        return "## type: ignore"
    if k == 8:
        return "# mypy: " + rng.choice(["always-true=A", "always_false=\"B,C\"", "ignore-errors", "ignore_errors=False", "strict"])
    return "# type: " + typ() + " # type: " + typ()


def program():
    lines = []
    for _ in range(rng.randint(1, 6)):
        k = rng.randrange(6)
        if k == 0:
            lines.append("x = 1  " + comment())
        elif k == 1:
            lines.append("def f(" + ", ".join(rng.choice(["a", "*b", "**c", "self", "d=1"]) for _ in range(rng.randint(0, 4))) + "):  " + comment())
            lines.append("    " + rng.choice(["pass", "return 1", "x = 2  " + comment()]))
        elif k == 2:
            lines.append("def g(")
            for _ in range(rng.randint(1, 3)):
                lines.append("    " + rng.choice(["a", "*b", "**c", "d=1"]) + ",  " + comment())
            lines.append("):")
            lines.append("    " + comment())
            lines.append("    pass")
        elif k == 3:
            lines.append(comment())
        elif k == 4:
            lines.append("class C:\n    def m(self, a):\n        " + comment() + "\n        pass")
        else:
            lines.append("if A:\n    import a  " + comment() + "\nelse:\n    import b")
    return "\n".join(lines) + "\n"


same = 0
n = 20000
for i in range(n):
    src = program()
    opts = {"cache_version": rng.choice([0, 5, 7]), "skip_function_bodies": rng.random() < 0.3}
    a = c.call(port.parse, "f.py", src, **opts)
    b = c.call(rust.parse, "f.py", src, **opts)
    if a == b:
        same += 1
    elif n - same < 10:
        print("MISMATCH", repr(src), opts)
        print(c.compare(a, b))
print(f"comment fuzz: {same}/{n} identical")
