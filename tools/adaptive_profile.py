"""Profile ordinary CPython applications before selecting a scalar call region.

Type collection, cProfile hotness, and uninstrumented application timings are
three separate passes. Profiling times are advisory selection data, never native
speedup measurements. No argument values, reprs, or container contents are saved.
"""

from __future__ import annotations

import argparse
import ast
from collections import Counter
import cProfile
import functools
import inspect
import json
from pathlib import Path
import statistics
import sys
import sysconfig
import textwrap
import time
from types import CodeType, FunctionType

import adaptive


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "examples" / "adaptive"))
import workloads  # noqa: E402 - share the unmodified examples with the benchmark


def _path(filename):
    path = Path(filename).resolve()
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _identifier(code):
    return f"{_path(code.co_filename)}:{code.co_firstlineno}:{code.co_qualname}"


def _function(frame):
    """Resolve ordinary module functions and methods without executing a descriptor."""
    code = frame.f_code
    value = frame.f_globals.get(code.co_name)
    if isinstance(value, FunctionType) and value.__code__ is code:
        return value
    # lru_cache wraps an ordinary function; do not unwrap arbitrary user objects.
    if type(value) is functools._lru_cache_wrapper:
        wrapped = value.__wrapped__
        if isinstance(wrapped, FunctionType) and wrapped.__code__ is code:
            return wrapped
    parts = code.co_qualname.split(".")
    value = frame.f_globals.get(parts[0])
    for part in parts[1:]:
        if not isinstance(value, type):
            return None
        value = vars(value).get(part)
        if isinstance(value, (staticmethod, classmethod)):
            value = value.__func__
    return value if isinstance(value, FunctionType) and value.__code__ is code else None


class SignatureCounts:
    """Bounded exact-type counts; overflow remains in the coverage denominator."""

    def __init__(self, limit):
        self.limit = limit
        self.counts = Counter()
        self.calls = 0
        self.unrecorded = 0

    def add(self, signature):
        self.calls += 1
        if signature in self.counts or len(self.counts) < self.limit:
            self.counts[signature] += 1
        else:
            self.unrecorded += 1

    def report(self, type_ids):
        rows = []
        for signature, count in self.counts.most_common():
            arguments = []
            for name, kind in signature:
                if kind not in type_ids:
                    type_ids[kind] = len(type_ids) + 1
                arguments.append({"name": name, "type": f"{kind.__module__}.{kind.__qualname__}",
                                  "type_id": type_ids[kind]})
            rows.append({"arguments": arguments, "calls": count})
        top = [count for _, count in self.counts.most_common(2)]
        return {"calls": self.calls, "signatures": rows, "unrecorded_signature_calls": self.unrecorded,
                "top1_coverage": sum(top[:1]) / self.calls if self.calls else 0,
                "top2_coverage": sum(top) / self.calls if self.calls else 0,
                "coverage_is_lower_bound": bool(self.unrecorded)}


