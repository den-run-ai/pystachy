"""Check the unchecked-access bridge on real IR, and that Lean rejects each corruption of it.

The corruptions replay the shapes of bugs that the compiler's own passes once had: a list
shortened between a length test and an unchecked read, a dict entry reused after a dict write
or in another dict, and a field reloaded across a write that may alias it.
"""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import check_lean_access as access
from check_lean_access import Unsupported, check_all, explain, normalize_snapshot


ROOT = Path(__file__).resolve().parent.parent
PROJECT = ROOT / "tools" / "lean_boundary"
CHECKER = PROJECT / ".lake" / "build" / "bin" / "pystachy-access"
TOOL = ROOT / "tools" / "check_lean_access.py"
EXAMPLE = PROJECT / "examples" / "unchecked_accesses.py"

if os.environ.get("LEAN_BOUNDARY_REQUIRED") == "1" and not CHECKER.is_file():
    raise RuntimeError("Lean access checker is required; build tools/lean_boundary first")


def op(kind, operands=(), results=(), text="", typ="", targets=(), immediate=0, descriptor=""):
    return {"op": kind, "type": typ, "text": text, "immediate": immediate, "descriptor": descriptor,
            "results": list(results), "operands": [{"value": value, "type": kind_}
                                                   for value, kind_ in operands],
            "targets": list(targets)}


class NegatedComparisonTests(unittest.TestCase):
    @staticmethod
    def snapshot(kind, negations, safe_branch=True):
        if kind == "list":
            prefix = [op("list.len", [("%a0", "list[int]")], [1], typ="int"),
                      op("int.ucmp", [("%a1", "int"), ("%t1", "int")], [2], text="<", typ="bool")]
            read = op("list.load", [("%a0", "list[int]"), ("%a1", "int")], [50, 51, 52, 53], typ="int")
        else:
            prefix = [op("rt", [("%a0", "dict[str,int]"), ("%a1", "str")], [1],
                         text="dict.find", typ="int", descriptor="S"),
                      op("num.cmp", [("%t1", "int"), ("-1", "int")], [2], text="!=", typ="bool")]
            read = op("rt", [("%a0", "dict[str,int]"), ("%t1", "int")], [50], text="dict.val", typ="int")
        flag = "%t2"
        for index in range(negations):
            number = 3 + index
            prefix.append(op("scalar.bin", [(flag, "bool"), ("true", "bool")], [number], text="xor", typ="bool"))
            flag = f"%t{number}"
        # Both original comparisons hold exactly on the safe path. Each Boolean
        # negation swaps that branch; the corruption selects its unsafe complement.
        targets = ["read", "done"] if (negations % 2 == 0) == safe_branch else ["done", "read"]
        prefix.append(op("cbr", [(flag, "bool")], targets=targets))
        function = {"name": "guarded", "symbol": "@f.guarded", "recursion": {}, "slots": [],
                    "blocks": [{"label": "entry", "handler": "", "operations": prefix},
                               {"label": "read", "handler": "", "operations": [read, op("ret")]},
                               {"label": "done", "handler": "", "operations": [op("ret")]}]}
        return {"schema_version": 1, "stage": "typed-after", "status": "completed", "functions": [function]}

    def test_negated_list_guard_preserves_safe_branch(self):
        for negations in (0, 1, 2, 3):
            with self.subTest(negations=negations):
                candidate, metadata = normalize_snapshot(self.snapshot("list", negations), "@f.guarded")
                self.assertEqual(metadata["unproved"], 0)
                self.assertIsNone(explain(candidate))

    def test_negated_missing_entry_guard_preserves_comparison_polarity(self):
        for negations in (0, 1, 2, 3):
            with self.subTest(negations=negations):
                candidate, metadata = normalize_snapshot(self.snapshot("dict", negations), "@f.guarded")
                self.assertEqual(metadata["unproved"], 0)
                self.assertIsNone(explain(candidate))

    def test_selecting_the_complement_cannot_justify_an_unchecked_access(self):
        for kind in ("list", "dict"):
            for negations in (0, 1, 2, 3):
                with self.subTest(kind=kind, negations=negations):
                    candidate, metadata = normalize_snapshot(self.snapshot(kind, negations, False), "@f.guarded")
                    self.assertEqual(metadata["unproved"], 1)
                    self.assertIsNotNone(explain(candidate))


