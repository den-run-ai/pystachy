"""Unused inherited class methods must retain linear AST storage.

usage: python3 tools/inheritprobe.py [NATIVE_COMPILER]
Counts unique retained AST nodes and clone work at N=80,160,320 (no RSS/timing
threshold), then checks native ir/run/build at N=800 under 256 MiB. Called
methods and declaration/flow behavior are covered by tests/exc_classmethod*.py.
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
