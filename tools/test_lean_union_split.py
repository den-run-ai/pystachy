"""Split union locals and union payload bits: each read of payload bits as a member's, each box
made of a tag and bits and each stored tag/payload pair is a Lean obligation.

Each refutation corrupts actual compiler IR of examples/union_split.py, whose locals unionslots
splits into a tag slot and a payload slot; Lean must reject it, or the adapter refuse it, while
the original stays proved.
"""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import check_lean_boundary as boundary
import check_lean_guards as guards

ROOT = Path(__file__).resolve().parent.parent
CHECKER = boundary.DEFAULT_CHECKER
EXAMPLE = ROOT / "tools/lean_boundary/examples/union_split.py"


def inspect(program, directory):
    env = {key: value for key, value in os.environ.items() if not key.startswith("PYSTACHY_")}
    env["PYSTACHY_HOME"] = str(ROOT)
    result = subprocess.run([sys.executable, str(ROOT / "tools/inspect_compiler.py"), str(program),
                             "--output", str(directory), "--guard-evidence", "--typed-after-only"],
                            cwd=ROOT, env=env, capture_output=True, text=True, timeout=60)
    if result.returncode:
        raise AssertionError(result.stdout + result.stderr)
    return json.loads((directory / "typed-after.json").read_text())


class UnionSplitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not CHECKER.is_file():
            if os.environ.get("LEAN_BOUNDARY_REQUIRED") == "1":
                raise RuntimeError("Lean checker required for split union controls")
            raise unittest.SkipTest("build the Lean boundary checker")
        with tempfile.TemporaryDirectory() as temporary:
            cls.snapshot = inspect(EXAMPLE, Path(temporary) / "split")
        cls.tags = {member: str(tag) for member, tag in cls.snapshot["union_tags"].items()}

    def sample(self):
        return copy.deepcopy(self.snapshot)

    @staticmethod
    def function(snapshot, name):
        return next(fn for fn in snapshot["functions"] if fn["symbol"] == "@f." + name)

    @staticmethod
    def operations(function):
        return [(block, offset, op) for block in function["blocks"] for offset, op in enumerate(block["operations"])]

    def pair_stores(self, function):
        """Each split pair store: (its block, the tag store's offset, the tag and payload stores)."""
        tags = {record["tag"] for record in function["split_unions"]}
        return [(block, offset, op, block["operations"][offset + 1]) for block, offset, op in self.operations(function)
                if op["op"] == "mem.store" and op["operands"][0]["value"] in tags]

    def tag_test(self, function):
        """The tag test of a pair load's tag value, and the branch on it."""
        tags = {record["tag"] for record in function["split_unions"]}
        loaded = {f"%t{op['results'][0]}" for _, _, op in self.operations(function)
                  if op["op"] == "mem.load" and op["operands"][0]["value"] in tags}
        for block, offset, op in self.operations(function):
            if op["op"] == "num.cmp" and op["operands"][0]["value"] in loaded:
                return op, block["operations"][-1]
        raise AssertionError("no tag test")

    def producer(self, function, value):
        return next((op for _, _, op in self.operations(function) if value in (f"%t{n}" for n in op["results"])), None)

    def lean(self, snapshot, name):
        function = self.function(snapshot, name)
        candidate, metadata = guards.normalize(snapshot, function, immutable_boxes=True)
        metadata.pop("origins")
        return boundary.run_checker(CHECKER, boundary.encode(candidate), metadata)

    def test_example_proves_every_split_payload(self):
        for name, typ in (("accumulate", "union[float,int]"), ("maybe", "opt[int]"), ("bump", "union[float,int]"),
                          ("lookup", "opt[int]"), ("total", "opt[int]"), ("drain.1", "opt[int]")):
            self.assertEqual([record["type"] for record in self.function(self.snapshot, name)["split_unions"]], [typ])
        report, code = guards.check_all(self.sample(), CHECKER)
        self.assertEqual(code, 0, report)
        self.assertGreaterEqual(report["payload_obligations"], 20)
        self.assertEqual(report["proved_payload_obligations"], report["payload_obligations"])
        self.assertEqual(report["proved_union_reads"], report["union_reads"])
        # (accumulate returns a box made again of its pair's tag and bits)
        self.assertEqual((report["union_returns"], report["proved_union_returns"]), (2, 2))

    def test_split_corruptions_are_rejected(self):
        def literal_tag(snapshot):  # float bits stored with int's tag
            function = self.function(snapshot, "accumulate")
            for _, _, tag, payload in self.pair_stores(function):
                made = self.producer(function, payload["operands"][1]["value"])
                if made is not None and made["op"] == "slot.pack" and made["operands"][0]["type"] == "float" and tag["operands"][1]["value"].isdigit():
                    tag["operands"][1]["value"] = self.tags["int"]
                    return "accumulate"
            raise AssertionError("no float pair")

        def swapped_phi(snapshot):  # each edge's tag the other edge's
            function = self.function(snapshot, "accumulate")
            for _, _, tag, _ in self.pair_stores(function):
                made = self.producer(function, tag["operands"][1]["value"])
                if made is not None and made["op"] == "phi":
                    made["operands"].reverse()
                    return "accumulate"
            raise AssertionError("no pair phi")

        def other_member(snapshot):  # the float branch taken for an int
            test, _ = self.tag_test(self.function(snapshot, "bump"))
            test["operands"][1]["value"] = self.tags["int"] if test["operands"][1]["value"] == self.tags["float"] else self.tags["float"]
            return "bump"

        def no_test(snapshot):
            _, branch = self.tag_test(self.function(snapshot, "bump"))
            branch["operands"][0]["value"] = "true"
            return "bump"

        def none_payload(snapshot):  # the payload read where the optional is None
            test, _ = self.tag_test(self.function(snapshot, "maybe"))
            test["text"] = "==" if test["text"] == "!=" else "!="
            return "maybe"

        def int_word_as_float(snapshot):  # total = 0 stored with float's tag
            function = self.function(snapshot, "accumulate")
            _, _, tag, payload = self.pair_stores(function)[0]
            self.assertEqual((tag["operands"][1]["value"], payload["operands"][1]["value"]), (self.tags["int"], "0"))
            tag["operands"][1]["value"] = self.tags["float"]
            return "accumulate"

        def boxed_with_other_tag(snapshot):  # value + 1.0 boxed with int's tag
            function = self.function(snapshot, "bump")
            box = next(op for _, _, op in self.operations(function) if op["op"] == "rt" and op["text"] == "ubox"
                       and op["operands"][0]["value"] == self.tags["float"])
            box["operands"][0]["value"] = self.tags["int"]
            return "bump"

        def appended_when_none(snapshot):  # next()'s None appended to a list[int] as an int
            test, _ = self.tag_test(self.function(snapshot, "drain.1"))
            test["text"] = "!=" if test["text"] == "==" else "=="
            return "drain.1"

        def read_as_other_member(snapshot):  # an int payload formatted as a float
            function = self.function(snapshot, "describe")
            show = next(op for _, _, op in self.operations(function) if op["op"] == "rt" and op["text"] == "str.int")
            show["text"], show["operands"][0]["type"] = "str.float", "float"
            return "describe"

        for corruption in (literal_tag, swapped_phi, other_member, no_test, none_payload, int_word_as_float,
                           boxed_with_other_tag, appended_when_none, read_as_other_member):
            with self.subTest(corruption=corruption.__name__):
                snapshot = self.sample()
                name = corruption(snapshot)
                self.assertTrue(self.lean(self.sample(), name))
                self.assertFalse(self.lean(snapshot, name))

    def test_split_slots_beyond_the_model_are_refused(self):
        def unrecorded(function):
            del function["split_unions"]

        def unpaired(function):
            block, offset, _, _ = self.pair_stores(function)[0]
            del block["operations"][offset + 1]

        def untyped(function):
            # (a split pair's own payload bits made a box of no tag the adapter knows)
            box = next(op for _, _, op in self.operations(function) if op["op"] == "rt" and op["text"] == "ubox"
                       and not op["operands"][0]["value"].isdigit())
            box["operands"][1]["value"] = box["operands"][0]["value"]

        def missed_lookup(function):
            # (presence set where the lookup missed: no longer its payload's)
            test = next(op for _, _, op in self.operations(function) if op["op"] == "num.cmp" and op["text"] == ">=")
            test["text"] = "<"

        for change, name, message in ((unrecorded, "accumulate", "without their inspection record"),
                                      (unpaired, "accumulate", "without its payload"),
                                      (untyped, "accumulate", "dynamic union reconstruction"),
                                      (missed_lookup, "lookup", "parts of no one box")):
            with self.subTest(change=change.__name__):
                snapshot = self.sample()
                change(self.function(snapshot, name))
                with self.assertRaisesRegex(boundary.Unsupported, message):
                    self.lean(snapshot, name)


if __name__ == "__main__":
    unittest.main()