class EntryAccessInventoryTests(unittest.TestCase):
    HELPERS = ("set.slot_del", "dict.val_or_zero", "dict.eq_find", "dict.eq_pair_find")

    @staticmethod
    def snapshot(helper, *, lookup=True, guarded=True, stale=False, index=None, after=(), invoke=False):
        table_type = "set[int]" if helper == "set.slot_del" else "dict[str,int]"
        table = ("%a0", table_type)
        prefix = []
        if lookup:
            find = "set.int_find_any" if helper == "set.slot_del" else "dict.find"
            key_type = "%ptr" if helper == "set.slot_del" else "str"
            prefix.append(op("rt", [table, ("%a1", key_type)], [1], text=find, typ="int", descriptor="S"))
        entry = index if index is not None else ("%t1" if lookup else "%a1")
        if guarded:
            prefix += [op("num.cmp", [(entry, "int"), ("-1", "int")], [2], text="!=", typ="bool"),
                       op("cbr", [("%t2", "bool")], targets=["read", "done"])]
        else:
            prefix.append(op("br", targets=["read"]))
        operands = [table, (entry, "int")]
        if helper.startswith("dict.eq_"):
            operands = [("%a2", "dict[str,int]"), table, (entry, "int")]
            if helper == "dict.eq_pair_find":
                operands.append(("%a3", "%ptr"))
        read = op("rt", operands, [] if helper == "set.slot_del" else [3], text=helper,
                  typ="None" if helper == "set.slot_del" else "int", descriptor="H1",
                  targets=["done", "handler"] if invoke else [])
        code = ([op("rt", [table], text="set.clear" if helper == "set.slot_del" else "dict.clear")]
                if stale else []) + [read]
        if not invoke:
            code += list(after) + [op("ret")]
        blocks = [{"label": "entry", "handler": "", "operations": prefix},
                  {"label": "read", "handler": "", "operations": code},
                  {"label": "done", "handler": "", "operations": [op("ret")]}]
        if invoke:
            blocks.append({"label": "handler", "handler": "", "operations": list(after) + [op("ret")]})
        function = {"name": "inventory", "symbol": "@f.inventory", "recursion": {}, "slots": [], "blocks": blocks}
        return {"schema_version": 1, "stage": "typed-after", "status": "completed", "functions": [function]}

    def assert_verdict(self, snapshot, expected):
        candidate, metadata = normalize_snapshot(snapshot, "@f.inventory")
        self.assertEqual(explain(candidate) is None, expected, explain(candidate))
        if CHECKER.is_file():
            self.assertEqual(access.run_checker(CHECKER, access.encode(candidate), metadata), expected)
        return metadata

    def test_every_direct_entry_helper_is_selected_and_counted(self):
        for helper in self.HELPERS:
            with self.subTest(helper=helper):
                snapshot = self.snapshot(helper, lookup=False, guarded=False)
                self.assertEqual(access.access_functions(snapshot), [("@f.inventory", 1)])
                _, metadata = normalize_snapshot(snapshot, "@f.inventory")
                self.assertEqual(metadata["dict_entries"], 1)
                self.assertEqual(metadata["accesses"], 1)

    def test_live_entries_pass_and_unguarded_or_stale_entries_reject(self):
        for helper in self.HELPERS:
            with self.subTest(helper=helper):
                self.assert_verdict(self.snapshot(helper), True)
                self.assert_verdict(self.snapshot(helper, lookup=False, guarded=False), False)
                self.assert_verdict(self.snapshot(helper, stale=True), False)
                alias = self.snapshot(helper, stale=True)
                alias["functions"][0]["blocks"][1]["operations"][0]["operands"][0]["value"] = "%a4"
                self.assert_verdict(alias, False)  # (a write through any alias invalidates the entry)

    def test_optional_entry_read_preserves_its_negative_no_read_path(self):
        self.assert_verdict(self.snapshot("dict.val_or_zero", guarded=False), True)
        for index in ("-1", "-2", str(access.MIN_I64)):
            with self.subTest(index=index):
                snapshot = self.snapshot("dict.val_or_zero", lookup=False, guarded=False, index=index)
                self.assertEqual(access.access_functions(snapshot), [("@f.inventory", 1)])
                self.assertEqual(self.assert_verdict(snapshot, True)["dict_entries"], 1)
                if CHECKER.is_file():
                    report, code = check_all(snapshot, CHECKER)
                    self.assertEqual((code, report["totals"]["accesses"], report["totals"]["proved_accesses"]),
                                     (0, 1, 1))
        self.assert_verdict(self.snapshot("dict.val_or_zero", lookup=False, guarded=False, index="0"), False)

    def test_set_deletion_invalidates_entries_after_checking_its_own(self):
        after = [op("rt", [("%a0", "set[int]"), ("%t1", "int")], [4], text="set.key", typ="int")]
        self.assert_verdict(self.snapshot("set.slot_del", after=after), False)

    def test_equality_lookup_checks_source_before_callback_invalidation(self):
        after = [op("rt", [("%a0", "dict[str,int]"), ("%t1", "int")], [4], text="dict.val", typ="int")]
        for helper in ("dict.eq_find", "dict.eq_pair_find"):
            with self.subTest(helper=helper):
                self.assert_verdict(self.snapshot(helper), True)
                self.assert_verdict(self.snapshot(helper, after=after), False)
                self.assert_verdict(self.snapshot(helper, after=after, invoke=True), False)

    def test_equality_lookup_result_still_belongs_to_its_target(self):
        for helper in ("dict.eq_find", "dict.eq_pair_find"):
            with self.subTest(helper=helper):
                snapshot = self.snapshot(helper)
                blocks = snapshot["functions"][0]["blocks"]
                blocks[1]["operations"][-1:] = [
                    op("num.cmp", [("%t3", "int"), ("-1", "int")], [4], text="!=", typ="bool"),
                    op("cbr", [("%t4", "bool")], targets=["target_read", "done"])]
                blocks.append({"label": "target_read", "handler": "", "operations": [
                    op("rt", [("%a2", "dict[str,int]"), ("%t3", "int")], [5], text="dict.val", typ="int"),
                    op("ret")]})
                self.assert_verdict(snapshot, True)


