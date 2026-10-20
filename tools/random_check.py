"""Check lib/random.py and lib/_pyrandom.py on CPython against CPython's own random.

This checks the adapted sources, not compiled Pystachy (tests/programs/library/lib_random*.py compare that): the
port with CPython's C _random, and the port with _pyrandom in its place, must give the standard
module's values for the same calls; _pyrandom's float hash must equal hash(); and random's port of
math.lgamma() must equal math.lgamma(). With --upstream DIR, it also runs CPython 3.13.16's
Lib/test/test_random.py, which DIR holds with its randv2_32.pck, randv2_64.pck and randv3.pck, on
the port with each generator: on C's, every test must pass; on _pyrandom's, all but those of
EXPECTED, which need more than 63 bits from getrandbits() or pickle a _random.Random.
Usage: python3 -I tools/random_check.py [--seeds N] [--upstream DIR]
"""
import argparse
import hashlib
import importlib.util
import math
from pathlib import Path
import random
import subprocess
import sys
import unittest

LIB = Path(__file__).resolve().parent.parent / "lib"
sys.dont_write_bytecode = True  # (no __pycache__ in lib/)
TEST_RANDOM_SHA256 = "04ffe61561421e6cf3b85edcea3ebaca995e6a5def1267cf3562acbb3b9b1337"
# the tests of test_random that fail on _pyrandom: getrandbits() of more than 63 bits raises
# OverflowError, as Pystachy's does, and a _random.Random written in Python pickles
EXPECTED = {
    "MersenneTwister_TestBasicOps.test_bigrand", "MersenneTwister_TestBasicOps.test_bigrand_ranges",
    "MersenneTwister_TestBasicOps.test_getrandbits",
    "MersenneTwister_TestBasicOps.test_getrandbits_2G_bits",
    "MersenneTwister_TestBasicOps.test_randbytes",
    "MersenneTwister_TestBasicOps.test_randbytes_getrandbits",
    "MersenneTwister_TestBasicOps.test_randrange_uses_getrandbits",
    "MersenneTwister_TestBasicOps.test_setstate_middle_arg", "TestModule.test_after_fork",
    "TestRawMersenneTwister.test_bug_41052",
}


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def calls(module, seed):
    # every supported method, in an order that carries one generator's state through all of them
    r = module.Random(seed)
    out = [r.random(), r.getrandbits(1), r.getrandbits(31), r.getrandbits(32), r.getrandbits(33),
           r.getrandbits(63), r.randrange(10), r.randrange(-5, 7), r.randrange(100, 3, -7),
           r.randint(-3, 3), r.randrange(2**62), r.randrange(2**63 - 1)]
    xs = list(range(30))
    r.shuffle(xs)
    out += [xs, r.sample(xs, 7), r.sample(list(range(1000)), 40),
            r.sample(["a", "b", "c"], k=5, counts=[3, 0, 4]),
            r.sample(["a", "b", "c"], k=9, counts=[10**17, 3, 2 * 10**18]), r.choices(xs, k=6),
            r.choices(xs[:4], [1, 0, 2.5, 3], k=6), r.choices(xs[:4], cum_weights=[1, 1, 3, 9], k=6),
            r.choice(xs), r.choice("abcdef"), r.uniform(-2.0, 3.0), r.triangular(),
            r.triangular(1.0, 5.0, 4.0), r.normalvariate(1.0, 2.0), r.gauss(), r.gauss(),
            r.gauss(5.0, 0.5), r.lognormvariate(0.5, 0.25), r.expovariate(0.5),
            r.vonmisesvariate(1.0, 0.0), r.vonmisesvariate(2.0, 4.0), r.gammavariate(0.3, 2.0),
            r.gammavariate(1.0, 2.0), r.gammavariate(7.5, 0.5), r.betavariate(0.5, 0.7),
            r.paretovariate(3.0), r.weibullvariate(2.0, 1.5), r.binomialvariate(1, 0.3),
            r.binomialvariate(30, 0.2), r.binomialvariate(5000, 0.35), r.binomialvariate(400, 0.9),
            r.binomialvariate(10**9, 0.4)]
    state = r.getstate()
    first = r.random()
    r.setstate(state)
    out.append(first == r.random())
    return repr(out)


def lgamma_port(source):
    # the fallback block of random's port, run with math's own functions
    start = source.index("    _lanczos_g = ")
    end = source.index("__all__ = [")
    names = {}
    exec("from math import fmod as _fmod, copysign as _copysign, inf as _inf, isinf as _isinf, "
         "isnan as _isnan, log as _log, floor as _floor, fabs as _fabs, sin as _sin, cos as _cos, "
         "pi as _pi, isfinite as _isfinite\n"
         + "\n".join(line[4:] for line in source[start:end].splitlines()), names)
    return names["_lgamma"]


def outcome(f, x):
    try:
        return repr(f(x))
    except (ValueError, OverflowError) as e:
        return f"{type(e).__name__}: {e}"


