"""Profile collection and application-region selection without native compilation."""

import json
from pathlib import Path
import sys
import textwrap
import unittest

import adaptive_profile as profile


def identity(value):
    return value


def two_sites():
    for _ in range(3):
        identity(1)
    identity(0.5)


def one_site(values):
    return [identity(value) for value in values]


def raises():
    raise RuntimeError("expected exception")


class NoRepr:
    def __repr__(self):
        raise AssertionError("profiling must not inspect argument values")


class IntSubclass(int):
    pass


class TypeCollectionTests(unittest.TestCase):
    def collect(self, function, *args, **options):
        collector = profile.TypeCollector([Path(__file__)], **options)
        collector.collect(function, *args)
        return collector

    def test_exact_types_and_individual_caller_bytecode_sites(self):
        collector = self.collect(two_sites)
        record = collector.records[identity.__code__]
        self.assertEqual(record["all"].calls, 4)
        self.assertEqual(len(record["sites"]), 2)
        self.assertEqual(len({offset for _, offset in record["sites"]}), 2)
        report = record["all"].report({})
        self.assertEqual(report["top1_coverage"], 0.75)
        self.assertEqual(report["top2_coverage"], 1)
        self.assertEqual([row["arguments"][0]["type"] for row in report["signatures"]],
                         ["builtins.int", "builtins.float"])

    def test_no_value_repr_and_bool_subclass_are_distinct(self):
        collector = self.collect(one_site, [1, True, IntSubclass(1), NoRepr()])
        record = collector.records[identity.__code__]
        report = record["all"].report({})
        self.assertEqual(len(report["signatures"]), 4)
        self.assertEqual(len({row["arguments"][0]["type_id"] for row in report["signatures"]}), 4)
        json.dumps(report)

    def test_phase_counts_retain_changed_distributions(self):
        collector = profile.TypeCollector([Path(__file__)])
        collector.collect(one_site, [1, 2, 3, 0.5], phase="steady")
        collector.collect(one_site, [0.5, 1.5, 2.5, 1], phase="shifted")
        record = collector.records[identity.__code__]
        self.assertEqual(record["phases"]["steady"].counts[(("value", int),)], 3)
        self.assertEqual(record["phases"]["shifted"].counts[(("value", float),)], 3)
        self.assertEqual(record["all"].calls, 8)

    def test_signature_overflow_stays_in_coverage_denominator(self):
        collector = self.collect(one_site, [1, 0.5, True], max_signatures=1)
        report = collector.records[identity.__code__]["all"].report({})
        self.assertEqual(report["calls"], 3)
        self.assertEqual(report["unrecorded_signature_calls"], 2)
        self.assertEqual(report["top2_coverage"], 1 / 3)
        self.assertTrue(report["coverage_is_lower_bound"])

    def test_function_and_site_overflow_keep_denominators(self):
        collector = self.collect(two_sites, max_functions=1)
        self.assertEqual(collector.calls, 5)
        self.assertEqual(collector.dropped_function_calls, 4)
        collector = self.collect(two_sites, max_sites=1)
        record = collector.records[identity.__code__]
        self.assertEqual(record["all"].calls, 4)
        self.assertEqual(record["dropped_site_calls"], 1)
        self.assertTrue(profile.fixed_budget_policy(record)[0]["coverage_is_lower_bound"])

    def test_profile_hook_is_restored_after_exception(self):
        collector = profile.TypeCollector([Path(__file__)])
        with self.assertRaisesRegex(RuntimeError, "expected exception"):
            collector.collect(raises)
        self.assertIsNone(sys.getprofile())

    def test_existing_profile_hook_is_preserved(self):
        def hook(*_args):
            pass
        collector = profile.TypeCollector([Path(__file__)])
        sys.setprofile(hook)
        try:
            with self.assertRaisesRegex(RuntimeError, "unused sys.setprofile"):
                collector.collect(identity, 1)
            self.assertIs(sys.getprofile(), hook)
        finally:
            sys.setprofile(None)

    def test_equal_body_budget_policy_does_not_invent_type_discovery(self):
        collector = self.collect(two_sites)
        rows = profile.fixed_budget_policy(collector.records[identity.__code__])
        self.assertEqual(rows[0]["callee_coverage"], rows[0]["caller_context_coverage"])
        self.assertEqual(rows[1]["compiled_body_budget"], 2)
        self.assertEqual(rows[1]["callee_coverage"], 1)
        self.assertEqual(rows[1]["caller_context_coverage"], 1)