class SnapshotFixture(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temporary.cleanup)
        output = Path(cls.temporary.name) / "inspection"
        env = {key: value for key, value in os.environ.items() if not key.startswith("PYSTACHY_")}
        env["PYSTACHY_HOME"] = str(ROOT)
        completed = subprocess.run(
            [sys.executable, str(ROOT / "tools" / "inspect_compiler.py"), str(EXAMPLE),
             "--output", str(output), "--typed-after-only"],
            cwd=ROOT, env=env, capture_output=True, text=True, timeout=120)
        if completed.returncode:
            raise AssertionError(completed.stdout + completed.stderr)
        cls.snapshot_path = output / "typed-after.json"
        cls.snapshot = json.loads(cls.snapshot_path.read_text())

    def selected(self, symbol):
        snapshot = copy.deepcopy(self.snapshot)
        function = next(fn for fn in snapshot["functions"] if fn["symbol"] == symbol)
        return snapshot, function

    @staticmethod
    def find(function, kind, text=None):
        return next((block, index) for block in function["blocks"]
                    for index, operation in enumerate(block["operations"])
                    if operation["op"] == kind and (text is None or operation["text"] == text))

    @staticmethod
    def definition(function, value):
        return next(operation for block in function["blocks"] for operation in block["operations"]
                    if operation["results"] and f"%t{operation['results'][0]}" == value)


class AdapterTests(SnapshotFixture):
    def test_every_access_of_the_example_is_normalized_without_changing_the_snapshot(self):
        original = copy.deepcopy(self.snapshot)
        counts = {}
        for symbol, count in access.access_functions(self.snapshot):
            candidate, metadata = normalize_snapshot(self.snapshot, symbol)
            counts[symbol] = metadata["accesses"]
            self.assertEqual(metadata["accesses"], count)
            self.assertEqual(metadata["unproved"], 0, symbol)
            self.assertEqual(candidate["certificate"][0], [])
        self.assertEqual(self.snapshot, original)
        self.assertEqual({symbol: count for symbol, count in counts.items() if not symbol.startswith("@m._")},
                         {"@f.item": 1, "@f.last": 1, "@f.pair": 2, "@f.ends": 2, "@f.tail3": 4,
                          "@f.class_lookup": 2, "@f.total": 1, "@f.odd_lengths": 1, "@f.ranked": 1,
                          "@f.counted": 3, "@f.global_lookup": 1, "@f.smoothed": 4, "@f.pairs": 4, "@f.shifted": 2,
                          "@m.Cache.lookup": 1})

    def test_selection_and_snapshot_header_are_checked(self):
        with self.assertRaisesRegex(ValueError, "exactly one function"):
            normalize_snapshot(self.snapshot, "@f.missing")
        partial = dict(self.snapshot, status="failed")
        with self.assertRaises(Unsupported):
            normalize_snapshot(partial, "@f.item")

    def test_a_generator_forgets_lengths_entries_and_fields_where_it_yields(self):
        # (its caller runs while it is suspended); an unknown terminator stays unsupported
        candidate, _ = normalize_snapshot(self.snapshot, "@f.every_other.1")
        nodes = candidate["program"]["nodes"]
        kills = {node["op"] for node in nodes if node["op"] in ("lists", "dicts", "heap")}
        self.assertEqual(kills, {"lists", "dicts", "heap"})
        snapshot, function = self.selected("@f.item")
        function["blocks"][-1]["operations"][-1]["op"] = "unreachable.other"
        with self.assertRaises(Unsupported):
            normalize_snapshot(snapshot, "@f.item")

    def test_a_use_its_definition_does_not_dominate_is_malformed(self):
        # (the model reads a test's operands where its branch uses it: SSA must hold)
        snapshot, function = self.selected("@f.item")
        block, index = self.find(function, "list.load")
        function["blocks"][0]["operations"].insert(0, block["operations"].pop(index))
        with self.assertRaisesRegex(ValueError, "dominate"):
            normalize_snapshot(snapshot, "@f.item")

    def test_possible_user_code_follows_the_operations_descriptor(self):
        # (a dict of str keys runs no __eq__; one keyed by objects may run anything)
        self.assertEqual(access.runtime_effects("dict.find", "S"), {"rD"})
        self.assertIsNone(access.runtime_effects("dict.find", "H3"))
        self.assertIsNone(access.runtime_effects("no.such.operation"))
        self.assertEqual(access.kills({"rL", "wL"}), (True, False, False, False))
        self.assertEqual(access.kills(None), (True, True, True, True))


