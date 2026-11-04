"""Generic requests own temporary context; abandoned semantic state needs a fresh Gen."""
from contextlib import redirect_stderr
import io
import inspect
import textwrap
import unittest
from unittest.mock import patch

from compiler_state_probe import ROOT
from src.pystachy_compiler import declarations, diagnostics, driver, loader, templates
from src.pystachy_compiler.diagnostics import Rejoin
from src.pystachy_compiler.gen import Gen
from src.pystachy_compiler.specs import GLUE, SPECSHOW
from src.pystachy_compiler.syntax import LAMBDAS


RECURSIVE = '''\
from typing import Generic, TypeVar
T = TypeVar("T")
class Node(Generic[T]):
    def __init__(self, value: T) -> None:
        self.next: Node[T] | None = None
        self.value = value
n: Node[str] = Node("first")
print(n.value)
'''
NESTED = '''\
from typing import Generic, TypeVar
T = TypeVar("T")
class Box(Generic[T]):
    def __init__(self, value: T) -> None:
        self.value = value
class Holder(Generic[T]):
    def __init__(self, value: T) -> None:
        self.box = Box(value)
h = Holder(1)
print(h.box.value)
'''


class GenericStateTests(unittest.TestCase):
    def setUp(self):
        self.roots = [diagnostics.FILES, diagnostics.DYNFILES, diagnostics.IDINERT,
                      diagnostics.INTFILES, diagnostics.INTSPANS, diagnostics.CAPTURED,
                      LAMBDAS, driver.RENAMED, driver.LIBS, driver.LINKDL,
                      GLUE, SPECSHOW, loader.ENUMCLASSES]
        self.saved = [root.copy() for root in self.roots]
        self.observer = diagnostics.SRC, diagnostics.CAPTURE, diagnostics.PHASE
        diagnostics.SRC = "generics.py"
        diagnostics.CAPTURE = True
        diagnostics.PHASE = "generic-state-test"
        diagnostics.CAPTURED.clear()

    def tearDown(self):
        for root, saved in zip(self.roots, self.saved, strict=True):
            root.clear()
            if isinstance(root, list):
                root.extend(saved)
            else:
                root.update(saved)
        diagnostics.SRC, diagnostics.CAPTURE, diagnostics.PHASE = self.observer

    def compile(self, source):
        generations = []
        original = Gen.program
        messages = io.StringIO()

        def observed(generator, modules):
            generations.append(generator)
            return original(generator, modules)

        with patch.object(Gen, "program", observed), redirect_stderr(messages):
            try:
                ir = driver.compile_program("generics.py", textwrap.dedent(source),
                                            [str(ROOT / "lib")], "")
                status = 0
            except SystemExit as error:
                ir, status = "", error.code
        return status, ir, messages.getvalue(), generations

    @staticmethod
    def scope(generator):
        return (generator.selfcls, generator.line, generator.lib,
                list(generator.making), dict(generator.specing))

    def test_recursive_annotation_and_call_share_one_layout(self):
        status, _, messages, generations = self.compile(RECURSIVE)
        self.assertEqual(status, 0, messages)
        generator = generations[-1]
        instances = [cls for cls in generator.classes.values() if cls.origin == "Node"]
        self.assertEqual(len(instances), 1)
        cls = instances[0]
        self.assertEqual(cls.tvars, {"T": "str"})
        # Class references already admit None; use the shared optional-type API.
        self.assertEqual(cls.ftypes["next"], generator.optional(cls.name))
        self.assertEqual(generator.specing, {})
        self.assertEqual(set(generator.specdone.values()), {cls.name})
        self.assertEqual(diagnostics.CAPTURED, [])

    def test_same_binding_does_not_merge_different_native_layouts(self):
        source = '''\
        from typing import Generic, TypeVar
        T = TypeVar("T")
        class Mixed(Generic[T]):
            def __init__(self, value: T, other):
                self.value = value
                self.other = other
        a = Mixed(1, 2)
        b = Mixed(1, "two")
        print(a.value, a.other, b.value, b.other)
        '''
        status, _, messages, generations = self.compile(source)
        self.assertEqual(status, 0, messages)
        instances = [cls for cls in generations[-1].classes.values() if cls.origin == "Mixed"]
        self.assertEqual(len(instances), 2)
        self.assertEqual([cls.tvars for cls in instances], [{"T": "int"}] * 2)
        self.assertEqual({cls.ftypes["other"] for cls in instances}, {"int", "str"})
        self.assertNotEqual(instances[0].name, instances[1].name)

    def test_dormant_template_and_unselected_branch_stay_lazy(self):
        source = '''\
        from typing import Generic, TypeVar
        T = TypeVar("T")
        class Dormant(Generic[T]):
            def __init__(self, value: T):
                self.value = unsupported_name
        class Box(Generic[T]):
            def __init__(self, value: T):
                if isinstance(value, int):
                    self.value = value
                else:
                    self.value = unsupported_name
        b = Box(1)
        print(b.value)
        '''
        status, _, messages, generations = self.compile(source)
        self.assertEqual(status, 0, messages)
        self.assertFalse(any(cls.origin == "Dormant" for cls in generations[-1].classes.values()))
        self.assertEqual(diagnostics.CAPTURED, [])

    def test_failed_then_valid_requests_preserve_observer_diagnostics(self):
        expected = self.compile(RECURSIVE)[:3]
        self.assertEqual(expected[0], 0, expected[2])
        failed = NESTED.replace("self.value = value", "self.value = unknown_name")
        first = self.compile(failed)
        self.assertEqual(first[0], 1)
        self.assertEqual(len(diagnostics.CAPTURED), 1)
        diagnostic = diagnostics.CAPTURED[0]
        context = list(diagnostic.context)
        self.assertTrue(any("specializing Box" in note for note in context))
        self.assertTrue(any("specializing Holder" in note for note in context))
        for source in (RECURSIVE, "# pystachy: dynamic-any\n" + RECURSIVE,
                       "# pystachy: python-int\n" + RECURSIVE, RECURSIVE):
            status, _, messages, _ = self.compile(source)
            self.assertEqual(status, 0, messages)
            self.assertEqual(diagnostics.CAPTURED, [diagnostic])
            self.assertEqual(diagnostic.context, context)
        self.assertEqual(self.compile(RECURSIVE)[:3], expected)
        self.assertEqual(self.compile(failed)[:3], first[:3])
        self.assertEqual(len(diagnostics.CAPTURED), 2)
        self.assertEqual(diagnostics.CAPTURED[1].context, context)

    def specialization_failure(self, terminal):
        # Fail within a real nested field scan. Temporary specialization state
        # unwinds; partial classes/functions are deliberately not reused.
        original_scan = Gen.scan_fields
        original_specialize = Gen.specialize
        calls = []
        failures = []

        def checked(generator, *args):
            before = self.scope(generator)
            try:
                return original_specialize(generator, *args)
            finally:
                after = self.scope(generator)
                calls.append((before, after))
                self.assertEqual(after, before)

        def interrupted(generator, cls, function, statements, locals_):
            if cls.origin == "Box" and not failures:
                failures.append(generator)
                self.assertIn(cls.name, generator.specing.values())
                active_origins = {generator.classes[name].origin
                                  for name in generator.specing.values()}
                self.assertEqual(active_origins, {"Holder", "Box"})
                # A nested operation can fail with a borrowed source/library
                # context; exercise restoring both values as well as the stack.
                generator.line = statements[0].line
                generator.lib = not generator.lib
                if terminal:
                    generator.err("injected generic field failure")
                raise Rejoin()
            return original_scan(generator, cls, function, statements, locals_)

        with patch.object(Gen, "specialize", checked), patch.object(Gen, "scan_fields", interrupted):
            result = self.compile(NESTED)
        self.assertTrue(calls)
        self.assertEqual(len(failures), 1)
        self.assertEqual(failures[0].specing, {})
        return result

    def test_nested_rejoin_discards_semantic_state_and_restores_context(self):
        expected = self.compile(NESTED)[:3]
        self.assertEqual(expected[0], 0, expected[2])
        sentinel = diagnostics.Diagnostic("observer retained record", 0, [])
        diagnostics.CAPTURED.append(sentinel)
        status, ir, messages, generations = self.specialization_failure(False)
        self.assertEqual((status, ir, messages), expected)
        self.assertEqual(len(generations), 2)
        self.assertIsNot(generations[0], generations[1])
        self.assertIsNot(generations[0].classes, generations[1].classes)
        self.assertIsNot(generations[0].specdone, generations[1].specdone)
        self.assertEqual(diagnostics.CAPTURED, [sentinel])

    def test_terminal_failure_restores_context_after_diagnostic_capture(self):
        status, _, messages, generations = self.specialization_failure(True)
        self.assertEqual(status, 1)
        self.assertIn("injected generic field failure", messages)
        self.assertEqual(len(generations), 1)
        self.assertEqual(len(diagnostics.CAPTURED), 1)
        diagnostic = diagnostics.CAPTURED[0]
        self.assertEqual(diagnostic.phase, "generic-state-test")
        self.assertEqual(len(diagnostic.context), 2)
        self.assertIn("specializing Holder", diagnostic.context[0])
        self.assertIn("specializing Box", diagnostic.context[1])
        self.assertEqual(generations[0].specing, {})
        # The repair enters through the driver and gets a fresh compilation.
        self.assertEqual(self.compile(NESTED)[0], 0)
        self.assertEqual(diagnostics.CAPTURED, [diagnostic])

    def declaration_failure(self, source, terminal):
        original_fields, original_declare = Gen.class_fields, Gen.declare_fields
        failures = []

        def checked(generator, cls):
            if cls.name != "Stack" or cls.fields_ready or cls.fields_preparing:
                return original_declare(generator, cls)
            before = generator.line, generator.selfcls
            try:
                original_declare(generator, cls)
            except (Rejoin, SystemExit):
                self.assertFalse(cls.fields_ready)
                raise
            else:
                self.assertTrue(cls.fields_ready)
            finally:
                self.assertFalse(cls.fields_preparing)
                self.assertEqual((generator.line, generator.selfcls), before)

        def interrupted(generator, cls):
            if cls.name != "Stack":
                return original_fields(generator, cls)
            self.assertTrue(cls.fields_preparing)
            self.assertFalse(cls.fields_ready)
            self.assertEqual(generator.selfcls, "Stack")
            original_fields(generator, cls)
            if not failures:
                failures.append(cls)
                if terminal:
                    generator.err("injected declaration failure")
                raise Rejoin()

        with patch.object(Gen, "declare_fields", checked), patch.object(Gen, "class_fields", interrupted):
            result = self.compile(source)
        self.assertEqual(len(failures), 1)
        self.assertFalse(failures[0].fields_ready)
        self.assertFalse(failures[0].fields_preparing)
        return result

    def test_declaration_readiness_and_context_survive_failure(self):
        source = (ROOT / "tests/programs/generics/generic_declaration_ready.py").read_text()
        expected = self.compile(source)[:3]
        self.assertEqual(expected[0], 0, expected[2])
        diagnostics.CAPTURED.append(diagnostics.Diagnostic("observer retained record", 0, []))
        for terminal in (False, True):
            with self.subTest(terminal=terminal):
                retained = list(diagnostics.CAPTURED)
                status, ir, messages, generations = self.declaration_failure(source, terminal)
                self.assertEqual(status, int(terminal), messages)
                self.assertEqual(len(generations), 1 if terminal else 2)
                self.assertEqual(diagnostics.CAPTURED[:len(retained)], retained)
                self.assertEqual(len(diagnostics.CAPTURED), len(retained) + int(terminal))
                if terminal:
                    self.assertEqual(diagnostics.CAPTURED[-1].message, "injected declaration failure")
                else:
                    self.assertEqual((status, ir, messages), expected)
                    self.assertTrue(generations[-1].classes["Stack"].fields_ready)
                self.assertEqual(self.compile(source)[:3], expected)

    def test_missing_declaration_scope_or_early_readiness_is_detected(self):
        source = (ROOT / "tests/programs/generics/generic_declaration_ready.py").read_text()
        mutations = (
            ('ci.fields_preparing = False', 'pass'),
            ('self.line, self.selfcls = line, cls', 'self.line = line'),
            ('self.line, self.selfcls = line, cls', 'self.selfcls = cls'),
            ('self.class_fields(ci)\n        ci.fields_ready = True',
             'ci.fields_ready = True\n        self.class_fields(ci)'),
        )
        for before, after in mutations:
            for terminal in (False, True):
                with self.subTest(mutation=after, terminal=terminal):
                    mutant = self.mutated_method(declarations, "gen_declare_fields", before, after)
                    with patch.object(Gen, "declare_fields", mutant), self.assertRaises(AssertionError):
                        self.declaration_failure(source, terminal)

    def mutated_method(self, module, name, before, after):
        source = inspect.getsource(getattr(module, name))
        self.assertEqual(source.count(before), 1)
        namespace = dict(vars(module))
        exec(compile(source.replace(before, after), "<generic-state-mutant>", "exec"), namespace)
        return namespace[name]

    def test_missing_or_inexact_scope_restoration_is_detected(self):
        mutations = (
            ('self.specing.pop(request, "")', 'pass'),
            ('self.specing.pop(request, "")', 'self.specing.clear()'),
            ('self.specing.pop(request, "")', 'self.specing.pop(doing, "")'),
            ('self.selfcls = sel', 'pass'),
            ('self.line = line\n        self.lib = lib', 'self.lib = lib'),
            ('self.lib = lib', 'pass'),
            ('while len(self.making) > depth:\n            self.making.pop()', 'pass'),
        )
        for before, after in mutations:
            for terminal in (False, True):
                with self.subTest(mutation=before, replacement=after, terminal=terminal):
                    mutant = self.mutated_method(templates, "gen_specialize", before, after)
                    with patch.object(Gen, "specialize", mutant), self.assertRaises(AssertionError):
                        self.specialization_failure(terminal)

    def test_missing_canonical_reservation_is_detected(self):
        mutant = self.mutated_method(templates, "gen_specialize",
            'if c in self.tparams and t.fields_ready and self.template_instances == instances:', 'if False:')
        with patch.object(Gen, "specialize", mutant):
            status, _, messages, _ = self.compile(RECURSIVE)
        self.assertEqual(status, 1)
        self.assertIn("expected Node[str], got Node[str]", messages)


if __name__ == "__main__":
    unittest.main()
