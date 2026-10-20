"""Check lib/io.py's IncrementalNewlineDecoder and text_encoding() on CPython against CPython's C
module _io.

The port takes str input (decoder=None), as CPython's does without a decoder; this feeds both the
same random calls: decode() of chunks of text whose \\r, \\n and \\r\\n fall anywhere, a \\r\\n split
between two chunks included, with final true or false, interleaved with getstate(), setstate() of
a state either one gave, and reset(), for translate true and false, and compares what each call
returns and the newlines decoded so far (where CPython's is one kind, the port's is the same; where
it is a tuple, the port raises NotImplementedError). translate and final are also given as other
objects, which both test for truth. text_encoding() of encodings and of None, and the classes' and
functions' signatures and docstrings, must be the C module's.
Usage: python3 -I tools/io_check.py [--rounds N]
"""
import _io
import argparse
import importlib.util
import inspect
from pathlib import Path
import random
import sys

LIB = Path(__file__).resolve().parent.parent / "lib"
sys.dont_write_bytecode = True  # (no __pycache__ in lib/)
PIECES = ["a", "bc", "é", "\U0001f600", "\r", "\n", "\r\n", "\n\r", "\r\r", "\x00", "\t", "\x0b\x0c", "z\r", "\r\nq", ""]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def outcome(f, *args, **kwargs):
    try:
        r = f(*args, **kwargs)
    except Exception as e:
        return f"{type(e).__name__}: {e}"
    return f"{type(r).__name__} {r!r}"


def newlines(d):
    try:
        return repr(d.newlines)
    except NotImplementedError:
        return "tuple"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rounds", type=int, default=20000)
    options = parser.parse_args()
    port = load("_io_port", LIB / "io.py")
    gen = random.Random(20261019)
    count = failures = 0

    def report(what, got, want):
        nonlocal failures
        failures += 1
        if failures <= 20:
            print(f"{what}: {got}, where CPython's is {want}")

    def same(what, got, want):
        nonlocal count
        count += 1
        if got != want:
            report(what, got, want)

    truths = [True, False, 1, 0, "", "x", None, 2.5, [], [0]]
    for r in range(options.rounds):
        translate = gen.choice(truths)
        a = port.IncrementalNewlineDecoder(None, translate)
        b = _io.IncrementalNewlineDecoder(None, translate)
        calls = []
        for i in range(gen.randrange(1, 9)):
            k = gen.random()
            if k < 0.7:
                text = "".join(gen.choice(PIECES) for j in range(gen.randrange(0, 6)))
                final = gen.choice(truths) if gen.random() < 0.3 else gen.random() < 0.2
                calls.append(f"decode({text!r}, {final!r})")
                same(" ".join(calls), outcome(a.decode, text, final), outcome(b.decode, text, final))
            elif k < 0.8:
                calls.append("getstate()")
                same(" ".join(calls), outcome(a.getstate), outcome(b.getstate))
            elif k < 0.9:
                state = (b"", gen.choice([0, 1, 2, 3, -1, 2**40 + 1]))
                calls.append(f"setstate({state!r})")
                same(" ".join(calls), outcome(a.setstate, state), outcome(b.setstate, state))
            else:
                calls.append("reset()")
                same(" ".join(calls), outcome(a.reset), outcome(b.reset))
            want = repr(b.newlines)
            same(" ".join(calls) + " .newlines", newlines(a), want if not isinstance(b.newlines, tuple) else "tuple")
        same(" ".join(calls) + " getstate()", outcome(a.getstate), outcome(b.getstate))
    same("decode(final=True) by keyword", outcome(port.IncrementalNewlineDecoder(None, True).decode, "x\r", final=True),
         outcome(_io.IncrementalNewlineDecoder(None, True).decode, "x\r", final=True))
    same("decode(input=...) by keyword", outcome(port.IncrementalNewlineDecoder(None, False).decode, input="\r"),
         outcome(_io.IncrementalNewlineDecoder(None, False).decode, input="\r"))
    for enc in ["utf-8", "latin-1", "locale", "", "x"]:
        same(f"text_encoding({enc!r})", port.text_encoding(enc), _io.text_encoding(enc))
    # (CPython's UTF-8 mode is on where the runtime's default_encoding() gives "utf-8": its C locale)
    sys.modules["_pystachy_io"] = type(sys)("_pystachy_io")
    for mode, enc in [(1, "utf-8"), (0, "UTF-8"), (0, "ISO-8859-1")]:
        sys.modules["_pystachy_io"].default_encoding = lambda e=enc: e
        same(f"text_encoding(None) in UTF-8 mode {mode}", port.text_encoding(None), "utf-8" if mode else "locale")
    for level in [3, 2**31 - 1, 2**31, -(2**31), -(2**31) - 1, 2**62]:
        same(f"text_encoding('ascii', {level})", outcome(port.text_encoding, "ascii", level), outcome(_io.text_encoding, "ascii", level))
    same("DEFAULT_BUFFER_SIZE", port.DEFAULT_BUFFER_SIZE, _io.DEFAULT_BUFFER_SIZE)
    same("open", port.open is _io.open, True)
    same("BlockingIOError", port.BlockingIOError is _io.BlockingIOError, True)
    # the signatures and docstrings
    for name in ["text_encoding"]:
        same(f"{name}.__doc__", getattr(port, name).__doc__, getattr(_io, name).__doc__)
        same(f"{name} signature", str(inspect.signature(getattr(port, name))).split(" -> ")[0].replace(": str | None", "").replace(": int", "").replace(" = ", "="),
             str(inspect.signature(getattr(_io, name))))
    same("IncrementalNewlineDecoder.__doc__", port.IncrementalNewlineDecoder.__doc__, _io.IncrementalNewlineDecoder.__doc__)
    same("IncrementalNewlineDecoder signature", str(inspect.signature(port.IncrementalNewlineDecoder)).split(" -> ")[0].replace(": None", ""),
         str(inspect.signature(_io.IncrementalNewlineDecoder)))
    for m in ["decode", "getstate", "setstate", "reset"]:
        mine = str(inspect.signature(getattr(port.IncrementalNewlineDecoder, m))).split(" -> ")[0]
        mine = mine.replace(": str", "").replace(": tuple[bytes, int]", "").replace(" = ", "=").replace("(self, ", "($self, /, ").replace("(self)", "($self, /)")
        mine = mine.replace("($self, /, state, /)", "($self, state, /)")
        same(f"IncrementalNewlineDecoder.{m} signature", mine, getattr(_io.IncrementalNewlineDecoder, m).__text_signature__)
        same(f"IncrementalNewlineDecoder.{m}.__doc__", getattr(port.IncrementalNewlineDecoder, m).__doc__, getattr(_io.IncrementalNewlineDecoder, m).__doc__)
    same("IncrementalNewlineDecoder names", sorted(n for n in dir(port.IncrementalNewlineDecoder) if not n.startswith("_")),
         sorted(n for n in dir(_io.IncrementalNewlineDecoder) if not n.startswith("_")))
    real = sys.modules["io"]
    sys.modules["io"] = port  # (the stand-in's io is lib's)
    stand = load("_io_stand", LIB / "_pystachy__io.py")
    sys.modules["io"] = real
    same("_io.__doc__", stand.__doc__, _io.__doc__)
    for n in sorted(x for x in dir(stand) if not x.startswith("_")):
        same(f"_io.{n}", getattr(stand, n) is getattr(port, n), True)
        same(f"_io.{n} in CPython's _io", hasattr(_io, n), True)
    print(f"{count} checks, {failures} differ")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
