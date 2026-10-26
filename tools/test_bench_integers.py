"""bench/integers: every variant of a workload computes CPython's checksum, at small sizes.

The runner times a workload only when its variants print one checksum; this checks the
programs themselves under CPython, without a compiler: NAME_i64.py directly, and
NAME_mpz.py with tools/rt_cpython's CPython-int oracle as its mpz module.
"""
import importlib.util
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / "bench" / "integers"
SPEC = importlib.util.spec_from_file_location("integers_run", BENCH / "run.py")
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)

# a size each program finishes in well under a second on CPython
SMALL = {"lcg32": "2000", "collatz": "2000", "cross64": "2000", "arith128": "2000",
         "factorial": "2", "fibadd": "2", "bigmul": "2", "dectext": "200", "modpow": "3",
         "containers": "2000"}
# run a program as __main__ with sys.argv [path, size], its mpz the CPython oracle
LAUNCH = ("import runpy, sys\n"
          "sys.path.insert(0, sys.argv[1])\n"
          "import mpz_oracle\n"
          "sys.modules['mpz'] = mpz_oracle\n"
          "sys.argv = sys.argv[2:]\n"
          "runpy.run_path(sys.argv[0], run_name='__main__')\n")


def checksum(path, size):
    out = subprocess.run([sys.executable, "-I", "-c", LAUNCH, str(ROOT / "tools" / "rt_cpython"), str(path), size],
                         capture_output=True, text=True, check=True, timeout=120).stdout.splitlines()
    float(out[-1])  # the timed loop's seconds
    return out[0]


class IntegerBenchmarks(unittest.TestCase):
    def test_files_match_workloads(self):
        self.assertEqual(sorted(SMALL), sorted(runner.WORKLOADS))
        expected = set()
        for name, (_, has_mpz, has_i64) in runner.WORKLOADS.items():
            expected.add(f"{name}.py")
            if has_mpz:
                expected.add(f"{name}_mpz.py")
            if has_i64:
                expected.add(f"{name}_i64.py")
        found = {p.name for p in BENCH.glob("*.py")} - {"run.py"}
        self.assertEqual(found, expected)

    def test_variants(self):
        self.assertEqual(runner.variants("lcg32", False), [("pys-i64", "_i64")])
        self.assertEqual(runner.variants("bigmul", True), [("pys-int", ""), ("pys-mpz", "_mpz")])

    def test_checksums_agree(self):
        for name in runner.WORKLOADS:
            with self.subTest(workload=name):
                ref = checksum(BENCH / f"{name}.py", SMALL[name])
                self.assertRegex(ref, r"^-?[0-9]+$")
                for _, suffix in runner.variants(name, False):
                    self.assertEqual(checksum(BENCH / f"{name}{suffix}.py", SMALL[name]), ref)


if __name__ == "__main__":
    unittest.main()
