"""The final CI gate must reject incomplete or inconsistent verification artifacts."""
import contextlib
import copy
import io
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import merge_verification as merge

CONTRACT = """all bootstrap tests-opt-off-0 check-ir
opt-off-0 bootstrap tests-opt-off-0
contracts bootstrap check-ir
"""
COMMIT = "a" * 40
BUNDLE = "d" * 64


@lru_cache(maxsize=4)
def optin_report(index):
    tool = merge.dynany_optin
    corpus = tool.programs()
    selected = corpus[index::merge.DYNANY_SHARDS]
    allowed = tool.exceptions(tool.ROOT, corpus)
    rows = []
    for case in selected:
        for mode in tool.MODES:
            exception = allowed.get((case, mode))
            rows.append({"case": case, "mode": mode,
                         "result": "expected-failure" if exception else "pass",
                         "diagnostic": exception["diagnostic"] if exception else ""})
    known = sum(row["result"] == "expected-failure" for row in rows)
    return {"schema": 1, "corpus_cases": len(corpus),
            "corpus_sha256": tool.corpus_digest(tool.ROOT, corpus),
            "exceptions_sha256": hashlib.sha256((tool.ROOT / tool.MANIFEST).read_bytes()).hexdigest(),
            "shard_index": index, "shard_count": merge.DYNANY_SHARDS, "modes": list(tool.MODES), "native_suite": True,
            "cases": selected, "subset": False, "oracle_cases": len(selected),
            "expected_checks": len(rows), "completed_checks": len(rows),
            "passed_checks": len(rows) - known, "expected_failures": known, "native_ir_checks": 0,
            "failures": [], "results": rows}


COMPILER_BYTES = b"verified test compiler\n"


def python_int_report(index):
    tool = merge.python_int_gate
    corpus = tool.programs()
    selected = corpus[index::merge.PYTHON_INT_SHARDS]
    allowed = tool.exceptions(tool.ROOT, corpus)
    rows = []
    for case in selected:
        for mode in tool.MODES:
            exception = allowed.get((case, mode))
            rows.append({"case": case, "mode": mode,
                         "result": "expected-failure" if exception else "pass",
                         "diagnostic": exception["diagnostic"] if exception else ""})
    known = sum(row["result"] == "expected-failure" for row in rows)
    return {"schema": 1, "kind": "python-int-gate", "pragma": tool.PRAGMA.decode().strip(),
            "python": (tool.ROOT / ".python-version").read_text().strip(),
            "compiler_sha256": hashlib.sha256(COMPILER_BYTES).hexdigest(),
            "source_sha256": tool.source_digest(tool.ROOT), "gc_stress": False,
            "corpus_cases": len(corpus), "corpus_sha256": tool.optin.corpus_digest(tool.ROOT, corpus),
            "exceptions_sha256": tool.sha256(tool.ROOT / tool.MANIFEST),
            "shard_index": index, "shard_count": merge.PYTHON_INT_SHARDS, "modes": list(tool.MODES),
            "native_suite": True, "cases": selected, "subset": False, "oracle_cases": len(selected),
            "expected_checks": len(rows), "completed_checks": len(rows),
            "passed_checks": len(rows) - known, "expected_failures": known, "native_ir_checks": 0,
            "failures": [], "results": rows}


