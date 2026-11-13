"""Check lib/hmac.py on CPython against CPython's hmac, whose hashing is OpenSSL's.

This checks the port's source, not compiled Pystachy (tests/programs/library/lib_hmac.py compares
that): lib/hmac.py runs over lib/hashlib.py, both loaded from their files, and for random keys
and messages of lengths around the block size, given whole and in pieces, with copies between
them, every algorithm of lib/hashlib must give CPython's digest, hex digest, name, digest_size
and block_size, by its name and by its constructor; hmac.digest() and compare_digest() must agree
with CPython's too.
Usage: python3 -I tools/hmac_check.py [--rounds N]
"""
import argparse
import hmac
import importlib.util
from pathlib import Path
import random
import sys

LIB = Path(__file__).resolve().parent.parent / "lib"
sys.dont_write_bytecode = True  # (no __pycache__ in lib/)
NAMES = ("md5", "sha1", "sha224", "sha256")
SIZES = (0, 1, 20, 55, 63, 64, 65, 128, 131, 300)


def load():
    # lib/hmac.py imports hashlib: it must be lib/hashlib.py, not CPython's
    spec = importlib.util.spec_from_file_location("_pystachy_hashlib_port", LIB / "hashlib.py")
    hashing = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(hashing)
    own = sys.modules.get("hashlib")
    sys.modules["hashlib"] = hashing
    try:
        spec = importlib.util.spec_from_file_location("_pystachy_hmac_port", LIB / "hmac.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        if own is not None:
            sys.modules["hashlib"] = own
    return module, hashing


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rounds", type=int, default=40)
    args = parser.parse_args()
    port, hashing = load()
    rng = random.Random(1395)
    checks = 0
    for name in NAMES:
        for size in SIZES:
            for _ in range(args.rounds):
                key = rng.randbytes(size)
                data = rng.randbytes(rng.choice(SIZES))
                cut = rng.randrange(len(data) + 1)
                want = hmac.new(key, data[:cut], name)
                got = port.new(key, data[:cut], name)
                other = port.new(key, digestmod=getattr(hashing, name))
                other.update(data[:cut])
                branch = got.copy()
                want.update(data[cut:])
                got.update(data[cut:])
                other.update(data[cut:])
                for have in (got, other):
                    if (have.digest(), have.hexdigest(), have.name, have.digest_size, have.block_size) != (want.digest(), want.hexdigest(), want.name, want.digest_size, want.block_size):
                        print(f"{name}: key of {size} bytes, data of {len(data)} cut at {cut}: {have.hexdigest()} is not {want.hexdigest()}")
                        return 1
                if branch.digest() != hmac.new(key, data[:cut], name).digest():
                    print(f"{name}: a copy changed with its original")
                    return 1
                if port.digest(key, data, name) != hmac.digest(key, data, name):
                    print(f"{name}: digest() differs")
                    return 1
                a = want.digest()
                b = a if rng.random() < 0.5 else rng.randbytes(len(a) - rng.randrange(2))
                if port.compare_digest(a, b) != hmac.compare_digest(a, b) or port.compare_digest(a.hex(), b.hex()) != hmac.compare_digest(a.hex(), b.hex()):
                    print(f"{name}: compare_digest() differs")
                    return 1
                checks += 5
    print(f"lib/hmac.py agrees with CPython's hmac: {checks} comparisons")
    return 0


if __name__ == "__main__":
    sys.exit(main())
