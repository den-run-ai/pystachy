"""Worker eligibility and emitted native map boundaries.

Run with python3 -m unittest discover -s tools -p test_parallel.py.
"""
from contextlib import redirect_stderr
from io import StringIO
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.pystachy_compiler import diagnostics, driver, parallel
from src.pystachy_compiler.driver import compile_program
from src.pystachy_compiler.gen import Gen
from src.pystachy_compiler.ir import Blk, FnInfo, IFn, Ins, Val
from src.pystachy_compiler.syntax import Node

ROOT = Path(__file__).resolve().parent.parent


def scalar_kernel():
    info = FnInfo("work", "@work", Node("def", "work", 1), "")
    info.ptypes = ["float"]
    info.ret = "float"
    fn = IFn(info)
    fn.ps = [0]
    op = Ins("scalar.bin", "float", "fmul")
    op.a = [Val("%a0", "float"), Val("%a0", "float")]
    op.r = [1]
    ret = Ins("ret", "", "")
    ret.a = [Val("%t1", "float")]
    fn.blocks[0].code = [op, ret]
    fn.n = 1
    fn.fx = 0
    return fn


def local_slot(fn):
    slot = Ins("slot", "float", "value")
    slot.r = [2]
    fn.slots = [slot]
    store = Ins("mem.store", "", "")
    store.a = [Val("%value.2", "*float"), Val("%t1", "float")]
    load = Ins("mem.load", "float", "")
    load.a = [Val("%value.2", "*float")]
    load.r = [3]
    fn.blocks[0].code[1:1] = [store, load]
    fn.blocks[0].code[-1].a[0].v = "%t3"
    fn.n = 3
    return store, load


class WorkerProofTests(unittest.TestCase):
    def assert_ineligible(self, fn, reason):
        self.assertIn(reason, parallel.kernel_reason(fn))

    def test_pure_float_and_private_slots(self):
        fn = scalar_kernel()
        self.assertEqual(parallel.kernel_reason(fn), "")
        local_slot(fn)
        self.assertEqual(parallel.kernel_reason(fn), "")

    def test_signature_must_match_worker_abi(self):
        for field, value in (("ptypes", ["int"]), ("ptypes", ["float", "float"]),
                             ("ret", "int")):
            with self.subTest(field=field, value=value):
                fn = scalar_kernel()
                setattr(fn.f, field, value)
                self.assert_ineligible(fn, "float argument")
        fn = scalar_kernel()
        fn.ps = []
        self.assert_ineligible(fn, "float argument")

    def test_numeric_identity_abi_is_not_called_as_plain_float(self):
        with patch.object(parallel, "identity_abi", return_value=True):
            self.assert_ineligible(scalar_kernel(), "identity ABI")

    def test_runtime_state_is_never_touched(self):
        for field, value in (("counted", True), ("rdepth", "%depth"),
                             ("pads", True), ("coro", True)):
            with self.subTest(field=field):
                fn = scalar_kernel()
                setattr(fn, field, value)
                self.assert_ineligible(fn, "state")

    def test_unknown_helper_is_unsafe_even_with_empty_effects(self):
        for kind, symbol in (("rt", "str.len"), ("call", "@helper"),
                             ("icall", ""), ("alloc.fixed", ""),
                             ("future.operation", "")):
            with self.subTest(kind=kind):
                fn = scalar_kernel()
                op = Ins(kind, "float", symbol)
                op.r = [2]
                fn.blocks[0].code.insert(0, op)
                self.assert_ineligible(fn, "unsupported operation")

    def test_division_is_not_just_an_effect_free_float_op(self):
        fn = scalar_kernel()
        fn.blocks[0].code[0].s = "fdiv"
        self.assert_ineligible(fn, "unsupported scalar operation")

    def test_memory_address_must_be_an_actual_private_slot(self):
        for address in ("@global", "%other.2", "%t7", "%a0"):
            for target in (0, 1):
                with self.subTest(address=address, target=target):
                    fn = scalar_kernel()
                    ops = local_slot(fn)
                    ops[target].a[0].v = address
                    self.assert_ineligible(fn, "outside private locals")

    def test_private_slot_layout_is_checked(self):
        for kind, value in (("t", "str"), ("k", 1), ("r", [])):
            with self.subTest(kind=kind):
                fn = scalar_kernel()
                local_slot(fn)
                setattr(fn.slots[0], kind, value)
                self.assert_ineligible(fn, "local storage")
        fn = scalar_kernel()
        store, _ = local_slot(fn)
        store.a[1].t = "int"
        self.assert_ineligible(fn, "type mismatch")

    def test_scalar_globals_are_not_worker_inputs(self):
        fn = scalar_kernel()
        fn.blocks[0].code[0].a[1].v = "@constant_or_global"
        self.assert_ineligible(fn, "global operand")

    def test_loops_and_unknown_successors_are_ineligible(self):
        for label in ("entry", "missing"):
            with self.subTest(label=label):
                fn = scalar_kernel()
                branch = Ins("br", "", "")
                branch.b = [label]
                fn.blocks[0].code[-1] = branch
                self.assert_ineligible(fn, "backward edge")

    def test_forward_branches_are_private_control_flow(self):
        fn = scalar_kernel()
        ret = fn.blocks[0].code.pop()
        branch = Ins("br", "", "")
        branch.b = ["done"]
        fn.blocks[0].code.append(branch)
        done = Blk("done")
        done.code = [ret]
        fn.blocks.append(done)
        self.assertEqual(parallel.kernel_reason(fn), "")
        done.handler = "exception"
        self.assert_ineligible(fn, "handler")

    def test_absent_body_and_malformed_control_are_ineligible(self):
        fn = scalar_kernel()
        fn.blocks = []
        self.assert_ineligible(fn, "missing kernel body")
        fn = scalar_kernel()
        fn.blocks[0].code.pop()
        self.assert_ineligible(fn, "terminator")
        fn = scalar_kernel()
        fn.blocks[0].code[0].x = "fast"
        self.assert_ineligible(fn, "metadata")
        fn = scalar_kernel()
        fn.blocks[0].code[0].a = []
        self.assert_ineligible(fn, "operand type mismatch")


