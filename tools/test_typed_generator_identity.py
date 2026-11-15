"""Numeric generator promises preserve raw values and nullable identities."""
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
import re
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.pystachy_compiler import gen as gen_module
from src.pystachy_compiler.gen import Gen
from src.pystachy_compiler.ir import Val
from src.pystachy_compiler.loader import Loader


def program(kind="float", protocol=False, promoting=False, tracking=True):
    comments = "# pystachy: dynamic-any\n" if tracking else ""
    if promoting:
        comments += "# pystachy: python-int\n"
    delta = "1.0" if kind == "float" else "1"
    text = "1.25" if kind == "float" else "18446744073709551617" if promoting else "1000"
    resume = "values.send(None)" if protocol else "next(values)"
    return comments + f'''from typing import Iterator

def numbers(value: {kind}) -> Iterator[{kind}]:
    yield value + {delta}
    yield value

values = numbers({kind}("{text}"))
print(next(values))
print({resume})
'''


def compile_generator(source, inspect=None):
    captured = {}
    lower = Gen.lower

    def capture(gen, fn):
        if fn.f.name == "numbers":
            gen.verify(fn, False)
            yields = [(block, item, index) for block in fn.blocks
                      for index, item in enumerate(block.code) if item.op == "gen.yield"]
            if inspect is not None:
                inspect(gen, fn, yields)
            captured["yields"] = [item for _, item, _ in yields]
            begin = len(gen.out)
            lower(gen, fn)
            captured["llvm"] = "\n".join(gen.out[begin:])
        else:
            lower(gen, fn)

    with patch.object(Gen, "lower", capture):
        Gen().program(Loader([]).program("generator_identity_probe.py", source))
    if "yields" not in captured:
        raise AssertionError("the numeric generator was not compiled")
    return captured


class GeneratorIdentityLayoutTests(unittest.TestCase):
    def test_tracking_frames_append_one_scanned_identity_word(self):
        for kind, protocol, promoting, slots, offset in [
            ("float", False, False, 6, 5),
            ("float", True, False, 8, 7),
            ("float", False, True, 10, 9),
            ("int", False, True, 10, 9),
            ("int", True, True, 10, 9),
        ]:
            with self.subTest(kind=kind, protocol=protocol, promoting=promoting):
                result = compile_generator(program(kind, protocol, promoting))
                llvm = result["llvm"]
                self.assertIn(f"%coro.promise = alloca [{slots} x i64]", llvm)
                self.assertIn(f"store [{slots} x i64] zeroinitializer, ptr %coro.promise", llvm)
                self.assertEqual(len(result["yields"]), 2)
                self.assertEqual(len(re.findall(
                    rf"\.identity = getelementptr i64, ptr %coro.promise, i64 {offset}\b", llvm)), 2)
                for index in re.findall(r"getelementptr i64, ptr %coro.promise, i64 (\d+)", llvm):
                    self.assertLess(int(index), slots, llvm)
                if kind == "float":
                    self.assertNotRegex(llvm, r"\.hi = getelementptr i64, ptr %coro.promise")
                else:
                    self.assertIn(".hi = getelementptr i64, ptr %coro.promise, i64 7", llvm)

    def test_fresh_yield_is_null_and_existing_source_has_a_box(self):
        for kind, promoting in [("float", False), ("int", False), ("int", True)]:
            with self.subTest(kind=kind, promoting=promoting):
                fresh, alias = compile_generator(program(kind, promoting=promoting))["yields"]
                self.assertEqual([value.t for value in fresh.a], ["%slot", "%ptr", "dyn"])
                self.assertEqual(fresh.a[2].v, "null")
                self.assertEqual(alias.a[2].t, "dyn")
                self.assertNotEqual(alias.a[2].v, "null")
                if not promoting:
                    self.assertEqual(fresh.a[1].v, "null")
                    self.assertEqual(alias.a[1].v, "null")

    def test_fresh_numeric_producer_has_no_per_yield_boxing(self):
        source = program().replace("    yield value\n", "    yield value + 2.0\n")
        plain = compile_generator(source)
        self.assertNotRegex(plain["llvm"], r"@pys_dyn_(?:float|int)(?:_box)?\(")
        self.assertTrue(all(item.a[2].v == "null" for item in plain["yields"]))

        original = gen_module.generators_gen_slots

        def eager(generator, value, channel):
            slots = original(generator, value, channel)
            if slots[2] != "":
                slots[2] = generator.dyn_id_box(value).v
            return slots

        # Restoring eager boxing must be visible in the actual producer body.
        with patch.object(gen_module, "generators_gen_slots", eager):
            regressed = compile_generator(source)
        self.assertRegex(regressed["llvm"], r"@pys_dyn_float\(")

    def test_nontracking_frames_keep_their_existing_layout(self):
        for protocol, promoting, slots in [(False, False, 5), (True, False, 7),
                                            (False, True, 9)]:
            with self.subTest(protocol=protocol, promoting=promoting):
                result = compile_generator(program("int", protocol, promoting, tracking=False))
                self.assertIn(f"%coro.promise = alloca [{slots} x i64]", result["llvm"])
                self.assertNotIn(".identity =", result["llvm"])
                self.assertTrue(all(len(item.a) == (2 if promoting else 1)
                                    for item in result["yields"]))


class GeneratorIdentityVerifierTests(unittest.TestCase):
    def reject_mutation(self, mutation, *, source=None, message="gen.yield needs"):
        checked = []

        def inspect(gen, fn, yields):
            block, item, index = yields[0]
            original = item.a
            try:
                item.a = [Val(value.v, value.t) for value in original]
                mutation(item)
                error = StringIO()
                with redirect_stderr(error), self.assertRaises(SystemExit):
                    gen.verify_gen(fn, block, item, index)
                self.assertIn(message, error.getvalue())
                checked.append(True)
            finally:
                item.a = original

        compile_generator(program() if source is None else source, inspect)
        self.assertEqual(checked, [True])

    def test_missing_identity_operand_is_rejected(self):
        self.reject_mutation(lambda item: item.a.pop())

    def test_extra_identity_operand_is_rejected(self):
        self.reject_mutation(lambda item: item.a.append(Val("null", "dyn")))

    def test_identity_operand_must_have_box_type(self):
        self.reject_mutation(lambda item: setattr(item.a[2], "t", "%ptr"))

    def test_high_placeholder_must_have_pointer_type(self):
        self.reject_mutation(lambda item: setattr(item.a[1], "t", "dyn"))

    def test_nonnumeric_payload_slot_is_rejected(self):
        self.reject_mutation(lambda item: setattr(item.a[0], "t", "dyn"))

    def test_nonnull_high_placeholder_is_rejected_without_wide_int(self):
        for promoting in [False, True]:
            with self.subTest(promoting=promoting):
                self.reject_mutation(lambda item: setattr(item.a[1], "v", "%not_null"),
                                     source=program(promoting=promoting),
                                     message="needs a null high placeholder")

    def test_nontracking_yield_cannot_add_a_companion(self):
        def add_companion(item):
            item.a.extend([Val("null", "%ptr"), Val("null", "dyn")])

        self.reject_mutation(add_companion, source=program(tracking=False))


if __name__ == "__main__":
    unittest.main()
