"""Check lib/librt/base64.py on CPython against librt 0.16.0's C extension (librt.base64).

This checks the port's source, not compiled Pystachy (tests/programs/library/lib_librt_base64.py
compares that): for random bytes, random text over the alphabet, padding and a few other
characters, and valid encodings with characters inserted, removed or appended, each of the four
functions must return the extension's bytes or raise the same exception with the same message,
for a bytes argument and, where the bytes are ASCII, for the str. Arguments of other types must
raise the extension's TypeError.
Needs librt==0.16.0 (mypy's dependency, tools/requirements-dev.txt).
Usage: python3 -I tools/librt_base64_check.py [--rounds N] [--seed S]
"""
import argparse
import importlib.metadata
import importlib.util
from pathlib import Path
import random
import sys

import librt.base64 as c

LIB = Path(__file__).resolve().parent.parent / "lib"
sys.dont_write_bytecode = True  # (no __pycache__ in lib/)
NAMES = ["b64encode", "urlsafe_b64encode", "b64decode", "urlsafe_b64decode"]
ALPHABET = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
NOISE = b"=-_\n !\x00\x80\xff"


def load():
    spec = importlib.util.spec_from_file_location("pystachy_librt_base64", LIB / "librt" / "base64.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def outcome(f, arg):
    try:
        return ("ok", f(arg))
    except Exception as e:  # (the comparison is of whatever either side raises)
        return (type(e).__name__, str(e))


def data(rng):
    k = rng.randrange(6)
    n = rng.randrange(0, 40)
    if k == 0:
        return bytes(rng.randrange(256) for _ in range(n))
    if k == 1:
        return bytes(rng.choice(ALPHABET + NOISE) for _ in range(n))
    if k == 2:
        return bytes(rng.choice(ALPHABET + b"=") for _ in range(n))
    d = c.b64encode(bytes(rng.randrange(256) for _ in range(n)))
    if k == 3:
        return d if rng.randrange(2) else c.urlsafe_b64encode(bytes(rng.randrange(256) for _ in range(n)))
    for _ in range(rng.randrange(1, 4)):
        j = rng.randrange(len(d) + 1)
        how = rng.randrange(3)
        if how == 0:
            d = d[:j] + bytes([rng.choice(ALPHABET + NOISE)]) + d[j:]
        elif how == 1 and d:
            d = d[:j] + d[j + 1:]
        else:
            d = d + bytes(rng.choice(b"=A\n") for _ in range(rng.randrange(1, 4)))
    return d


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--rounds", type=int, default=20000)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()
    version = importlib.metadata.version("librt")
    if version != "0.16.0":
        sys.exit(f"librt_base64_check: librt {version}, not 0.16.0 (tools/requirements-dev.txt)")
    p = load()
    rng = random.Random(args.seed)
    calls = 0
    for _ in range(args.rounds):
        d = data(rng)
        forms = [d]
        try:
            forms.append(d.decode("ascii"))
        except UnicodeDecodeError:
            pass
        for name in NAMES:
            for arg in forms:
                want, got = outcome(getattr(c, name), arg), outcome(getattr(p, name), arg)
                calls += 1
                if want != got:
                    sys.exit(f"librt_base64_check: {name}({arg!r}): the extension gives {want}, the port {got}")
    for arg in [None, 5, 2.5, [97], (b"a",), bytearray(b"aGk="), memoryview(b"aGk="), "hé", "€"]:
        for name in NAMES:
            want, got = outcome(getattr(c, name), arg), outcome(getattr(p, name), arg)
            calls += 1
            if want != got:
                sys.exit(f"librt_base64_check: {name}({arg!r}): the extension gives {want}, the port {got}")
    for name in NAMES:
        if getattr(c, name).__doc__ != getattr(p, name).__doc__:
            sys.exit(f"librt_base64_check: {name}.__doc__ differs")
    print(f"librt_base64_check: {calls} calls agree with librt {version} ({args.rounds} rounds, seed {args.seed})")


if __name__ == "__main__":
    main()
