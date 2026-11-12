"""A str local that appends build stays the local's own through calls that only read it.

An append (s += t) writes in place while only the local holds its str (Gen.str_append): every other
read of the local clears its owned flag first, as what reads the str may keep it, and the next
append then copies. len() and the methods of calls.STR_PEEKS return a number and keep nothing, so
their read leaves the flag alone, and a loop that appends and then tests what it built
(s.endswith("*/")) stays linear, as CPython's is. This test counts the stores that clear the flag
in the function's IR; tests/programs/strings/str_append_peeks.py compares the results with CPython.

Run with python3 -m unittest discover -s tools -p test_str_append_peeks.py.
"""
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.pystachy_compiler import driver  # noqa: E402
from src.pystachy_compiler.calls import STR_PEEKS  # noqa: E402

PROGRAM = """
def build(text: str) -> str:
    s = ""
    n = 0
    for c in text:
        s += c
        {use}
    return s + str(n)


print(build("ab"))
"""
# a call of each method, which leaves the local owned
PEEKS = {"startswith": 's.startswith("a", 1)', "endswith": 's.endswith(("a", "b"))', "find": 's.find("a", n)',
         "rfind": 's.rfind("a")', "index": 's.index("a")', "rindex": 's.rindex("a", 0, 9)', "count": 's.count("a")',
         "isdigit": "s.isdigit()", "isalpha": "s.isalpha()", "isalnum": "s.isalnum()", "isspace": "s.isspace()",
         "isupper": "s.isupper()", "islower": "s.islower()", "istitle": "s.istitle()", "isascii": "s.isascii()",
         "isdecimal": "s.isdecimal()", "isnumeric": "s.isnumeric()"}
# reads whose value may be the local's str, or that an argument's own read of the local makes
KEEPS = ["len(s.strip())", "len(s.upper())", "len(s[1:])", "ord(s[0])", "len(s.replace('a', 'b'))", "len(s.split())",
         "len([s])", "s.endswith(s)", "s.count(s[-1])", "s.find(c + s)", "int(s == c)", "int(c in s)", "hash(s)"]


class StrAppendPeekTests(unittest.TestCase):
    def clears(self, use):
        """How many stores clear the owned flag of build()'s s, where the loop runs `use`."""
        with tempfile.TemporaryDirectory() as tmp:
            ir = driver.compile_program("str_append_probe.py", PROGRAM.format(use=use), [tmp, str(ROOT / "lib")], "")
        body = re.search(r"^define [^\n]*@f\.build\(.*?^}", ir, re.S | re.M).group(0)
        self.assertEqual(len(re.findall(r"call ptr @pys_str_iadd\(", body)), 1, use)
        self.assertEqual(len(re.findall(r"store i64 1, ptr %s\.own\.", body)), 1, use)
        return len(re.findall(r"store i64 0, ptr %s\.own\.", body))

    def test_every_listed_method_has_a_call_here(self):
        self.assertEqual(sorted(PEEKS), sorted(STR_PEEKS))

    def test_reading_calls_leave_the_local_owned(self):
        plain = self.clears("pass")
        self.assertEqual(self.clears("n += len(s)"), plain)
        for method, call in PEEKS.items():
            with self.subTest(method=method):
                self.assertEqual(self.clears(f"n += int({call})"), plain)
                self.assertEqual(self.clears(f"if {call}:\n            break"), plain)

    def test_other_reads_give_the_str_up(self):
        plain = self.clears("pass")
        for use in KEEPS:
            with self.subTest(use=use):
                self.assertGreater(self.clears(f"n += int({use})"), plain)

    def test_only_an_owned_str_local_is_read_this_way(self):
        # an optional str has no owned flag, and a parameter that nothing appends to needs none
        for source in ("def f(s: str | None, t: str) -> bool:\n    s += t\n    return s.endswith(t)\n\n\nprint(f('a', 'b'))\n",
                       "def f(s: str, t: str) -> bool:\n    return s.endswith(t)\n\n\nprint(f('a', 'b'))\n"):
            with tempfile.TemporaryDirectory() as tmp:
                ir = driver.compile_program("str_append_probe.py", source, [tmp, str(ROOT / "lib")], "")
            self.assertNotIn(".own.", ir)


if __name__ == "__main__":
    unittest.main()
