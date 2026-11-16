"""Public stage boundaries, consumed IR and fresh-attempt failure isolation."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parent.parent
STAGES = ["prepare", "discover", "analyze", "optimize", "finalize", "lower"]
SOURCE = """def total(values: list[int]) -> int:
    result = 0
    for value in values:
        result += value
    return result

def first(values: list[int]) -> int:
    try:
        return values[0]
    except IndexError:
        return -1

print(total([1, 2, 3]), first([]))
"""
TEMPLATES = """class Box:
    def __init__(self, v):
        self.v = v


def twice(x):
    return x + x


print(Box(1).v, twice(2))
"""
RETRY = """total = 0
def add(value: float) -> None:
    global total
    total += value
add(1.5)
print(total)
"""

# All real compiles run in fresh interpreters. Neither the stage API nor these
# tests promise that process-global compiler registries can be safely reused.
SETUP = """
from contextlib import redirect_stderr
from io import StringIO
import json
from pathlib import Path
import sys
from unittest.mock import patch
from src.pystachy_compiler import diagnostics, driver
from src.pystachy_compiler.gen import Gen
from src.pystachy_compiler.loader import Loader

sys.setrecursionlimit(diagnostics.MAXNEST * 40)
path = Path(sys.argv[1])
source = path.read_text(encoding=diagnostics.RAW)
diagnostics.SRC = str(path)
root = Path.cwd()
dirs = [str(path.parent), str(root / 'lib')]
stages = ['prepare', 'discover', 'analyze', 'optimize', 'finalize', 'lower']

def fresh():
    gen = Gen()
    gen.libdir = dirs[-1]
    gen.prefix = str(root)
    gen.final = False
    modules = Loader(dirs).program(str(path), source)
    return gen, modules

def forbidden(*args, **kwargs):
    raise AssertionError('stage body executed after a rejected transition')

def rejected(action):
    text = StringIO()
    with redirect_stderr(text):
        try:
            action()
        except SystemExit as exc:
            assert exc.code == 1, exc.code
        else:
            raise AssertionError('invalid stage operation was accepted')
    assert 'internal error' in text.getvalue(), text.getvalue()
    return text.getvalue()
"""


class CompilerPipelineTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.env = {key: value for key, value in os.environ.items()
                    if not key.startswith("PYSTACHY_")}
        self.env.update(PYSTACHY_HOME=str(ROOT), PYSTACHY_IRCHECK="1")

    def source(self, source=SOURCE):
        path = self.directory / "program.py"
        path.write_text(source, encoding="utf-8")
        return path

    def run_stage(self, path, script, env=None):
        return subprocess.run(
            [sys.executable, "-c", SETUP + script, str(path)],
            cwd=ROOT, env=self.env if env is None else env,
            text=True, capture_output=True, timeout=45,
        )

    def ordinary(self, path, env=None):
        return subprocess.run(
            [sys.executable, str(ROOT / "pystachy.py"), "ir", str(path)],
            cwd=ROOT, env=self.env if env is None else env,
            text=True, capture_output=True, timeout=45,
        )

    def succeeded(self, result):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_empty_and_unknown_completions_cannot_create_a_stage(self):
        result = self.run_stage(self.source(), """
from src.pystachy_compiler.pipeline import PipelineState
for name in ['', 'new', 'unknown']:
    state = PipelineState()
    rejected(lambda: state.complete(name))
    assert (state.stage, state.active, state.history) == ('new', '', [])
state = PipelineState()
state.begin('prepare')
rejected(lambda: state.complete('discover'))
assert (state.stage, state.active, state.history) == ('new', 'prepare', [])
state.complete('prepare')
assert (state.stage, state.active, state.history) == ('prepare', '', ['prepare'])
""")
        self.succeeded(result)

    def test_finalized_boundary_checks_shared_ir_fragments(self):
        result = self.run_stage(self.source(), """
from src.pystachy_compiler.ir import ONENUMS, one_num
g, modules = fresh()
prepared = g.prepare_program(modules)
g.discover_program(prepared)
g.analyze_program()
g.optimize_program()
one_num(0)
ONENUMS[0].append(1)
try:
    error = rejected(g.finalize_program)
    assert 'shared list of its number' in error
    assert (g.pipeline.stage, g.pipeline.active) == ('optimize', 'finalize')
finally:
    ONENUMS[0].pop()
rejected(g.lower_program)
""")
        self.succeeded(result)

    def test_explicit_stages_preserve_ordinary_llvm(self):
        path = self.source()
        script = """
g, modules = fresh()
assert (g.pipeline.stage, g.pipeline.active, g.pipeline.history) == ('new', '', [])
prepared = g.prepare_program(modules)
assert prepared.modules is modules
actions = [lambda: g.discover_program(prepared), g.analyze_program,
           g.optimize_program, g.finalize_program]
assert (g.pipeline.stage, g.pipeline.active, g.pipeline.history) == ('prepare', '', ['prepare'])
for index, action in enumerate(actions, 1):
    action()
    assert g.pipeline.stage == stages[index], g.pipeline.stage
    assert g.pipeline.history == stages[:index + 1], g.pipeline.history
    assert g.pipeline.active == '', g.pipeline.active
