"""Tests of constant arguments, fields and results fold only what no code that runs changes."""
from copy import copy
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.pystachy_compiler import constargs
from src.pystachy_compiler.gen import Gen
from src.pystachy_compiler.loader import Loader


HELPER = """
class Helper:
    def __init__(self, tag: str) -> None:
        self.tag = tag

    def run(self, text: str) -> str:
        return self.tag + text


def heavy(text: str, tag: str) -> str:
    return Helper(tag).run(text)


def repair(text: str, schema: dict[str, str] | None = None, strict: bool = False) -> str:
    helper = Helper(schema["tag"]) if schema is not None else None
    if strict:
        text = text.strip()
    if helper is not None:
        return helper.run(text)
    if schema is not None:
        return heavy(text, "x")
    return text


def loads(text: str, schema: dict[str, str] | None = None) -> str:
    return repair(text, schema=schema)
"""
PARSER = """
class Parser:
    def __init__(self) -> None:
        self.helper: Parser | None = None
        self.strict = False

    def attach(self, other: "Parser") -> None:
        self.helper = other

    def parse(self, text: str) -> str:
        if self.helper is not None:
            text = self.helper.parse(text)
        if self.strict:
            return text.strip()
        return text
"""


def compile_source(source, opt=""):
    captured = {}
    lower = Gen.lower

    def capture(gen, fn):
        # program() releases these lists after lowering; retain the pre-lowering IR.
        captured[fn.f.ll] = copy(fn)
        lower(gen, fn)

    with patch.object(Gen, "lower", capture), patch.dict(os.environ, {
            "PYSTACHY_IRCHECK": "1", "PYSTACHY_IRFX": "0", "PYSTACHY_OPT": opt}):
        gen = Gen()
        gen.program(Loader([]).program("constargs_contract.py", source))
    return captured


def operations(fn):
    return [op for block in fn.blocks for op in block.code]


def tests(fn):
    return sum(op.op in ("cbr", "switch") for op in operations(fn))


def callees(fn):
    return {op.s for op in operations(fn) if op.op == "call"}


def blocks_of(fn):
    return {block.label: block for block in fn.blocks}


def traps(fn):
    return sum(op.op == "rt" and op.s == "exit_msg" for op in operations(fn))


