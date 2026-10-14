"""Differential and conservative-boundary checks for opt-in local versions."""
import argparse
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import textwrap


ACCEPTED = '''
def parse_count(text):
    value = text.strip()
    value = int(value)
    return value + 1

def rebind_parameter(value):
    value = str(value)
    value = int(value)
    return value + 2

def mean(xs: list[int]) -> float:
    total = 0
    for x in xs:
        total += x
    total = total / len(xs)
    return total

def branches(flag: bool) -> float:
    value = 2
    if flag:
        value = 4
    else:
        value = 6
    value = value / 2
    return value

def aliases() -> str:
    value = "9"
    old = value
    value = int(value)
    previous = value
    value = str(value + 1)
    return old + ":" + str(previous) + ":" + value

class Match:
    def __init__(self, text: str) -> None:
        self.text = text
    def group(self, index: int) -> str:
        return self.text

def replace(s):
    s = s.group(1)
    if s[0] == "#":
        return int(s[1:])
    return 0

print(parse_count(" 41 "))
print(rebind_parameter("20"), rebind_parameter(20))
print(mean([1, 2, 3, 4]), mean([3]))
print(branches(True), branches(False))
print(aliases())
print(replace(Match("#123")), replace(Match("abc")))
'''

# These are intentionally Python-valid but unsupported by this bounded pass.
# The ordinary compiler's exact rejection must survive the experiment.
REJECTED = {
    "annotation": '''
        def f() -> int:
            value: str = "3"
            value = int(value)
            return value
        print(f())
    ''',
    "parameter_annotation": '''
        def f(value: str) -> int:
            value = int(value)
            return value
        print(f("3"))
    ''',
    "loop": '''
        def f() -> int:
            value = "3"
            for i in range(1):
                value = int(value)
            return value
        print(f())
    ''',
    "branch": '''
        def f(flag: bool) -> int:
            value = "3"
            if flag:
                value = int(value)
            return value
        print(f(True))
    ''',
    "capture": '''
        def f() -> int:
            value = "3"
            def read() -> str:
                return value
            value = int(value)
            print(read())
            return value
        print(f())
    ''',
    "global": '''
        value = "3"
        def f() -> int:
            global value
            value = int(value)
            return value
        print(f())
    ''',
    "del": '''
        def f() -> int:
            value = "3"
            del value
            value = 3
            return value
        print(f())
    ''',
    "exception": '''
        def f() -> int:
            value = "3"
            try:
                value = int(value)
            except ValueError:
                print(value)
            return value
        print(f())
    ''',
    "deferred_read": '''
        def f() -> int:
            value = "3"
            read = lambda: value
            value = int(value)
            print(read())
            return value
        print(f())
    ''',
}


def run(command: list[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, env=env, capture_output=True, text=True, timeout=180)


def check(compiler: list[str]) -> None:
    base = dict(os.environ)
    base.pop("PYSTACHY_FLOW_LOCALS", None)
    enabled = dict(base, PYSTACHY_FLOW_LOCALS="1", PYSTACHY_IRCHECK="1")
    with tempfile.TemporaryDirectory(prefix="pystachy-flow-locals-") as tmp:
        source = Path(tmp) / "accepted.py"
        source.write_text(textwrap.dedent(ACCEPTED))
        oracle = run([sys.executable, str(source)], base)
        assert oracle.returncode == 0, oracle.stderr
        baseline = run(compiler + ["ir", str(source), "-o", str(Path(tmp) / "old.ll")], base)
        assert baseline.returncode == 1 and "error:" in baseline.stderr, baseline
        jit = run(compiler + ["run", str(source)], enabled)
        assert (jit.returncode, jit.stdout, jit.stderr) == (0, oracle.stdout, ""), jit
        binary = Path(tmp) / "accepted"
        build = run(compiler + ["build", str(source), "-o", str(binary)], enabled)
        assert (build.returncode, build.stderr) == (0, ""), build
        aot = run([str(binary)], base)
        assert (aot.returncode, aot.stdout, aot.stderr) == (0, oracle.stdout, ""), aot
        print("PASS: 6 accepted scenarios match CPython in JIT and AOT; flag-off rejects")
        for name, code in REJECTED.items():
            source = Path(tmp) / (name + ".py")
            source.write_text(textwrap.dedent(code))
            command = compiler + ["ir", str(source), "-o", str(Path(tmp) / "rejected.ll")]
            old = run(command, base)
            new = run(command, enabled)
            assert old.returncode == 1 and "error:" in old.stderr, (name, old)
            assert (new.returncode, new.stdout, new.stderr) == (old.returncode, old.stdout, old.stderr), (name, old, new)
        print(f"PASS: {len(REJECTED)} excluded cases preserve their exact diagnostic")
        source = Path(tmp) / "unresolved.py"
        source.write_text("def f():\n    value = 3\n    value = []\n    return value\nprint(f())\n")
        error = run(compiler + ["ir", str(source)], enabled)
        assert error.returncode == 1 and "cannot infer the type of 'value'" in error.stderr, error
        assert ".flow." not in error.stderr, error.stderr
        print("PASS: unresolved inference diagnostic retains the original local name")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", default=f"{shlex.quote(sys.executable)} -m pystachy")
    args = parser.parse_args()
    check(shlex.split(args.compiler))