def run_upstream(directory, generator):
    # test_random on the port, as the random module, with C's _random or with _pyrandom: prints
    # the tests that fail, then the counts
    if generator == "py":
        sys.modules["_random"] = load("_pyrandom", LIB / "_pyrandom.py")
    load("random", LIB / "random.py")
    sys.path.insert(0, directory)  # (support.findfile() of the .pck files)
    tests = load("test_random", Path(directory) / "test_random.py")
    suite = unittest.defaultTestLoader.loadTestsFromModule(tests)
    result = unittest.TextTestRunner(stream=open("/dev/null", "w")).run(suite)
    for test, _ in result.failures + result.errors:
        print("failed", test.id().removeprefix("test_random."))
    print("ran", result.testsRun, "skipped", len(result.skipped))


def upstream(directory):
    path = Path(directory) / "test_random.py"
    if hashlib.sha256(path.read_bytes()).hexdigest() != TEST_RANDOM_SHA256:
        print(f"{path}: not CPython 3.13.16's Lib/test/test_random.py")
        return 1
    status = 0
    for generator, expected in (("c", set()), ("py", EXPECTED)):
        out = subprocess.run([sys.executable, "-I", __file__, "--run-upstream", directory,
                              generator], capture_output=True, text=True, check=False).stdout
        failed = {line.split()[1] for line in out.splitlines() if line.startswith("failed ")}
        counts = out.splitlines()[-1].split() if out else ["ran", "0", "skipped", "0"]
        passed = int(counts[1]) - int(counts[3]) - len(failed)
        print(f"test_random on {'C' if generator == 'c' else 'the subset'}'s _random: {passed} "
              f"passed, {counts[3]} skipped, {len(failed)} failed")
        for name in sorted(failed ^ expected):
            print("  unexpected:", name, "failed" if name in failed else "passed")
            status = 1
    return status


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, default=1000)
    parser.add_argument("--upstream", metavar="DIR")
    parser.add_argument("--run-upstream", nargs=2, help=argparse.SUPPRESS)
    options = parser.parse_args()
    if options.run_upstream:
        run_upstream(*options.run_upstream)
        return 0
    count = options.seeds
    pyrandom = load("_pyrandom", LIB / "_pyrandom.py")
    port_c = load("random_port_c", LIB / "random.py")
    saved = sys.modules["_random"]
    sys.modules["_random"] = pyrandom  # the port imports _random, which is this one
    port_py = load("random_port_py", LIB / "random.py")
    sys.modules["_random"] = saved
    assert port_c._random is not pyrandom and port_py._random is pyrandom

    gen = random.Random(20261015)
    seeds = [0, 1, -1, 2**32 - 1, 2**32, -2**32, 2**63 - 1, -2**63, True, False, 0.0, -0.0, 1.5,
             -2.25, 3.0, 1e300, -1e-300, math.inf, -math.inf]
    seeds += [gen.randrange(-2**63, 2**63) for i in range(count)]
    seeds += [gen.uniform(-1e9, 1e9) for i in range(count // 3)]
    failures = 0
    for seed in seeds:
        want = calls(random, seed)
        for port in (port_c, port_py):
            if calls(port, seed) != want:
                failures += 1
                print(f"{port.__name__}: seed {seed!r} differs")
    print(f"{2 * len(seeds)} seeded runs, {failures} differ")

    floats = [math.ldexp(gen.random(), gen.randrange(-1074, 1024)) * gen.choice([1, -1])
              for i in range(100 * count)]
    floats += [float(gen.randrange(-2**70, 2**70)) for i in range(30 * count)]
    hashes = sum(hash(f) != pyrandom._hash_float(f) for f in floats)
    print(f"{len(floats)} float hashes, {hashes} differ")

    lgamma = lgamma_port((LIB / "random.py").read_text(encoding="utf-8"))
    args = [float(i) for i in range(-20, 2000)] + [i / 8 for i in range(-400, 400)]
    args += [-1e20, 1e20, -1e300, 1e300, 2.0**63, -2.0**63, 0.49999999999999994,
             -2.5000000000000004]
    for i in range(200 * count):
        big = math.ldexp(gen.random(), gen.randrange(-70, 1024)) * gen.choice([1, -1])
        args.append(gen.choice([float(gen.randrange(1, 10**12)), gen.uniform(-100.0, 100.0), big]))
    gammas = sum(outcome(math.lgamma, x) != outcome(lgamma, x) for x in args)
    print(f"{len(args)} lgamma arguments, {gammas} differ")

    same = port_c.__all__ == random.__all__ and sorted(port_py.__all__) == sorted(random.__all__)
    print("__all__", "matches" if same else "differs")
    status = 1 if failures or hashes or gammas or not same else 0
    if options.upstream:
        status |= upstream(options.upstream)
    return status


if __name__ == "__main__":
    sys.exit(main())
