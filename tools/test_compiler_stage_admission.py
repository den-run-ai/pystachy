"""The retained typed-program boundary admits the same module as full compilation."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
STAGES = ["prepare", "discover", "analyze", "optimize", "finalize", "lower"]
WORKER = r'''
import json
from pathlib import Path
import sys
from unittest.mock import patch
from src.pystachy_compiler import diagnostics, driver
from src.pystachy_compiler.gen import Gen

sys.setrecursionlimit(diagnostics.MAXNEST * 40)
path = Path(sys.argv[1])
mode, stop = sys.argv[2:]
source = path.read_text(encoding=diagnostics.RAW)
diagnostics.SRC = str(path)
attempts = []
original = Gen.program

def forbidden(*args, **kwargs):
    raise AssertionError('typed module admission entered LLVM lowering')

def program(gen, modules):
    attempts.append(gen)
    if stop == 'full':
        return original(gen, modules)
    with patch.object(Gen, 'lower', forbidden), patch.object(Gen, 'lower_module', forbidden):
        gen.typed_program(modules)
    assert gen.pipeline.stage == 'finalize'
    assert gen.pipeline.active == ''
    assert any(fn.blocks for fn in gen.fns), 'finalization consumed function bodies'
    if stop == 'staged':
        return gen.lower_program()
    return ''

with patch.object(Gen, 'program', program):
    try:
        if mode == 'runtime':
            result = driver.runtime_ir(str(path), source, False)
        else:
            ext = path.stem if mode == 'extension' else ''
            result = driver.compile_program(str(path), source,
                                            [str(path.parent), str(Path.cwd() / 'lib')], ext)
    except SystemExit:
        if stop == 'rejected-finalize':
            gen = attempts[-1]
            assert (gen.pipeline.stage, gen.pipeline.active) == ('optimize', 'finalize')
            assert any(fn.blocks for fn in gen.fns), 'admission consumed function bodies'
        raise
if stop in ('typed', 'rejected-finalize'):
    print(json.dumps([{'stage': g.pipeline.stage, 'active': g.pipeline.active,
                      'history': g.pipeline.history} for g in attempts]))
else:
    print(result, end='')
'''


class CompilerStageAdmissionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.env = {key: value for key, value in os.environ.items()
                    if not key.startswith("PYSTACHY_")}
        self.env.update(PYSTACHY_HOME=str(ROOT), PYSTACHY_IRCHECK="1")

    def source(self, text):
        path = self.directory / "probe.py"
        path.write_text(text, encoding="utf-8")
        return path

    def compile(self, path, mode, stop, options=None):
        return subprocess.run([sys.executable, "-c", WORKER, str(path), mode, stop],
                              cwd=ROOT, env=dict(self.env, **(options or {})),
                              text=True, capture_output=True, timeout=45)

    def test_existing_extension_rejections_happen_before_lowering(self):
        # Read the checked-in diagnostic rather than deriving the expected message
        # from this revision's backend. Each case compiles in a fresh interpreter.
        for name in ("ext_pub", "ext_def", "ext_untyped", "ext_ret", "ext_cls",
                     "ext_singleton", "ext_var"):
            with self.subTest(case=name):
                path = Path("tests/ffi/errors") / (name + ".py")
                expected = (ROOT / path).read_text().splitlines()[0].removeprefix("# error: ") + "\n"
                ordinary = self.compile(path, "extension", "full")
                typed = self.compile(path, "extension", "rejected-finalize")
                self.assertEqual((ordinary.returncode, ordinary.stderr), (1, expected))
                self.assertEqual((typed.returncode, typed.stderr), (1, expected))
                self.assertEqual(typed.stdout, "")

    def test_extension_rejection_priority_is_preserved(self):
        cases = [
            ("def visible(value: int) -> int:\n    return value\n"
             "class Public:\n    pass\nlimit = 1\n", "visible() is public"),
            ("from ffi import export\n@export\ndef visible(value: int) -> int:\n    return value\n"
             "class Public:\n    pass\nlimit = 1\n", "class Public is public"),
        ]
        for source, fragment in cases:
            with self.subTest(first_error=fragment):
                path = self.source(source)
                ordinary = self.compile(path, "extension", "full")
                typed = self.compile(path, "extension", "rejected-finalize")
                self.assertEqual(ordinary.returncode, 1, ordinary.stderr)
                self.assertIn(fragment, ordinary.stderr)
                self.assertEqual((typed.returncode, typed.stderr),
                                 (ordinary.returncode, ordinary.stderr))

    def test_extension_discovery_failure_still_precedes_export_admission(self):
        path = self.source("def visible(value: int) -> int:\n    return unknown\n")
        ordinary = self.compile(path, "extension", "full")
        typed = self.compile(path, "extension", "typed")
        self.assertEqual(ordinary.returncode, 1, ordinary.stderr)
        self.assertIn("unknown", ordinary.stderr)
        self.assertNotIn("not @export", ordinary.stderr)
        self.assertEqual((typed.returncode, typed.stderr),
                         (ordinary.returncode, ordinary.stderr))

    def test_extension_and_runtime_stages_preserve_exact_llvm(self):
        sources = {
            "extension": "from ffi import export\n_private = 4\nclass _Hidden(Exception):\n    pass\n"
                         "@export\ndef value(number: int) -> int:\n    if number < 0:\n"
                         "        raise _Hidden('negative')\n    return number + _private\n",
            "runtime": "def probe(number: int) -> int:\n    return number + 1\n",
        }
        for mode, source in sources.items():
            path = self.source(source)
            for options in ({}, {"PYSTACHY_OPT": "-all"}):
                with self.subTest(mode=mode, options=options):
                    ordinary = self.compile(path, mode, "full", options)
                    staged = self.compile(path, mode, "staged", options)
                    typed = self.compile(path, mode, "typed", options)
                    for result in (ordinary, staged, typed):
                        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertEqual((staged.stdout, staged.stderr),
                                     (ordinary.stdout, ordinary.stderr))
                    self.assertEqual(json.loads(typed.stdout)[-1],
                                     {"stage": "finalize", "active": "", "history": STAGES[:-1]})

    def test_runtime_source_rejection_preserves_early_diagnostic(self):
        path = self.source("class Unsupported:\n    pass\n")
        ordinary = self.compile(path, "runtime", "full")
        typed = self.compile(path, "runtime", "typed")
        self.assertEqual(ordinary.returncode, 1, ordinary.stderr)
        self.assertIn("runtime.py may hold only functions", ordinary.stderr)
        self.assertEqual((typed.returncode, typed.stderr),
                         (ordinary.returncode, ordinary.stderr))

    def test_extension_retry_retains_only_the_final_attempt(self):
        path = self.source("from ffi import export\n_total = 0\n"
                           "def _add(value: float) -> None:\n    global _total\n    _total += value\n"
                           "_add(1.5)\n@export\ndef result() -> float:\n    return float(_total)\n")
        ordinary = self.compile(path, "extension", "full")
        staged = self.compile(path, "extension", "staged")
        typed = self.compile(path, "extension", "typed")
        for result in (ordinary, staged, typed):
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((staged.stdout, staged.stderr), (ordinary.stdout, ordinary.stderr))
        attempts = json.loads(typed.stdout)
        self.assertEqual(len(attempts), 2)
        self.assertEqual(attempts[0], {"stage": "prepare", "active": "discover", "history": ["prepare"]})
        self.assertEqual(attempts[1], {"stage": "finalize", "active": "", "history": STAGES[:-1]})

    def test_runtime_class_invariant_is_checked_before_retention(self):
        # Ordinary runtime source already rejects classes during preparation.
        # Simulate a later pass introducing one to exercise the retained-module
        # invariant independently of that parser/frontend admission check.
        path = self.source("def probe(value: int) -> int:\n    return value\n")
        injection = '''
from src.pystachy_compiler.symbols import ClassInfo
from src.pystachy_compiler.syntax import Node
optimize = Gen.optimize_program
def bad_optimization(gen):
    optimize(gen)
    gen.classes['Injected'] = ClassInfo('Injected', Node('class', 'Injected', 1))
Gen.optimize_program = bad_optimization
'''
        worker = WORKER.replace("with patch.object(Gen, 'program', program):",
                                injection + "\nwith patch.object(Gen, 'program', program):")
        result = subprocess.run([sys.executable, "-c", worker, str(path), "runtime", "rejected-finalize"],
                                cwd=ROOT, env=self.env, text=True, capture_output=True, timeout=45)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("runtime.py may not define classes (Injected)", result.stderr)
        self.assertNotIn("AssertionError", result.stderr)

    def test_ordinary_program_does_not_inherit_extension_restrictions(self):
        path = self.source("class Public:\n    pass\nlimit = 2\n"
                           "def visible(value: int) -> int:\n    return value + limit\nprint(visible(3))\n")
        ordinary = self.compile(path, "program", "full")
        staged = self.compile(path, "program", "staged")
        self.assertEqual(ordinary.returncode, 0, ordinary.stderr)
        self.assertEqual((staged.returncode, staged.stdout, staged.stderr),
                         (ordinary.returncode, ordinary.stdout, ordinary.stderr))


if __name__ == "__main__":
    unittest.main()
