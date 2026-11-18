"""Field inference types each module constant once per guess, not once per path to it.

A chain A1 = A0 + A0, A2 = A1 + A1, ... reads each constant twice, so guessing the last one
re-guessed every earlier one 2**n times before guess() kept what it had typed (#1295).
Each count runs in a fresh process: compiling a program changes module-level state.
"""
import subprocess
import sys
import unittest

from compiler_state_probe import ROOT

COUNT = '''
import sys
sys.path.insert(0, sys.argv[1])
from src.pystachy_compiler.driver import compile_program
from src.pystachy_compiler.gen import Gen

n = int(sys.argv[2])
source = "A0 = 1\\n" + "".join(f"A{i} = A{i - 1} + A{i - 1}\\n" for i in range(1, n + 1))
source += f"\\n\\nclass Box:\\n    def __init__(self) -> None:\\n        self.x = A{n}\\n\\n\\nprint(Box().x)\\n"
calls = [0]
original = Gen.guess


def counted(self, e, f):
    calls[0] += 1
    return original(self, e, f)


Gen.guess = counted
compile_program("chain.py", source, [sys.argv[1] + "/lib"], "")
print(calls[0])
'''


def guesses(n):
    r = subprocess.run([sys.executable, "-c", COUNT, str(ROOT), str(n)], capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        raise AssertionError(r.stderr)
    return int(r.stdout.split()[-1])


class GuessBoundTests(unittest.TestCase):
    def test_shared_constants_are_guessed_once(self):
        small, large = guesses(8), guesses(16)
        # Eight more constants add a bounded number of guesses (an exponential count would
        # multiply by about 2**8 here).
        self.assertGreater(large, small)
        self.assertLessEqual(large - small, 8 * 8)


if __name__ == "__main__":
    unittest.main()