def report(group, steps):
    checks = []
    for name in steps:
        step = {"name": name, "result": "pass", "seconds": 2.0,
                "log": f"build/verify/{name}.log"}
        if name == "bootstrap":
            step.update(ir_identical=True, ir_sha256="b" * 64, bootstrap_bundle_id=BUNDLE)
            if group != "bootstrap":
                step["bootstrap_reused"] = True
        if name in merge.SUITE_STEPS:
            step.update(passed=10, failed=0, expected=10, failures=[])
        if name in ("tests-native-0", "tests-native-1", "tests-opt-off-0", "tests-opt-off-1", "gc-jit-0", "gc-jit-1",
                    "python-free-0", "python-free-1"):
            step.update(passed=5, expected=5)   # halves of a 10-check suite
        if name.startswith("tests-native"):
            step.update(compiler="stage2", modes=["jit", "aot"])
        if name == "tests-cpython":   # every case's IR identical, its sample run end to end
            step.update(reference="stage2", ir_identical=True, ir_cases=5, check_cases=2, modes=["jit", "aot"],
                        sample_index=0, sample_count=merge.HOSTED_SAMPLE_OF)
        if name in ("gc-aot-0", "gc-aot-1", "gc-aot-2"):
            count = 4 if name.endswith("-0") else 3   # thirds of a 10-check suite
            step.update(passed=count, expected=count)
        if name in ("ubsan-0", "ubsan-1", "ubsan-2"):
            count = 6 if name == "ubsan-2" else 7   # thirds of a suite of 10 checks in each of two modes
            step.update(passed=count, expected=count)
        if name.startswith("tests-opt-off"):
            step.update(PYSTACHY_OPT=["-all"])
        if name == "gc-self":
            step.update(compiler_interval=5000, ir_identical=True)
        if name == "dynany-fuzz":
            step.update(programs=3, cases=540, parity_cases=90, modes=["jit", "aot", "jit-gc", "aot-gc"],
                        program_gc_interval=1, mismatches=0)
        if name.startswith("dynany-optin-"):
            step["optin"] = copy.deepcopy(optin_report(int(name[-1])))
        if name.startswith("python-int-optin-"):
            step["python_int_optin"] = copy.deepcopy(python_int_report(int(name[-1])))
        if name in merge.GC_STEPS:
            step.update(tests_compiler_interval=1000, tests_interval=1,
                        modes=["jit" if name.startswith("gc-jit") else "aot"])
        if name in merge.SHARDED_STEPS:
            step.update(shard_index=int(name[-1]), shard_count=merge.SHARDED_STEPS[name])
        if name in merge.SCALING_STEPS:
            step.update(shapes=merge.scaling_shapes()[int(name[-1])::2])
        checks.append(step)
    return {"project": "Pystachy", "group": group, "result": "pass",
            "summary": {"steps": len(steps), "passed": len(steps), "failed": 0, "seconds": 6.0},
            "git": {"commit": COMMIT, "dirty": False},
            "sources": {"pystachy.py": {"sha256": "c" * 64}, "test_programs": 5, "suite_checks": 10, "mode_checks": 10,
                        "corpus_cases": 5, "syntax_cases": 2},
            "toolchain": {"llvm": "LLVM 18", "python": "Python 3.13"},
            "platform": {"machine": "x86_64"}, "steps": checks}


