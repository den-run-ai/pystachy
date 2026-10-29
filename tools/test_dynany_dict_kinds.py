"""Guard scalar dictionary specialization without weakening cross-key probe semantics."""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.pystachy_compiler import driver  # noqa: E402


class DictionaryKindsTests(unittest.TestCase):
    def compile(self, source):
        return driver.compile_program("dict_kinds_probe.py", source, [str(ROOT / "lib")], "")

    def kinds(self, ir):
        return re.findall(r"call ptr @pys_dict_new(?:_atomic)?\(i64 (\d+),", ir)

    def test_optin_strings_keep_compatible_immediate_kind(self):
        source = '''# pystachy: dynamic-any
from typing import Any
strings: dict[str, int] = {"a": 1}
bytes_keys: dict[bytes, int] = {b"a": 2}
values: dict[str, Any] = {"a": 3}
print(strings, bytes_keys, values)
'''
        ir = self.compile(source)
        self.assertEqual(self.kinds(ir), ["3", "3"])
        self.assertNotIn('c"!s\\00"', ir)
        self.assertIn('c"A\\00"', ir)  # dynamic values use the existing boxed dictionary layout

    def test_plain_strings_keep_native_kind(self):
        ir = self.compile('a = {"a": 1}\nb = {b"a": 2}\nprint(a, b)\n')
        self.assertEqual(self.kinds(ir), ["1", "1"])

    def test_other_dynamic_key_layouts_keep_descriptors(self):
        ir = self.compile('''# pystachy: dynamic-any
from typing import Any
ints = {1: 2}
tuples = {("a", 1): 3}
boxed: dict[Any, Any] = {"a": 4}
print(ints, tuples, boxed)
''')
        self.assertIn('c"!i\\00"', ir)
        self.assertIn('c"!T2si\\00"', ir)
        self.assertIn('c"A\\00"', ir)
        self.assertEqual(self.kinds(ir), [])


if __name__ == "__main__":
    unittest.main()