assert any(fn.blocks for fn in g.fns), 'finalized IR was discarded'
print(g.lower_program(), end='')
assert (g.pipeline.stage, g.pipeline.active, g.pipeline.history) == ('lower', '', stages)
"""
        for options in ({}, {"PYSTACHY_OPT": "-all"}):
            with self.subTest(options=options):
                env = dict(self.env, **options)
                expected = self.ordinary(path, env)
                actual = self.run_stage(path, script, env)
                self.succeeded(expected)
                self.succeeded(actual)
                self.assertEqual(actual.stdout, expected.stdout)
                self.assertEqual(actual.stderr, expected.stderr)

    def test_typed_program_stops_before_llvm_and_does_not_execute_source(self):
        marker = self.directory / "executed.txt"
        path = self.source(SOURCE + f"with open({str(marker)!r}, 'w') as stream:\n    stream.write('ran')\n")
        result = self.run_stage(path, """
g, modules = fresh()
with patch.object(Gen, 'lower', forbidden), patch.object(Gen, 'lower_module', forbidden):
    g.typed_program(modules)
assert g.pipeline.stage == 'finalize'
assert g.pipeline.active == ''
assert g.pipeline.history == stages[:-1]
assert any(fn.blocks for fn in g.fns), 'typed stage returned no retained IR'
print(json.dumps({'stage': g.pipeline.stage, 'history': g.pipeline.history}))
""")
        self.succeeded(result)
        self.assertEqual(json.loads(result.stdout), {"stage": "finalize", "history": STAGES[:-1]})
        self.assertFalse(marker.exists(), "compiling to typed IR executed the source")

    def test_only_preparation_and_discovery_make_decisions(self):
        # Template instances, class specializations and field layouts are final once
        # discovery completes: the stages that consume them cannot add one.
        result = self.run_stage(self.source(TEMPLATES), """
from src.pystachy_compiler.pipeline import PipelineState
state = PipelineState()
state.decide('outside any stage')
for name in ['prepare', 'discover']:
    state.begin(name)
    state.decide('while ' + name)
    state.complete(name)
for name in ['analyze', 'optimize', 'finalize', 'lower']:
    assert 'after discovery completed (stage ' in rejected(lambda: state.decide('a probe'))
    state.begin(name)
    assert 'after discovery completed (stage ' + name + ')' in rejected(lambda: state.decide('a probe'))
    state.complete(name)
g, modules = fresh()
g.typed_program(modules)
twice = g.funcs['twice']
made = lambda: (len(twice.insts), len([c for c in g.classes.values() if c.origin == 'Box']))
before = made()
assert 'an instance of twice()' in rejected(lambda: g.instance(twice, ['float'], []))
assert 'a specialization of class Box' in rejected(lambda: g.specialize('Box', ['float'], {}, False, {}))
assert made() == before
print(json.dumps(before))
""")
        self.succeeded(result)
        self.assertEqual(json.loads(result.stdout), [1, 1])

    def test_lowering_consumes_ir_and_rejects_a_second_lowering(self):
        result = self.run_stage(self.source(), """
g, modules = fresh()
g.typed_program(modules)
assert any(fn.blocks for fn in g.fns)
output = g.lower_program()
assert 'define' in output
assert all(not fn.blocks and not fn.slots and not fn.loops for fn in g.fns)
before = list(g.pipeline.history)
with patch.object(Gen, 'lower', forbidden), patch.object(Gen, 'lower_module', forbidden):
    rejected(g.lower_program)
assert g.pipeline.stage == 'lower'
assert g.pipeline.history == before
""")
        self.succeeded(result)

    def test_stages_cannot_skip_predecessors(self):
        # Body hooks distinguish a boundary rejection from a failure caused by
        # attempting to operate on missing IR later in the stage.
        result = self.run_stage(self.source(), """
for name, hook in [('analyze_program', 'effects'), ('optimize_program', 'optimize'),
                   ('finalize_program', 'tuple_rets'), ('lower_program', 'lower_module')]:
    g = Gen()
    with patch.object(Gen, hook, forbidden):
        rejected(getattr(g, name))
    assert g.pipeline.stage == 'new'
    assert g.pipeline.history == []
""")
        self.succeeded(result)

    def test_each_completed_stage_rejects_repetition(self):
        # A separate child per boundary avoids carrying an intentionally poisoned
        # attempt or its process-global declarations into the next control.
        hooks = ["identity_modules", "function", "effects", "optimize", "tuple_rets"]
        for index, hook in enumerate(hooks):
            with self.subTest(stage=STAGES[index]):
                result = self.run_stage(self.source(), f"""
g, modules = fresh()
prepared = g.prepare_program(modules)
actions = [lambda: g.prepare_program(modules), lambda: g.discover_program(prepared),
           g.analyze_program, g.optimize_program, g.finalize_program]
