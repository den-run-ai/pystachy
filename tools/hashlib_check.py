"""Check lib/hashlib.py on CPython against CPython's hashlib, whose hash objects are OpenSSL's.

This checks the port's source, not compiled Pystachy (tests/programs/library/lib_hashlib.py
compares that): for random data of every length around the block and padding boundaries, hashed
whole and in random pieces with digests and copies between them, each of the port's algorithms
must give CPython's digest, hex digest, name, digest_size and block_size; new() must raise
CPython's error for an unknown name; and the docstrings of the constructors, new() and the hash
objects must be CPython's.
Usage: python3 -I tools/hashlib_check.py [--rounds N]
"""
import argparse
import hashlib
import importlib.util
from pathlib import Path
import random
import sys

LIB = Path(__file__).resolve().parent.parent / "lib"
sys.dont_write_bytecode = True  # (no __pycache__ in lib/)
NAMES = ("md5", "sha1", "sha224", "sha256")
STEPS = (1, 3, 55, 56, 57, 63, 64, 65, 119, 120, 128, 200, 1000)


def load():
    spec = importlib.util.spec_from_file_location("_pystachy_hashlib_port", LIB / "hashlib.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def state(h):
    return h.digest(), h.hexdigest(), h.name, h.digest_size, h.block_size


def check(port, gen, name, size):
    # the number of comparisons made; an AssertionError names the first that differs
    data = gen.randbytes(size)
    made = 1
    assert state(getattr(port, name)(data)) == state(getattr(hashlib, name)(data)), (name, size, "whole")
    ours = port.new(name)
    theirs = hashlib.new(name)
    at = 0
    while at < size:
        step = gen.choice(STEPS)
        ours.update(data[at:at + step])
        theirs.update(data[at:at + step])
        at += step
        if gen.random() < 0.3:  # a digest between updates changes nothing
            assert state(ours) == state(theirs), (name, size, at, "between")
            made += 1
        if gen.random() < 0.2:  # a copy goes on alone
            a = ours.copy()
            b = theirs.copy()
            a.update(data[:at % 97])
            b.update(data[:at % 97])
            assert state(a) == state(b) and state(ours) == state(theirs), (name, size, at, "copy")
            made += 2
    assert state(ours) == state(theirs), (name, size, "pieces")
    return made + 1


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--rounds", type=int, default=3, help="passes over the lengths (default 3)")
    args = parser.parse_args()
    port = load()
    gen = random.Random(20261112)
    made = 0
    for _ in range(args.rounds):
        for name in NAMES:
            for size in list(range(260)) + [511, 512, 513, 4095, 4096, 4097, 65537]:
                made += check(port, gen, name, size)
    for name in ("sha512", "", "sha 1"):
        try:
            port.new(name)
        except ValueError as e:
            ours = str(e)
        else:
            raise AssertionError("new() took " + repr(name))
        try:
            hashlib.new("no " + name)
        except ValueError as e:
            assert ours == str(e).replace("no " + name, name), (ours, str(e))
    kind = type(hashlib.sha1())
    assert port.HASH.__doc__ == kind.__doc__
    for method in ("update", "digest", "hexdigest", "copy"):
        assert getattr(port.HASH, method).__doc__ == getattr(kind, method).__doc__, method
    for name in NAMES + ("new",):
        assert getattr(port, name).__doc__ == getattr(hashlib, name).__doc__, name
    print(f"lib/hashlib.py: {made} comparisons with CPython's hashlib agree")


if __name__ == "__main__":
    main()
