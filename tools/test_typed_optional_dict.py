"""Private dictionary optionals must not allocate or change observable boxes."""
from pathlib import Path
import os
import re
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.pystachy_compiler import diagnostics
from src.pystachy_compiler.gen import Gen
from src.pystachy_compiler.loader import Loader


def compile_body(source, options=""):
    with patch.dict(os.environ, {"PYSTACHY_IRCHECK": "1", "PYSTACHY_OPT": options}), \
            patch.object(diagnostics, "SRC", "optional_dict.py"), \
            patch.object(diagnostics, "FILES", []):
        ir = Gen().program(Loader([]).program("optional_dict.py", source))
    match = re.search(r"^define internal [^\n]* @f\.read(?:\.\d+)?\([^\n]*\n.*?^\}", ir, re.S | re.M)
    if match is None:
        raise AssertionError("read function was not compiled")
    return match.group(0)


def program(body, item="int", prefix="", caller="print(read({'a': 5}, 'a'))"):
    return prefix + f"\ndef read(d: dict[str, {item}], key: str):\n" + "\n".join(
        "    " + line for line in body.splitlines()) + "\n" + caller + "\n"


class OptionalDictSlotsTests(unittest.TestCase):
    def test_private_scalar_reads_use_one_lookup_and_no_box(self):
        for item, literal in (("int", "5"), ("float", "0.0"), ("bool", "False")):
            with self.subTest(item=item):
                body = compile_body(program("x = d.get(key)\nif x is None:\n    return 0\nreturn int(x)",
                                            item, caller=f"print(read({{'a': {literal}}}, 'a'))"))
                self.assertEqual(body.count("call i64 @pys_dict_find("), 1)
                self.assertEqual(body.count("call i64 @pys_dict_val_or_zero("), 1)
                self.assertNotIn("call i64 @pys_dict_getbox(", body)

    def test_optimizer_off_retains_boxed_negative_control(self):
        body = compile_body(program("x = d.get(key)\nif x is None:\n    return 0\nreturn x + 1"), "-unionslots")
        self.assertIn("call i64 @pys_dict_getbox(", body)
        self.assertNotIn("@pys_dict_val_or_zero", body)

    def test_escaped_optional_return_stays_boxed(self):
        body = compile_body(program("x = d.get(key)\nreturn x"))
        self.assertIn("@pys_dict_getbox", body)

    def test_optional_copy_stays_boxed(self):
        body = compile_body(program("x = d.get(key)\ny = x\nif y is None:\n    return 0\nreturn y + 1"))
        self.assertIn("@pys_dict_getbox", body)

    def test_optional_argument_stays_boxed(self):
        body = compile_body(program("x = d.get(key)\nreturn consume(x)", prefix="def consume(x: int | None) -> int:\n    print(x)\n    return 0\n"))
        self.assertIn("@pys_dict_getbox", body)
        self.assertNotIn("@pys_dict_val_or_zero", body)

    def test_optional_default_stays_boxed(self):
        body = compile_body(program("default: int | None = 7\nx = d.get(key, default)\nif x is None:\n    return 0\nreturn x + 1"))
        self.assertIn("@pys_dict_getbox", body)

    def test_phi_producer_stays_boxed(self):
        body = compile_body(program("x = d.get(key) if len(key) > 0 else None\nif x is None:\n    return 0\nreturn x + 1"))
        self.assertIn("@pys_dict_getbox", body)

    def test_promoting_int_program_stays_boxed(self):
        body = compile_body(program("x = d.get(key)\nif x is None:\n    return 0\nreturn x + 1", prefix="# pystachy: python-int\n").replace("key: str):", "key: str) -> int:"))
        self.assertNotIn("@pys_dict_val_or_zero", body)

    def test_dynamic_program_stays_boxed(self):
        body = compile_body(program("x = d.get(key)\nif x is None:\n    return 0\nreturn x + 1", prefix="# pystachy: dynamic-any\n"))
        self.assertNotIn("@pys_dict_val_or_zero", body)


if __name__ == "__main__":
    unittest.main()