class ConstantArgumentTests(unittest.TestCase):
    def test_defaults_that_every_call_leaves_decide_the_tests(self):
        functions = compile_source(HELPER + 'print(repair(" a "))\nprint(loads(" b "))\n')
        repair = functions["@f.repair"]
        self.assertEqual(tests(repair), 0)
        self.assertEqual(callees(repair), set())
        self.assertIn("unreachable", [op.op for op in operations(repair)])

    def test_turning_the_pass_off_is_the_control(self):
        for opt in ("-constargs", "-all"):
            with self.subTest(opt=opt):
                functions = compile_source(HELPER + 'print(repair(" a "))\nprint(loads(" b "))\n', opt)
                repair = functions["@f.repair"]
                self.assertEqual(tests(repair), 4)
                self.assertIn("@f.heavy", callees(repair))

    def test_one_call_that_passes_a_value_keeps_its_tests(self):
        functions = compile_source(HELPER + 'print(repair(" a "))\nprint(repair(" b ", strict=True))\n')
        repair = functions["@f.repair"]
        self.assertEqual(tests(repair), 1)  # (strict; schema is still None everywhere)
        self.assertEqual(callees(repair), set())
        functions = compile_source(HELPER + 'print(repair(" a "))\nprint(loads(" b ", {"tag": "t"}))\n')
        repair = functions["@f.repair"]
        self.assertEqual(tests(repair), 3)  # (schema, twice, and helper: strict is still False)
        self.assertIn("@f.heavy", callees(repair))

    def test_a_call_that_cannot_run_passes_nothing(self):
        # verbose() is called only where loud is true, which no call makes it
        functions = compile_source("""
def verbose(text: str, wide: bool = False) -> str:
    return text.upper() + ("!" * 3 if wide else "!")


def render(text: str, loud: bool = False) -> str:
    if loud:
        return verbose(text, True)
    return text


def quiet(text: str) -> str:
    return verbose(text)


print(render("a"), quiet("b"))
""")
        self.assertEqual(tests(functions["@f.render"]), 0)
        self.assertEqual(tests(functions["@f.verbose"]), 0)

    def test_a_function_used_as_a_value_keeps_its_tests(self):
        functions = compile_source("""
from typing import Callable


def render(text: str, loud: bool = False) -> str:
    if loud:
        return text.upper()
    return text


def through(f: Callable[[str, bool], str]) -> str:
    return f("x", True)


print(render("a"), through(render))
""")
        self.assertEqual(tests(functions["@f.render"]), 1)

    def test_a_reassigned_parameter_is_what_it_was_assigned(self):
        source = """
def find(name: str) -> str | None:
    return name if name != "" else None


def pick(key: str, alias: str | None = None) -> str:
    if alias is None:
        alias = find(key)
    if alias is None:
        return "none"
    return alias


print(pick("a"), pick(""))
"""
        self.assertEqual(tests(compile_source(source, "-constargs")["@f.pick"]), 2)
        self.assertEqual(tests(compile_source(source)["@f.pick"]), 1)  # (the second reads what find() gave)

    def test_a_field_that_only_code_which_never_runs_assigns(self):
        functions = compile_source(PARSER + 'p = Parser()\nprint(p.parse(" a "))\n')
        parse = functions["@m.Parser.parse"]
        self.assertEqual(tests(parse), 0)
        self.assertEqual(callees(parse), set())

    def test_a_field_that_code_which_runs_assigns_keeps_its_tests(self):
        functions = compile_source(PARSER + 'p = Parser()\np.strict = True\nprint(p.parse(" a "))\n')
        self.assertEqual(tests(functions["@m.Parser.parse"]), 1)
        functions = compile_source(PARSER + 'p = Parser()\nsetattr(p, "strict", True)\nprint(p.parse(" a "))\n')
        self.assertEqual(tests(functions["@m.Parser.parse"]), 1)
        functions = compile_source(PARSER + 'p = Parser()\np.attach(Parser())\nprint(p.parse(" a "))\n')
        parse = functions["@m.Parser.parse"]
        self.assertEqual(tests(parse), 1)
        self.assertIn("@m.Parser.parse", callees(parse))

    def test_an_item_of_a_returned_tuple_decides_the_callers_tests(self):
        functions = compile_source("""
class Rules:
    def __init__(self) -> None:
        self.active: Rules | None = None

    def resolve(self, key: str) -> tuple["Rules | None", str]:
        rules = self.active if self.active is not None and key != "" else None
        if rules is None:
            return None, key
        return rules, key.upper()

    def apply(self, key: str) -> str:
        rules, key = self.resolve(key)
        if rules is not None:
            return rules.apply(key)
        return key


print(Rules().apply("k"))
""")
        apply = functions["@m.Rules.apply"]
        self.assertEqual(tests(apply), 0)
        self.assertEqual(callees(apply), {"@m.Rules.resolve"})

    def test_a_function_over_the_bound_is_read_as_written(self):
        def source(statements):
            body = "\n".join(f"    total += len(text) + {k}" for k in range(statements))
            return (f"def big(text: str, loud: bool = False) -> int:\n    total = 0\n{body}\n"
                    "    if loud:\n        total = -total\n    return total\n\nprint(big('a'))\n")

        small = compile_source(source(8))["@f.big"]
        self.assertLess(len(operations(small)), constargs.CLOSE_OPS)
        self.assertEqual(tests(small), 0)
        big = compile_source(source(1200))["@f.big"]
        self.assertGreater(len(operations(big)), constargs.CLOSE_OPS)
        self.assertEqual(tests(big), 1)  # (loud's test stays)

    def test_without_folding_the_decided_code_stops_the_program(self):
        source = HELPER + 'print(repair(" a "))\n'
        folded = compile_source(source)["@f.repair"]
        trapped = compile_source(source, "-constfold")["@f.repair"]
        self.assertEqual((tests(folded), traps(folded)), (0, 0))
        self.assertEqual(tests(trapped), 4)  # (every test stays)
        self.assertGreater(traps(trapped), 0)
        self.assertNotIn("@f.heavy", callees(trapped))
        last = trapped.blocks[-1]
        self.assertEqual([op.op for op in last.code], ["rt", "unreachable"])
        for block in trapped.blocks:
            if block.code[-1].op == "cbr":
                self.assertIn(last.label, block.code[-1].b)  # (the edge not taken goes there)

    def test_a_planted_bug_reaches_a_trap(self):
        # blind the pass to every store of a field: parse()'s test of strict is then decided,
        # wrongly, and the block that runs when it is set is one that stops the program
        source = PARSER + 'p = Parser()\np.strict = True\nprint(p.parse(" a "))\n'
        init = constargs.Fields.__init__

        def blind(self, fns, index, classes):
            init(self, fns, index, classes)
            self.sfirst = [0] * (len(fns) + 1)
            self.sblk, self.sname, self.sval = [], [], []

        sound = compile_source(source, "-constfold")["@m.Parser.parse"]
        self.assertEqual(sum(block.code[-1].op == "cbr" and any(blocks_of(sound)[label].code[0].op == "rt" for label in block.code[-1].b) for block in sound.blocks), 1)  # (helper's test alone)
        with patch.object(constargs.Fields, "__init__", blind):
            parse = compile_source(source, "-constfold")["@m.Parser.parse"]
        blocks = blocks_of(parse)
        decided = [block.code[-1] for block in parse.blocks if block.code[-1].op == "cbr"]
        self.assertEqual(len(decided), 2)
        for test in decided:  # (helper's, and now strict's too)
            self.assertTrue(any(blocks[label].code[0].op == "rt" and blocks[label].code[0].s == "exit_msg" for label in test.b))


if __name__ == "__main__":
    unittest.main()