class TypeCollector:
    """Collect bounded Python-call signatures, including ineligible functions."""

    def __init__(self, roots, *, max_functions=256, max_sites=64, max_signatures=32):
        if min(max_functions, max_sites, max_signatures) < 1:
            raise ValueError("profile limits must be positive")
        self.roots = tuple(Path(root).resolve() for root in roots)
        self.max_functions, self.max_sites, self.max_signatures = max_functions, max_sites, max_signatures
        self.records = {}
        self.phase = "steady"
        self.workload = ""
        self.calls = 0
        self.dropped_function_calls = 0
        self.dropped_by_workload_phase = Counter()
        self._scope_cache = {}

    def in_scope(self, code):
        if code in self._scope_cache:
            return self._scope_cache[code]
        if code.co_filename.startswith("<"):
            return False
        path = Path(code.co_filename).resolve()
        matches = any(path == root or root in path.parents for root in self.roots)
        if len(self._scope_cache) < self.max_functions * 4:
            self._scope_cache[code] = matches
        return matches

    def __call__(self, frame, event, _arg):
        if event != "call" or not self.in_scope(frame.f_code):
            return
        code = frame.f_code
        self.calls += 1
        if code not in self.records:
            if len(self.records) >= self.max_functions:
                self.dropped_function_calls += 1
                self.dropped_by_workload_phase[(self.workload, self.phase)] += 1
                return
            self.records[code] = {"function": _function(frame), "all": SignatureCounts(self.max_signatures),
                                  "phases": {}, "sites": {}, "dropped_site_calls": 0, "workloads": set(),
                                  "workload_phase_calls": Counter()}
        record = self.records[code]
        record["workloads"].add(self.workload)
        record["workload_phase_calls"][(self.workload, self.phase)] += 1
        count = code.co_argcount + code.co_kwonlyargcount
        if code.co_flags & inspect.CO_VARARGS:
            count += 1
        if code.co_flags & inspect.CO_VARKEYWORDS:
            count += 1
        local = frame.f_locals
        signature = tuple((name, type(local[name])) for name in code.co_varnames[:count] if name in local)
        record["all"].add(signature)
        record["phases"].setdefault(self.phase, SignatureCounts(self.max_signatures)).add(signature)
        caller = frame.f_back
        site = (caller.f_code, caller.f_lasti) if caller is not None else (None, -1)
        if site not in record["sites"]:
            if len(record["sites"]) >= self.max_sites:
                record["dropped_site_calls"] += 1
                return
            record["sites"][site] = {"all": SignatureCounts(self.max_signatures), "phases": {},
                                      "line": caller.f_lineno if caller is not None else None}
        location = record["sites"][site]
        location["all"].add(signature)
        location["phases"].setdefault(self.phase, SignatureCounts(self.max_signatures)).add(signature)

    def collect(self, function, *args, phase="steady", workload="", **kwargs):
        if sys.getprofile() is not None:
            raise RuntimeError("type collection requires an unused sys.setprofile hook")
        self.phase, self.workload = phase, workload
        sys.setprofile(self)
        try:
            return function(*args, **kwargs)
        finally:
            sys.setprofile(None)


def _helpers(function):
    """Discover only ordinary, directly named helpers, bounded to 32 functions."""
    helpers, seen, pending = {}, set(), [function]
    while pending:
        current = pending.pop()
        if current in seen:
            continue
        seen.add(current)
        if len(seen) > 32:
            raise ValueError("helper graph exceeds profile limit")
        source = inspect.getsource(current)
        tree = ast.parse(textwrap.dedent(source))
        for child in ast.walk(tree):
            if isinstance(child, ast.Call) and isinstance(child.func, ast.Name):
                name = child.func.id
                target = current.__globals__.get(name)
                if isinstance(target, FunctionType):
                    if name in helpers and helpers[name] is not target:
                        raise ValueError("helper names resolve to different functions")
                    helpers[name] = target
                    pending.append(target)
    return helpers


def eligibility(function):
    """AST purity policy only; acceptance by the native compiler is untested here."""
    if function is None:
        return {"leaf": False, "region": False, "reason": "ordinary function could not be resolved", "helpers": []}
    leaf = False
    try:
        adaptive._source(function)
        leaf = True
    except (OSError, TypeError, ValueError, SyntaxError):
        pass
    try:
        graph = adaptive._Region(function, _helpers(function))
        helpers = sorted(helper.__name__ for helper in graph.nodes if helper is not function)
        return {"leaf": leaf, "region": True, "reason": "source-checked pure scalar call graph", "helpers": helpers}
    except (OSError, TypeError, ValueError, SyntaxError) as error:
        return {"leaf": leaf, "region": False, "reason": str(error), "helpers": []}