class RuntimeMapVerifierTests(unittest.TestCase):
    def mapped(self):
        g = Gen()
        key = g.runtime("pys_parallel_map_f64")
        kernel = scalar_kernel()
        info = FnInfo("caller", "@caller", Node("def", "caller", 1), "")
        info.ptypes = ["list[float]", "int"]
        info.ret = "list[float]"
        caller = IFn(info)
        caller.ps = [0, 1]
        caller.n = 1
        op = Ins("rt", "list[float]", key)
        op.a = [Val("%a0", "list[float]"), Val("%a1", "int"),
                Val("@pys.parallel.work", "%ptr")]
        op.r = [1]
        ret = Ins("ret", "", "")
        ret.a = [Val("%t1", "list[float]")]
        caller.blocks[0].code = [op, ret]
        g.fns = [kernel, caller]
        g.fll = {"@work": 0, "@caller": 1}
        return g, caller, kernel, op

    def assert_bad(self, g, caller, reason):
        err = StringIO()
        with redirect_stderr(err), self.assertRaises(SystemExit):
            g.verify(caller, False)
        self.assertIn("parallel.map_f64", err.getvalue())
        self.assertIn(reason, err.getvalue())

    def test_proven_thunk_and_typed_list_are_valid(self):
        g, caller, _, _ = self.mapped()
        g.verify(caller, False)

    def test_raw_and_missing_thunks_are_rejected(self):
        for name in ("%raw_pointer", "null", "@work", "@pys.parallel.missing"):
            with self.subTest(name=name):
                g, caller, _, op = self.mapped()
                op.a[2].v = name
                self.assert_bad(g, caller, "compiled kernel thunk")

    def test_operand_shapes_and_result_layout_are_checked(self):
        for field, value in (("t", "list[int]"), ("r", []), ("k", 1), ("x", "float"),
                             ("a", [])):
            with self.subTest(field=field):
                g, caller, _, op = self.mapped()
                setattr(op, field, value)
                self.assert_bad(g, caller, "proven kernel pointer")
        for index, typename in ((0, "list[int]"), (1, "float"), (2, "int")):
            with self.subTest(index=index):
                g, caller, _, op = self.mapped()
                op.a[index].t = typename
                self.assert_bad(g, caller, "proven kernel pointer")

    def test_changing_proven_kernel_invalidates_the_call(self):
        g, caller, kernel, _ = self.mapped()
        g.verify(caller, False)
        # Empty effects cannot bless a helper inserted after the worker proof.
        call = Ins("call", "float", "@hidden_helper")
        call.r = [2]
        kernel.blocks[0].code.insert(0, call)
        kernel.fx = 0
        self.assert_bad(g, caller, "unsafe kernel")


