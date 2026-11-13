"""Random f-strings and t-strings, port vs extension."""
import random
import sys

seed = int(sys.argv[1]) if len(sys.argv) > 1 else 11
sys.argv = [sys.argv[0]]
sys.path.insert(0, "/home/user/wt-astser/tools")
import ast_serialize_check as c  # noqa: E402

port = c.load()
import ast_serialize as rust  # noqa: E402

rng = random.Random(seed)
TEXT = ["a", " ", "{{", "}}", "\\n", "\\\\", "\\{", "\\N{BULLET}", "é", "\\x41", "'", '"', "#", "\\ud800", "{", "}", "\n"]
EXPRS = ["x", "x.y", "f(a)", "a[1]", "1 + 2", "'s'", '"d"', "x if y else z", "(lambda: 1)", "lambda: 1", "*a", "x, y",
         "yield", "a := 1", "(a := 1)", "{a: b}", "{a}", "[i for i in x]", "x!r", "", " x ", "f'{y}'", "x # c\n", "\\n"]
CONV = ["", "!r", "!s", "!a", "!x", "!", " !r", "!r "]
SPEC = ["", ":>10", ":{w}", ":{w}.{p}f", ":%Y-%m", ":", ":{", ":}", ":{x!r}", ":=^10", ": {x = }"]


def fpiece(depth=0):
    parts = []
    for _ in range(rng.randint(0, 4)):
        if rng.random() < 0.5:
            parts.append(rng.choice(TEXT))
        else:
            e = rng.choice(EXPRS)
            if depth < 2 and rng.random() < 0.2:
                e = fstring(depth + 1)
            dbg = "=" if rng.random() < 0.2 else ""
            parts.append("{" + e + dbg + rng.choice(CONV) + rng.choice(SPEC) + ("}" if rng.random() < 0.95 else ""))
    return "".join(parts)


def fstring(depth=0):
    prefix = rng.choice(["f", "F", "rf", "fR", "t", "rt", "Tr", "f", "f"])
    q = rng.choice(["'", '"', "'''", '"""'])
    return prefix + q + fpiece(depth) + (q if rng.random() < 0.95 else "")


same = 0
n = 20000
for i in range(n):
    src = "x = " + " ".join(fstring() if rng.random() < 0.8 else rng.choice(["'s'", "b'b'", "u'u'"]) for _ in range(rng.randint(1, 3))) + "\n"
    if rng.random() < 0.3:
        src += "y = 1\n"
    cv = rng.choice([0, 5, 7])
    a = c.call(port.parse, "f.py", src, cache_version=cv)
    b = c.call(rust.parse, "f.py", src, cache_version=cv)
    if a == b:
        same += 1
    elif n - same < 8:
        print("MISMATCH", repr(src), cv)
        print(c.compare(a, b))
print(f"f-string fuzz: {same}/{n} identical")