class ApplicationTests(unittest.TestCase):
    def test_numeric_leaf_override_keeps_original_bindings_and_code(self):
        original = profile.workloads.numeric_step
        calls = []

        def step(x, i):
            calls.append((type(x), type(i)))
            return original(x, i)

        expected = profile.workloads.run_numeric("steady", 4, inner=5)
        actual = profile.workloads.run_numeric("steady", 4, step=step, inner=5)
        self.assertEqual(actual, expected)
        self.assertEqual(len(calls), 23)
        self.assertIs(profile.workloads.numeric_batch.__globals__["numeric_step"], original)
        self.assertIs(profile.workloads.numeric_step, original)

    def test_region_policy_distinguishes_leaf_from_caller(self):
        leaf = profile.eligibility(profile.workloads.numeric_step)
        region = profile.eligibility(profile.workloads.numeric_batch)
        self.assertTrue(leaf["leaf"])
        self.assertFalse(region["leaf"])
        self.assertTrue(region["region"])
        self.assertEqual(region["helpers"], ["numeric_step"])
        self.assertFalse(profile.eligibility(profile.workloads.normalize_text)["region"])

    def test_profile_covers_original_stdlib_and_router_and_selects_numeric_region(self):
        original_fill = textwrap.fill
        report = profile.run_profiles(iterations=4, samples=1, numeric_inner=300)
        self.assertIs(textwrap.fill, original_fill)
        self.assertIsNone(sys.getprofile())
        self.assertEqual(report["numeric_inner"], 300)
        selected = report["selected_region"]
        self.assertEqual(selected["function"], "numeric_batch")
        self.assertEqual(selected["helpers"], ["numeric_step"])
        files = {row["file"] for row in report["functions"]}
        self.assertIn("examples/route/route.py", files)
        self.assertTrue(any(filename.endswith("/textwrap.py") for filename in files))
        self.assertTrue(any(filename.endswith("/fnmatch.py") for filename in files))
        coverage = report["coverage"]
        self.assertGreater(coverage["all_in_scope_python_calls"], coverage["eligible_region_python_calls"])
        self.assertEqual(sum(row["calls"] for row in report["functions"])
                         + coverage["unrecorded_function_calls"], coverage["all_in_scope_python_calls"])
        self.assertGreater(coverage["ast_policy_function_counts"]["unsupported"], 0)
        self.assertGreaterEqual(coverage["steady_all_profiled_self_time_s"], coverage["steady_python_self_time_s"])
        self.assertLessEqual(coverage["steady_eligible_all_profiled_self_time_fraction"], 1)
        self.assertFalse(report["method"]["profile_times_are_speed_benchmarks"])
        self.assertFalse(report["method"]["argument_values_recorded"])
        self.assertEqual({app["name"] for app in report["applications"]}, {"event", "text", "numeric"})
        applications = {app["name"]: app for app in report["applications"]}
        for name in ("event", "text"):
            app_coverage = applications[name]["steady_ast_policy_coverage"]
            self.assertGreater(app_coverage["all_in_scope_python_calls"], 0)
            self.assertEqual(app_coverage["eligible_region_python_calls"], 0)
            self.assertEqual(app_coverage["eligible_all_profiled_self_time_fraction"], 0)
        numeric_coverage = applications["numeric"]["steady_ast_policy_coverage"]
        self.assertGreater(numeric_coverage["eligible_region_python_calls"], 0)
        normalizer = next(row for row in report["functions"] if row["name"] == "normalize_text")
        self.assertIn("attribute_access", normalizer["source_feature_tags"])
        self.assertIn("keyword_calls", normalizer["source_feature_tags"])
        numeric_step = next(row for row in report["functions"] if row["name"] == "numeric_step")
        self.assertEqual(numeric_step["phases"]["steady"]["top2_coverage"], 1)
        for policy in numeric_step["steady_fixed_budget_policy"]:
            self.assertEqual(policy["callee_coverage"], policy["caller_context_coverage"])
        self.assertEqual(len(numeric_step["caller_sites"]), 1)
        json.dumps(report)


if __name__ == "__main__":
    unittest.main()