@unittest.skipUnless(CHECKER.is_file() or os.environ.get("LEAN_BOUNDARY_REQUIRED") == "1",
                     "build tools/lean_boundary first")
class ProvedCheckerTests(SnapshotFixture):
    def check(self, candidate):
        completed = subprocess.run([str(CHECKER)], input=json.dumps(candidate),
                                   capture_output=True, text=True, timeout=60)
        self.assertIn(completed.returncode, (0, 1), completed.stdout + completed.stderr)
        result = json.loads(completed.stdout)
        self.assertEqual(result["accepted"], completed.returncode == 0)
        # (the Python mirror that explains a rejection agrees with Lean)
        self.assertEqual(explain(candidate) is None, result["accepted"], explain(candidate))
        return result["accepted"]

    def verdict(self, snapshot, symbol):
        return self.check(normalize_snapshot(snapshot, symbol)[0])

    def test_every_access_of_the_example_is_proved(self):
        fields, code = check_all(self.snapshot, CHECKER)
        self.assertEqual((fields["status"], code), ("accepted", 0), fields)
        self.assertEqual(fields["totals"]["proved_accesses"], 30)
        self.assertEqual(fields["totals"]["accesses"], 30)

    def test_negated_guards_prove_only_the_safe_branch(self):
        for kind in ("list", "dict"):
            for negations in (0, 1, 2, 3):
                for safe_branch in (False, True):
                    with self.subTest(kind=kind, negations=negations, safe_branch=safe_branch):
                        snapshot = NegatedComparisonTests.snapshot(kind, negations, safe_branch)
                        self.assertEqual(self.verdict(snapshot, "@f.guarded"), safe_branch)

    def test_identical_functions_reuse_their_verdicts(self):
        # (a corpus's programs share library functions: their normalized nodes and the checker,
        # not their names, key the reuse, so a changed function is checked again)
        verdicts = {}
        calls = []
        real = access.run_checker

        def counted(*arguments, **keywords):
            calls.append(arguments)
            return real(*arguments, **keywords)

        with mock.patch.object(access, "run_checker", counted):
            first, _ = check_all(self.snapshot, CHECKER, verdicts)
            checked = len(calls)
            self.assertGreater(checked, 0)
            second, _ = check_all(self.snapshot, CHECKER, verdicts)
            self.assertEqual(len(calls), checked)
            self.assertEqual(first["functions"], second["functions"])
            snapshot, function = self.selected("@f.total")
            block, index = self.find(function, "list.load")
            listed = block["operations"][index]["operands"][0]["value"]
            block["operations"].insert(index, op("rt", [(listed, "list[int]")], text="list.clear"))
            third, _ = check_all(snapshot, CHECKER, verdicts)
            self.assertEqual(len(calls), checked + 1)
            self.assertEqual(third["status"], "rejected")

    def test_a_list_write_between_the_loop_test_and_the_read_rejects(self):
        snapshot, function = self.selected("@f.total")
        block, index = self.find(function, "list.load")
        listed = block["operations"][index]["operands"][0]["value"]
        block["operations"].insert(index, op("rt", [(listed, "list[int]")], text="list.clear"))
        self.assertFalse(self.verdict(snapshot, "@f.total"))

    def test_a_range_loop_that_shortens_its_list_after_the_read_rejects(self):
        # (the length read before the loop is stale on the next iteration)
        snapshot, function = self.selected("@f.odd_lengths")
        block, index = self.find(function, "list.load")
        listed = block["operations"][index]["operands"][0]["value"]
        block["operations"].insert(index + 1, op("rt", [(listed, "list[str]")], text="list.clear"))
        self.assertFalse(self.verdict(snapshot, "@f.odd_lengths"))

    def test_a_signed_test_or_another_list_does_not_bound_the_read(self):
        snapshot, function = self.selected("@f.item")
        block, index = self.find(function, "int.ucmp")
        block["operations"][index].update(op="num.cmp")
        self.assertFalse(self.verdict(snapshot, "@f.item"))
        # (the parameter is the tested list itself; a new list is another)
        snapshot, function = self.selected("@f.item")
        block, index = self.find(function, "list.load")
        block["operations"][index]["operands"][0]["value"] = "%a0"
        self.assertTrue(self.verdict(snapshot, "@f.item"))
        block["operations"].insert(index, op("rt", [("4", "int")], results=[900], text="list.new", typ="list[int]"))
        block["operations"][index + 1]["operands"][0]["value"] = "%t900"
        self.assertFalse(self.verdict(snapshot, "@f.item"))

    def test_a_range_loop_read_in_a_generator_cannot_be_unchecked(self):
        # (listget leaves it checked: a pass that ignored the yield would read past a list the
        # caller shortened)
        snapshot, function = self.selected("@f.every_other.1")
        block, index = self.find(function, "rt", "list.get")
        block["operations"][index].update(op="list.load", text="")
        self.assertFalse(self.verdict(snapshot, "@f.every_other.1"))

    def test_unpacking_needs_its_length_check(self):
        snapshot, function = self.selected("@f.pair")
        block, index = self.find(function, "rt", "unpack_check")
        del block["operations"][index]
        self.assertFalse(self.verdict(snapshot, "@f.pair"))
        snapshot, function = self.selected("@f.pair")
        block, index = self.find(function, "rt", "unpack_check")
        block["operations"][index]["operands"][1]["value"] = "1"
        self.assertFalse(self.verdict(snapshot, "@f.pair"))

    def test_a_reused_entry_needs_the_found_branch_and_no_dict_write(self):
        # (the missing key's branch, a dict write and a rebound dict: dictfuse's past bugs)
        snapshot, function = self.selected("@f.counted")
        block, index = self.find(function, "cbr")
        block["operations"][index]["targets"].reverse()
        self.assertFalse(self.verdict(snapshot, "@f.counted"))
        snapshot, function = self.selected("@f.counted")
        block, index = self.find(function, "rt", "dict.val")
        reused = block["operations"][index]["operands"][0]["value"]
        block["operations"].insert(index, op("rt", [(reused, "dict[str,int]")], text="dict.clear"))
        self.assertFalse(self.verdict(snapshot, "@f.counted"))
        snapshot, function = self.selected("@f.counted")
        block, index = self.find(function, "rt", "dict.val")
        block["operations"][index:index] = [
            op("rt", [("1", "int"), ("1", "int")], results=[900], text="dict.new", typ="dict[str,int]"),
            op("mem.store", [("%d.2", "*dict[str,int]"), ("%t900", "dict[str,int]")])]
        self.assertFalse(self.verdict(snapshot, "@f.counted"))

    def test_a_lookup_or_minus_one_through_a_phi_keeps_its_entry(self):
        # (e = -1 if not d else lookup(d, k), as dynamic Any's int-key lookups compile: the phi
        # holds -1 or the lookup's entry, still live where nothing runs between them)
        def through_phi(between=(), other="-1", typ="int"):
            snapshot, function = self.selected("@f.counted")
            entry = function["blocks"][0]
            at = next(index for index, operation in enumerate(entry["operations"])
                      if operation["text"] == "dict.find")
            find, rest = entry["operations"][at], entry["operations"][at + 1:]
            found = f"%t{find['results'][0]}"
            table = find["operands"][0]["value"]
            entry["operations"][at:] = [
                op("mach.load", [(table, "%ptr")], [900], typ="int"),
                op("num.cmp", [("%t900", "int"), ("0", "int")], [901], text="==", typ="bool"),
                op("cbr", [("%t901", "bool")], targets=["Lphi", "Llook"])]
            phi = op("phi", [(other, typ), (found, typ)], [902], typ=typ, targets=[entry["label"], "Llook"])
            for operation in rest + [operation for block in function["blocks"][1:]
                                     for operation in block["operations"]]:
                for operand in operation["operands"]:
                    if operand["value"] == found:
                        operand["value"] = "%t902"
            function["blocks"][1:1] = [
                {"label": "Llook", "handler": "", "operations": [find, *between, op("br", targets=["Lphi"])]},
                {"label": "Lphi", "handler": "", "operations": [phi, *rest]}]
            return self.verdict(snapshot, "@f.counted"), table

        accepted, table = through_phi()
        self.assertTrue(accepted)
        self.assertTrue(through_phi(typ="%slot")[0])  # (as promoting-int lookups type it)
        self.assertFalse(through_phi(between=[op("rt", [(table, "dict[str,int]")], text="dict.clear")])[0])
        self.assertFalse(through_phi(other="0")[0])

    def test_a_starred_tail_read_stays_below_the_length_but_one_further_does_not(self):
        # (a, *m, c, d, e = xs reads len - 3 + 2: an exact offset of a length, which cannot wrap)
        self.assertTrue(self.verdict(self.snapshot, "@f.tail3"))
        snapshot, function = self.selected("@f.tail3")
        add = next(operation for block in function["blocks"] for operation in block["operations"]
                   if operation["op"] == "scalar.bin" and operation["text"] == "add"
                   and operation["operands"][1]["value"] == "2")
        add["operands"][1]["value"] = "3"  # (len - 3 + 3 is the length itself)
        self.assertFalse(self.verdict(snapshot, "@f.tail3"))

    def test_a_class_variable_reload_keeps_its_entry_unless_it_is_stored_between(self):
        self.assertTrue(self.verdict(self.snapshot, "@f.class_lookup"))
        snapshot, function = self.selected("@f.class_lookup")
        block, _ = self.find(function, "rt", "dict.val")
        reload = next(index for index, operation in enumerate(block["operations"])
                      if operation["op"] == "mach.load" and operation["operands"][0]["value"].startswith("@"))
        table = block["operations"][reload]["operands"][0]["value"]
        # (Registry.names = <another value> before the reload: the entry belongs to the old dict)
        block["operations"].insert(reload, op("mach.store", [(table, "%ptr"), ("%a0", "str")]))
        self.assertFalse(self.verdict(snapshot, "@f.class_lookup"))

    def test_another_field_of_the_class_keeps_the_dict_but_an_aliasing_view_does_not(self):
        self.assertTrue(self.verdict(self.snapshot, "@m.Cache.lookup"))
        for aliasing in (None, "the dict's own field", "another class's view"):
            for constant in (False, True):
                snapshot, function = self.selected("@m.Cache.lookup")
                # (self.hits += 1 stores through a field address: make it the dict's field, or a
                # field of another class, which may view the same object; a constant stored, as
                # where numeric identity clears a field's companion, writes that field alone too)
                store = next(operation for block in function["blocks"] for operation in block["operations"]
                             if operation["op"] == "mem.store" and operation["operands"][0]["value"].startswith("%t"))
                field = self.definition(function, store["operands"][0]["value"])
                if constant:
                    store["operands"][1]["value"] = "0"
                if aliasing == "the dict's own field":
                    field["immediate"] = 1
                elif aliasing == "another class's view":
                    field["operands"][0]["type"] = "object"
                self.assertEqual(self.verdict(snapshot, "@m.Cache.lookup"), aliasing is None, (aliasing, constant))

    def test_a_guarded_copy_is_proved_and_each_corruption_of_its_tests_rejects(self):
        # (listguard: the copy's unchecked reads and stores of xs[i + c] hold where the tests
        # before the loop found the stop at most len(xs) - c)
        for symbol in ("@f.smoothed", "@f.pairs", "@f.shifted"):
            self.assertTrue(self.verdict(copy.deepcopy(self.snapshot), symbol), symbol)
        # (a 1-based loop's test against len(xs) + 2 lets xs[i - 1] reach the length)
        snapshot, function = self.selected("@f.shifted")
        block, index = self.find(function, "scalar.bin", "sub")
        self.assertEqual(block["operations"][index]["operands"][1]["value"], "-1")
        block["operations"][index]["operands"][1]["value"] = "-2"
        self.assertFalse(self.verdict(snapshot, "@f.shifted"))

        def further(symbol):
            # (the copy's read of xs[i + 1] reads xs[i + 2]: one past what the test allows)
            snapshot, function = self.selected(symbol)
            sums = {f"%t{operation['results'][1]}": operation for block in function["blocks"]
                    for operation in block["operations"]
                    if operation["op"] == "ovf" and operation["text"] == "+" and len(operation["results"]) == 3}
            # (the copy's blocks follow the loop's: its last read of one, unchecked; the loop's own
            # inline reads test the index they read, also a further one)
            read = [operation for block in function["blocks"] for operation in block["operations"]
                    if operation["op"] == "list.load" and operation["operands"][1]["value"] in sums][-1]
            sums[read["operands"][1]["value"]]["operands"][1]["value"] = "2"
            return snapshot

        def lowered(symbol):
            # (the test before the loop checks the stop against len(xs), not len(xs) - 1)
            snapshot, function = self.selected(symbol)
            block, index = self.find(function, "scalar.bin", "sub")
            block["operations"][index]["operands"][1]["value"] = "0"
            return snapshot

        def shortened(symbol):
            # (the copy shortens a list before a read: the length the test read is stale)
            snapshot, function = self.selected(symbol)
            block, index = [(block, index) for block in function["blocks"]
                            for index, operation in enumerate(block["operations"])
                            if operation["op"] == "list.load"][-1]
            listed = block["operations"][index]["operands"][0]
            block["operations"].insert(index, op("rt", [(listed["value"], listed["type"])], text="list.clear"))
            return snapshot

        for symbol in ("@f.smoothed", "@f.pairs"):
            for corrupt in (further, lowered, shortened):
                self.assertFalse(self.verdict(corrupt(symbol), symbol), (symbol, corrupt.__name__))

    def test_a_global_write_between_reloads_rejects(self):
        # (TABLE = {} after the lookup and before its reload: the entry belongs to another dict)
        snapshot, function = self.selected("@f.global_lookup")
        block, index = self.find(function, "rt", "dict.val")
        reloaded = block["operations"][index]["operands"][0]["value"]
        block, index = next((b, i) for b in function["blocks"] for i, o in enumerate(b["operations"])
                            if o["results"] and f"%t{o['results'][0]}" == reloaded)
        address = block["operations"][index]["operands"][0]["value"]
        self.assertTrue(address.startswith("@"))
        block["operations"][index:index] = [
            op("rt", [("1", "int"), ("1", "int")], results=[900], text="dict.new", typ="dict[str,int]"),
            op("mem.store", [(address, "*dict[str,int]"), ("%t900", "dict[str,int]")])]
        self.assertFalse(self.verdict(snapshot, "@f.global_lookup"))

    def test_a_forged_or_seeded_certificate_rejects(self):
        candidate = normalize_snapshot(self.snapshot, "@f.counted")[0]
        self.assertTrue(self.check(candidate))
        load = next(index for index, node in enumerate(candidate["program"]["nodes"]) if node["op"] == "value")
        dict_, entry = candidate["program"]["nodes"][load]["dict"], candidate["program"]["nodes"][load]["entry"]
        forged = copy.deepcopy(candidate)
        forged["certificate"][1] = [["entry", entry, dict_]]
        self.assertFalse(self.check(forged))
        seeded = copy.deepcopy(candidate)
        seeded["certificate"][0] = [["absurd"]]
        self.assertFalse(self.check(seeded))

    def test_cli_reports_each_outcome(self):
        def run(*arguments):
            completed = subprocess.run([sys.executable, str(TOOL), *arguments], capture_output=True,
                                       text=True, timeout=300)
            return completed.returncode, json.loads(completed.stdout)

        code, report = run("--snapshot", str(self.snapshot_path), "--function", "@f.total")
        self.assertEqual((code, report["status"], report["checked"]), (0, "accepted", True))
        code, report = run("--snapshot", str(self.snapshot_path), "--all")
        self.assertEqual((code, report["status"], report["totals"]["proved_accesses"]), (0, "accepted", 30))
        with tempfile.TemporaryDirectory() as temporary:
            emitted = Path(temporary) / "candidate.json"
            code, report = run("--snapshot", str(self.snapshot_path), "--function", "@f.item", "--emit", str(emitted))
            self.assertEqual((code, report["status"], report["checked"]), (0, "prepared", False))
            self.assertTrue(emitted.is_file())
            snapshot, function = self.selected("@f.total")
            block, index = self.find(function, "list.load")
            listed = block["operations"][index]["operands"][0]["value"]
            block["operations"].insert(index, op("rt", [(listed, "list[int]")], text="list.clear"))
            corrupted = Path(temporary) / "typed-after.json"
            corrupted.write_text(json.dumps(snapshot))
            code, report = run("--snapshot", str(corrupted), "--all")
            self.assertEqual((code, report["status"]), (1, "rejected"))
            self.assertIn("is not proved", next(f["message"] for f in report["functions"] if f["status"] == "rejected"))
            code, report = run("--snapshot", str(self.snapshot_path), "--function", "@f.item",
                               "--checker", str(Path(temporary) / "missing"))
            self.assertEqual((code, report["status"]), (3, "error"))



