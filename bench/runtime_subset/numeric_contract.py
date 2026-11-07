"""Compare the native int64 power/range ports with their C predecessors and CPython.

Run with the repository's pinned Python and LLVM (PYSTACHY_LLVM, or tools on PATH):
    python3 bench/runtime_subset/numeric_contract.py --before ../main --after . --json result.json

The after checkout's CPython-hosted compiler emits runtime.py's actual LLVM IR. An
optional --compiler selects a built Pystachy executable instead. Only the three
helpers, their strings, and a small exception shim are linked into this probe;
it does not build Pystachy or change either checkout's runtime caches.

CPython range indexing/membership and arbitrary-precision pow supply independent
oracles. The int64 result limit and the existing rejection of negative integer
exponents are applied explicitly. Exceptions use a local C setjmp/longjmp shim,
so this checks values/error text, not Pystachy's unwinder, GC, or JIT/AOT timings.
"""

import argparse
import ctypes
import hashlib
import itertools
import json
import os
from pathlib import Path
import platform
import random
import re
import shutil
import subprocess
import sys
import tempfile

FUNCTIONS = {"pys_pow": 2, "pys_range_len": 3, "pys_range_has": 4}
LOW = -(1 << 63)
HIGH = (1 << 63) - 1
OVERFLOW = "OverflowError: integer result does not fit in 64 bits"
HARNESS = r"""
#include <stdint.h>
#include <setjmp.h>
#include <stdio.h>
typedef int64_t I;
/* STR_TYPE */
I numeric_before_pow(I, I); I numeric_after_pow(I, I);
I numeric_before_range_len(I, I, I); I numeric_after_range_len(I, I, I);
I numeric_before_range_has(I, I, I, I); I numeric_after_range_has(I, I, I, I);
static jmp_buf jump;
static char failure[256];
_Noreturn void numeric_contract_fail(const char *message) {
  snprintf(failure, sizeof failure, "%s", message);
  longjmp(jump, 1);
}
_Noreturn void numeric_contract_raise(Str *kind, Str *message) {
  snprintf(failure, sizeof failure, "%.*s: %.*s",
           (int)kind->len, kind->s, (int)message->len, message->s);
  longjmp(jump, 1);
}
const char *numeric_contract_call(int mode, I a, I b, I step, I x, I *out) {
  if (setjmp(jump)) return failure;
  switch (mode) {
  case 0: *out = numeric_before_pow(a, b); break;
  case 1: *out = numeric_after_pow(a, b); break;
  case 2: *out = numeric_before_range_len(a, b, step); break;
  case 3: *out = numeric_after_range_len(a, b, step); break;
  case 4: *out = numeric_before_range_has(x, a, b, step); break;
  case 5: *out = numeric_after_range_has(x, a, b, step); break;
  default: return "invalid probe mode";
  }
  return NULL;
}
"""


