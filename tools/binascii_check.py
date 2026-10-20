"""Check lib/_pystachy_binascii.py on CPython against CPython's C binascii module.

This checks the port's source, not compiled Pystachy (tests/programs/library/lib_binascii.py compares that): for
random arguments of every function, mostly near the inputs' edge cases (padding and junk in
base64, line lengths and line ends in quoted-printable, lengths in uu, separators in hex), the
port must return what the C module returns, or raise the same exception with the same message;
and its functions must have the C module's signatures. With --upstream DIR, it also runs CPython
3.13.16's Lib/test/test_binascii.py, which DIR holds, with the port as binascii: every test must
pass but those of EXPECTED, which need non-contiguous memoryview buffers.
Usage: python3 -I tools/binascii_check.py [--rounds N] [--upstream DIR]
"""
import argparse
import binascii
import hashlib
import importlib.util
import inspect
from pathlib import Path
import random
import subprocess
import sys
import unittest

LIB = Path(__file__).resolve().parent.parent / "lib"
sys.dont_write_bytecode = True  # (no __pycache__ in lib/)
TEST_BINASCII_SHA256 = "95648ecc7cd21319fd515090ef5c0c2e4a501d43409ffc3ce27f5f647e73c7d7"
EXPECTED = {f"{c}.test_c_contiguity" for c in ("BinASCIITest", "ArrayBinASCIITest", "BytearrayBinASCIITest",
                                               "MemoryviewBinASCIITest")}
B64 = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def outcome(module, name, args, kwargs):
    try:
        return repr(getattr(module, name)(*args, **kwargs))
    except Exception as e:  # (binascii.Error and binascii.Incomplete are each module's own)
        return f"{type(e).__name__}: {e}"


def cases(gen, rounds):
    # (function name, args, kwargs)
    def data(alphabet=None, low=0, high=12):
        n = gen.randint(low, high)
        return bytes(gen.randrange(256) if alphabet is None else gen.choice(alphabet) for i in range(n))

    def mutate(b, inserts):
        b = bytearray(b)
        for i in range(gen.randint(0, 3)):
            pos = gen.randint(0, len(b))
            if gen.random() < 0.7 or not b:
                b[pos:pos] = bytes([gen.choice(inserts)])
            else:
                del b[min(pos, len(b) - 1)]
        return bytes(b)

    for i in range(rounds):
        d = data(high=50)
        sep = gen.choice(["-", b":", " ", "ab", b"", "é", "Ā", "😀", b"\xff", "?"])
        n = gen.choice([gen.randint(-6, 6), 2**31 - 1, 2**31, -2**31, -2**31 - 1])
        yield "hexlify", (d,), {}
        yield "hexlify", (d, sep, n), {}
        yield "b2a_hex", (d,), {"sep": sep, "bytes_per_sep": n}
        h = data(b"0123456789abcdefABCDEFxg \n", 0, 10)
        yield "unhexlify", (h,), {}
        yield "a2b_hex", (h.decode("latin-1"),), {}
        yield "b2a_base64", (d,), {"newline": gen.random() < 0.5}
        t = mutate(binascii.b2a_base64(data(), newline=False), b"=\n!A ")
        for strict in (False, True):
            yield "a2b_base64", (t,), {"strict_mode": strict}
            yield "a2b_base64", (data(b"AQ=\n!g", 0, 9),), {"strict_mode": strict}
        yield "a2b_base64", (t.decode("latin-1"),), {}
        crc = gen.choice([0, 1, 0xFFFFFFFF, gen.randrange(1 << 32), -1, 1 << 40])
        yield "crc32", (d,), {}
        yield "crc32", (d, crc), {}
        yield "crc_hqx", (d, crc), {}
        u = data(high=47)
        yield "b2a_uu", (u,), {"backtick": gen.random() < 0.5}
        line = binascii.b2a_uu(u[:45], backtick=gen.random() < 0.5)
        yield "a2b_uu", (mutate(line, b" `\n\r!~a\x7f"),), {}
        yield "a2b_uu", (data(b" !`\n\rM~a#", 0, 7),), {}
        k = gen.random()
        if k < 0.3:
            q = data(b"a =_.\t\r\n\x00\x7f\xe9Z", 0, 12)
        elif k < 0.6:
            q = data(b"ab \t\n" + bytes([gen.choice(b".=_\r\x00")]), 60, 180)
        else:
            q = data(high=100)
        flags = {"quotetabs": gen.random() < 0.3, "istext": gen.random() < 0.7, "header": gen.random() < 0.3}
        yield "b2a_qp", (q,), flags
        yield "a2b_qp", (binascii.b2a_qp(q, **flags),), {"header": flags["header"]}
        e = data(b"=\r\n_aF0g ", 0, 10)
        yield "a2b_qp", (e,), {"header": gen.random() < 0.5}
        yield "a2b_qp", (e.decode("latin-1"),), {}