def base_loop(low=0, checked=True, inclusive=False, stored=False, offset=0):
    """listguard's copy of `for i in range(s): ... xs[b + i + offset] ...` as normalized nodes
    (PystachyAccess.baseLoop): tests before the loop that b >= low and that the checked sum
    t = s + b is at most the length, then the loop's own test, i < s (or i <= s), and a plain
    sum j = b + i; stored: the loop stores b (a havoc) in place of its increment's check."""
    nodes = [
        {"op": "length", "dst": "n", "list": "xs", "next": 1},
        {"op": "test", "cond": {"cmp": "sle", "a": low, "b": "b"}, "yes": 2, "no": 13},
        ({"op": "add_checked_reg", "dst": "t", "x": "s", "y": "b", "next": 3, "overflow": 13} if checked
         else {"op": "add_reg", "dst": "t", "x": "s", "y": "b", "next": 3}),
        {"op": "test", "cond": {"cmp": "sle", "a": "t", "b": "n"}, "yes": 4, "no": 13},
        {"op": "lit", "dst": "h", "value": 0, "next": 5},
        {"op": "jump", "next": 6},
        {"op": "copy", "dst": "i", "src": "h", "next": 7},
        {"op": "test", "cond": {"cmp": "sle" if inclusive else "slt", "a": "i", "b": "s"}, "yes": 8, "no": 13},
        {"op": "add_reg", "dst": "j", "x": "b", "y": "i", "next": 9},
        ({"op": "load", "list": "xs", "index": "j", "next": 10} if offset == 0 else
         {"op": "add_checked", "dst": "k", "src": "j", "k": offset, "next": 14, "overflow": 13}),
        ({"op": "havoc", "dst": "b", "next": 11} if stored else
         {"op": "add_checked", "dst": "u", "src": "i", "k": 1, "next": 11, "overflow": 13}),
        {"op": "copy", "dst": "h", "src": "i" if stored else "u", "next": 12},
        {"op": "jump", "next": 6},
        {"op": "stop"},
    ]
    if offset != 0:
        nodes.append({"op": "load", "list": "xs", "index": "k", "next": 10})
    return nodes