def run(command, *, cwd=None, env=None):
    result = subprocess.run([str(arg) for arg in command], cwd=cwd, env=env, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(f"command failed ({result.returncode}): {command}\n{result.stdout}{result.stderr}")
    return result.stdout


def tool(name):
    directory = os.environ.get("PYSTACHY_LLVM", "")
    path = shutil.which(str(Path(directory).expanduser() / name) if directory else name)
    if path is None:
        raise RuntimeError(f"cannot find {name}; set PYSTACHY_LLVM to the LLVM bin directory or add it to PATH")
    return str(Path(path).resolve())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def checkout_info(path, *, compiler_sources=False):
    files = [path / "runtime.c"]
    if compiler_sources:
        files += [path / "runtime.py", path / "pystachy.py"]
        files += sorted((path / "src" / "pystachy_compiler").rglob("*.py"))
    inputs = {str(file.relative_to(path)): digest(file) for file in files}
    return {
        "path": str(path),
        "commit": run(["git", "-C", path, "rev-parse", "HEAD"]).strip(),
        "status": run(["git", "-C", path, "status", "--porcelain", "--untracked-files=all"]).splitlines(),
        "inputs_sha256": inputs,
    }


def c_function(source, name):
    start = re.search(r"^I\s+" + re.escape(name) + r"\([^;{}]*\)\s*\{", source, re.M)
    if start is None:
        # A declaration means this checkout has already migrated the helper.
        raise RuntimeError(f"--before runtime.c must contain the definition of {name}")
    tokens = r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|/\*.*?\*/|//[^\n]*|[{}]'
    depth = 0
    for match in re.finditer(tokens, source[start.end() - 1:], re.S):
        if match[0] == "{":
            depth += 1
        elif match[0] == "}":
            depth -= 1
            if depth == 0:
                return source[start.start():start.end() - 1 + match.end()]
    raise RuntimeError(f"unterminated C definition of {name}")


def llvm_function(source, name):
    match = re.search(r"^define[^\n]*@" + re.escape(name) + r"\([^\n]*\)[^\n]*\{\n.*?^\}", source, re.M | re.S)
    if match is None:
        raise RuntimeError(f"--after generated runtime IR must define {name}")
    return match[0]


def symbol_sizes(nm, path, prefix):
    symbols = {}
    for line in run([nm, "--print-size", "--defined-only", "--format=posix", path]).splitlines():
        parts = line.split()
        if len(parts) == 4 and parts[0].lstrip("_").startswith(prefix):
            symbols["pys_" + parts[0].lstrip("_")[len(prefix):]] = int(parts[3], 16)
    return symbols


def build_probe(args, tmp, tools, report):
    before_c = (args.before / "runtime.c").read_text(encoding="latin-1")
    overflow = re.search(r"^#define[ \t]+OVF[ \t]+[^\n]+", before_c, re.M)
    if overflow is None:
        raise RuntimeError("--before runtime.c must define OVF")
    source = ['#include <stdint.h>', 'typedef int64_t I;',
              'extern _Noreturn void numeric_contract_fail(const char *);',
              '#define pys_fail numeric_contract_fail', overflow[0]]
    source += [f"#define {name} numeric_before_{name[4:]}" for name in FUNCTIONS]
    source += [c_function(before_c, name) for name in FUNCTIONS]
    (tmp / "before.c").write_text("\n".join(source) + "\n", encoding="latin-1")

    command = [args.compiler] if args.compiler else [sys.executable, "-B", "-E", args.after / "pystachy.py"]
    # A probe has fixed defaults; caller GC, unchecked-mode or diagnostic settings
    # must not change what is generated or cause a native compiler to do extra work.
    env = {key: value for key, value in os.environ.items() if not key.startswith("PYSTACHY_")}
    run(command + ["rt", args.after / "runtime.py", "-o", tmp / "runtime.ll"], cwd=args.after, env=env)
    ir = (tmp / "runtime.ll").read_text(encoding="latin-1")
    functions = [llvm_function(ir, name) for name in FUNCTIONS]
    for name, function in zip(FUNCTIONS, functions):
        signature = re.match(r"define i64 @" + name + r"\(([^)]*)\)", function)
        parameters = signature[1].split(",") if signature else []
        if len(parameters) != FUNCTIONS[name] or not all(re.fullmatch(r"\s*i64 %[\w.$]+\s*", p) for p in parameters):
            raise RuntimeError(f"unexpected native signature for {name}")
    globals_defined = set(re.findall(r"^@([\w.$]+) =", ir, re.M))
    globals_used = set(re.findall(r"@([\w.$]+)", "\n".join(functions))) & globals_defined
    extract = [tools["llvm-extract"]] + [f"--func={name}" for name in FUNCTIONS]
    extract += [f"--glob={name}" for name in sorted(globals_used)]
    run(extract + [tmp / "runtime.ll", "-o", tmp / "extracted.bc"])
    run([tools["opt"], "-S", "-passes=default<O2>", tmp / "extracted.bc", "-o", tmp / "after.ll"])
    optimized = (tmp / "after.ll").read_text(encoding="latin-1")
    report["optimized_calls"] = {
        name: sorted(re.findall(r"\b(?:call|invoke) [^\n]*?@([\w.$]+)", llvm_function(optimized, name)))
        for name in FUNCTIONS
    }
    for name in FUNCTIONS:
        optimized = re.sub(r"@" + name + r"\b", "@numeric_after_" + name[4:], optimized)
    optimized = optimized.replace("@pys_raise(", "@numeric_contract_raise(")
    (tmp / "after.ll").write_text(optimized, encoding="latin-1")

    # Use the after checkout's actual Str header layout for the error-only shim.
    after_c = (args.after / "runtime.c").read_text(encoding="latin-1")
    string_type = re.search(r"^typedef struct \{[^\n]+\} Str;", after_c, re.M)
    if string_type is None:
        raise RuntimeError("cannot extract Str's layout from --after runtime.c")
    (tmp / "harness.c").write_text(HARNESS.replace("/* STR_TYPE */", string_type[0]), encoding="latin-1")
    flags = ["-O2", "-fPIC"]
    run([tools["clang"], *flags, "-c", tmp / "before.c", "-o", tmp / "before.o"])
    run([tools["clang"], *flags, "-Wno-override-module", "-c", tmp / "after.ll", "-o", tmp / "after.o"])
    run([tools["clang"], *flags, "-shared", tmp / "before.o", tmp / "after.o", tmp / "harness.c", "-o", tmp / "probe.so"])
    report["function_size_bytes"] = {
        label: symbol_sizes(tools["llvm-nm"], tmp / f"{label}.o", f"numeric_{label}_")
        for label in ("before", "after")
    }
    report["native_flags"] = flags
    report["llvm_passes"] = "default<O2>"
    return ctypes.CDLL(str(tmp / "probe.so"))


def check_contract(library, seed, random_ranges):
    library.numeric_contract_call.argtypes = [ctypes.c_int] + [ctypes.c_int64] * 4 + [ctypes.POINTER(ctypes.c_int64)]
    library.numeric_contract_call.restype = ctypes.c_char_p

    def check(mode, a, b, step, x, expected):
        values = []
        for side in (0, 1):
            result = ctypes.c_int64()
            error = library.numeric_contract_call(mode + side, a, b, step, x, ctypes.byref(result))
            values.append(result.value if error is None else error.decode())
        if values != [expected, expected]:
            name = list(FUNCTIONS)[mode // 2]
            raise RuntimeError(json.dumps({"function": name, "a": a, "b": b, "step": step, "x": x,
                                           "expected": expected, "before": values[0], "after": values[1]}))

    ends = [LOW, LOW + 1, -3037000500, -3037000499, -123, -1, 0, 1, 123, 3037000499, 3037000500, HIGH - 1, HIGH]
    steps = [LOW, -HIGH, -7, -1, 0, 1, 7, HIGH]
    rng = random.Random(seed)
    ranges = list(itertools.product(ends, ends, steps))
    ranges += [(rng.randint(LOW, HIGH), rng.randint(LOW, HIGH), rng.randint(LOW, HIGH)) for _ in range(random_ranges)]
    memberships = 0
    for a, b, step in ranges:
        try:
            values = range(a, b, step)
        except ValueError as error:
            # Use CPython's error too, including for an empty range with step 0.
            expected = f"{type(error).__name__}: {error}"
        else:
            # len() itself would reject counts above Py_ssize_t; index(last) does
            # not. Convert only the independently obtained count to the native ABI.
            expected = ctypes.c_int64(values.index(values[-1]) + 1 if values else 0).value
        check(2, a, b, step, 0, expected)
        for x in (a, b, LOW, HIGH, rng.randint(LOW, HIGH)):
            expected_has = expected if step == 0 else int(x in values)
            check(4, a, b, step, x, expected_has)
            memberships += 1

    powers = list(itertools.product(range(-64, 65), range(-3, 71)))
    powers += list(itertools.product(ends, [LOW, -1, 0, 1, 2, 3, 62, 63, 64]))
    powers += list(itertools.product([-1, 0, 1], [HIGH, HIGH - 1]))
    for a, b in powers:
        if b < 0 and a != 0:
            expected = "ValueError: negative exponent for int ** int"  # existing checked-int64 contract
        else:
            try:
                expected = pow(a, b)
            except ZeroDivisionError as error:
                expected = f"{type(error).__name__}: {error}"
            else:
                if not LOW <= expected <= HIGH:
                    expected = OVERFLOW
        check(0, a, b, 0, 0, expected)
    return {"range_length": len(ranges), "range_membership": memberships, "integer_power": len(powers)}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--before", type=Path, required=True, help="checkout with the three definitions in runtime.c")
    parser.add_argument("--after", type=Path, required=True, help="checkout with the three definitions in runtime.py")
    parser.add_argument("--compiler", type=Path, help="optional built compiler; default: after/pystachy.py under this Python")
    parser.add_argument("--seed", type=int, default=1123)
    parser.add_argument("--random-ranges", type=int, default=20000)
    parser.add_argument("--json", type=Path, help="also save the JSON summary to this file")
    args = parser.parse_args()
    if args.random_ranges < 0:
        parser.error("--random-ranges must be nonnegative")
    args.before, args.after = args.before.resolve(), args.after.resolve()
    if args.compiler:
        args.compiler = args.compiler.resolve()
    report = {"schema": 1, "status": "error", "seed": args.seed, "random_ranges": args.random_ranges,
              "python": sys.version, "platform": platform.platform(),
              "runner_sha256": digest(Path(__file__)),
              "scope": "isolated native helper values and error text; excludes full unwinder, GC and performance"}
    try:
        report["before"] = checkout_info(args.before)
        report["after"] = checkout_info(args.after, compiler_sources=args.compiler is None)
        # Native mode also needs hashes of the runtime inputs, independent of the binary.
        report["after"]["inputs_sha256"]["runtime.py"] = digest(args.after / "runtime.py")
        report["compiler"] = {"mode": "native" if args.compiler else "hosted", "path": str(args.compiler or sys.executable)}
        if args.compiler:
            report["compiler"]["sha256"] = digest(args.compiler)
        tools = {name: tool(name) for name in ("clang", "opt", "llvm-extract", "llvm-nm")}
        report["toolchain"] = {name: {"path": path, "version": run([path, "--version"]).splitlines()[0]}
                               for name, path in tools.items()}
        with tempfile.TemporaryDirectory(prefix="pystachy-numeric-contract.") as temporary:
            library = build_probe(args, Path(temporary), tools, report)
            report["cases_passed"] = check_contract(library, args.seed, args.random_ranges)
        report["status"] = "pass"
    except (OSError, RuntimeError, ValueError) as error:
        report["error"] = str(error)
    encoded = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(encoded)
    print(encoded, end="")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
