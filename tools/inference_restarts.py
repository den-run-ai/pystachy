#!/usr/bin/env python3
"""Name what made the compiler start a program's type inference again.

Each restart (diagnostics.Rejoin or a subclass) compiles the whole program again,
from loading through every frontend phase, so a variable that holds two types can
double a program's compile time. The bootstrap requires the compiler's own source
to compile in one attempt (tools/self_compile_once.sh); run this under CPython to
list each restart's kind, the error that raised it and the joins it found.

usage: python3 tools/inference_restarts.py [PROGRAM.py]   (default: pystachy.py)
Exits 0 when the program compiled in one attempt, 1 when it needed more.
"""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.pystachy_compiler import diagnostics, driver  # noqa: E402
from src.pystachy_compiler.gen import Gen  # noqa: E402


def describe(gen, retry, error):
    lines = [type(retry).__name__ + (f" after {error[0]}: {error[1]}" if error else "")]
    lines += [f"  join {key}: {gen.newhints[key]}" for key in sorted(gen.newhints)]
    lines += [f"  without {key}" for key in sorted(gen.newx)]
    lines += [f"  narrowing {key}" for key in sorted(gen.newwant)]
    if gen.idevent != "":
        lines.append(f"  identity crossing {gen.idevent}")
    lines += [f"  class boxes of file {key}" for key in sorted(gen.clsused)]
    return lines


def restarts(path):
    """Compile PATH as `pystachy ir` does; return each restart's description and the attempts."""
    found = []
    attempts = [0]
    error = []
    program = Gen.program
    err = Gen.err
    load = driver.Loader.program

    def observed_err(gen, msg):
        try:
            return err(gen, msg)
        except diagnostics.Rejoin as retry:
            # (named only if this very exception ends the attempt: dynamic.py catches some)
            error[:] = [retry, diagnostics.where(gen.line), msg]
            raise

    def observed_program(gen, mods):
        error.clear()
        try:
            return program(gen, mods)
        except diagnostics.Rejoin as retry:
            found.append(describe(gen, retry, error[1:] if error and error[0] is retry else []))
            raise
        except Exception as failure:
            if diagnostics.TRIAL:
                # (a pass that kept optional imports' handlers failed: the driver starts again without)
                found.append([f"{type(failure).__name__} while keeping optional-import handlers"])
            raise

    def observed_load(loader, filename, code):
        attempts[0] += 1
        try:
            return load(loader, filename, code)
        except diagnostics.Rejoin as retry:
            found.append([type(retry).__name__] + [f"  keeps the handlers of {key}" for key in loader.newkeeps])
            raise

    Gen.program, Gen.err, driver.Loader.program = observed_program, observed_err, observed_load
    try:
        diagnostics.SRC = str(path)
        driver.compile_program(str(path), path.read_text(encoding="utf-8"),
                               driver.program_dirs(str(path), str(ROOT)), "")
    finally:
        Gen.program, Gen.err, driver.Loader.program = program, err, load
    return found, attempts[0]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("program", nargs="?", default=str(ROOT / "pystachy.py"))
    args = parser.parse_args(argv)
    # (the compiler recurses for each level of nesting, as driver.main allows)
    sys.setrecursionlimit(driver.MAXNEST * 40)
    found, attempts = restarts(Path(args.program))
    for index, lines in enumerate(found):
        print(f"restart {index + 1}: {lines[0]}")
        for line in lines[1:]:
            print(line)
    print(f"{attempts} inference attempt{'s' if attempts != 1 else ''}")
    return 0 if attempts == 1 else 1


if __name__ == "__main__":
    sys.exit(main())
