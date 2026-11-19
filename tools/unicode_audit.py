"""Compare str operations on text that is not ASCII with CPython, in JIT and AOT.

usage: python3 tools/unicode_audit.py [-c LABEL=COMMAND]...
Each compiler runs one program of every operation on a set of samples, under JIT, as an AOT
executable and as one under GC stress, and prints every code point's classification, repr(),
case tests and case mappings. CPython's output is the expected one.
"""
import argparse
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
OPS = [
    ("len(str)", "print(len(s))"),
    ("str.get", "print(repr(s[0]))"),
    ("str.slice", "print(repr(s[:2]))"),
    ("str.slice_step", "print(repr(s[::2]))"),
    ("str.list", "print(list(s))"),
    ("str.list", "print(tuple(s))"),
    ("str.get", "print([c for c in s])"),
    ("str.get", "print([c for i, c in enumerate(s)])"),
    ("str.get", "print([c for c, d in zip(s, s)])"),
    ("str.get", "print([c for c in reversed(s)])"),
    ("len(str)", "len(s)\nprint('discarded')"),
    ("chr", "print([repr(chr(i)) for i in [0, 127, 128, 233, 255, 2047, 65535, 65536, 1114111]])"),
]
for name, args in [
    ("find", "'b'"), ("rfind", "'b'"), ("index", "'b'"), ("rindex", "'b'"),
    ("count", "''"), ("startswith", "'a', 0, 2"), ("endswith", "'b', 0, 3"),
    ("replace", "'', 'x'"), ("replace", "'', 'x', 2"),
]:
    OPS.append((f"str.{name}", f"print(repr(s.{name}({args})))"))
for name in ("isalpha", "isalnum", "isdecimal", "isdigit", "isnumeric"):
    OPS.append((f"str.{name}", f"print(s.{name}())"))
# Case mapping and the case tests follow CPython's characters (#120), also through a bound
# method, with the result dropped and in another module.
for name in ("upper", "lower", "swapcase", "capitalize", "title", "casefold", "isupper", "islower", "istitle"):
    OPS.append((f"str.{name}", f"print(repr(s.{name}()))"))
OPS += [
    ("str.upper", "f = s.upper\nprint(repr(f()))"),
    ("str.upper", "s.upper()\nprint('discarded')"),
    ("str.upper", "print(repr(audit_module.upper(s)))"),
    # expandtabs counts a character as one column, whatever its bytes
    ("str.expandtabs", "g = s.expandtabs\nprint(repr(g()))"),
    ("str.expandtabs", "s.expandtabs()\nprint('discarded')"),
    ("str.expandtabs", "print(repr(audit_module.expandtabs(s)))"),
    ("str.expandtabs", "print(repr(s.expandtabs(4)), repr((s + '\\t|').expandtabs(3)))"),
]
PROGRAM = "import audit_module\n\ns = input()\n" + "\n".join(body for _, body in OPS) + "\n" + """print(repr(s), bool(s), s == s, s in s, repr(s + s))
print(s.split(), repr(s.strip()), repr(s.center(8)), s.isascii(), s.isspace())
print(s.partition('b'))
"""