def source_feature_tags(function):
    """Visible source features, independent of source-identity rejection details.

    These describe this conservative experiment's boundary. They do not identify
    missing features in the full Pystachy compiler, which supports many of them.
    """
    if function is None:
        return []
    try:
        tree = ast.parse(textwrap.dedent(inspect.getsource(function)))
    except (OSError, TypeError, ValueError, SyntaxError):
        return ["source_unavailable"]
    tags = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            tags.add("attribute_access")
        if isinstance(node, ast.Subscript):
            tags.add("indexing")
        if isinstance(node, (ast.List, ast.Tuple, ast.Dict, ast.Set)):
            tags.add("container_literals_or_destructuring")
        if isinstance(node, ast.Constant) and type(node.value) not in (int, float, bool):
            tags.add("nonnumeric_literals_or_docstrings")
        if isinstance(node, ast.Call) and node.keywords:
            tags.add("keyword_calls")
        if isinstance(node, ast.arguments) and (node.defaults or node.kw_defaults or node.vararg or node.kwarg or node.kwonlyargs):
            tags.add("default_keyword_only_or_variadic_parameters")
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            tags.add("imports")
        if isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            tags.add("comprehensions")
        if isinstance(node, (ast.Try, ast.TryStar, ast.Raise, ast.Assert)):
            tags.add("exceptions_or_assertions")
        if isinstance(node, (ast.With, ast.AsyncWith)):
            tags.add("context_managers")
    if sum(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) for node in ast.walk(tree)) > 1:
        tags.add("nested_functions")
    return sorted(tags)


def _hotness(function, phase, iterations, collector, **options):
    profiler = cProfile.Profile()
    profiler.enable()
    try:
        result = function(phase, iterations, **options)
    finally:
        profiler.disable()
    rows = {}
    python_self, native_self = 0.0, 0.0
    for entry in profiler.getstats():
        if isinstance(entry.code, CodeType):
            if collector.in_scope(entry.code):
                rows[entry.code] = {"calls": entry.callcount, "self_time_s": entry.inlinetime,
                                    "cumulative_time_s": entry.totaltime}
                python_self += entry.inlinetime
        else:
            native_self += entry.inlinetime
    return result, rows, {"in_scope_python_self_time_s": python_self, "native_builtin_self_time_s": native_self}


def fixed_budget_policy(record, phase="steady"):
    """Offline signature coverage with an equal budget of compiled bodies.

    A context-keyed (call-site, signature) variant consumes one body slot. This
    diagnostic cannot measure inlining, dispatch overhead, or speed gains.
    """
    global_counts = record["phases"].get(phase)
    if global_counts is None:
        return []
    callee = sorted(global_counts.counts.values(), reverse=True)
    contexts = []
    incomplete = bool(global_counts.unrecorded or record["dropped_site_calls"])
    for location in record["sites"].values():
        counts = location["phases"].get(phase)
        if counts is not None:
            contexts.extend(counts.counts.values())
            incomplete |= bool(counts.unrecorded)
    contexts.sort(reverse=True)
    denominator = global_counts.calls
    return [{"compiled_body_budget": budget, "calls": denominator,
             "callee_covered_calls": sum(callee[:budget]),
             "caller_context_covered_calls": sum(contexts[:budget]),
             "callee_coverage": sum(callee[:budget]) / denominator if denominator else 0,
             "caller_context_coverage": sum(contexts[:budget]) / denominator if denominator else 0,
             "coverage_is_lower_bound": incomplete} for budget in (1, 2)]


