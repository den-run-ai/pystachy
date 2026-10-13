"""Bound compiler rejection resources on small inputs that used to exhaust memory.

usage: python3 tools/compilelimits.py [-c LABEL=COMMAND]...
Default commands are the CPython-hosted compiler and ./pystachy. Each ir/run/build
rejection must complete under 256 MiB address space and ten CPU seconds, without
executing the program or creating an AOT output, and report a short source error.
The generated controls exercise finite specializations, reuse at the retained-instance
boundary, and release of the active signature budget. Linux/POSIX resource limits
are intentional, as in verify.sh.
"""
import argparse
import os
from pathlib import Path
import resource
import shlex
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parent.parent
TYPE_ERROR = "type representation exceeds 65536 bytes"
SIGNATURE_ERROR = "template signature exceeds 1048576 bytes"
ACTIVE_ERROR = "active template signatures exceed 1048576 bytes"
INSTANCES_ERROR = "compilation needs more than 4096 template specializations"
RETAINED_ERROR = "retained template signatures exceed 16777216 bytes"


def limits():
    resource.setrlimit(resource.RLIMIT_AS, (256 * 1024 * 1024, 256 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_CPU, (10, 10))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


def wide_calls(params, depth):
    # x12 has a 45,048-byte type; repeated references need no large source input.
    src = ["x0 = 1"]
    for i in range(1, 13):
        src.append(f"x{i} = (x{i - 1}, x{i - 1})")
    names = [f"p{i}" for i in range(params)]
    for i in range(depth):
        src.append(f"def f{i}({', '.join(names)}) -> int:")
        src.append(f"    return f{i + 1}({', '.join(names)})" if i + 1 < depth else "    return 7")
    src.append(f"print(f0({', '.join(['x12'] * params)}))")
    return "\n".join(src) + "\n"


def branching_calls(depth, leaves=0):
    # Source, active nesting and individual types grow linearly, but each function
    # calls the next with two different types: 2**(depth + 1) - 1 retained instances.
    # The argument starts as x{leaves}, 2**leaves ints nested in pairs, whose type every
    # signature then holds (x12's is 45 KB: issue #179's gen.py DEPTH LEAVES).
    src = ["x0 = 1"] + [f"x{i} = (x{i - 1}, x{i - 1})" for i in range(1, leaves + 1)]
    for i in range(depth):
        src += [f"def f{i}(x, choose: bool) -> int:", "    if choose:",
                f"        return f{i + 1}((x, 1), choose)",
                f'    return f{i + 1}((x, ""), choose)']
    src += [f"def f{depth}(x, choose: bool) -> int:", "    return 1", f"print(f0(x{leaves}, True))"]
    return "\n".join(src) + "\n"


def fanned_calls(params, ways, depth):
    # params arguments start as x12, and each branch of each function passes all of them on
    # wrapped with one of `ways` types: with 4, 15 and 3, issue #179's 4.3 KB variant, 3,616
    # instances of 180 KB signatures.
    vals = ["1", '""', "1.0", "True", "None", "(1,)", "(1, 1)", '("",)', "(1.0,)", "(True,)",
            "((1,),)", '(1, "")', '("", 1)', "(1.0, 1)", "(None,)"][:ways]
    names = [f"p{i}" for i in range(params)]
    src = ["x0 = 1"] + [f"x{i} = (x{i - 1}, x{i - 1})" for i in range(1, 13)]
    for i in range(depth):
        src.append(f"def f{i}({', '.join(names)}, n: int) -> int:")
        for j, v in enumerate(vals):
            src += [f"    if n == {j}:", f"        return f{i + 1}({', '.join([f'({p}, {v})' for p in names])}, n)"]
        src.append("    return 0")
    src += [f"def f{depth}({', '.join(names)}, n: int) -> int:", "    return 1",
            f"print(f0({', '.join(['x12'] * params)}, 0))"]
    return "\n".join(src) + "\n"


def invoke(cmd, mode, source, output):
    args = cmd + [mode, str(source)]
    if mode == "build":
        args += ["-o", str(output)]
    try:
        return subprocess.run(args, cwd=ROOT, env=os.environ.copy(), stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, preexec_fn=limits, timeout=30, check=False)
    except subprocess.TimeoutExpired:
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-c", action="append", default=[], metavar="LABEL=COMMAND")
    args = parser.parse_args()
    commands = args.c or [f"hosted={shlex.quote(sys.executable)} {ROOT / 'pystachy.py'}", f"native={ROOT / 'pystachy'}"]
    passed = 0
    failed = 0
    with tempfile.TemporaryDirectory(prefix="pystachy-compilelimits-") as tmp:
        temp = Path(tmp)
        sources = []
        for name in ("template_type_growth", "template_type_growth_mutual", "template_type_growth_expression", "tuple_repeat_type_size"):
            sources.append((name, ROOT / "tests" / "errors" / f"{name}.py", TYPE_ERROR))
        for name, src, error in (("wide_signature", wide_calls(24, 1), SIGNATURE_ERROR),
                                 ("active_signatures", wide_calls(12, 2), ACTIVE_ERROR),
                                 ("branching_instances", branching_calls(16), INSTANCES_ERROR),
                                 ("retained_signatures", branching_calls(11, 12), RETAINED_ERROR),
                                 ("retained_wide_signatures", fanned_calls(4, 15, 3), RETAINED_ERROR)):
            source = temp / f"{name}.py"
            source.write_text(src)
            sources.append((name, source, error))
        # Three calls with distinct signatures, each below the bound, total over 1 MiB;
        # successful completion proves finished calls release the active budget.
        control = wide_calls(8, 2)
        for i in (11, 10):
            control += f"print(f0({', '.join([f'x{i}'] * 8)}))\n"
        control_path = temp / "released_signatures.py"
        control_path.write_text(control)
        # 4,095 instances across twelve templates, then one more reaches the limit.
        # Reusing both completed signatures at the limit must remain valid, while
        # a new signature must fail. This also checks accounting is compilation-wide.
        boundary = branching_calls(11) + "def extra(x) -> int:\n    return 2\nprint(extra(1))\n"
        boundary += "print(f0(0, False))\nprint(extra(1))\n"
        boundary_path = temp / "instance_boundary.py"
        boundary_path.write_text(boundary)
        overflow_path = temp / "instance_boundary_overflow.py"
        overflow_path.write_text(boundary + 'print(extra(""))\n')
        sources.append(("instance_boundary_overflow", overflow_path, INSTANCES_ERROR))
        for spec in commands:
            label, command = spec.split("=", 1)
            cmd = shlex.split(command)
            for name, source, error in sources:
                for mode in ("ir", "run", "build"):
                    output = temp / f"{label}-{name}.exe"
                    result = invoke(cmd, mode, source, output)
                    ok = (result is not None and result.returncode == 1 and result.stdout == b""
                          and error.encode() in result.stderr and b"error:" in result.stderr
                          and len(result.stderr) < 32768 and b"MemoryError" not in result.stderr
                          and not output.exists())
                    if ok:
                        passed += 1
                    else:
                        failed += 1
                        print(f"FAIL {label} {mode} {name}: {result.stderr[-1000:] if result else 'timeout'}")
            # IR compilation of these large, valid controls stays under the same process limits.
            for path in (control_path, boundary_path):
                result = invoke(cmd, "ir", path, temp / "unused.exe")
                ok = result is not None and result.returncode == 0 and result.stderr == b"" and b"define" in result.stdout
                if ok and path == boundary_path:
                    ok = result.stdout.count(b"define internal i64 @f.") == 4096
                if ok:
                    passed += 1
                else:
                    failed += 1
                    print(f"FAIL {label} {path.stem}: {result.stderr[-1000:] if result else 'timeout'}")
    print(f"{passed} passed, {failed} failed (256 MiB address space, 10 CPU seconds, 30 seconds wall time)")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