class NativeMapIRTests(unittest.TestCase):
    def compile(self, text):
        path = str(ROOT / "parallel_test.py")
        # compile_program owns retries and supplies the library's canonical path.
        with patch.object(diagnostics, "SRC", path), redirect_stderr(StringIO()):
            return compile_program(path, text, [str(ROOT / "lib")], "")

    def runtime_flags(self, source):
        ir = self.compile(source)

        class BeforeBuild(Exception):
            pass

        recursion_limit = sys.getrecursionlimit()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "flags.py"
                path.write_text(source)
                with patch.dict(os.environ, {"PYSTACHY_HOME": str(ROOT),
                                             "PYSTACHY_CFLAGS": "", "PYSTACHY_PATH": ""}), \
                        patch.object(sys, "argv", [str(ROOT / "pystachy.py"), "build", str(path)]), \
                        patch.object(diagnostics, "SRC", str(path)), \
                        patch.object(driver, "compile_program", return_value=ir), \
                        patch.object(driver, "address_sanitized", side_effect=BeforeBuild) as flags:
                    # Capture the actual driver-selected runtime/link/cache flags,
                    # before any compiler subprocess or cache write can happen.
                    with self.assertRaises(BeforeBuild):
                        driver.main()
                    return flags.call_args.args[0]
        finally:
            sys.setrecursionlimit(recursion_limit)

    def test_pure_map_gets_a_nonthrowing_chunk_with_no_fast_math(self):
        ir = self.compile("""
from parallel import map_float
def square(x: float) -> float:
    return x * x + 0.25
print(map_float(square, [1.0, 2.0], 4))
""")
        self.assertIn("@pys_parallel_map_f64", ir)
        self.assertIn("define internal void @pys.parallel.", ir)
        chunk = ir.split("define internal void @pys.parallel.", 1)[1].split("\n}", 1)[0]
        self.assertIn("nounwind", chunk)
        self.assertIn("getelementptr double", chunk)
        self.assertIn("store double", chunk)
        self.assertNotIn(" fast ", ir)
        self.assertNotIn(" contract ", ir)

    def test_unsafe_callbacks_keep_original_call(self):
        bodies = (
            "return x / 2.0",
            "print(x)\n    return x",
            "seen.append(x)\n    return x",
            "return helper(x)",
            "return x * factor",
            "for i in range(2):\n        x = x * x\n    return x",
            "if x == 0.0:\n        raise ValueError('zero')\n    return x",
        )
        for body in bodies:
            with self.subTest(body=body):
                ir = self.compile("""
from parallel import map_float
seen: list[float] = []
factor = 2.0
def helper(x: float) -> float:
    return x * x
def work(x: float) -> float:
    """ + body + "\nprint(map_float(work, [1.0, 2.0], 4))\n")
                self.assertNotIn("@pys_parallel_map_f64", ir)
                self.assertNotIn("define internal void @pys.parallel.", ir)

    def test_dynamic_identity_graph_stays_sequential(self):
        ir = self.compile("""# pystachy: dynamic-any
from parallel import map_float
from typing import Any
def same(x: float) -> float:
    return x
x = float('1234.5')
values = map_float(same, [x], 4)
result: Any = values[0]
print(result is x)
""")
        self.assertNotIn("@pys_parallel_map_f64", ir)

    def test_plain_program_does_not_gain_parallel_symbols(self):
        ir = self.compile("def square(x: float) -> float:\n    return x * x\nprint(square(2.0))\n")
        self.assertNotIn("parallel", ir)

    def test_symbol_text_does_not_link_the_parallel_backend(self):
        for text in ("@pys_parallel_map_f64(", "\ndeclare ptr @pys_parallel_map_f64("):
            with self.subTest(text=text):
                self.assertEqual(self.runtime_flags("print(" + repr(text) + ")\n"), [])
        self.assertEqual(self.runtime_flags("""
from parallel import map_float
def square(x: float) -> float:
    return x * x
print(map_float(square, [1.0], 4))
"""), ["-DPYSTACHY_PARALLEL", "-pthread"])

    def test_shadowing_module_is_not_replaced_by_a_runtime_intrinsic(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "parallel.py").write_text("""
from typing import Callable
def map_float(fn: Callable[[float], float], values: list[float], workers: int = 1) -> list[float]:
    return [123.0]
""")
            source = """
from parallel import map_float
def square(x: float) -> float:
    return x * x
print(map_float(square, [1.0], 4))
"""
            path = str(Path(tmp) / "main.py")
            with patch.object(diagnostics, "SRC", path), redirect_stderr(StringIO()):
                ir = compile_program(path, source, [tmp, str(ROOT / "lib")], "")
            self.assertNotIn("@pys_parallel_map_f64", ir)
            self.assertNotIn("define internal void @pys.parallel.", ir)


if __name__ == "__main__":
    unittest.main()
