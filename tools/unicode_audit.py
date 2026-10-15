"""Check opt-in Unicode auditing in JIT/AOT without changing default string behavior.

usage: python3 tools/unicode_audit.py [-c LABEL=COMMAND]...
Checks use one runtime cache, alternate normal/audit/normal compilation, and run AOT
executables both with and without the compile-time option in their environment.
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
    ("str.list", "print(list(s))"),
    ("str.list", "print(tuple(s))"),
    ("str.get", "print([c for c in s])"),
    ("str.get", "print([c for i, c in enumerate(s)])"),
    ("str.get", "print([c for c, d in zip(s, s)])"),
    ("str.get", "print([c for c in reversed(s)])"),
    ("str.upper", "f = s.upper\nprint(repr(f()))"),
    ("str.upper", "s.upper()\nprint('discarded')"),
    ("str.upper", "print(repr(audit_module.upper(s)))"),
    ("len(str)", "len(s)\nprint('discarded')"),
]
for name, args in [
    ("find", "'b'"), ("rfind", "'b'"), ("index", "'b'"), ("rindex", "'b'"),
    ("count", "''"), ("startswith", "'a', 0, 2"), ("endswith", "'b', 0, 3"),
    ("replace", "'', 'x'"), ("upper", ""), ("lower", ""), ("swapcase", ""),
    ("capitalize", ""), ("title", ""), ("casefold", ""), ("isdigit", ""),
    ("isalpha", ""), ("isalnum", ""), ("isupper", ""), ("islower", ""),
    ("istitle", ""), ("isdecimal", ""), ("isnumeric", ""), ("expandtabs", "4"),
]:
    OPS.append((f"str.{name}", f"print(repr(s.{name}({args})))"))
SAFE = """print(repr(s), bool(s), s == s, s in s, repr(s + s))
print(s.split(), repr(s.strip()), repr(s.center(8)), s.isascii(), s.isspace())
print(s.partition('b'))
"""


def source():
    parts = ["import audit_module"]
    for i, (_, body) in enumerate(OPS):
        parts.append(f"def op{i}(s: str) -> None:\n" + "\n".join("    " + line for line in body.splitlines()))
    parts.append("s = input()")
    for i in range(len(OPS)):
        parts.append(f"try:\n    op{i}(s)\nexcept NotImplementedError as e:\n    print(str(e))")
    parts.append(SAFE)
    return "\n\n".join(parts)


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
        program.write_text(source())
        (temp / "audit_module.py").write_text("def upper(s: str) -> str:\n    return s.upper()\n")
        safe = temp / "safe.py"
        safe.write_text("s = input()\n" + SAFE)
        env = dict(os.environ, PYSTACHY_IRCHECK="1", PYSTACHY_CACHE=str(temp / "cache"))
        env.pop("PYSTACHY_UNICODE_AUDIT", None)
        audit = env | {"PYSTACHY_UNICODE_AUDIT": "1"}
        samples = [b"axb\n", b"a\0b\n", "añb\n".encode(), "a\0ñb\n".encode()]
        literal = temp / "literal.py"
        literal.write_text('try:\n    print(len("日本語"))\nexcept NotImplementedError as e:\n    print(str(e))\n'
                           'try:\n    print("ß".upper())\nexcept NotImplementedError as e:\n    print(str(e))\n'
                           'try:\n    print(len(chr(233)))\nexcept NotImplementedError as e:\n    print(str(e))\n'
                           'print(len(""), bool("日本語"), "é" == "é")\n')
        literal_expected = ("Unicode audit: len(str) on non-ASCII str uses byte/ASCII semantics\n"
                            "Unicode audit: str.upper on non-ASCII str uses byte/ASCII semantics\n"
                            "Unicode audit: len(str) on non-ASCII str uses byte/ASCII semantics\n"
                            "0 True True\n").encode()
        errors = "".join(f"Unicode audit: {name} on non-ASCII str uses byte/ASCII semantics\n" for name, _ in OPS).encode()
        for item in commands:
            label, command = item.split("=", 1)
            cmd = shlex.split(command)
            ordinary = []
            for enabled in (False, True, False):
                buildenv = audit if enabled else env
                binary = temp / f"{label}-{int(enabled)}"
                invoke(cmd + ["build", str(program), "-o", str(binary)], buildenv)
                for sample in samples:
                    expected = invoke([sys.executable, str(program if sample.isascii() else safe)], env, sample)
                    if enabled and not sample.isascii():
                        expected = errors + expected
                    for mode in ("jit", "aot", "aot-stress"):
                        runtimeenv = buildenv if mode == "jit" else (env if enabled else audit)
                        if mode == "aot-stress":
                            runtimeenv = runtimeenv | {"PYSTACHY_GC_STRESS": "1"}
                        result = invoke(cmd + ["run", str(program)] if mode == "jit" else [str(binary)], runtimeenv, sample)
                        if enabled or sample.isascii():
                            if result != expected:
                                raise RuntimeError(f"{label}/{enabled}/{mode}/{sample!r}: wrong output\n{result!r}\nwant {expected!r}")
                        elif b"Unicode audit:" in result:
                            raise RuntimeError("disabled audit raised")
                        if not enabled:
                            ordinary.append(result)
                        checked += len(OPS) + 3
            half = len(ordinary) // 2
            if ordinary[:half] != ordinary[half:]:
                raise RuntimeError("normal/audit/normal changed default output")
            # Literal folding and intentional raw-byte construction must not bypass checks.
            literal_binary = temp / "literal"
            invoke(cmd + ["build", str(literal), "-o", str(literal_binary)], audit)
            for call, config in [(cmd + ["run", str(literal)], audit),
                                 ([str(literal_binary)], env | {"PYSTACHY_GC_STRESS": "1"})]:
                if invoke(call, config) != literal_expected:
                    raise RuntimeError("literal/raw-byte auditing or truth/empty-string controls failed")
                checked += 6
            # Runtime IR is independent of audit mode, even when rebuilt rather than reused.
            irs = []
            for config in (env, audit):
                out = temp / "runtime.ll"
                invoke(cmd + ["rt", "runtime.py", "-o", str(out)], config)
                irs.append(out.read_bytes())
            if irs[0] != irs[1]:
                raise RuntimeError("audit mode changed cached runtime IR")
            print(f"{label}: normal/audit/normal JIT + AOT + GC stress passed; runtime IR identical")
    print(f"{checked} operation/control checks passed")


if __name__ == "__main__":
    main()