for action in actions[1:{index + 1}]:
    action()
before = list(g.pipeline.history)
with patch.object(Gen, {hook!r}, forbidden):
    rejected(actions[{index}])
assert g.pipeline.stage == stages[{index}]
assert g.pipeline.history == before
""")
                self.succeeded(result)

    def test_prepared_artifact_cannot_cross_attempt_owners(self):
        result = self.run_stage(self.source(), """
first, first_modules = fresh()
foreign = first.prepare_program(first_modules)
second, second_modules = fresh()
owned = second.prepare_program(second_modules)
with patch.object(Gen, 'function', forbidden):
    rejected(lambda: second.discover_program(foreign))
assert first.pipeline.stage == second.pipeline.stage == 'prepare'
assert first.pipeline.history == second.pipeline.history == ['prepare']
assert first.pipeline.active == ''
assert second.pipeline.active == ''
second.discover_program(owned)
assert second.pipeline.history == ['prepare', 'discover']
""")
        self.succeeded(result)

    def test_semantic_failure_preserves_diagnostic_and_poisoned_attempt(self):
        path = self.source("print(unknown)\n")
        expected = self.ordinary(path)
        self.assertEqual(expected.returncode, 1, expected.stderr)
        actual = self.run_stage(path, """
g, modules = fresh()
prepared = g.prepare_program(modules)
text = StringIO()
with redirect_stderr(text):
    try:
        g.discover_program(prepared)
    except SystemExit as exc:
        assert exc.code == 1
    else:
        raise AssertionError('undefined name was accepted')
assert g.pipeline.stage == 'prepare'
assert g.pipeline.active == 'discover'
assert g.pipeline.history == ['prepare']
with patch.object(Gen, 'function', forbidden):
    rejected(lambda: g.discover_program(prepared))
rejected(g.analyze_program)
rejected(g.lower_program)
print(text.getvalue(), end='')
""")
        self.succeeded(actual)
        self.assertEqual(actual.stdout, expected.stderr)
        self.assertEqual(actual.stderr, "")

    def test_discovery_retry_requires_fresh_attempt(self):
        result = self.run_stage(self.source(RETRY), """
g, modules = fresh()
prepared = g.prepare_program(modules)
try:
    g.discover_program(prepared)
except diagnostics.Rejoin:
    pass
else:
    raise AssertionError('global type widening did not request its fresh attempt')
assert g.pipeline.stage == 'prepare'
assert g.pipeline.active == 'discover'
assert g.pipeline.history == ['prepare']
with patch.object(Gen, 'function', forbidden):
    rejected(lambda: g.discover_program(prepared))
rejected(g.analyze_program)
rejected(g.lower_program)
""")
        self.succeeded(result)

    def test_backend_failure_cannot_resume_a_partially_consumed_program(self):
        result = self.run_stage(self.source(), """
g, modules = fresh()
g.typed_program(modules)
assert len(g.fns) > 1
lowered = []
original = Gen.lower
failure = RuntimeError('injected serialization failure')
def interrupted(gen, fn):
    if lowered:
        raise failure
    original(gen, fn)
    lowered.append(fn)
with patch.object(Gen, 'lower', interrupted):
    try:
        g.lower_program()
    except RuntimeError as exc:
        assert exc is failure
    else:
        raise AssertionError('injected lowering failure was swallowed')
assert not lowered[0].blocks, 'the control did not consume a function'
assert any(fn.blocks for fn in g.fns), 'the control did not leave partial IR'
assert g.pipeline.stage == 'finalize'
assert g.pipeline.active == 'lower'
assert g.pipeline.history == stages[:-1]
with patch.object(Gen, 'lower', forbidden), patch.object(Gen, 'lower_module', forbidden):
    rejected(g.lower_program)
rejected(g.finalize_program)
""")
        self.succeeded(result)

    def test_driver_retries_with_fresh_stage_state(self):
        path = self.source(RETRY)
        expected = self.ordinary(path)
        actual = self.run_stage(path, """
attempts = []
original = Gen.program
def observed(g, modules):
    attempts.append(g)
    assert (g.pipeline.stage, g.pipeline.active, g.pipeline.history) == ('new', '', [])
    return original(g, modules)
with patch.object(Gen, 'program', observed):
    output = driver.compile_program(str(path), source, dirs, '')
assert len(attempts) == 2, len(attempts)
assert attempts[0] is not attempts[1]
assert attempts[0].pipeline is not attempts[1].pipeline
assert attempts[0].pipeline.stage == 'prepare'
assert attempts[0].pipeline.active == 'discover'
assert attempts[0].pipeline.history == ['prepare']
assert attempts[1].pipeline.stage == 'lower'
assert attempts[1].pipeline.active == ''
assert attempts[1].pipeline.history == stages
print(output, end='')
""")
        self.succeeded(expected)
        self.succeeded(actual)
        self.assertEqual(actual.stdout, expected.stdout)
        self.assertEqual(actual.stderr, expected.stderr)


if __name__ == "__main__":
    unittest.main()