class RegisterSumMirrorTests(unittest.TestCase):
    """The Python mirror of PystachyAccess's facts about sums of two values."""

    def test_a_checked_sum_gives_its_fact_only_where_it_fits(self):
        node = {"op": "add_checked_reg", "dst": "t", "x": "s", "y": "b", "next": 1, "overflow": 2}
        self.assertEqual(access.generated([], node, 0), [("sum", "t", "s", "b")])
        self.assertEqual(access.generated([], node, 1), [])
        self.assertEqual(access.generated([], dict(node, dst="b"), 0), [])  # (b is the new value)

    def test_a_plain_sum_needs_its_bound_below_a_checked_one(self):
        node = {"op": "add_reg", "dst": "j", "x": "b", "y": "i", "next": 1}
        facts = [("sum", "t", "s", "b"), ("lt", "i", "s"), ("ge", "i", 0), ("ge", "b", 0)]
        self.assertEqual(access.generated(facts, node, 0), [("sum", "j", "b", "i")])
        self.assertEqual(sorted(access.generation_premises(facts, node, ("sum", "j", "b", "i"))), sorted(facts))
        for missing in facts:
            known = [f for f in facts if f != missing]
            self.assertEqual(access.generated(known, node, 0), [], missing)
        # (lower bounds whose sum is below the least 64-bit value do not show it fits)
        low = [("sum", "t", "s", "b"), ("lt", "i", "s"), ("ge", "i", -2 ** 63), ("ge", "b", -1)]
        self.assertEqual(access.generated(low, node, 0), [])

    def test_adding_a_value_keeps_order_and_lower_bounds_add_up(self):
        known = [("sum", "j", "b", "i"), ("sum", "t", "s", "b"), ("lt", "i", "s"), ("ge", "i", 2), ("ge", "b", 3)]
        self.assertTrue(access.rule(known, ("lt", "j", "t")))
        self.assertTrue(access.rule(known, ("ge", "j", 5)))
        self.assertFalse(access.rule(known, ("ge", "j", 6)))
        self.assertFalse(access.rule([f for f in known if f != ("lt", "i", "s")], ("lt", "j", "t")))
        self.assertFalse(access.rule(known, ("lt", "t", "j")))
        derived, _ = access.closure(known, known, {"j", "t", "b", "i", "s"})
        self.assertIn(("lt", "j", "t"), derived)
        self.assertIn(("ge", "j", 5), derived)


