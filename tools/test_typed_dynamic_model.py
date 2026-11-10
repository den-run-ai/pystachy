"""Check dynamic-guard soundness against a small independent tag interpreter.

The generated IR is never lowered or executed. The oracle follows concrete tags
and booleans until the program returns, reads a wrong payload, or repeats a state.
It does not use the proof solver's domains, aliases, liveness or implications.
"""
from itertools import product
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.test_typed_dynamic_proofs import Case


TAGS = ("float", "str", "bool", "int")


def loop_case(next_x, next_y, compared, operation, rhs):
    c = Case()
    initial = c.compare("%a0")
    c.op("br", b=["loop"])
    c.block("loop")
    x = c.op("phi", "dyn", a=[("%a0", "dyn"), ("next_x", "dyn")],
             b=["entry", "body"])
    x_phi = c.b.code[-1]
    y = c.op("phi", "dyn", a=[("%a1", "dyn"), ("next_y", "dyn")],
             b=["entry", "body"])
    y_phi = c.b.code[-1]
    flag = c.op("phi", "bool", a=[(initial, "bool"), ("next_flag", "bool")],
                b=["entry", "body"])
    flag_phi = c.b.code[-1]
    # Keep the second value live across the join: stale guard facts must remain
    # invalid even when another phi preserves the old value.
    c.op("dyn.type", "dyntype", a=[(y, "dyn")])
    c.branch(flag, "body", "done")
    c.block("body")
    c.payload(x)
    values = [x, y, "%a0", "%a1"]
    condition = c.compare(values[compared])
    if operation:
        other = ["%a2", flag, "true", "false"][rhs]
        condition = c.op("scalar.bin", "bool", operation,
                         a=[(condition, "bool"), (other, "bool")])
    x_phi.a[1].v = values[next_x]
    y_phi.a[1].v = values[next_y]
    flag_phi.a[1].v = condition
    c.op("br", b=["loop"])
    c.block("done")
    c.ret()
    return c


def payloads_are_safe(case, first, second, choice):
    values = {"%a0": first, "%a1": second, "%a2": choice}

    def read(name):
        if name.startswith("@pys_dyntype_"):
            return name.removeprefix("@pys_dyntype_")
        if name == "true":
            return True
        if name == "false":
            return False
        return values[name]

    blocks = {block.label: block for block in case.fn.blocks}
    label, predecessor = "entry", ""
    seen = set()
    for _ in range(100):
        state = (label, predecessor, tuple(sorted(values.items())))
        if state in seen:
            # Inputs are fixed and every modeled step is deterministic. A repeated
            # state has exactly the same future, with no unsafe read so far.
            return True
        seen.add(state)
        block = blocks[label]
        incoming = {}
        for ins in block.code:
            if ins.op != "phi":
                break
            source = ins.a[ins.b.index(predecessor)].v
            incoming[f"%t{ins.r[0]}"] = read(source)
        # Real phi assignments read the old state and then commit simultaneously.
        values.update(incoming)
        successor = None
        for ins in block.code:
            if ins.op == "phi":
                continue
            args = [read(operand.v) for operand in ins.a]
            result = f"%t{ins.r[0]}" if ins.r else ""
            if ins.op == "dyn.type":
                values[result] = args[0]
            elif ins.op == "ptr.cmp":
                assert ins.s in ("==", "!=")
                values[result] = (args[0] == args[1]) == (ins.s == "==")
            elif ins.op == "scalar.bin":
                assert all(isinstance(x, bool) for x in args)
                if ins.s == "and":
                    values[result] = args[0] and args[1]
                elif ins.s == "or":
                    values[result] = args[0] or args[1]
                elif ins.s == "xor":
                    values[result] = args[0] != args[1]
                else:
                    raise AssertionError(f"unmodeled boolean operation: {ins.s}")
            elif ins.op == "dyn.payload":
                if args[0] != ins.s:
                    return False
            elif ins.op == "cbr":
                assert isinstance(args[0], bool)
                successor = ins.b[0 if args[0] else 1]
            elif ins.op == "br":
                successor = ins.b[0]
            elif ins.op == "ret.none":
                return True
            else:
                raise AssertionError(f"unmodeled operation: {ins.op}")
        assert successor is not None
        predecessor, label = label, successor
    raise AssertionError("model did not reach a result or repeat a state")


class DynamicModelTests(unittest.TestCase):
    def test_stale_guard_and_paired_value_guard_controls(self):
        # The backedge swaps the values, but the saved condition still tests the
        # original first input. Its tag cannot justify the new first phi value.
        case = loop_case(1, 0, 2, "", 0)
        self.assertFalse(payloads_are_safe(case, "float", "str", False))
        self.assertTrue(case.proof().bad)
        # The incoming guard can instead describe the incoming value.
        paired = loop_case(1, 0, 1, "", 0)
        self.assertTrue(payloads_are_safe(paired, "float", "str", False))
        self.assertFalse(paired.proof().bad)

    def test_bounded_phi_and_boolean_models(self):
        shapes = inputs = accepted = unsafe = 0
        for parameters in product(range(4), range(4), range(4), ("", "and", "or", "xor"), range(4)):
            if parameters[3] == "" and parameters[4] != 0:
                continue  # The unused RHS is not a distinct shape.
            case = loop_case(*parameters)
            bad = case.proof().bad
            accepted += not bad
            safe = True
            for arguments in product(TAGS, TAGS, (False, True)):
                result = payloads_are_safe(case, *arguments)
                inputs += 1
                safe = safe and result
                if not bad:
                    self.assertTrue(result, f"unsafe accepted model: {parameters}, inputs {arguments}")
            shapes += 1
            unsafe += not safe
        self.assertEqual(shapes, 832)
        self.assertEqual(inputs, 26624)
        self.assertEqual(unsafe, 256)
        self.assertGreater(accepted, 0)
        # Safe programs may be rejected by this deliberately bounded proof.


if __name__ == "__main__":
    unittest.main()
