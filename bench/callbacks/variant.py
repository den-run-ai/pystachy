"""Hosted compiler experiment for the two callback fixtures in this directory."""

import os
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT))

from src.pystachy_compiler import driver  # noqa: E402
from src.pystachy_compiler.gen import Gen  # noqa: E402
from src.pystachy_compiler.utils import identity_abi, is_callable, lt  # noqa: E402


# A fixed allowlist makes target-selection costs and the number of variants explicit.
TARGETS = {
    "callback_bisect.py": ("bisect$bisect_left", "key", "text_length"),
    "callback_effects.py": ("search", "key", "project"),
}
MAX_EXTRA_IR_BYTES = 16 * 1024


class CallbackVariant(Gen):
    selection: tuple[str, str, str]
    emitted = False

    def program(self, mod):
        module = super().program(mod)
        if not self.rtmode and not self.emitted:
            raise ValueError("callback experiment did not find an eligible specialization")
        return module

    def lower(self, fn):
        start = len(self.out)
        super().lower(fn)
        consumer, parameter, target = self.selection
        f = fn.f
        if self.rtmode or f.name != consumer or parameter not in f.params:
            return
        index = f.params.index(parameter)
        if index not in fn.ps or not is_callable(f.ptypes[index]):
            return
        # Only the immutable top-level adapter of exactly this Callable signature can hit.
        adapter = self.adapters.get(f"fn[f:{target}] {f.ptypes[index]}")
        descriptor = next((item.name for item in self.consts
                           if item.kind == "callable" and item.refs == [adapter, "null"]), None)
        if descriptor is None:
            return

        # Defer functions with extra ABI arguments, multi-body lowerings or exception pads.
        body = self.out[start:]
        if f.export or f.cls or identity_abi(f) or f.ll in self.vrets or f.ll in self.rdpass or fn.coro or fn.pads:
            return
        params = [f"{lt(f.ptypes[i])} %a{i}" for i in fn.ps]
        ret = lt(f.ret)
        header = f"define internal {ret} {f.ll}({', '.join(params)}) {{"
        if ret == "void" or body[0] != header or body.count("}") != 1:
            return
        if self.emitted:
            raise ValueError("callback experiment matched more than one specialization")

        # Each clone reuses the original body, including recursion checks. The original
        # symbol tests the incoming descriptor once, before either path can have effects.
        clones = []
        wrapper = [header, "entry:", f"  %hit = icmp eq ptr %a{index}, {descriptor}",
                   "  br i1 %hit, label %hot, label %fallback"]
        for branch in ("hot", "fallback"):
            # Program function names start with @f.; this experiment emits only one pair.
            symbol = f"@pystachy.cbbench.{branch}"
            clones.extend([header.replace(f.ll, symbol, 1), *body[1:]])
            args = params.copy()
            if branch == "hot":
                args[fn.ps.index(index)] = f"ptr {descriptor}"
            wrapper.extend([f"{branch}:", f"  %r_{branch} = tail call {ret} {symbol}({', '.join(args)})",
                            f"  ret {ret} %r_{branch}"])
        wrapper.append("}")
        replacement = clones + wrapper
        extra_bytes = len("\n".join(replacement).encode()) - len("\n".join(body).encode())
        if extra_bytes > MAX_EXTRA_IR_BYTES:
            raise ValueError(f"callback variant exceeds the IR budget ({extra_bytes} extra bytes)")
        self.out[start:] = replacement
        self.emitted = True


def main():
    if (len(sys.argv) < 4 or sys.argv[1] not in ("generic", "guarded")
            or sys.argv[2] not in ("ir", "run", "build") or Path(sys.argv[3]).name not in TARGETS):
        sys.exit("usage: variant.py {generic|guarded} {ir|run|build} CALLBACK_FIXTURE.py [args]")
    if sys.argv.pop(1) == "guarded":
        CallbackVariant.selection = TARGETS[Path(sys.argv[2]).name]
        driver.Gen = CallbackVariant
    os.environ["PYSTACHY_HOME"] = str(ROOT)
    # The normal driver hashes compiler components relative to the invoking script.
    # Keep the experiment itself and the actual compiler sources in its cache identity.
    driver.COMPILER_SOURCES = [os.path.relpath(ROOT / path, HERE) for path in driver.COMPILER_SOURCES]
    driver.main()


if __name__ == "__main__":
    main()
