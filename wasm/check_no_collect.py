"""Check that each runtime entry tir_wasm.py's RETURNS_UNCOLLECTED names never collects and then returns.

usage: PYTHONPATH=. python3 wasm/check_no_collect.py RUNTIME.wasm

The direct emitter gives a function no guest roots when none of its calls can collect and then
return to it (wasm/README.md). It trusts this list for runtime calls; wasm/spill_roots.py's analysis
of runtime.wasm's code, the same that decides which calls its frames surround, decides whether the
list is right. wasm/build.sh runtime-wasm runs this check on each runtime.wasm it builds. Exits 1
naming each entry that may collect and return, or that runtime.wasm lacks.
"""
import sys

from src.pystachy_compiler.specs import RUNTIME
from src.pystachy_compiler.utils import rtsym
from wasm.spill_roots import returning_collectors
from wasm.tir_wasm import RETURNS_UNCOLLECTED
from wasm.wasi_abi import LIBC_WRAPPERS


def wrong(collects: dict) -> list:
    # the entries the list should not name, given {function name: whether it collects and returns}
    out = []
    for key in RETURNS_UNCOLLECTED:
        sym = rtsym(key) if key in RUNTIME else ""
        sym = LIBC_WRAPPERS.get(sym, sym)
        if sym not in collects:
            out.append(f"{key}: runtime.wasm has no function {sym or '(no RUNTIME entry)'}")
        elif collects[sym]:
            out.append(f"{key}: {sym} may collect and then return")
    return out


def main() -> int:
    if len(sys.argv) != 2:
        sys.stderr.write(__doc__.split("\n\n")[1] + "\n")
        return 2
    with open(sys.argv[1], "rb") as f:
        problems = wrong(returning_collectors(f.read()))
    for p in problems:
        print(f"check_no_collect: {p}", file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