class ContractTests(unittest.TestCase):
    def setUp(self):
        # The gate's own tests cover filesystem hashing. These aggregate controls vary the
        # reported digest, without rescanning the complete checkout for every mutation.
        corpus = merge.dynany_optin.programs()
        digest = merge.dynany_optin.corpus_digest(merge.ROOT, corpus)
        for module, name, value in ((merge.python_int_gate, "source_digest", "e" * 64),
                                    (merge.python_int_gate, "programs", corpus),
                                    (merge.dynany_optin, "programs", corpus),
                                    (merge.dynany_optin, "corpus_digest", digest)):
            patch = mock.patch.object(module, name, return_value=value)
            patch.start()
            self.addCleanup(patch.stop)

    def test_real_plan_requires_native_suites_and_every_gc_job(self):
        groups = merge.load_groups()
        for alias in ("gc-stress", "gc-jit", "gc-aot", "ubsan", "native", "opt-off", "python-free", "scaling", "python-int-optin"):
            self.assertNotIn(alias, groups)  # Compatibility aliases must not duplicate CI work.
        for group in ("gc-self", "gc-jit-0", "gc-jit-1", "gc-aot-0", "gc-aot-1", "gc-aot-2", "ubsan-0", "ubsan-1",
                      "ubsan-2", "python-free-0", "python-free-1", "runtime-cache", "scaling-1"):
            self.assertEqual(groups[group], ["bootstrap", group])
        self.assertEqual(groups["hosted"], ["bootstrap", "tests-cpython"])  # one job: the IR oracle and its sample
        for shard in ("0", "1", "2"):
            self.assertNotIn("hosted-" + shard, groups)
        for shard in ("0", "1"):
            self.assertEqual(groups["native-" + shard], ["bootstrap", "tests-native-" + shard])
            self.assertEqual(groups["opt-off-" + shard], ["bootstrap", "tests-opt-off-" + shard])
        self.assertEqual(groups["benchmarks"], ["bootstrap", "benchmarks", "scaling-0"])
        for group in ("all", "contracts"):
            self.assertIn("select-io", groups[group])
            self.assertIn("weakrefs", groups[group])
            self.assertIn("box-slots", groups[group])
            self.assertIn("dynany-fuzz", groups[group])
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            for group, steps in groups.items():
                if group == "all":
                    continue
                path = directory / f"verification-{group}" / "verification.json"
                path.parent.mkdir()
                path.write_text(json.dumps(report(group, steps)))
            result = merge.merge_reports(directory, groups, COMMIT)
            self.assertEqual([step["name"] for step in result["steps"]], groups["all"])
            for group in ("opt-off-0", "opt-off-1", "gc-self", "gc-jit-0", "gc-jit-1", "gc-aot-0", "gc-aot-1", "gc-aot-2",
                          "hosted", "native-0", "native-1", "python-free-0", "python-free-1",
                          "ubsan-0", "ubsan-1", "ubsan-2", "runtime-cache", "contracts", "benchmarks",
                          "scaling-1", *(f"dynany-optin-{index}" for index in range(merge.DYNANY_SHARDS)),
                          *(f"python-int-optin-{index}" for index in range(merge.PYTHON_INT_SHARDS))):
                path = directory / f"verification-{group}" / "verification.json"
                original = path.read_text()
                path.unlink()
                with self.subTest(missing=group), self.assertRaisesRegex(ValueError, f"missing report groups.*{group}"):
                    merge.merge_reports(directory, groups, COMMIT)
                path.write_text(original)
            for group in ("gc-aot-0", "gc-aot-2", "native-0", "opt-off-1", "python-free-0",
                          "python-free-1", "ubsan-0"):
                path = directory / f"verification-{group}" / "verification.json"
                original = path.read_text()
                for delta in (-1, 1):
                    data = report(group, groups[group])
                    count = data["steps"][-1]["expected"] + delta
                    data["steps"][-1].update(passed=count, expected=count)
                    path.write_text(json.dumps(data))
                    with self.subTest(group=group, delta=delta), \
                            self.assertRaisesRegex(ValueError, "same full-suite check count"):
                        merge.merge_reports(directory, groups, COMMIT)
                path.write_text(original)
            # opt-off's halves run the corpus once per PYSTACHY_OPT setting, the same settings in both
            for settings, scale, error in (([["-all", "-inline"]] * 2, 2, None),
                                           ([["-all", "-inline"]] * 2, 1, "same full-suite check count"),
                                           ([["-all"], ["-inline"]], 1, "same PYSTACHY_OPT settings"),
                                           ([[], []], 1, "same PYSTACHY_OPT settings")):
                for index in (0, 1):
                    data = report(f"opt-off-{index}", groups[f"opt-off-{index}"])
                    count = data["steps"][-1]["expected"] * scale
                    data["steps"][-1].update(passed=count, expected=count, PYSTACHY_OPT=settings[index])
                    (directory / f"verification-opt-off-{index}" / "verification.json").write_text(json.dumps(data))
                with self.subTest(settings=settings, scale=scale):
                    if error is None:
                        merge.merge_reports(directory, groups, COMMIT)
                    else:
                        with self.assertRaisesRegex(ValueError, error):
                            merge.merge_reports(directory, groups, COMMIT)
            for index in (0, 1):
                (directory / f"verification-opt-off-{index}" / "verification.json").write_text(
                    json.dumps(report(f"opt-off-{index}", groups[f"opt-off-{index}"])))
            # the shards of each JIT and AOT suite make the checks of the whole corpus (sources.suite_checks)
            paths = sorted(directory.glob("verification-*/verification.json"))
            for suite, error in ((11, "shards must cover the same full-suite check count as the corpus"), (10, None)):
                for path in paths:
                    data = json.loads(path.read_text())
                    data["sources"]["suite_checks"] = suite
                    path.write_text(json.dumps(data))
                if error is not None:
                    with self.subTest(suite_checks=suite), self.assertRaisesRegex(ValueError, error):
                        merge.merge_reports(directory, groups, COMMIT)
            # the shards of each GC suite make the checks of the corpus in one mode (sources.mode_checks),
            # and the UBSan thirds twice as many
            for checks, error in ((11, "GC JIT shards must cover the same full-suite check count"), (10, None)):
                for path in paths:
                    data = json.loads(path.read_text())
                    data["sources"]["mode_checks"] = checks
                    path.write_text(json.dumps(data))
                if error is not None:
                    with self.subTest(mode_checks=checks), self.assertRaisesRegex(ValueError, error):
                        merge.merge_reports(directory, groups, COMMIT)
            merge.merge_reports(directory, groups, COMMIT)
            # scaling-0 and scaling-1 check every shape of tools/scaling.py once
            path = directory / "verification-scaling-1" / "verification.json"
            original = path.read_text()
            shapes = merge.scaling_shapes()
            for wrong in (shapes[1::2][1:], shapes[1::2] + shapes[:1], shapes[1::2] + ["unknown"]):
                data = report("scaling-1", groups["scaling-1"])
                data["steps"][-1].update(shapes=wrong)
                path.write_text(json.dumps(data))
                with self.subTest(shapes=wrong), self.assertRaisesRegex(ValueError, "every shape of tools/scaling.py"):
                    merge.merge_reports(directory, groups, COMMIT)
            path.write_text(original)

    def test_gc_reports_require_original_stress_mode_ir_and_complete_counts(self):
        groups = merge.load_groups()
        mutations = {
            "gc-self": [lambda step: step.update(compiler_interval=5001),
                        lambda step: step.pop("compiler_interval"),
                        lambda step: step.update(ir_identical=False),
                        lambda step: step.pop("ir_identical")],
            "gc-jit-0": [lambda step: step.update(tests_compiler_interval=1001),
                         lambda step: step.update(tests_interval=2),
                         lambda step: step.pop("tests_interval"),
                         lambda step: step.update(modes=["aot"]),
                         lambda step: step.update(modes=["jit", "aot"]),
                         lambda step: step.pop("modes"),
                         lambda step: step.update(passed=9),
                         lambda step: step.pop("expected")],
        }
        shard_mutations = [lambda step: step.update(shard_index=1 - step["shard_index"]),
                           lambda step: step.update(shard_index=False),
                           lambda step: step.pop("shard_index"),
                           lambda step: step.update(shard_count=step["shard_count"] + 1),
                           lambda step: step.update(shard_count=str(step["shard_count"])),
                           lambda step: step.pop("shard_count")]
        for group in ("native-0", "native-1", "opt-off-0", "opt-off-1",
                      "python-free-0", "python-free-1", "ubsan-0", "ubsan-1", "ubsan-2"):
            mutations[group] = shard_mutations + [lambda step: step.update(passed=step["expected"] - 1),
                                                  lambda step: step.update(failed=1),
                                                  lambda step: step.pop("expected")]
        # the CPython-hosted compiler: identical on every case and syntax check, its sample run end to end
        mutations["hosted"] = [lambda step: step.update(ir_identical=False),
                               lambda step: step.pop("ir_identical"),
                               lambda step: step.update(ir_identical="true"),
                               lambda step: step.update(reference="stage1"),
                               lambda step: step.update(ir_cases=4),
                               lambda step: step.update(ir_cases=6),
                               lambda step: step.pop("ir_cases"),
                               lambda step: step.update(check_cases=1),
                               lambda step: step.update(check_cases=0),
                               lambda step: step.update(modes=["jit"]),
                               lambda step: step.update(sample_index=1),
                               lambda step: step.update(sample_count=merge.HOSTED_SAMPLE_OF * 2),
                               lambda step: step.pop("sample_count"),
                               lambda step: step.update(passed=step["expected"] - 1),
                               lambda step: step.update(failed=1),
                               lambda step: step.pop("expected")]
        for group in ("gc-aot-0", "gc-aot-1", "gc-aot-2"):
            mutations[group] = [lambda step: step.update(tests_compiler_interval=1001),
                                lambda step: step.update(tests_interval=2),
                                lambda step: step.pop("tests_compiler_interval"),
                                lambda step: step.update(modes=["jit"]),
                                lambda step: step.update(modes=[]),
                                lambda step: step.update(failed=1),
                                lambda step: step.pop("passed"),
                                lambda step: step.update(shard_index=(step["shard_index"] + 1) % 3),
                                lambda step: step.update(shard_index=False),
                                lambda step: step.pop("shard_index"),
                                lambda step: step.update(shard_count=2),
                                lambda step: step.update(shard_count="3"),
                                lambda step: step.pop("shard_count")]
        for group in ("benchmarks", "scaling-1"):
            mutations[group] = [lambda step: step.pop("shapes"),
                                lambda step: step.update(shapes=[]),
                                lambda step: step.update(shapes="chain"),
                                lambda step: step.update(shapes=[1])]
        for group, changes in mutations.items():
            valid = report(group, groups[group])
            merge.validate_report(valid, group, groups[group])
            for index, mutate in enumerate(changes):
                data = copy.deepcopy(valid)
                mutate(data["steps"][-1])
                with self.subTest(group=group, mutation=index), self.assertRaises(ValueError):
                    merge.validate_report(data, group, groups[group])

    def test_dynany_fuzz_requires_full_budget_modes_stress_and_zero_mismatches(self):
        groups = merge.load_groups()
        valid = report("contracts", groups["contracts"])
        merge.validate_report(valid, "contracts", groups["contracts"])
        for key, wrong in (("programs", 2), ("cases", 539), ("parity_cases", 89), ("modes", ["jit", "aot"]),
                           ("program_gc_interval", 0), ("program_gc_interval", True),
                           ("mismatches", 1), ("mismatches", False)):
            for missing in (False, True):
                data = copy.deepcopy(valid)
                step = next(s for s in data["steps"] if s["name"] == "dynany-fuzz")
                if missing:
                    del step[key]
                else:
                    step[key] = wrong
                with self.subTest(key=key, value=wrong, missing=missing), self.assertRaises(ValueError):
                    merge.validate_report(data, "contracts", groups["contracts"])

    def test_reports_require_the_corpus_check_counts(self):
        groups = merge.load_groups()
        valid = report("native-0", groups["native-0"])
        merge.validate_report(valid, "native-0", groups["native-0"])
        for key in ("suite_checks", "mode_checks"):
            for value in (None, 0, "10", True):
                data = copy.deepcopy(valid)
                if value is None:
                    del data["sources"][key]
                else:
                    data["sources"][key] = value
                with self.subTest(key=key, value=value), self.assertRaisesRegex(ValueError, key):
                    merge.validate_report(data, "native-0", groups["native-0"])

    def test_optin_reports_require_exact_shard_modes_and_complete_evidence(self):
        groups = merge.load_groups()
        self.assertNotIn(f"dynany-optin-{merge.DYNANY_SHARDS}", groups)
        for index in range(merge.DYNANY_SHARDS):
            group = f"dynany-optin-{index}"
            self.assertEqual(groups[group], ["bootstrap", group])
            valid = report(group, groups[group])
            merge.validate_report(valid, group, groups[group])
            mutations = [lambda d: d.update(shard_count=3),
                         lambda d: d.update(shard_index=True),
                         lambda d: d.update(modes=["jit"]),
                         lambda d: d.update(subset=True),
                         lambda d: d.update(oracle_cases=d["oracle_cases"] - 1),
                         lambda d: d.update(completed_checks=d["completed_checks"] - 1),
                         lambda d: d.update(corpus_sha256="0" * 64),
                         lambda d: d.update(exceptions_sha256="0" * 64),
                         lambda d: d["cases"].pop(),
                         lambda d: d["results"].pop(),
                         lambda d: d["results"][0].update(mode="aot"),
                         lambda d: d.update(failures=["incomplete"])]
            for mutate in mutations:
                data = copy.deepcopy(valid)
                mutate(data["steps"][-1]["optin"])
                with self.subTest(group=group, mutation=mutate), self.assertRaises(ValueError):
                    merge.validate_report(data, group, groups[group])

    def test_python_int_reports_require_exact_modes_shards_and_source_identity(self):
        groups = merge.load_groups()
        for index in range(merge.PYTHON_INT_SHARDS):
            group = f"python-int-optin-{index}"
            self.assertEqual(groups[group], ["bootstrap", group])
            valid = report(group, groups[group])
            merge.validate_report(valid, group, groups[group])
            mutations = [lambda d: d.update(shard_count=8),
                         lambda d: d.update(shard_index=True),
                         lambda d: d.update(modes=["jit"]),
                         lambda d: d.update(subset=True),
                         lambda d: d.update(gc_stress=True),
                         lambda d: d.update(python="3.13.0"),
                         lambda d: d.update(kind="exploratory-sweep"),
                         lambda d: d.update(compiler_sha256=""),
                         lambda d: d.update(source_sha256="0" * 64),
                         lambda d: d.update(oracle_cases=d["oracle_cases"] - 1),
                         lambda d: d.update(completed_checks=d["completed_checks"] - 1),
                         lambda d: d.update(corpus_sha256="0" * 64),
                         lambda d: d.update(exceptions_sha256="0" * 64),
                         lambda d: d["cases"].pop(),
                         lambda d: d["results"].pop(),
                         lambda d: d["results"][0].update(mode="aot"),
                         lambda d: d.update(failures=["incomplete"])]
            for mutate in mutations:
                data = copy.deepcopy(valid)
                mutate(data["steps"][-1]["python_int_optin"])
                with self.subTest(group=group, mutation=mutate), self.assertRaises(ValueError):
                    merge.validate_report(data, group, groups[group])

    def test_python_int_aggregate_binds_all_shards_to_one_compiler(self):
        names = [f"python-int-optin-{index}" for index in range(merge.PYTHON_INT_SHARDS)]
        # (with the tests-native suite the shards' --native-suite deferral needs)
        groups = merge.parse_groups("all bootstrap tests-native-0 tests-native-1 " + " ".join(names) + "\n" +
                                    "native-0 bootstrap tests-native-0\nnative-1 bootstrap tests-native-1\n" +
                                    "\n".join(f"{name} bootstrap {name}" for name in names))
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            for name in groups:
                if name == "all":
                    continue
                path = directory / f"verification-{name}" / "verification.json"
                path.parent.mkdir()
                path.write_text(json.dumps(report(name, groups[name])))
            merge.merge_reports(directory, groups, COMMIT)
            path = directory / f"verification-{names[0]}" / "verification.json"
            changed = report(names[0], groups[names[0]])
            changed["steps"][-1]["python_int_optin"]["compiler_sha256"] = "f" * 64
            path.write_text(json.dumps(changed))
            with self.assertRaisesRegex(ValueError, "compiler identity differs"):
                merge.merge_reports(directory, groups, COMMIT)
            path.unlink()
            with self.assertRaisesRegex(ValueError, "missing report groups"):
                merge.merge_reports(directory, groups, COMMIT)
            # Even a weakened contract that lists only one otherwise-valid shard fails.
            for old in directory.glob("verification-*/verification.json"):
                old.unlink()
            path.write_text(json.dumps(report(names[0], groups[names[0]])))
            partial = merge.parse_groups(f"all bootstrap {names[0]}\n{names[0]} bootstrap {names[0]}\n")
            with self.assertRaisesRegex(ValueError, f"all {merge.PYTHON_INT_SHARDS} shards"):
                merge.merge_reports(directory, partial, COMMIT)

    def test_optin_sweeps_deferring_to_tests_native_require_its_complete_suite(self):
        # The opt-in sweeps leave expected failures' baselines and AOT checks of byte-identical IR
        # to tests-native (--native-suite): even a contract without its groups cannot drop it.
        names = [f"python-int-optin-{index}" for index in range(merge.PYTHON_INT_SHARDS)]
        native = "native-0 bootstrap tests-native-0\nnative-1 bootstrap tests-native-1\n"
        full = merge.parse_groups("all bootstrap tests-native-0 tests-native-1 " + " ".join(names) + "\n" + native +
                                  "\n".join(f"{name} bootstrap {name}" for name in names))
        without = merge.parse_groups("all bootstrap " + " ".join(names) + "\n" +
                                     "\n".join(f"{name} bootstrap {name}" for name in names))
        for groups, local, error in ((full, False, None), (without, True, None),
                                     (without, False, "defers to tests-native")):
            with self.subTest(groups=list(groups), local=local), tempfile.TemporaryDirectory() as tmp:
                directory = Path(tmp)
                for name in groups:
                    if name == "all":
                        continue
                    data = report(name, groups[name])
                    if local and name.startswith("python-int-optin-"):
                        data["steps"][-1]["python_int_optin"]["native_suite"] = False
                    path = directory / f"verification-{name}" / "verification.json"
                    path.parent.mkdir()
                    path.write_text(json.dumps(data))
                if error is None:
                    merge.merge_reports(directory, groups, COMMIT)
                else:
                    with self.assertRaisesRegex(ValueError, error):
                        merge.merge_reports(directory, groups, COMMIT)
                if groups is full:
                    data = report("native-1", groups["native-1"])
                    data["steps"][-1].update(modes=["jit"])
                    (directory / "verification-native-1" / "verification.json").write_text(json.dumps(data))
                    with self.assertRaisesRegex(ValueError, "defers to tests-native"):
                        merge.merge_reports(directory, groups, COMMIT)

    def test_missing_duplicate_or_unknown_checks_cannot_weaken_the_gate(self):
        contracts = [CONTRACT.replace("contracts bootstrap check-ir", "contracts bootstrap"),
                     CONTRACT + "extra bootstrap check-ir\n",
                     CONTRACT.replace("contracts bootstrap check-ir", "contracts bootstrap unknown"),
                     CONTRACT + "opt-off-0 bootstrap tests-opt-off-0\n",
                     CONTRACT.replace("opt-off-0 bootstrap", "opt-off-0 tests-opt-off-0"),
                     CONTRACT.replace("all bootstrap tests-opt-off", "all bootstrap bootstrap tests-opt-off")]
        for contract in contracts:
            with self.subTest(contract=contract), self.assertRaises(ValueError):
                merge.parse_groups(contract)


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.groups = merge.parse_groups(CONTRACT)
        self.reports = {group: report(group, steps) for group, steps in self.groups.items() if group != "all"}
        self.write_reports()

    def write_reports(self):
        for group, data in self.reports.items():
            path = self.directory / f"verification-{group}" / "verification.json"
            path.parent.mkdir(exist_ok=True)
            path.write_text(json.dumps(data))

    def merged(self):
        return merge.merge_reports(self.directory, self.groups, COMMIT)

    def test_valid_reports_preserve_checks_and_distinguish_parallel_from_runner_time(self):
        self.reports["contracts"]["summary"]["seconds"] = 9.0
        self.write_reports()
        merged = self.merged()
        self.assertEqual([step["name"] for step in merged["steps"]], self.groups["all"])
        self.assertEqual(merged["result"], "pass")
        self.assertEqual(merged["summary"], {"steps": 3, "passed": 3, "failed": 0, "seconds": 9.0})
        self.assertEqual(merged["ci"]["runner_seconds"], 15.0)
        self.assertEqual(merged["ci"]["max_group_seconds"], 9.0)
        self.assertEqual(merged["git"], self.reports["opt-off-0"]["git"])
        self.assertEqual(merged["sources"], self.reports["opt-off-0"]["sources"])
        self.assertEqual(merged["steps"][0]["ci_group"], "opt-off-0")
        self.assertTrue(merged["steps"][2]["log"].endswith("verification-contracts/verify/check-ir.log"))

    def test_missing_group_cannot_report_success(self):
        (self.directory / "verification-contracts/verification.json").unlink()
        with self.assertRaisesRegex(ValueError, "missing report groups"):
            self.merged()

    def test_failed_skipped_missing_reordered_and_unexpected_steps_are_rejected(self):
        original = copy.deepcopy(self.reports["opt-off-0"])
        mutations = [lambda data: data.update(result="fail"),
                     lambda data: data["steps"][1].update(result="skip"),
                     lambda data: data["steps"].pop(),
                     lambda data: data["steps"].reverse(),
                     lambda data: data["steps"].append({"name": "extra", "result": "pass", "seconds": 0}),
                     lambda data: data["summary"].update(failed=1),
                     lambda data: data["summary"].update(passed=1),
                     lambda data: data["steps"][1].update(passed=9),
                     lambda data: data["steps"][1].update(failed=1),
                     lambda data: data["steps"][1].update(failures=["lost case"]),
                     lambda data: data["steps"][1].update(seconds=float("nan"))]
        for mutation in mutations:
            self.reports["opt-off-0"] = copy.deepcopy(original)
            mutation(self.reports["opt-off-0"])
            self.write_reports()
            with self.subTest(report=self.reports["opt-off-0"]), self.assertRaises(ValueError):
                self.merged()

    def test_unexpected_and_duplicate_groups_are_rejected(self):
        self.reports["unknown"] = report("unknown", ["bootstrap", "check-ir"])
        self.write_reports()
        with self.assertRaisesRegex(ValueError, "unexpected group"):
            self.merged()
        (self.directory / "verification-unknown/verification.json").unlink()
        duplicate = self.directory / "verification-opt-off-copy"
        duplicate.mkdir()
        (duplicate / "verification.json").write_text(json.dumps(self.reports["opt-off-0"]))
        with self.assertRaisesRegex(ValueError, "duplicate report group"):
            self.merged()

    def test_commit_source_toolchain_and_bootstrap_drift_are_rejected(self):
        original = copy.deepcopy(self.reports["contracts"])
        changes = [("git", "commit", "d" * 40), ("sources", "test_programs", 4),
                   ("toolchain", "llvm", "LLVM 19")]
        for field, key, value in changes:
            self.reports["contracts"] = copy.deepcopy(original)
            self.reports["contracts"][field][key] = value
            self.write_reports()
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "identity differs"):
                self.merged()
        self.reports["contracts"] = copy.deepcopy(original)
        self.reports["contracts"]["steps"][0]["ir_sha256"] = "e" * 64
        self.write_reports()
        with self.assertRaisesRegex(ValueError, "bootstrap IR hash differs"):
            self.merged()

    def test_all_reports_from_a_previous_commit_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "differs from checkout"):
            merge.merge_reports(self.directory, self.groups, "f" * 40)

    def test_failed_cli_overwrites_a_stale_success_report_and_exits_nonzero(self):
        output = self.directory / "combined.json"
        output.write_text('{"result": "pass"}')
        (self.directory / "verification-contracts/verification.json").unlink()
        with mock.patch.object(merge, "load_groups", return_value=self.groups), \
                mock.patch.object(merge.subprocess, "run", return_value=mock.Mock(stdout=COMMIT)), \
                contextlib.redirect_stderr(io.StringIO()):
            status = merge.main([str(self.directory), "-o", str(output)])
        self.assertEqual(status, 1)
        self.assertEqual(json.loads(output.read_text())["result"], "fail")


class SharedBootstrapTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        # Deliberately list the producer last: its real proof must win deduplication anyway.
        self.groups = merge.parse_groups(CONTRACT + "bootstrap bootstrap\n")
        self.reports = {group: report(group, steps) for group, steps in self.groups.items() if group != "all"}

    def merged(self):
        for group, data in self.reports.items():
            path = self.directory / f"verification-{group}" / "verification.json"
            path.parent.mkdir(exist_ok=True)
            path.write_text(json.dumps(data))
        return merge.merge_reports(self.directory, self.groups, COMMIT)

    def test_shared_bootstrap_preserves_producer_and_counts_serial_work_once(self):
        self.reports["bootstrap"]["summary"]["seconds"] = 10.0
        self.reports["bootstrap"]["steps"][0]["seconds"] = 10.0
        self.reports["contracts"]["summary"]["seconds"] = 9.0
        result = self.merged()
        self.assertEqual(result["steps"][0]["ci_group"], "bootstrap")
        self.assertEqual(result["steps"][0]["seconds"], 10.0)
        self.assertNotIn("bootstrap_reused", result["steps"][0])
        self.assertEqual(result["summary"]["seconds"], 19.0)
        self.assertEqual(result["ci"]["critical_path_seconds"], 19.0)
        self.assertEqual(result["ci"]["max_group_seconds"], 10.0)
        self.assertEqual(result["ci"]["runner_seconds"], 25.0)
        self.assertIn("bootstrap then parallel groups", result["ci"]["timing_scope"])

    def test_missing_producer_is_rejected(self):
        del self.reports["bootstrap"]
        with self.assertRaisesRegex(ValueError, "missing report groups.*bootstrap"):
            self.merged()

    def test_missing_changed_or_malformed_bundle_identity_is_rejected(self):
        for group in self.reports:
            original = copy.deepcopy(self.reports[group])
            for value in (None, "", "e" * 64, "D" * 64, True, 123):
                if group == "bootstrap" and value == "e" * 64:
                    continue  # Valid producer identity, but mismatched consumers, covered below.
                self.reports[group] = copy.deepcopy(original)
                bootstrap = self.reports[group]["steps"][0]
                if value is None:
                    bootstrap.pop("bootstrap_bundle_id")
                else:
                    bootstrap["bootstrap_bundle_id"] = value
                with self.subTest(group=group, value=value), self.assertRaisesRegex(ValueError, "bundle identity"):
                    self.merged()
            self.reports[group] = original
        self.reports["bootstrap"]["steps"][0]["bootstrap_bundle_id"] = "e" * 64
        with self.assertRaisesRegex(ValueError, "bundle identity differs from producer"):
            self.merged()

    def test_producer_cannot_reuse_and_consumers_must_reuse(self):
        for group in self.reports:
            original = copy.deepcopy(self.reports[group])
            values = (True, 0, 1, "false", None) if group == "bootstrap" else (False, 0, 1, "true", None)
            for value in values:
                self.reports[group] = copy.deepcopy(original)
                self.reports[group]["steps"][0]["bootstrap_reused"] = value
                with self.subTest(group=group, value=value), self.assertRaises(ValueError):
                    self.merged()
            self.reports[group] = original
            if group != "bootstrap":
                self.reports[group] = copy.deepcopy(original)
                del self.reports[group]["steps"][0]["bootstrap_reused"]
                with self.subTest(group=group, missing=True), self.assertRaises(ValueError):
                    self.merged()
                self.reports[group] = original
        self.reports["bootstrap"]["steps"][0]["bootstrap_reused"] = False
        self.merged()

    def test_producer_commit_and_failed_fixed_point_are_rejected(self):
        original = copy.deepcopy(self.reports["bootstrap"])
        self.reports["bootstrap"]["git"]["commit"] = "f" * 40
        with self.assertRaisesRegex(ValueError, "differs from checkout"):
            self.merged()
        self.reports["bootstrap"] = original
        self.reports["bootstrap"]["steps"][0]["ir_identical"] = False
        with self.assertRaisesRegex(ValueError, "bootstrap IR identity"):
            self.merged()

    def test_producer_cannot_claim_other_stages(self):
        with self.assertRaisesRegex(ValueError, "producer must run only bootstrap"):
            merge.parse_groups(CONTRACT.replace("contracts bootstrap check-ir", "bootstrap bootstrap check-ir"))


if __name__ == "__main__":
    unittest.main()