@unittest.skipUnless(CHECKER.is_file() or os.environ.get("LEAN_BOUNDARY_REQUIRED") == "1",
                     "build tools/lean_boundary to run the Lean checker")
class RegisterSumCheckerTests(unittest.TestCase):
    """A base's sum with a loop's index, as listguard copies it, is proved, and each corruption of
    its tests rejected, by Lean and by the mirror alike."""

    def verdict(self, nodes):
        certificate, _ = access.infer_certificate(nodes, 0)
        candidate = {"schema_version": 1, "program": {"entry": 0, "nodes": nodes}, "certificate": certificate}
        completed = subprocess.run([str(CHECKER)], input=json.dumps(candidate), capture_output=True, text=True,
                                   timeout=60)
        self.assertIn(completed.returncode, (0, 1), completed.stdout + completed.stderr)
        accepted = json.loads(completed.stdout)["accepted"]
        self.assertEqual(explain(candidate) is None, accepted, explain(candidate))
        return accepted

    def test_a_base_loop_is_proved(self):
        self.assertTrue(self.verdict(base_loop()))

    def test_each_corruption_of_a_base_loop_rejects(self):
        for name, nodes in [("the base may be negative", base_loop(low=-1)),
                            ("the stop's sum with the base may wrap", base_loop(checked=False)),
                            ("the loop runs to its stop inclusive", base_loop(inclusive=True)),
                            ("the loop stores its base", base_loop(stored=True)),
                            ("the read is one past the tested sum", base_loop(offset=1))]:
            self.assertFalse(self.verdict(nodes), name)


if __name__ == "__main__":
    unittest.main()
