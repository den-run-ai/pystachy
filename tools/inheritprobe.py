"""Unused inherited class methods must retain linear AST storage, and comparisons of a
base's values compile to code linear in its subclasses.

usage: python3 tools/inheritprobe.py [NATIVE_COMPILER]
Counts unique retained AST nodes and clone work at N=80,160,320 (no RSS/timing
threshold), then checks native ir/run/build at N=800 under 256 MiB. Called
methods and declaration/flow behavior are covered by tests/programs/exceptions/exc_classmethod*.py.
Then counts the native IR lines of SITES comparisons of values typed by a base whose __eq__
N=40 and N=80 subclasses inherit, for an exception base and an ordinary one, whose __eq__
declares other's type or takes it as object (#625): they must grow with N, not with its
square. tests/programs/classes/inheritance_compare_pairs.py and inheritance_compare_object.py
check what such comparisons call.
"""
import importlib.util
import os
from pathlib import Path
import resource
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parent.parent


def source(n):
    lines = ["class Base(Exception):", "    @classmethod", "    def make(cls) -> int:",
             "        x = cls()", "        total = 0"]
    lines += ["        total += 1"] * n
    lines += ["        return total"]
    for i in range(n):
        lines += [f"class C{i}(Base):", "    pass"]
    return "\n".join(lines + ["print(1)", ""])


SITES = 8


def compare_source(n, kind):
    # N subclasses inheriting the base's __eq__, which a function calls at SITES comparisons:
    # an exception class's, whose other is object, a template's parameter, and an ordinary
    # one's, compiled for each receiver's class, whose other is declared or object (its body
    # reads no field, whose AttributeError would name each class: #786)
    if kind == "exception":
        lines = ["class Base(Exception):", "    def __eq__(self, other: object) -> bool:",
                 "        return isinstance(other, Base) and str(self) == str(other)"]
    else:
        lines = ["class Base:", "    def __init__(self, n: str) -> None:", "        pass",
                 f"    def __eq__(self, other: {'object' if kind == 'object' else repr('Base')}) -> bool:",
                 "        return other is not self"]
    for i in range(n):
        lines += [f"class C{i}(Base):", "    pass"]
    lines += ["def same(x: Base, y: Base) -> int:", "    k = 0"]
    for s in range(SITES):
        lines += [f"    if x {'==' if s % 2 == 0 else '!='} y:", f"        k += {s + 1}"]
    lines += ["    return k", f"print(same(C0('a'), C{n - 1}('a')))", ""]
    return "\n".join(lines)


def compare_lines(native, path, n, kind):
    path.write_text(compare_source(n, kind))
    output = path.with_suffix(".ll")
    result = subprocess.run([str(native.resolve()), "ir", str(path), "-o", str(output)], cwd=ROOT,
                            capture_output=True, preexec_fn=limits, timeout=30, check=False)
    assert result.returncode == 0 and result.stderr == b"", (n, kind, result.stderr[-2000:])
    return len(output.read_text().splitlines())


def retained(roots):
    seen = set()
    todo = list(roots)
    while todo:
        node = todo.pop()
        if id(node) not in seen:
            seen.add(id(node))
            todo.extend(node.kids)
    return len(seen)


def limits():
    resource.setrlimit(resource.RLIMIT_AS, (256 * 1024 * 1024, 256 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_CPU, (10, 10))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


def main():
    sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location("pystachy", ROOT / "pystachy.py")
    p = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(p)
    clone = p.clone
    work = [0]

    def counted(node):
        work[0] += 1
        return clone(node)

    # Every component that imported clone must use the same counting wrapper.
    for module in list(sys.modules.values()):
        if module is not None and vars(module).get("clone") is clone:
            module.clone = counted
    p.clone = counted  # importlib did not register this launcher in sys.modules
    previous = 0
    with tempfile.TemporaryDirectory(prefix="pystachy-inherit-") as tmp:
        path = Path(tmp) / "main.py"
        for n in (80, 160, 320):
            text = source(n)
            path.write_text(text)
            mods = p.Loader([]).program(str(path), text)
            gen = p.Gen()
            work[0] = 0
            gen.program(mods)
            roots = [m.body for m in mods]
            for cls in gen.classes.values():
                for method in cls.methods.values():
                    roots += [method.node, method.orig]
            nodes = retained(roots)
            assert nodes <= 40 * n + 100, (n, "retained AST nodes", nodes)
            assert work[0] <= 40 * n + 100, (n, "cloned AST nodes", work[0])
            assert previous == 0 or nodes <= 2.2 * previous, (previous, nodes)
            print(f"N={n}: {nodes} retained AST nodes, {work[0]} cloned nodes")
            previous = nodes
        path.write_text(source(800))
        native = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "pystachy"
        for mode in ("ir", "run", "build"):
            output = Path(tmp) / "program"
            args = [str(native.resolve()), mode, str(path)]
            if mode != "run":
                args += ["-o", os.devnull if mode == "ir" else str(output)]
            result = subprocess.run(args, cwd=ROOT, capture_output=True, preexec_fn=limits,
                                    timeout=30, check=False)
            assert result.returncode == 0 and result.stderr == b"", (mode, result.stderr[-2000:])
            assert result.stdout == (b"1\n" if mode == "run" else b""), (mode, result.stdout)
            if mode == "build":
                result = subprocess.run([str(output)], capture_output=True, timeout=10, check=False)
                assert result.returncode == 0 and result.stdout == b"1\n", result
            print(f"N=800: native {mode} passed under 256 MiB / 10 CPU seconds")
        # (an arm for each call a comparison makes, not for each pair of classes: deterministic
        # line counts, which doubling N roughly doubles, and quadrupled before #625)
        for kind in ("exception", "declared", "object"):
            small = compare_lines(native, path, 40, kind)
            large = compare_lines(native, path, 80, kind)
            what = {"exception": "an exception base's", "declared": "an ordinary base's",
                    "object": "an ordinary base's (other: object)"}[kind]
            assert large <= 2.3 * small, (what, "comparisons grow quadratically", small, large)
            print(f"N=40, N=80: {SITES} comparisons of {what} values in {small} and {large} IR lines")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
