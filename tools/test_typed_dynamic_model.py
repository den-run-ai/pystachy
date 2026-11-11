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


# A class hierarchy for the class models: each class's number and base; the other tags are
# builtins, whose class number is -1.
CLASSES = {"Base": (0, ""), "Child": (1, "Base"), "Other": (2, "")}
CLASS_TAGS = ("Base", "Child", "Other", "none", "float")
CLASS_TESTS = ("isa", "isa or None", "==", "!=", "switch")


def ancestors(tag):
    out = []
    while tag in CLASSES:
        out.append(tag)
        tag = CLASSES[tag][1]
    return out


def class_case(next_x, tested, test, descriptor, member):
    """A loop whose header tests the tag of one of x (a phi), y or the first argument, and
    whose taken branch reads x's payload as member before the back edge rebinds x."""
    c = Case()
    for name in CLASSES:
        number, base = CLASSES[name]
        c.dyntype("@dt." + name, number=number, base="@dt." + base if base else "", held=name)
    c.op("br", b=["loop"])
    c.block("loop")
    x = c.op("phi", "dyn", a=[("%a0", "dyn"), ("next_x", "dyn")], b=["entry", "body"])
    x_phi = c.b.code[-1]
    y = c.op("phi", "dyn", a=[("%a1", "dyn"), ("%a0", "dyn")], b=["entry", "body"])
    c.branch("%a2", "test", "done")
    c.block("test")
    value = [x, y, "%a0"][tested]
    target = "@dt." + descriptor if descriptor in CLASSES else "@pys_dyntype_" + descriptor
    if test == "switch":
        c.dispatch({str(CLASSES[descriptor][0]) if descriptor in CLASSES else "9": "hit"}, value=value)
        c.block("miss")
        c.op("br", b=["body"])
    else:
        if test.startswith("isa"):
            condition = c.isa(value, target, none=test == "isa or None")
        else:
            tag = c.op("dyn.type", "dyntype", a=[(value, "dyn")])
            condition = c.op("ptr.cmp", "bool", test, [(tag, "dyntype"), (target, "dyntype")])
        c.branch(condition, "hit", "body")
    c.block("hit")
    c.payload(x, member)
    c.op("br", b=["body"])
    c.block("body")
    x_phi.a[1].v = [x, y, "%a0", "%a1"][next_x]
    c.op("br", b=["loop"])
    c.block("done")
    c.ret()
    return c


def class_payloads_are_safe(case, first, second, choice):
    """Run the class model on concrete tags: pys_dyn_isa follows bases and admits None for a
    class; a class payload read takes its class's or a subclass's box."""
    values = {"%a0": first, "%a1": second, "%a2": choice}

    def read(name):
        if name.startswith("@dt."):
            return name.removeprefix("@dt.")
        if name.startswith("@pys_dyntype_"):
            return name.removeprefix("@pys_dyntype_")
        if name in ("true", "false"):
            return name == "true"
        if name.lstrip("-").isdigit():
            return int(name)
        return values[name]

    blocks = {block.label: block for block in case.fn.blocks}
    label, predecessor = "entry", ""
    seen = set()
    for _ in range(100):
        state = (label, predecessor, tuple(sorted((k, repr(v)) for k, v in values.items())))
        if state in seen:
            return True
        seen.add(state)
        block = blocks[label]
        incoming = {}
        for ins in block.code:
            if ins.op != "phi":
                break
            incoming[f"%t{ins.r[0]}"] = read(ins.a[ins.b.index(predecessor)].v)
        values.update(incoming)
        successor = None
        for ins in block.code:
            if ins.op == "phi":
                continue
            args = [read(operand.v) for operand in ins.a]
            result = f"%t{ins.r[0]}" if ins.r else ""
            if ins.op == "dyn.type":
                values[result] = args[0]
            elif ins.op == "rt":
                assert ins.s == "dyn.isa"
                tag, cls = args
                values[result] = int(tag == cls or (cls in CLASSES and (tag == "none" or cls in ancestors(tag))))
            elif ins.op == "num.cmp":
                values[result] = (args[0] == args[1]) == (ins.s == "==")
            elif ins.op == "mach.addr":
                values[result] = ("word", args[0], args[1])
            elif ins.op == "mach.load":
                _, tag, word = args[0]
                assert word == 3
                values[result] = CLASSES[tag][0] if tag in CLASSES else -1
            elif ins.op == "ptr.cmp":
                values[result] = (args[0] == args[1]) == (ins.s == "==")
            elif ins.op == "scalar.bin":
                assert ins.s == "and"
                values[result] = args[0] and args[1]
            elif ins.op == "dyn.payload":
                if args[0] != ins.s and ins.s not in ancestors(args[0]):
                    return False
            elif ins.op == "switch":
                successor = ins.b[0]
                for j in range(1, len(args)):
                    if args[0] == args[j]:
                        successor = ins.b[j]
                        break
            elif ins.op == "cbr":
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


    def test_bounded_class_test_and_dispatch_models(self):
        # isa calls, exact tag comparisons and class number switches on a loop's values: the
        # proof never accepts a program that reads a wrong payload.
        shapes = inputs = accepted = unsafe = 0
        descriptors = {"isa": CLASSES, "isa or None": CLASSES, "switch": CLASSES,
                       "==": tuple(CLASSES) + ("none",), "!=": tuple(CLASSES) + ("none",)}
        for test in CLASS_TESTS:
            for next_x, tested, descriptor, member in product(range(4), range(3), descriptors[test], CLASSES):
                case = class_case(next_x, tested, test, descriptor, member)
                bad = case.proof().bad
                accepted += not bad
                safe = True
                for arguments in product(CLASS_TAGS, CLASS_TAGS, (False, True)):
                    result = class_payloads_are_safe(case, *arguments)
                    inputs += 1
                    safe = safe and result
                    if not bad:
                        self.assertTrue(result, f"unsafe accepted model: {test, next_x, tested, descriptor, member}, inputs {arguments}")
                shapes += 1
                unsafe += not safe
        self.assertEqual(shapes, 612)
        self.assertEqual(inputs, 30600)
        self.assertEqual(unsafe, 540)
        # Here the proof also accepts every safe shape: those that read the tested value.
        self.assertEqual(accepted, shapes - unsafe)


if __name__ == "__main__":
    unittest.main()
