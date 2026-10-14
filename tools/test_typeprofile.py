"""The type-feedback census measures what each synthetic program is built to show."""
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest

import typeprofile

TOOL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "typeprofile.py")

PROGRAM = textwrap.dedent("""\
    class Square:
        def __init__(self, side):
            self.side = side
            self.label = None

        def area(self):
            return self.side * self.side


    class Circle:
        def __init__(self, radius):
            self.radius = radius

        def area(self):
            return 3.0 * self.radius * self.radius


    class Base:
        pass


    class Derived(Base):
        pass


    def helper(x):
        return x + x


    def mid(x):
        return helper(x)


    def ints():
        for i in range(30):
            mid(i)


    def floats():
        for i in range(10):
            mid(i + 0.5)


    def direct():
        for i in range(30):
            helper(i)
        for i in range(10):
            helper(i + 0.5)


    def maybe(x):
        return x if x > 0 else None


    def mixed(x):
        return x if x > 0 else "negative"


    def take(value):
        return value


    class Lazy:
        # Any attribute lookup through __getattr__ before __init__ sets ready would recurse.
        __slots__ = ("ready",)

        def __getattr__(self, name):
            return self.ready

        def __init__(self):
            self.ready = 1


    class Key:
        hashes = 0

        def __hash__(self):
            Key.hashes += 1
            return 1


    shapes = [Square(2), Circle(1.5)] * 10
    for shape in shapes:
        shape.area()
    ints()
    floats()
    direct()
    for v in (1, -1, 2, -2):
        maybe(v)
        mixed(v)
    take([1, 2, 3])
    take([1, "a", 2])
    take({0.5: 1})
    take({"a": [1, 2]})
    take(1 << 70)
    take(Derived())
    take((1, "a"))
    take([{}, {"a": True}, {"b": False}])
    take([(), (1,), (2,)])
    for _ in range(20):
        Lazy()
    keyed = {Key(): 1}
    before = Key.hashes
    take(keyed)
    assert Key.hashes == before, "the census ran a key's __hash__"
""")


class CensusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory(prefix="typeprofile-test-")
        program = os.path.join(cls.directory.name, "program.py")
        with open(program, "w", encoding="utf-8") as stream:
            stream.write(PROGRAM)
        out = os.path.join(cls.directory.name, "program.json")
        subprocess.run([sys.executable, TOOL, "record", out, program], check=True, timeout=60)
        with open(out, encoding="utf-8") as stream:
            cls.data = json.load(stream)
        cls.summary = typeprofile.summarize(cls.data)

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def calls_of(self, name):
        index = next(i for i, row in enumerate(self.data["codes"]) if row["qualname"] == name)
        return [c for c in self.data["calls"] if c[0] == index]

    def group_shares(self, name, key):
        groups = {}
        for c in self.calls_of(name):
            groups.setdefault(key(c), {}).setdefault(c[5], 0)
            groups[key(c)][c[5]] += c[-1]
        total = sum(sum(g.values()) for g in groups.values())
        return sum(max(g.values()) for g in groups.values()) / total

    def test_context_resolves_a_polymorphic_helper(self):
        # helper sees int and float overall, at mid's one call site too; the caller's own
        # site (call string of 2) or argument types separate them, as specialization would.
        self.assertLess(self.group_shares("helper", lambda c: c[0]), 1.0)
        mid_calls = [c for c in self.calls_of("helper") if self.data["sites"][c[1]]["name"] == "mid"]
        sites = {c[1] for c in mid_calls}
        self.assertEqual(len(sites), 1)
        self.assertEqual(len({c[5] for c in mid_calls}), 2)
        self.assertEqual(self.group_shares("helper", lambda c: (c[0], c[1], c[2])), 1.0)
        self.assertEqual(self.group_shares("helper", lambda c: (c[0], c[1], c[3])), 1.0)

    def test_send_site_sees_both_targets_while_each_method_is_monomorphic(self):
        area_sites = {c[1] for name in ("Square.area", "Circle.area") for c in self.calls_of(name)}
        self.assertEqual(len(area_sites), 1)
        for name in ("Square.area", "Circle.area"):
            self.assertEqual(self.group_shares(name, lambda c: c[0]), 1.0)
        # helper(int) and helper(float) share a target: one entry in an inline cache, two specializations
        receiver = typeprofile.summarize(self.data)["views"]["send site: target and receiver class"]
        classes = typeprofile.summarize(self.data)["views"]["send site: target and classes"]
        self.assertGreater(receiver["mono"], classes["mono"])
        self.assertLess(receiver["mono"], 1.0)
        top = self.summary["polymorphic_sites"]
        self.assertTrue(any("Square.area" in " ".join(p["top"]) and "Circle.area" in " ".join(p["top"]) for p in top))

    def test_deep_types_and_their_pystachy_reasons(self):
        reasons = self.data["reasons"]
        seen = {tuple(self.data["sigs"][c[5]]) for c in self.calls_of("take")}
        expected = {("list[int]",): "", ("list[int|str]",): "mixed list", ("dict[float:int]",): "unsupported key type float",
                    ("dict[str:list[int]]",): "", ("int>64",): "int beyond 64 bits",
                    ("tuple[int,str]",): "", ("list[dict[str:bool]]",): "", ("list[tuple[]|tuple[int]]",): "mixed list"}
        for sig, reason in expected.items():
            self.assertIn(sig, seen)
            self.assertEqual(reasons[sig[0]], reason, sig)
        derived = next(s for s in seen if s[0].endswith("Derived"))
        self.assertEqual(reasons[derived[0]], "inheritance")

    def test_optional_returns_are_stable_and_mixed_returns_are_not(self):
        codes = self.data["codes"]
        by_name = {}
        for code, sig, rtype, n in self.data["returns"]:
            by_name.setdefault(codes[code]["qualname"], set()).add(rtype)
        self.assertEqual(by_name["maybe"], {"int", "None"})
        self.assertEqual(by_name["mixed"], {"int", "str"})
        self.assertLess(self.summary["returns_determined_by_arg_types"], 1.0)

    def test_fields_are_sampled_when_init_returns(self):
        fields = {(owner, attr): ftype for owner, attr, ftype, n in self.data["fields"]}
        square = next(owner for owner, attr in fields if owner.endswith("Square"))
        self.assertEqual(fields[square, "side"], "int")
        self.assertEqual(fields[square, "label"], "None")

    def test_views_refine_monotonically(self):
        views = self.summary["views"]
        self.assertLessEqual(views["function: Pystachy types"]["top1"], views["function + call site: Pystachy types"]["top1"])
        self.assertLessEqual(views["function + call site: Pystachy types"]["top1"], views["function + call string of 2: Pystachy types"]["top1"])


if __name__ == "__main__":
    unittest.main()
