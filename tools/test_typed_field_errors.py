"""Missing-field error paths must stay linear in a class hierarchy (#786)."""
from pathlib import Path
import re
import sys
from tempfile import TemporaryDirectory
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.pystachy_compiler.gen import Gen
from src.pystachy_compiler.loader import Loader


def hierarchy(n):
    # Inherited equality specializes for each receiver; its other argument remains Base.
    # The old error-name chains therefore grow quadratically, even for one source read.
    lines = ["class Base:", "    def __init__(self, ready: bool) -> None:"]
    lines += ["        if ready:", "            self.value = 7"]
    lines += ["    def __eq__(self, other: 'Base') -> bool:", "        return self.value == other.value"]
    for i in range(n):
        lines += [f"class C{i}(Base):", "    pass"]
    lines += ["def same(a: Base, b: Base) -> bool:", "    return a == b",
              f"print(same(C0(True), C{n - 1}(True)))", ""]
    return "\n".join(lines)


def compile_source(source):
    gen = Gen()
    return gen.program(Loader([]).program("field_errors.py", source)), gen


class FieldErrorTests(unittest.TestCase):
    def test_error_ir_scales_linearly_with_inherited_methods(self):
        small, _ = compile_source(hierarchy(8))
        large, _ = compile_source(hierarchy(16))
        self.assertLess(len(large.splitlines()), len(small.splitlines()) * 2.25)
        # Independent of constant numbering and table layout: a field read must not
        # select among a class's N subclass string constants at every specialization.
        self.assertLessEqual(len(re.findall(r"select i1 .*ptr @s\.", large)), 2)

    def test_exact_names_share_one_static_table_across_families(self):
        source = (Path(__file__).resolve().parent.parent / "tests/programs/classes/inheritance_field_errors.py").read_text()
        ir, gen = compile_source(source)
        tables = [d for d in gen.consts if d.kind == "fieldnames"]
        self.assertEqual(len(tables), 1)
        table = tables[0]
        literals = {d.name: d.text for d in gen.consts if d.kind == "string"}
        for cls in gen.classes.values():
            if cls.tag > 0:
                self.assertEqual(literals[table.refs[cls.tag]], cls.name)
        self.assertEqual(ir.count("@pys.field.names ="), 1)
        self.assertIn("@pys_exc_cls(", ir)
        self.assertNotIn("@pys.field.names", " ".join(gen.gcroots))

    def test_hierarchy_without_field_reads_needs_no_name_table(self):
        source = hierarchy(16).replace("return self.value == other.value", "return self is other")
        ir, _ = compile_source(source)
        self.assertNotIn("@pys.field.names", ir)

    def test_exact_class_missing_field_needs_no_table(self):
        source = """class Exact:
    def __init__(self, ready: bool) -> None:
        if ready:
            self.value = 7

def read(obj: Exact) -> int:
    return obj.value
print(read(Exact(True)))
"""
        ir, _ = compile_source(source)
        self.assertNotIn("@pys.field.names", ir)
        self.assertIn("'Exact' object has no attribute 'value'", ir)

    def test_template_specializations_do_not_change_class_tags(self):
        source = hierarchy(4) + """
class Box:
    def __init__(self, value):
        self.item = value
print(Box(3).item, Box("ok").item)
"""
        _, gen = compile_source(source)
        instances = [c for c in gen.classes.values() if c.origin]
        self.assertEqual(len(instances), 2)
        self.assertTrue(all(c.tag == 0 for c in instances))
        table = next(d for d in gen.consts if d.kind == "fieldnames")
        self.assertEqual(len(table.refs), 1 + max(c.tag for c in gen.classes.values()))

    def test_excluded_imported_classes_leave_unreused_tag_holes(self):
        with TemporaryDirectory() as tmp:
            (Path(tmp) / "family.py").write_text("""class Base:
    def __init__(self, ready: bool) -> None:
        if ready:
            self.value = 7
class Excluded(Base):
    def value(self) -> int:
        return 2
class ExcludedChild(Excluded):
    pass
class Child(Base):
    pass
""")
            source = """from family import Base, Child

def read(obj: Base) -> int:
    return obj.value
print(read(Child(True)))
"""
            gen = Gen()
            gen.program(Loader([tmp]).program("main.py", source))
        excluded = [c for c in gen.classes.values() if c.excluded]
        self.assertEqual(len(excluded), 2)
        self.assertTrue(all(c.tag == 0 for c in excluded))
        table = next(d for d in gen.consts if d.kind == "fieldnames")
        literals = {d.name: d.text for d in gen.consts if d.kind == "string"}
        base = gen.classes["family$Base"]
        child = gen.classes["family$Child"]
        self.assertGreater(child.tag, base.tag + 1)
        self.assertEqual(literals[table.refs[base.tag]], "Base")
        self.assertEqual(literals[table.refs[child.tag]], "Child")
        self.assertTrue(all(x == "null" for x in table.refs[base.tag + 1:child.tag]))

    def test_first_table_created_in_dry_run_is_retained(self):
        class ObservedGen(Gen):
            def __init__(self):
                super().__init__()
                self.created_dry = False

            def getfield(self, obj, ptr, name):
                before = self.fieldnames
                result = super().getfield(obj, ptr, name)
                if not before and self.fieldnames:
                    self.created_dry = self.drying > 0
                return result

        # Typing a None-initialized local probes the later field read with dry().
        source = """class Base:
    def __init__(self, ready: bool) -> None:
        if ready:
            self.value = 7
class Child(Base):
    pass

def read(obj: Base) -> int:
    value = None
    print(value)
    value = obj.value
    return value
print(read(Child(True)))
"""
        gen = ObservedGen()
        ir = gen.program(Loader([]).program("field_errors.py", source))
        self.assertTrue(gen.created_dry)
        self.assertTrue(gen.fieldnames)
        self.assertEqual(ir.count("@pys.field.names ="), 1)
        self.assertGreater(ir.count("ptr @pys.field.names,"), 0)

    def test_fresh_generators_emit_identical_ir(self):
        source = hierarchy(12)
        first, _ = compile_source(source)
        second, _ = compile_source(source)
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
