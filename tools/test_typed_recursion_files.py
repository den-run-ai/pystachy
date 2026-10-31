"""Only explicitly rooted native files may relax the finalization safeguard."""
from unittest.mock import patch
import unittest

from test_typed_recursion import ROOT, compile_source, operations
from src.pystachy_compiler.gen import Gen


SCOPED = '''
def scalar(n: int) -> int:
    return n + 1

with open("scoped.txt", "w") as stream:
    stream.write(str(scalar(2)))
'''


class ScopedFileRecursionTests(unittest.TestCase):
    def test_scoped_open_keeps_unwind_roots_and_allows_scalar_leaf(self):
        ir, functions = compile_source(SCOPED)
        guarded, _ = compile_source(SCOPED, opt="-recursionleaf")
        self.assertNotEqual(ir, guarded)
        self.assertIn("@pys_unwind_file(", ir)
        self.assertIn("@pys_file_close(", ir)
        self.assertIn(("rt", "recursion.check"),
                      [op[:2] for op in operations(functions["@f.scalar"])])
        self.assertIn("define internal void @pys.recursion.check() {", ir)
        self.assertIn("define internal i64 @pys.recursion.enter() {", guarded)

    def test_unmanaged_open_in_other_function_preserves_guarded_ir(self):
        source = SCOPED + '''
def unmanaged() -> None:
    stream = open("unmanaged.txt", "w")
    stream.write("pending")

unmanaged()
'''
        ir, _ = compile_source(source)
        guarded, _ = compile_source(source, opt="-recursionleaf")
        self.assertEqual(ir, guarded)

    def test_suspended_with_file_preserves_guarded_ir(self):
        source = SCOPED + '''
from collections.abc import Iterator

def values() -> Iterator[int]:
    with open("generator.txt", "w") as stream:
        stream.write("pending")
        yield 1

values_iterator = values()
print(next(values_iterator))
values_iterator.close()
'''
        ir, _ = compile_source(source)
        guarded, _ = compile_source(source, opt="-recursionleaf")
        self.assertEqual(ir, guarded)

    def test_scoped_file_does_not_override_weakref_exclusion(self):
        source = SCOPED + '''
from _weakref import ref

class Item:
    def __init__(self, n: int) -> None:
        self.n = n

item = Item(1)
weak = ref(item)
print(weak() is item)
'''
        ir, _ = compile_source(source)
        guarded, _ = compile_source(source, opt="-recursionleaf")
        self.assertEqual(ir, guarded)

    def test_root_must_protect_the_exact_open_result(self):
        original = Gen.recursionleaf

        def broken_root(g):
            for fn in g.fns:
                for b in fn.blocks:
                    for i in b.code:
                        if i.op == "rt" and i.s == "unwind_file":
                            i.a[0].v = "null"
            return original(g)

        with patch.object(Gen, "recursionleaf", broken_root):
            _, functions = compile_source(SCOPED)
        self.assertIn(("rt", "recursion.enter"),
                      [op[:2] for op in operations(functions["@f.scalar"])])

    def test_native_fixture_uses_only_scoped_opens(self):
        source = (ROOT / "tests/programs/runtime/rt_recursion_scoped_files.py").read_text()
        _, functions = compile_source(source)
        self.assertIn(("rt", "recursion.check"),
                      [op[:2] for op in operations(functions["@f.scalar"])])


if __name__ == "__main__":
    unittest.main()
