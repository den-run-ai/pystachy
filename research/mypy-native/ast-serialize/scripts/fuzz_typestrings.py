"""Random type strings for parse_type_string() and string annotations, port vs extension."""
import random
import sys

seed = int(sys.argv[1]) if len(sys.argv) > 1 else 7
sys.argv = [sys.argv[0]]
sys.path.insert(0, "/home/user/wt-astser/tools")
sys.path.insert(0, "/tmp/claude-0/-home-user-pystachy/8dfd0d3f-eb31-5d1b-8d1b-90a856e3b0b1/scratchpad/astser/scripts")
import ast_serialize_check as c  # noqa: E402

port = c.load()
import ast_serialize as rust  # noqa: E402

rng = random.Random(seed)
ATOMS = ["int", "str", "None", "...", "a.b.C", "1", "-1", "+2", "--3", "0x10", "1_0", "3.5", "2j", "True", "b'x'",
         "'T'", '"U"', "f(x)", "f(x, k=1)", "Arg(int, 'x')", "[int]", "()", "(int,)", "*Ts", "lambda: 1", "x if y else z",
         "not x", "~x", "a + b", "é", "18446744073709551616", "{'a': int}", "{**a}", "{}", "x[1:2]", "x[]", "(", "]",
         "'a' 'b'", "u'x'", "r'\\\\x'", "f'{x}'", "await x", "yield", "x := 1", "#c", "\\\\", " ", "\\t"]


def typ(depth=0):
    k = rng.randrange(7)
    if depth > 2 or k < 3:
        return rng.choice(ATOMS)
    if k == 3:
        return f"{rng.choice(['List', 'Dict', 'x.y', 'Callable', 'Literal', 'Union', 'f(x)'])}[{', '.join(typ(depth + 1) for _ in range(rng.randint(0, 3)))}]"
    if k == 4:
        return f"{typ(depth + 1)} | {typ(depth + 1)}"
    if k == 5:
        return "'" + typ(depth + 1).replace("'", '"') + "'"
    return "[" + ", ".join(typ(depth + 1) for _ in range(rng.randint(0, 3))) + "]"


same = 0
n = 20000
for i in range(n):
    t = typ()
    rng_ = (rng.randint(1, 50), rng.randint(0, 80), rng.randint(1, 50), rng.randint(0, 80))
    cv = rng.choice([0, 2, 5, 7])
    a = c.call(port.parse_type_string, t, rng_, cv)
    b = c.call(rust.parse_type_string, t, rng_, cv)
    ok = a == b
    src = "x: " + repr(t) + "\ndef f(a: " + repr(t) + ") -> " + repr(t) + ": pass\ny = 1  # type: " + t.replace("\n", " ") + "\n"
    a2 = c.call(port.parse, "t.py", src, cache_version=cv)
    b2 = c.call(rust.parse, "t.py", src, cache_version=cv)
    ok = ok and a2 == b2
    if ok:
        same += 1
    elif n - same < 8:
        print("MISMATCH", repr(t), rng_, cv, a == b)
        print(c.compare(a2, b2) if a == b else c.describe(a, b, "type") if isinstance(a, bytes) and isinstance(b, bytes) else (a, b))
print(f"type string fuzz: {same}/{n} identical")