def run_profiles(iterations=24, samples=3, *, numeric_inner=256):
    """Profile all three applications and select an eligible region by steady hotness."""
    if any(type(value) is not int or value < 1 for value in (iterations, samples, numeric_inner)):
        raise ValueError("iterations, samples and numeric_inner must be positive integers")
    roots = (ROOT / "examples" / "adaptive", ROOT / "examples" / "route", sysconfig.get_path("stdlib"))
    collector = TypeCollector(roots)
    applications, hotness = [], {}
    for name, function in workloads.WORKLOADS.items():
        options = {"inner": numeric_inner} if name == "numeric" else {}
        phases = {}
        for phase in workloads.PHASES:
            oracle = collector.collect(function, phase, iterations, phase=phase, workload=name, **options)
            result, rows, totals = _hotness(function, phase, iterations, collector, **options)
            if result != oracle:
                raise RuntimeError("hotness pass result differs from type pass")
            for code, values in rows.items():
                hotness[(name, phase, code)] = values
            times = []
            for _ in range(samples):
                start = time.perf_counter()
                result = function(phase, iterations, **options)
                elapsed = time.perf_counter() - start
                if result != oracle:
                    raise RuntimeError("uninstrumented result differs from type pass")
                times.append(elapsed)
            phases[phase] = {"uninstrumented_median_s": statistics.median(times),
                             "uninstrumented_samples_s": times, "profiled_hotness": totals}
        applications.append({"name": name, "phases": phases,
                             "source": "examples/route/route.py (original router functions)" if name == "event"
                             else "stdlib textwrap/re (original functions), small driver" if name == "text"
                             else "synthetic scalar mini-application, Python orchestration"})
    functions, type_ids, policies = [], {}, {}
    for code, record in collector.records.items():
        policy = eligibility(record["function"])
        policies[code] = policy
        sites = []
        for (caller, offset), location in record["sites"].items():
            sites.append({"caller": _identifier(caller) if caller is not None else None,
                          "caller_line": location["line"], "bytecode_offset": offset,
                          **location["all"].report(type_ids),
                          "phases": {phase: counts.report(type_ids) for phase, counts in location["phases"].items()}})
        per_phase = {}
        for phase, counts in record["phases"].items():
            measures = [hotness[(name, phase, code)] for name in record["workloads"] if (name, phase, code) in hotness]
            per_phase[phase] = {**counts.report(type_ids),
                                "self_time_s": sum(value["self_time_s"] for value in measures),
                                "cumulative_time_s": sum(value["cumulative_time_s"] for value in measures)}
        steady = per_phase.get("steady", {})
        numeric_calls = sum(count for signature, count in record["all"].counts.items()
                            if all(kind is int or kind is float for _, kind in signature))
        functions.append({"id": _identifier(code), "name": code.co_name, "qualname": code.co_qualname,
                          "file": _path(code.co_filename), "line": code.co_firstlineno,
                          "workloads": sorted(record["workloads"]), **record["all"].report(type_ids),
                          "training_calls": steady.get("calls", 0),
                          "exact_numeric_signature_calls": numeric_calls,
                          "self_time_s": steady.get("self_time_s", 0),
                          "cumulative_time_s": steady.get("cumulative_time_s", 0),
                          "eligibility": policy, "phases": per_phase, "caller_sites": sites,
                          "source_feature_tags": source_feature_tags(record["function"]),
                          "steady_fixed_budget_policy": fixed_budget_policy(record),
                          "unrecorded_site_calls": record["dropped_site_calls"]})
    functions.sort(key=lambda row: row["cumulative_time_s"], reverse=True)
    candidates = [row for row in functions if row["eligibility"]["region"] and row["training_calls"]]
    selected = candidates[0] if candidates else None
    total_calls = collector.calls
    eligible_calls = sum(row["calls"] for row in functions if row["eligibility"]["region"])
    total_self = sum(app["phases"]["steady"]["profiled_hotness"]["in_scope_python_self_time_s"] for app in applications)
    eligible_self = sum(row["self_time_s"] for row in functions if row["eligibility"]["region"])
    builtin_self = sum(app["phases"]["steady"]["profiled_hotness"]["native_builtin_self_time_s"] for app in applications)
    for app in applications:
        name = app["name"]
        calls = sum(record["workload_phase_calls"][(name, "steady")] for record in collector.records.values())
        dropped = collector.dropped_by_workload_phase[(name, "steady")]
        eligible = sum(record["workload_phase_calls"][(name, "steady")]
                       for code, record in collector.records.items() if policies[code]["region"])
        eligible_time = sum(values["self_time_s"] for (workload, phase, code), values in hotness.items()
                            if workload == name and phase == "steady" and policies.get(code, {}).get("region", False))
        totals = app["phases"]["steady"]["profiled_hotness"]
        python_time = totals["in_scope_python_self_time_s"]
        all_time = python_time + totals["native_builtin_self_time_s"]
        app["steady_ast_policy_coverage"] = {
            "all_in_scope_python_calls": calls + dropped, "eligible_region_python_calls": eligible,
            "eligible_call_fraction": eligible / (calls + dropped) if calls + dropped else 0,
            "unrecorded_function_calls": dropped, "coverage_is_lower_bound": bool(dropped),
            "python_self_time_s": python_time, "eligible_python_self_time_s": eligible_time,
            "native_builtin_self_time_s": totals["native_builtin_self_time_s"],
            "all_profiled_self_time_s": all_time,
            "eligible_python_self_time_fraction": eligible_time / python_time if python_time else 0,
            "eligible_all_profiled_self_time_fraction": eligible_time / all_time if all_time else 0,
        }
    return {"schema_version": 1, "iterations": iterations, "samples": samples, "numeric_inner": numeric_inner,
            "method": {"selection_phase": "steady", "selection_metric": "eligible region cProfile cumulative_time_s",
                       "profile_times_are_speed_benchmarks": False,
                       "scope": [str(root) for root in roots],
                       "argument_values_recorded": False, "container_contents_recorded": False,
                       "notes": ["cProfile and sys.setprofile are separate passes; both perturb execution.",
                                 "Only uninstrumented_median_s measures application wall time.",
                                 "Eligibility is conservative adaptive purity policy, not the full Pystachy language subset.",
                                 "AST-admissible sources have not been compiled by this profile-only tool.",
                                 "source_feature_tags describe visible syntax; many tagged features are already supported by the full compiler.",
                                 "Exact int/float types do not establish native value bounds, finiteness, or intermediate overflow safety.",
                                 "Fixed-budget context coverage assigns one body slot per (caller site, signature); it measures coverage, not dispatch or inlining gains.",
                                 "Static-known entry signatures are supplied by the benchmark; they are not runtime discovery.",
                                 "Per-function cumulative times overlap and must not be summed for coverage.",
                                 "The int/float stream fits a two-variant cache; region cloning alone adds no type-discovery evidence."]},
            "applications": applications, "functions": functions,
            "coverage": {"all_in_scope_python_calls": total_calls, "eligible_region_python_calls": eligible_calls,
                         "eligible_call_fraction": eligible_calls / total_calls if total_calls else 0,
                         "eligible_region_exact_numeric_signature_calls": sum(row["exact_numeric_signature_calls"] for row in functions if row["eligibility"]["region"]),
                         "unrecorded_function_calls": collector.dropped_function_calls,
                         "eligible_coverage_is_lower_bound": bool(collector.dropped_function_calls),
                         "steady_python_self_time_s": total_self, "steady_eligible_python_self_time_s": eligible_self,
                         "steady_eligible_python_self_time_fraction": eligible_self / total_self if total_self else 0,
                         "steady_native_builtin_self_time_s": builtin_self,
                         "steady_all_profiled_self_time_s": total_self + builtin_self,
                         "steady_eligible_all_profiled_self_time_fraction": eligible_self / (total_self + builtin_self) if total_self + builtin_self else 0,
                         "ast_policy_function_counts": {"leaf": sum(row["eligibility"]["leaf"] for row in functions),
                                                        "region_including_leaf": sum(row["eligibility"]["region"] for row in functions),
                                                        "unsupported": sum(not row["eligibility"]["region"] for row in functions)}},
            "selected_region": ({"id": selected["id"], "function": selected["name"],
                                 "workload": selected["workloads"][0], "helpers": selected["eligibility"]["helpers"],
                                 "training_calls": selected["training_calls"],
                                 "cumulative_time_s": selected["cumulative_time_s"]} if selected else None)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iterations", type=int, default=24)
    parser.add_argument("--samples", type=int, default=3)
    parser.add_argument("--numeric-inner", type=int, default=256)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    if min(args.iterations, args.samples, args.numeric_inner) < 1:
        parser.error("iterations, samples and numeric-inner must be positive")
    report = run_profiles(args.iterations, args.samples, numeric_inner=args.numeric_inner)
    output = json.dumps(report, indent=2)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(output + "\n", encoding="utf-8")
    else:
        print(output)


if __name__ == "__main__":
    main()