def invoke(command, env, data=None):
    result = subprocess.run(command, cwd=ROOT, env=env, input=data, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, timeout=180)
    if result.returncode or result.stderr:
        raise RuntimeError(f"{shlex.join(command)}: exit {result.returncode}\n{result.stderr.decode(errors='replace')}")
    return result.stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-c", action="append", default=[], metavar="LABEL=COMMAND")
    args = parser.parse_args()
    commands = args.c or [f"hosted={shlex.quote(sys.executable)} {ROOT / 'pystachy.py'}", f"native={ROOT / 'pystachy'}"]
    checked = 0
    with tempfile.TemporaryDirectory(prefix="pystachy-unicode-audit-") as tmp:
        temp = Path(tmp)
        program = temp / "audit.py"
        program.write_text(PROGRAM)
        (temp / "audit_module.py").write_text("def upper(s: str) -> str:\n    return s.upper()\n\n\n"
                                              "def expandtabs(s: str) -> str:\n    return s.expandtabs()\n")
        env = dict(os.environ, PYSTACHY_IRCHECK="1", PYSTACHY_CACHE=str(temp / "cache"))
        samples = [b"axb\n", b"a\0b\n", "añb\n".encode(), "a\0ñb\n".encode(),
                   "a日本😀b\n".encode(), "ae\u0301b\n".encode(), "straße ΟΔΟΣ ǅungla ﬁn İb\n".encode(),
                   "é\tжb\t天😀\t|\n".encode()]
        # Literal folding and chr() have the same code points.
        literal = temp / "literal.py"
        literal.write_text('print(len("日本語"), len(chr(233)), len(""), bool("日本語"), "é" == "é")\n'
                           'print("ß\\t|".expandtabs(), "ß".upper(), "ΟΔΟΣ".lower())\n')
        literal_expected = invoke([sys.executable, str(literal)], env)
        # Exact comparison of five predicate bits for every code point, and of whether repr()
        # shows it as it is (printable), emitted in bounded chunks. Focused corpus cases
        # additionally cover mixed strings and GC stress.
        classification = temp / "classification.py"
        classification.write_text("""for start in range(0, 0x110000, 4096):
    result = ""
    for cp in range(start, start + 4096):
        s = chr(cp)
        bits = int(s.isalpha()) + int(s.isalnum()) * 2 + int(s.isdecimal()) * 4 + int(s.isdigit()) * 8 + int(s.isnumeric()) * 16
        bits += int(len(repr(s)) == 3) * 32
        result += chr(bits + 32)
    print(result)
""")
        classification_expected = invoke([sys.executable, str(classification)], env)
        # Every code point's six mappings (printed where one changes it) and three case tests,
        # and the two properties that only context shows: whether a character is cased (title()
        # lowers the letter after it) and whether it is case-ignorable (lower() looks past it
        # for a capital sigma's context, on either side).
        case = temp / "case.py"
        case.write_text("""for start in range(0, 0x110000, 4096):
    tests = ""
    context = ""
    maps = ""
    for cp in range(start, start + 4096):
        s = chr(cp)
        tests += chr(48 + int(s.isupper()) + int(s.islower()) * 2 + int(s.istitle()) * 4)
        bits = int((s + "A").title()[-1] == "a") + int(("A" + s + "\u03a3").lower()[-1] == "\u03c2") * 2
        bits += int((s + "\u03a3").lower()[-1] == "\u03c2") * 4 + int(("\u0391\u03a3" + s).lower()[1] == "\u03c2") * 8
        context += chr(48 + bits)
        u = s.upper()
        low = s.lower()
        t = s.title()
        f = s.casefold()
        c = s.capitalize()
        w = s.swapcase()
        if u != s or low != s or t != s or f != s or c != s or w != s:
            maps += str(cp) + ":" + u + "|" + low + "|" + t + "|" + f + "|" + c + "|" + w + ";"
    print(tests)
    print(context)
    print(maps)
""")
        case_expected = invoke([sys.executable, str(case)], env)
        for item in commands:
            label, command = item.split("=", 1)
            cmd = shlex.split(command)
            binary = temp / label
            invoke(cmd + ["build", str(program), "-o", str(binary)], env)
            for sample in samples:
                expected = invoke([sys.executable, str(program)], env, sample)
                for mode in ("jit", "aot", "aot-stress"):
                    runtimeenv = env | {"PYSTACHY_GC_STRESS": "1"} if mode == "aot-stress" else env
                    result = invoke(cmd + ["run", str(program)] if mode == "jit" else [str(binary)], runtimeenv, sample)
                    if result != expected:
                        raise RuntimeError(f"{label}/{mode}/{sample!r}: output differs from CPython\n{result!r}\nwant {expected!r}")
                    checked += len(OPS) + 3
            literal_binary = temp / "literal"
            invoke(cmd + ["build", str(literal), "-o", str(literal_binary)], env)
            for call, config in [(cmd + ["run", str(literal)], env),
                                 ([str(literal_binary)], env | {"PYSTACHY_GC_STRESS": "1"})]:
                if invoke(call, config) != literal_expected:
                    raise RuntimeError(f"{label}: operations on literals or chr() differ from CPython")
                checked += 8
            classification_binary = temp / "classification"
            invoke(cmd + ["build", str(classification), "-o", str(classification_binary)], env)
            for call in (cmd + ["run", str(classification)], [str(classification_binary)]):
                if invoke(call, env) != classification_expected:
                    raise RuntimeError(f"{label}: Unicode classification or repr() differs from CPython")
                checked += 6 * 0x110000
            case_binary = temp / "case"
            invoke(cmd + ["build", str(case), "-o", str(case_binary)], env)
            for call in (cmd + ["run", str(case)], [str(case_binary)]):
                if invoke(call, env) != case_expected:
                    raise RuntimeError(f"{label}: Unicode case mapping or case tests differ from CPython")
                checked += 13 * 0x110000
            print(f"{label}: JIT + AOT + GC stress match CPython; "
                  "all 1,114,112 code points classify, print, map and test their case identically")
    print(f"{checked} operation/control checks passed")


if __name__ == "__main__":
    main()
