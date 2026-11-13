"""Check lib/librt/internal.py on CPython against librt 0.16.0's C extension (librt.internal).

This checks the port's source, not compiled Pystachy (tests/programs/library/lib_librt_internal.py
compares that): for random values, mostly at the int formats' boundaries, random strings, bytes
and float bit patterns, every write must give the extension's bytes and every read its value; for
random nested cache objects, extract_symbol must return its bytes; and for random truncations and
corruptions of those encodings, each read and extract_symbol must return what the extension
returns, or raise the same exception with the same message, leaving the same position (the next
tag read). write_tag's out-of-range errors are left out: the extension crashes there.
Needs librt==0.16.0 (mypy's dependency, tools/requirements-dev.txt).
Usage: python3 -I tools/librt_check.py [--rounds N] [--seed S]
"""
import argparse
import importlib.metadata
import importlib.util
from pathlib import Path
import random
import struct
import sys

import librt.internal as c

LIB = Path(__file__).resolve().parent.parent / "lib"
sys.dont_write_bytecode = True  # (no __pycache__ in lib/)
BOUNDS = [-10, 117, -100, 16283, -10000, 536860911, -2**31, 2**31, -2**63, 2**63 - 1]
NAMES = ["write_bool", "write_str", "write_bytes", "write_float", "write_int", "write_tag"]
READS = ["read_bool", "read_str", "read_bytes", "read_float", "read_int", "read_tag", "extract_symbol"]


def load():
    spec = importlib.util.spec_from_file_location("pystachy_librt_internal", LIB / "librt" / "internal.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def an_int(rng):
    k = rng.randrange(4)
    if k == 0:
        return rng.choice(BOUNDS) + rng.randint(-2, 2)
    if k == 1:
        return rng.randint(-200, 20000)
    v = rng.getrandbits(rng.randint(1, 63))
    return -v if rng.random() < 0.3 else v


def a_str(rng):
    n = rng.choice([0, 1, 5, 116, 117, 118, 300, 16283, 16284])
    alphabet = "abé中\U0001f40d"
    return "".join(rng.choice(alphabet) for _ in range(rng.randint(0, n) if n > 300 else n))


def a_value(rng):
    k = rng.randrange(6)
    if k == 0:
        return "write_bool", rng.random() < 0.5
    if k == 1:
        return "write_str", a_str(rng)
    if k == 2:
        return "write_bytes", bytes(rng.getrandbits(8) for _ in range(rng.choice([0, 3, 117, 118, 400])))
    if k == 3:
        return "write_float", struct.unpack("<d", struct.pack("<Q", rng.getrandbits(64)))[0]
    if k == 4:
        return "write_int", an_int(rng)
    return "write_tag", rng.randrange(256)


def an_object(rng, ops, depth):
    # a tagged value as mypy's cache writes one (the tags of librt_internal.c's _skip_object)
    k = rng.randrange(12 if depth < 3 else 6)
    if k == 0:
        ops += [("write_tag", rng.choice([4, 5])), ("write_str", a_str(rng)) if rng.random() < 0.5 else ("write_bytes", b"xy")]
    elif k == 1:
        ops.append(("write_tag", rng.choice([0, 1, 2])))
    elif k == 2:
        ops += [("write_tag", 3), ("write_int", an_int(rng))]
    elif k == 3:
        ops += [("write_tag", 6), ("write_float", rng.random())]
    elif k == 4:
        ops += [("write_tag", 80), ("write_tag", rng.choice([83, 84, 85, 86, 87]))]
    elif k == 5:
        ops += [("write_tag", 80), ("write_tag", 81), ("write_str", a_str(rng))]
    elif k == 6:
        n = rng.randint(0, 3)
        ops += [("write_tag", rng.choice([20, 24])), ("write_int", n)]
        for _ in range(n):
            an_object(rng, ops, depth + 1)
    elif k == 7:
        n = rng.randint(0, 3)
        ops += [("write_tag", 21), ("write_int", n)] + [("write_int", an_int(rng)) for _ in range(n)]
    elif k == 8:
        n = rng.randint(0, 3)
        ops += [("write_tag", rng.choice([22, 23])), ("write_int", n)] + [("write_str", a_str(rng)) for _ in range(n)]
    elif k == 9:
        n = rng.randint(0, 2)
        ops += [("write_tag", 30), ("write_int", n)]
        for _ in range(n):
            ops.append(("write_str", a_str(rng)))
            an_object(rng, ops, depth + 1)
    elif k == 10:
        ops += [("write_tag", rng.choice([51, 120, 253]) if rng.random() < 0.5 else 80)]
        if ops[-1][1] == 80:
            ops.append(("write_tag", 82))
        for _ in range(rng.randint(0, 3)):
            an_object(rng, ops, depth + 1)
        ops.append(("write_tag", 255))
    else:
        ops += [("write_tag", 7), ("write_float", 1.0), ("write_float", -2.0)] if rng.random() < 0.5 else \
               [("write_tag", 8), ("write_str", "a"), ("write_str", "b")]


def encode(module, ops):
    w = module.WriteBuffer()
    for name, value in ops:
        getattr(module, name)(w, value)
    return w.getvalue()


def read_outcome(module, data, name):
    r = module.ReadBuffer(data)
    try:
        value = getattr(module, name)(r)
        result = ("ok", value if not isinstance(value, float) else struct.pack("<d", value))
    except (ValueError, UnicodeDecodeError, OverflowError) as e:
        result = (type(e).__name__, str(e))
    try:
        after = module.read_tag(r)
    except ValueError as e:
        after = str(e)
    return result, after


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=20000)
    ap.add_argument("--seed", type=int, default=1)
    args = ap.parse_args()
    if importlib.metadata.version("librt") != "0.16.0":
        sys.exit(f"librt {importlib.metadata.version('librt')} is installed; this checks 0.16.0")
    p = load()
    rng = random.Random(args.seed)
    checks = 0
    for _ in range(args.rounds):
        ops = [a_value(rng) for _ in range(rng.randint(1, 6))]
        data = encode(c, ops)
        assert encode(p, ops) == data, ops
        rp = p.ReadBuffer(data)
        rc = c.ReadBuffer(data)
        for name, _ in ops:
            read = "read" + name[5:]
            a = getattr(p, read)(rp)
            b = getattr(c, read)(rc)
            assert a == b or (a != a and b != b), (read, a, b)
        sym: list[tuple[str, object]] = []
        for _ in range(rng.randint(0, 4)):
            an_object(rng, sym, 0)
        sym.append(("write_tag", 255))
        blob = encode(c, sym)
        assert encode(p, sym) == blob, sym
        cut = blob[: rng.randint(0, len(blob))]
        flipped = bytearray(blob)
        if flipped:
            flipped[rng.randrange(len(flipped))] = rng.getrandbits(8)
        for raw in (blob, cut, bytes(flipped), data[: rng.randint(0, len(data))]):
            for name in READS:
                assert read_outcome(p, raw, name) == read_outcome(c, raw, name), (name, raw.hex())
                checks += 1
    print(f"librt.internal 0.16.0: {args.rounds} rounds, {checks} read outcomes identical")


if __name__ == "__main__":
    main()
