"""Bound compiler rejection resources on small inputs that used to exhaust memory.

usage: python3 tools/compilelimits.py [-c LABEL=COMMAND]...
Default commands are the CPython-hosted compiler and ./pystachy. Each ir/run/build
rejection must complete under 256 MiB address space and ten CPU seconds, without
executing the program or creating an AOT output, and report a short source error.
The generated controls exercise finite specializations and release of the active
signature budget. Linux/POSIX resource limits are intentional, as in verify.sh.
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
                                 ("active_signatures", wide_calls(12, 2), ACTIVE_ERROR)):
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
            # IR compilation of this large, valid control stays under the same process limits.
            result = invoke(cmd, "ir", control_path, temp / "unused.exe")
            if result is not None and result.returncode == 0 and result.stderr == b"" and b"define" in result.stdout:
                passed += 1
            else:
                failed += 1
                print(f"FAIL {label} released_signatures: {result.stderr[-1000:] if result else 'timeout'}")
    print(f"{passed} passed, {failed} failed (256 MiB address space, 10 CPU seconds, 30 seconds wall time)")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