def signature(f):
    # f's parameters, without annotations, as a builtin's __text_signature__ spells them
    text = str(inspect.signature(f)).split(" -> ")[0]
    for t in (": bytes", ": bool", ": int", ": str"):
        text = text.replace(t, "")
    return text.replace(" = ", "=").replace("sep=None", "sep=<unrepresentable>")


def run_upstream(directory):
    # test_binascii with the port as the binascii module: prints the tests that fail, then the counts
    load("binascii", LIB / "_pystachy_binascii.py")
    tests = load("test_binascii", Path(directory) / "test_binascii.py")
    suite = unittest.defaultTestLoader.loadTestsFromModule(tests)
    result = unittest.TextTestRunner(stream=open("/dev/null", "w")).run(suite)
    for test, _ in result.failures + result.errors:
        print("failed", test.id().removeprefix("test_binascii."))
    print("ran", result.testsRun, "skipped", len(result.skipped))


def upstream(directory):
    path = Path(directory) / "test_binascii.py"
    if hashlib.sha256(path.read_bytes()).hexdigest() != TEST_BINASCII_SHA256:
        print(f"{path}: not CPython 3.13.16's Lib/test/test_binascii.py")
        return 1
    out = subprocess.run([sys.executable, "-I", __file__, "--run-upstream", directory], capture_output=True,
                         text=True, check=False).stdout
    failed = {line.split()[1] for line in out.splitlines() if line.startswith("failed ")}
    counts = out.splitlines()[-1].split() if out else ["ran", "0", "skipped", "0"]
    passed = int(counts[1]) - int(counts[3]) - len(failed)
    print(f"test_binascii on the port: {passed} passed, {counts[3]} skipped, {len(failed)} failed")
    status = 0
    for name in sorted(failed ^ EXPECTED):
        print("  unexpected:", name, "failed" if name in failed else "passed")
        status = 1
    return status


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rounds", type=int, default=20000)
    parser.add_argument("--upstream", metavar="DIR")
    parser.add_argument("--run-upstream", help=argparse.SUPPRESS)
    options = parser.parse_args()
    if options.run_upstream:
        run_upstream(options.run_upstream)
        return 0
    port = load("binascii_port", LIB / "_pystachy_binascii.py")
    count = failures = 0
    for name, args, kwargs in cases(random.Random(20261016), options.rounds):
        count += 1
        want = outcome(binascii, name, args, kwargs)
        got = outcome(port, name, args, kwargs)
        if got != want:
            failures += 1
            if failures <= 20:
                print(f"{name}(*{args!r}, **{kwargs!r}): {got}, where CPython's is {want}")
    print(f"{count} calls, {failures} differ")
    names = sorted(n for n in dir(binascii) if not n.startswith("_") and not isinstance(getattr(binascii, n), type))
    want = {n: getattr(binascii, n).__text_signature__.replace("$module, /, ", "").replace("$module, ", "") for n in names}
    differ = [n for n in names if not hasattr(port, n) or signature(getattr(port, n)) != want[n]]
    for n in differ:
        print(f"{n}: signature {signature(getattr(port, n)) if hasattr(port, n) else 'missing'}, where CPython's is {want[n]}")
    print(f"{len(names)} functions, {len(differ)} signatures differ")
    status = 1 if failures or differ else 0
    if options.upstream:
        status |= upstream(options.upstream)
    return status


if __name__ == "__main__":
    sys.exit(main())
