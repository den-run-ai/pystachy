"""The final CI gate must reject incomplete or inconsistent verification artifacts."""
import contextlib
from collections import Counter
import copy
import io
from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
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
# The corpus of the reports below: its cases (which the GC suites' shards hold between them, and the
# gc-ir halves and tests-cpython compile) and its syntax cases
CORPUS_CASES = 60
SYNTAX_CASES = 2


def gc_suite(name):
    """The fields of GC suite NAME: its shard of CORPUS_CASES (halves in JIT, thirds in AOT), of which
    the stressed sample takes the positions of its mode's offset modulo GC_SAMPLE_EVERY and the
    program-stressed run the others, and a share of the mode's 10 checks, 1 of them in the sample."""
    mode = "aot" if name.startswith("gc-aot") else "jit"
    count, index = merge.SHARDED_STEPS[name], int(name[-1])
    offset = merge.GC_SAMPLE_OFFSETS[mode]
    shard = CORPUS_CASES // count + (index < CORPUS_CASES % count)
    sample = len(range(offset, shard, merge.GC_SAMPLE_EVERY))
    checks = 10 // count + (index < 10 % count) - 1
    return {"tests_compiler_interval": 0, "tests_interval": 1, "modes": [mode], "passed": checks, "expected": checks,
            "shard_cases": shard, "cases": shard - sample,
            "stressed_sample": {"every": merge.GC_SAMPLE_EVERY, "offset": offset, "cases": sample, "tests_interval": 1,
                                "tests_compiler_interval": merge.GC_COMPILER_INTERVAL,
                                "passed": 1, "failed": 0, "expected": 1, "failures": []}}


def resize_gc_shard(step, shard):
    """Make STEP's shard SHARD cases, its sample and other cases consistent with it."""
    sample = step["stressed_sample"]
    sample["cases"] = len(range(sample["offset"], shard, sample["every"]))
    step.update(shard_cases=shard, cases=shard - sample["cases"])


# A GC suite's sample, which runs end to end with the compiler GC-stressed too, must be the shard's
# cases at its mode's offset modulo the period, the others the program-stressed run's (each case of the
# shard in one of them), at the compiler's interval, and complete
SAMPLE_MUTATIONS = [lambda step: step.pop("stressed_sample"),
                    lambda step: step.update(stressed_sample=[]),
                    lambda step: step["stressed_sample"].update(every=merge.GC_SAMPLE_EVERY // 2),
                    lambda step: step["stressed_sample"].update(every=merge.GC_SAMPLE_EVERY * 2),
                    lambda step: step["stressed_sample"].update(every=str(merge.GC_SAMPLE_EVERY)),
                    lambda step: step["stressed_sample"].pop("every"),
                    lambda step: step["stressed_sample"].update(offset=step["stressed_sample"]["offset"] + 1),
                    lambda step: step["stressed_sample"].update(   # (the other mode's)
                        offset=merge.GC_SAMPLE_OFFSETS["aot" if step["modes"] == ["jit"] else "jit"]),
                    lambda step: step["stressed_sample"].pop("offset"),
                    lambda step: step["stressed_sample"].update(cases=step["stressed_sample"]["cases"] + 1),
                    lambda step: step["stressed_sample"].update(cases=step["stressed_sample"]["cases"] - 1),
                    lambda step: step["stressed_sample"].update(cases=0),
                    lambda step: step["stressed_sample"].pop("cases"),
                    lambda step: step.update(cases=step["cases"] + 1),   # (a case run twice)
                    lambda step: step.update(cases=step["cases"] - 1),   # (a case never run)
                    lambda step: step.update(cases=0, shard_cases=step["stressed_sample"]["cases"]),
                    lambda step: step.pop("cases"),
                    lambda step: step.update(shard_cases=step["shard_cases"] + 1),
                    lambda step: step.update(shard_cases=0, cases=0),
                    lambda step: step.update(shard_cases=str(step["shard_cases"])),
                    lambda step: step.pop("shard_cases"),
                    # (a sample of a size other than the shard's positions at that offset)
                    lambda step: step.update(shard_cases=step["shard_cases"] + merge.GC_SAMPLE_EVERY,
                                             cases=step["cases"] + merge.GC_SAMPLE_EVERY),
                    lambda step: step.update(shard_cases=step["shard_cases"] - merge.GC_SAMPLE_EVERY,
                                             cases=step["cases"] - merge.GC_SAMPLE_EVERY),
                    lambda step: step["stressed_sample"].update(tests_compiler_interval=0),
                    lambda step: step["stressed_sample"].update(tests_compiler_interval=5000),
                    lambda step: step["stressed_sample"].pop("tests_compiler_interval"),
                    lambda step: step["stressed_sample"].update(tests_interval=2),
                    lambda step: step["stressed_sample"].pop("tests_interval"),
                    lambda step: step["stressed_sample"].update(passed=0),
                    lambda step: step["stressed_sample"].update(passed=0, expected=0),
                    lambda step: step["stressed_sample"].pop("expected"),
                    lambda step: step["stressed_sample"].update(failed=1),
                    lambda step: step["stressed_sample"].update(failures=["lost case"]),
                    lambda step: step["stressed_sample"].pop("failures")]
# The gc-ir halves: the stressed compiler's IR, messages, status and checks identical to stage 2's
GC_IR_MUTATIONS = [lambda step: step.update(ir_identical=False),
                   lambda step: step.update(ir_identical="true"),
                   lambda step: step.pop("ir_identical"),
                   lambda step: step.update(runtime_identical=False),
                   lambda step: step.pop("runtime_identical"),
                   lambda step: step.update(reference="stage1"),
                   lambda step: step.update(compiler_interval=5000),
                   lambda step: step.update(compiler_interval=0),
                   lambda step: step.pop("compiler_interval"),
                   lambda step: step.update(ir_cases=0),
                   lambda step: step.update(ir_cases=True),
                   lambda step: step.pop("ir_cases"),
                   lambda step: step.update(check_cases=-1),
                   lambda step: step.pop("check_cases"),
                   lambda step: step.update(check_identical=False),
                   lambda step: step.update(check_identical="true"),
                   lambda step: step.pop("check_identical"),
                   lambda step: step.update(shard_index=1 - step["shard_index"]),
                   lambda step: step.pop("shard_index"),
                   lambda step: step.update(shard_count=3),
                   lambda step: step.update(result="fail")]


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


@lru_cache(maxsize=1)
def hosted_strata():
    """The first program of the checkout's corpus of each kind tests-cpython samples (merge.HOSTED_STRATA)."""
    programs = merge.dynany_optin.programs()
    return {kind: next(case for case in programs if merge.hosted_stratum(kind, case))
            for kind in merge.HOSTED_STRATA}


@lru_cache(maxsize=1)
def hosted_corpus():
    """The checkout's corpus as tests/verify.sh lists it for tests-cpython: tests/corpus.sh's, in C order."""
    return subprocess.run(["sh", "-c", ". tests/corpus.sh; corpus"], cwd=merge.ROOT, env={**os.environ, "LC_ALL": "C"},
                          check=True, capture_output=True, text=True).stdout.splitlines()


def hosted_cases(index=0):
    """tests-cpython's sample as tests/verify.sh draws it from the checkout's corpus, if from shard INDEX
    of HOSTED_SAMPLE_OF (sample_cases), with the first program of each kind, in the corpus's order."""
    strata = set(hosted_strata().values())
    return [case for position, case in enumerate(hosted_corpus())
            if position % merge.HOSTED_SAMPLE_OF == index or case in strata]


def hosted_sample(step, *cases, strata=None):
    """Make CASES tests-cpython's sample, and STRATA its strata if given."""
    step.update(sample=list(cases), sample_cases=len(cases))
    if strata is not None:
        step.update(sample_strata=strata)


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


@lru_cache(maxsize=1)
def widening_inventory():
    return merge.annotation_widening.discover(merge.ROOT)


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
        if name in merge.PR_NATIVE_STEPS:
            step.update(shard_index=int(name[-1]), shard_count=merge.PR_SHARDED_STEPS[name])
        elif name.startswith(("tests-native-", "tests-opt-off-")):   # thirds of a 10-check suite
            share = 10 // merge.SHARDED_STEPS[name] + (int(name[-1]) < 10 % merge.SHARDED_STEPS[name])
            step.update(passed=share, expected=share)
        if name.startswith("tests-native"):
            step.update(compiler="stage2", modes=["jit", "aot"])
        if name == "tests-cpython":   # every case's IR identical, its sample run end to end
            step.update(reference="stage2", ir_identical=True, ir_cases=CORPUS_CASES, check_cases=SYNTAX_CASES,
                        check_identical=True, modes=["jit", "aot"], sample_index=0,
                        sample_count=merge.HOSTED_SAMPLE_OF)
            hosted_sample(step, *hosted_cases(), strata=dict(hosted_strata()))
        if name.startswith("python-free-"):
            shards = merge.SHARDED_STEPS[name]
            count = 10 // shards + (int(name[-1]) < 10 % shards)
            step.update(passed=count, expected=count)
        if name.startswith("ubsan-"):
            shards = merge.SHARDED_STEPS[name]
            count = 20 // shards + (int(name[-1]) < 20 % shards)
            step.update(passed=count, expected=count)
        if name.startswith("tests-opt-off"):
            step.update(PYSTACHY_OPT=["-all"])
        if name == "gc-self":
            step.update(compiler_interval=5000, ir_identical=True)
        if name == "dynany-fuzz":
            step.update(programs=3, cases=540, parity_cases=90, modes=["jit", "aot", "jit-gc", "aot-gc"],
                        program_gc_interval=1, mismatches=0)
        if name == "annotation-widening":
            step["widening"] = merge.annotation_widening.expected_ci_report(merge.ROOT, "pr" if group == "opt-in" else "full")
        if name == "example-cli":
            step["example_cli"] = {"schema": 1, "result": "pass", "python": (merge.ROOT / ".python-version").read_text().strip(),
                                   "modes": merge.check_example_cli.MODES, "cases": merge.check_example_cli.case_names(),
                                   "integrations": merge.check_example_cli.integrations()}
        if name == "benchmarks":
            programs = merge.benchmark_programs()
            step.update(programs=len(programs), identical=len(programs), timings=[
                {"name": program, "identical": True, "cpython_seconds": 0.1, "jit_seconds": 0.2,
                 "aot_build_seconds": 0.3, "aot_seconds": 0.01} for program in programs])
        if name == "aot-dead-code":
            step.update(opt_in_symbols=12, programs=["plain", "python-int", "dynamic-any", "python-int-import", "dynamic-any-import"],
                        compilers=["CPython-hosted", "stage2"])
        if name.startswith("dynany-optin-"):
            step["optin"] = copy.deepcopy(optin_report(int(name[-1])))
        if name.startswith("python-int-optin-"):
            step["python_int_optin"] = copy.deepcopy(python_int_report(int(name[-1])))
        if name in merge.GC_STEPS:
            step.update(gc_suite(name))
        if name in merge.GC_IR_STEPS:   # halves of the corpus's cases and its 2 syntax cases
            step.update(compiler_interval=merge.GC_COMPILER_INTERVAL, reference="stage2", ir_identical=True,
                        runtime_identical=True, ir_cases=CORPUS_CASES // 2, check_cases=1, check_identical=True)
        if name in merge.SHARDED_STEPS:
            step.update(shard_index=int(name[-1]), shard_count=merge.SHARDED_STEPS[name])
        if name in merge.SCALING_STEPS:
            step.update(shapes=merge.scaling_shapes()[int(name[-1])::2])
        checks.append(step)
    return {"project": "Pystachy", "group": group, "result": "pass",
            "summary": {"steps": len(steps), "passed": len(steps), "failed": 0, "seconds": 6.0},
            "git": {"commit": COMMIT, "dirty": False},
            "sources": {"pystachy.py": {"sha256": "c" * 64}, "test_programs": 5, "suite_checks": 10, "mode_checks": 10,
                        "corpus_cases": CORPUS_CASES, "syntax_cases": SYNTAX_CASES},
            "toolchain": {"llvm": "LLVM 18", "python": "Python 3.13"},
            "platform": {"machine": "x86_64"}, "steps": checks}


class BenchmarkTests(unittest.TestCase):
    def test_report_requires_every_program_once_with_parity_and_positive_timings(self):
        steps = ["bootstrap", "benchmarks"]
        original = report("benchmarks", steps)
        merge.validate_report(original, "benchmarks", steps)
        mutations = [lambda step: step.pop("timings"),
                     lambda step: step.update(timings=[]),
                     lambda step: step.update(timings={}),
                     lambda step: step["timings"].pop(),
                     lambda step: step["timings"].append(step["timings"][0]),
                     lambda step: step["timings"].__setitem__(0, None),
                     lambda step: step["timings"][0].update(name=step["timings"][1]["name"]),
                     lambda step: step["timings"][0].update(name="unknown"),
                     lambda step: step["timings"][0].update(name=[]),
                     lambda step: step["timings"][0].pop("name"),
                     lambda step: step["timings"][0].pop("identical")]
        for field in ("programs", "identical"):
            mutations.append(lambda step, field=field: step.pop(field))
            count = len(merge.benchmark_programs())
            for value in (0, True, str(count), float(count), count - 1, count + 1):
                mutations.append(lambda step, field=field, value=value: step.update({field: value}))
        for value in (False, 1, "true"):
            mutations.append(lambda step, value=value: step["timings"][0].update(identical=value))
        for field in ("cpython_seconds", "jit_seconds", "aot_build_seconds", "aot_seconds"):
            mutations.append(lambda step, field=field: step["timings"][0].pop(field))
            for value in (None, True, "0.1", 0, -1, float("nan"), float("inf"), -float("inf")):
                mutations.append(lambda step, field=field, value=value: step["timings"][0].update({field: value}))
        for index, mutate in enumerate(mutations):
            data = copy.deepcopy(original)
            mutate(data["steps"][1])
            with self.subTest(mutation=index), self.assertRaises(ValueError):
                merge.validate_report(data, "benchmarks", steps)

    def test_inventory_comes_from_checkout_and_cannot_be_empty(self):
        with tempfile.TemporaryDirectory() as temp, mock.patch.object(merge, "ROOT", Path(temp)):
            bench = Path(temp) / "bench"
            bench.mkdir()
            (bench / "one.py").write_text("")
            (bench / ".hidden.py").write_text("")
            (bench / "nested").mkdir()
            (bench / "nested/two.py").write_text("")
            self.assertEqual(merge.benchmark_programs(), ["one"])
            steps = ["bootstrap", "benchmarks"]
            data = report("benchmarks", steps)
            merge.validate_report(data, "benchmarks", steps)
            (bench / "two.py").write_text("")
            with self.assertRaisesRegex(ValueError, "count every"):
                merge.validate_report(data, "benchmarks", steps)
            (bench / "one.py").unlink()
            (bench / "two.py").unlink()
            data["steps"][1].update(programs=0, identical=0, timings=[])
            with self.assertRaisesRegex(ValueError, "no benchmark programs"):
                merge.validate_report(data, "benchmarks", steps)

    def test_producer_rejects_failed_build_stale_output_and_process_mismatches(self):
        source = (merge.ROOT / "tests/verify.sh").read_text()
        stage = source.split("# ---- benchmarks:", 1)[1].split("# ---- example-cli:", 1)[0]
        stage = stage[stage.index("if want benchmarks;"):]
        # Execute the real shell stage with deterministic clocks and a tiny compiler double.
        header = '''want() { return 0; }
now() { echo 0; }
secs() { echo 0.1; }
step() { printf '{"name":"%s","result":"%s"%s}\\n' "$1" "$2" "$5" > "$V/report.json"; [ "$2" = pass ]; }
'''
        oracle = '''import os, sys
print("answer")
print("diagnostic", file=sys.stderr)
sys.exit(7 if os.environ["MOCK_BENCH_MODE"] == "all-nonzero" else 0)
'''
        compiler = '''import os, sys
from pathlib import Path
mode = os.environ["MOCK_BENCH_MODE"]
if sys.argv[1] == "run":
    if mode == "jit-stdout":
        print("unexpected JIT output", flush=True)
    if mode == "jit-stderr":
        print("unexpected JIT diagnostic", file=sys.stderr)
    if mode == "jit-nonzero":
        sys.exit(7)
    os.execv(sys.executable, [sys.executable, sys.argv[2]])
if mode == "build-fail":
    print("build failed", file=sys.stderr)
    sys.exit(7)
if mode == "build-missing":
    sys.exit(0)
if mode == "build-stdout":
    print("unexpected build output")
if mode == "build-stderr":
    print("unexpected build diagnostic", file=sys.stderr)
output = Path(sys.argv[sys.argv.index("-o") + 1])
prefix = 'from pathlib import Path\\nPath("aot-ran").touch()\\n'
if mode == "aot-stdout":
    prefix += 'print("unexpected AOT output")\\n'
if mode == "aot-stderr":
    prefix += 'import sys\\nprint("unexpected AOT diagnostic", file=sys.stderr)\\n'
if mode == "aot-nonzero":
    prefix += 'import sys\\nsys.exit(7)\\n'
output.write_text("#!" + sys.executable + "\\n" + prefix + Path(sys.argv[2]).read_text())
output.chmod(0o644 if mode == "build-not-executable" else 0o755)
sys.exit(7 if mode == "build-fail-after-output" else 0)
'''
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "bench").mkdir()
            (root / "bench/one.py").write_text(oracle)
            verify = root / "verify"
            verify.mkdir()
            (verify / "pystachy2").write_text(f"#!{sys.executable}\n" + compiler)
            (verify / "pystachy2").chmod(0o755)
            for mode in ("pass", "build-fail", "build-fail-after-output", "build-missing", "build-not-executable",
                         "build-stdout", "build-stderr", "jit-stdout", "jit-stderr", "jit-nonzero",
                         "aot-stdout", "aot-stderr", "aot-nonzero", "all-nonzero"):
                with self.subTest(mode=mode):
                    marker = root / "aot-ran"
                    marker.unlink(missing_ok=True)
                    # A previous successful output must never rescue a failed/no-output build.
                    stale = verify / "bench-one.exe"
                    stale.write_text(f"#!{sys.executable}\nfrom pathlib import Path\nPath('aot-ran').touch()\n" + oracle)
                    stale.chmod(0o755)
                    result = subprocess.run(["sh", "-c", header + stage], cwd=root, capture_output=True, text=True,
                                            env={**os.environ, "V": str(verify), "PY": sys.executable, "MOCK_BENCH_MODE": mode},
                                            timeout=10)
                    data = json.loads((verify / "report.json").read_text())
                    log = (verify / "benchmarks.log").read_text()
                    passed = mode == "pass"
                    self.assertEqual(result.returncode, 0 if passed else 1, result.stdout + result.stderr + log)
                    self.assertEqual(data["result"], "pass" if passed else "fail", log)
                    self.assertEqual(data["programs"], 1)
                    self.assertEqual(data["identical"], int(passed))
                    self.assertIs(data["timings"][0]["identical"], passed)
                    self.assertEqual(marker.exists(), not mode.startswith("build-"))
                    if not passed:
                        self.assertIn("FAIL one: CPython=", log)
                        self.assertIn("build diagnostics:", log)
                        self.assertIn("ref stderr:\ndiagnostic\n", log)
                    if mode == "build-fail":
                        self.assertIn("build failed", log)


class ContractTests(unittest.TestCase):
    def setUp(self):
        # The gate's own tests cover filesystem hashing. These aggregate controls vary the
        # reported digest, without rescanning the complete checkout for every mutation.
        corpus = merge.dynany_optin.programs()
        digest = merge.dynany_optin.corpus_digest(merge.ROOT, corpus)
        for module, name, value in ((merge.python_int_gate, "source_digest", "e" * 64),
                                    (merge.python_int_gate, "programs", corpus),
                                    (merge.annotation_widening, "discover", widening_inventory()),
                                    (merge.dynany_optin, "programs", corpus),
                                    (merge.dynany_optin, "corpus_digest", digest)):
            patch = mock.patch.object(module, name, return_value=value)
            patch.start()
            self.addCleanup(patch.stop)

    def test_real_plan_requires_native_suites_and_every_gc_job(self):
        groups = merge.load_groups()
        for alias in ("gc-stress", "gc-ir", "gc-jit", "gc-aot", "ubsan", "native", "opt-off", "python-free", "scaling-1",
                      "python-int-optin"):
            self.assertNotIn(alias, groups)  # Compatibility aliases must not duplicate CI work.
        for group in ("gc-self", "gc-ir-0", "gc-ir-1", "gc-jit-0", "gc-jit-1", "gc-aot-0", "gc-aot-1", "gc-aot-2", "ubsan-0", "ubsan-1",
                      "ubsan-2", "ubsan-3", "ubsan-4", "python-free-0", "python-free-1", "python-free-2", "python-free-3", "runtime-cache"):
            self.assertEqual(groups[group], ["bootstrap", group])
        self.assertNotIn("gc-aot-3", groups)
        self.assertEqual(groups["hosted"], ["bootstrap", "tests-cpython"])  # one job: the IR oracle and its sample
        for shard in ("0", "1", "2"):
            self.assertNotIn("hosted-" + shard, groups)
        for shard in ("0", "1"):
            self.assertEqual(groups["native-" + shard], ["bootstrap", "tests-native-" + shard])
            self.assertEqual(groups["opt-off-" + shard], ["bootstrap", "tests-opt-off-" + shard])
        self.assertEqual(groups["benchmarks"], ["bootstrap", "benchmarks", "example-cli"])
        self.assertEqual(groups["scaling"], ["bootstrap", "scaling-0", "scaling-1"])
        # (all lists the steps in the order a run of all records them: the contracts' steps in their
        # group's order, as the lanes report them, after the opt-in sweeps and before scaling)
        contracts = groups["contracts"][1:]
        at = groups["all"].index(contracts[0])
        self.assertEqual(groups["all"][at:at + len(contracts)], contracts)
        self.assertEqual(groups["all"][at - 1], "annotation-widening")
        self.assertEqual(groups["all"][at + len(contracts):], groups["scaling"][1:])
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
            for group in ("opt-off-0", "opt-off-1", "opt-off-2", "gc-self", "gc-ir-0", "gc-ir-1", "gc-jit-0", "gc-jit-1", "gc-aot-0", "gc-aot-1", "gc-aot-2",
                          "hosted", "native-0", "native-1", "native-2", "python-free-0", "python-free-1",
                          "python-free-2", "python-free-3", "ubsan-0", "ubsan-1", "ubsan-2", "ubsan-3", "ubsan-4", "runtime-cache", "contracts", "benchmarks",
                          "scaling", "dynany-optin-0", "dynany-optin-1", "dynany-optin-2",
                          *(f"python-int-optin-{index}" for index in range(merge.PYTHON_INT_SHARDS))):
                path = directory / f"verification-{group}" / "verification.json"
                original = path.read_text()
                path.unlink()
                with self.subTest(missing=group), self.assertRaisesRegex(ValueError, f"missing report groups.*{group}"):
                    merge.merge_reports(directory, groups, COMMIT)
                path.write_text(original)
            for group in ("gc-jit-1", "gc-aot-0", "gc-aot-2", "native-0", "opt-off-1", "python-free-1",
                          "python-free-2", "python-free-3", "ubsan-0", "ubsan-4"):
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
            # opt-off's thirds run the corpus once per PYSTACHY_OPT setting, the same settings in each
            for settings, scale, error in (([["-all", "-inline"]] * 3, 2, None),
                                           ([["-all", "-inline"]] * 3, 1, "same full-suite check count"),
                                           ([["-all"], ["-all"], ["-inline"]], 1, "same PYSTACHY_OPT settings"),
                                           ([[], [], []], 1, "same PYSTACHY_OPT settings")):
                for index in (0, 1, 2):
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
            for index in (0, 1, 2):
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
            # and the UBSan fifths twice as many
            for checks, error in ((11, "GC JIT shards must cover the same full-suite check count"), (10, None)):
                for path in paths:
                    data = json.loads(path.read_text())
                    data["sources"]["mode_checks"] = checks
                    path.write_text(json.dumps(data))
                if error is not None:
                    with self.subTest(mode_checks=checks), self.assertRaisesRegex(ValueError, error):
                        merge.merge_reports(directory, groups, COMMIT)
            merge.merge_reports(directory, groups, COMMIT)
            # the gc-ir halves compile every corpus case once (sources.corpus_cases) and check every syntax
            # case (sources.syntax_cases); a GC suite's stressed sample counts toward its mode's checks,
            # and its shards hold every corpus case between them
            for group, mutate, error in (
                    ("gc-ir-0", lambda data: data["steps"][1].update(ir_cases=CORPUS_CASES // 2 - 1), "gc-ir halves"),
                    ("gc-ir-1", lambda data: data["steps"][1].update(ir_cases=CORPUS_CASES // 2 + 1), "gc-ir halves"),
                    ("gc-ir-1", lambda data: data["steps"][1].update(check_cases=0), "gc-ir halves"),
                    ("gc-ir-0", lambda data: data["steps"][1].update(check_cases=2), "gc-ir halves"),
                    ("gc-jit-0", lambda data: data["steps"][-1]["stressed_sample"].update(passed=2, expected=2),
                     "GC JIT shards must cover"),
                    ("gc-aot-1", lambda data: data["steps"][-1]["stressed_sample"].update(passed=2, expected=2),
                     "GC AOT shards must cover"),
                    ("gc-aot-0", lambda data: data["steps"][-1].update(passed=4, expected=4), "GC AOT shards must cover"),
                    ("gc-jit-1", lambda data: resize_gc_shard(data["steps"][-1], data["steps"][-1]["shard_cases"] - 1),
                     "GC JIT shards must hold every corpus case"),
                    ("gc-aot-2", lambda data: resize_gc_shard(data["steps"][-1], data["steps"][-1]["shard_cases"] + 1),
                     "GC AOT shards must hold every corpus case")):
                path = directory / f"verification-{group}" / "verification.json"
                original = path.read_text()
                data = report(group, groups[group])
                mutate(data)
                merge.validate_report(data, group, groups[group])   # (each report alone is consistent)
                path.write_text(json.dumps(data))
                with self.subTest(group=group, error=error), self.assertRaisesRegex(ValueError, error):
                    merge.merge_reports(directory, groups, COMMIT)
                path.write_text(original)
            merge.merge_reports(directory, groups, COMMIT)
            # scaling-0 and scaling-1 check every shape of tools/scaling.py once
            path = directory / "verification-scaling" / "verification.json"
            original = path.read_text()
            shapes = merge.scaling_shapes()
            for wrong in (shapes[1::2][1:], shapes[1::2] + shapes[:1], shapes[1::2] + ["unknown"]):
                data = report("scaling", groups["scaling"])
                data["steps"][-1].update(shapes=wrong)
                path.write_text(json.dumps(data))
                with self.subTest(shapes=wrong), self.assertRaisesRegex(ValueError, "every shape of tools/scaling.py"):
                    merge.merge_reports(directory, groups, COMMIT)
            path.write_text(original)

    def test_full_partitions_preserve_every_corpus_case_and_check(self):
        corpus = hosted_corpus()
        self.assertTrue(corpus)
        for suite, count, modes in (("python-free", 4, ["jit", "aot"]),
                                     ("ubsan", 5, ["jit"]), ("coverage", 10, ["jit", "aot"])):
            with self.subTest(suite=suite):
                if suite != "coverage":
                    self.assertEqual(merge.SHARDED_STEPS[f"{suite}-0"], count)
                shards = [subprocess.run(
                    ["tools/shard_cases.sh", f"{index}/{count}"], cwd=merge.ROOT,
                    env={**os.environ, "LC_ALL": "C"}, check=True, capture_output=True,
                    text=True, timeout=10).stdout.splitlines() for index in range(count)]
                self.assertTrue(all(shards))
                self.assertEqual(Counter(case for shard in shards for case in shard), Counter(corpus))
                self.assertEqual(sum(merge.case_checks(shard, modes) for shard in shards),
                                 merge.case_checks(corpus, modes))

    def test_gc_reports_require_original_stress_mode_ir_and_complete_counts(self):
        groups = merge.load_groups()
        mutations = {
            "gc-self": [lambda step: step.update(compiler_interval=5001),
                        lambda step: step.pop("compiler_interval"),
                        lambda step: step.update(ir_identical=False),
                        lambda step: step.pop("ir_identical")],
            # program stress alone, honestly reported, and the sample with the compiler stressed too
            "gc-jit-0": [lambda step: step.update(tests_compiler_interval=1000),
                         lambda step: step.update(tests_compiler_interval=1001),
                         lambda step: step.pop("tests_compiler_interval"),
                         lambda step: step.update(tests_interval=2),
                         lambda step: step.pop("tests_interval"),
                         lambda step: step.update(modes=["aot"]),
                         lambda step: step.update(modes=["jit", "aot"]),
                         lambda step: step.pop("modes"),
                         lambda step: step.update(passed=9),
                         lambda step: step.pop("expected"),
                         *SAMPLE_MUTATIONS],
        }
        shard_mutations = [lambda step: step.update(shard_index=1 - step["shard_index"]),
                           lambda step: step.update(shard_index=False),
                           lambda step: step.pop("shard_index"),
                           lambda step: step.update(shard_count=step["shard_count"] + 1),
                           lambda step: step.update(shard_count=str(step["shard_count"])),
                           lambda step: step.pop("shard_count")]
        for group in ("native-0", "native-1", "native-2", "opt-off-0", "opt-off-1", "opt-off-2",
                      "python-free-0", "python-free-1", "python-free-2", "python-free-3", "ubsan-0", "ubsan-1", "ubsan-2", "ubsan-3", "ubsan-4"):
            mutations[group] = shard_mutations + [lambda step: step.update(passed=step["expected"] - 1),
                                                  lambda step: step.update(failed=1),
                                                  lambda step: step.pop("expected")]
        # the CPython-hosted compiler: identical on every case and syntax check, its sample run end to end
        mutations["hosted"] = [lambda step: step.update(ir_identical=False),
                               lambda step: step.pop("ir_identical"),
                               lambda step: step.update(ir_identical="true"),
                               lambda step: step.update(reference="stage1"),
                               lambda step: step.update(ir_cases=CORPUS_CASES - 1),
                               lambda step: step.update(ir_cases=CORPUS_CASES + 1),
                               lambda step: step.pop("ir_cases"),
                               lambda step: step.update(check_cases=1),
                               lambda step: step.update(check_cases=0),
                               lambda step: step.update(modes=["jit"]),
                               lambda step: step.update(sample_index=1),
                               lambda step: step.update(sample_count=merge.HOSTED_SAMPLE_OF * 2),
                               lambda step: step.pop("sample_count"),
                               lambda step: step.update(passed=step["expected"] - 1),
                               lambda step: step.update(failed=1),
                               lambda step: step.pop("expected"),
                               lambda step: step.update(check_identical=False),
                               lambda step: step.pop("check_identical"),
                               # its sample: a program of each kind, which it holds, once each
                               lambda step: step.pop("sample_strata"),
                               lambda step: step.pop("sample"),
                               lambda step: step.update(sample_cases=step["sample_cases"] + 1),
                               lambda step: step["sample_strata"].pop("sigint"),
                               lambda step: step["sample_strata"].update(sigint=None),
                               lambda step: step["sample_strata"].update(extra=step["sample"][0]),
                               lambda step: hosted_sample(step, *step["sample"], step["sample"][0]),
                               lambda step: hosted_sample(step, *(case for case in step["sample"]
                                                                  if case != step["sample_strata"]["ffi"])),
                               # (the strata alone, padded with junk or with other cases, out of order, or a
                               # case of shard 0 lost or one of another shard added)
                               lambda step: hosted_sample(step, *(case for case in step["sample"]
                                                                  if case in step["sample_strata"].values())),
                               lambda step: hosted_sample(step, *(
                                   case if case in step["sample_strata"].values() else f"tests/programs/x/junk{index}.py"
                                   for index, case in enumerate(step["sample"]))),
                               lambda step: hosted_sample(step, *hosted_cases(1)),
                               lambda step: hosted_sample(step, *reversed(step["sample"])),
                               lambda step: hosted_sample(step, *step["sample"][1:]),
                               lambda step: hosted_sample(step, *step["sample"], hosted_corpus()[-1]),
                               # (a program of another kind, a rejection, a missing or an outside file)
                               lambda step: step["sample_strata"].update(
                                   full=next(case for case in step["sample"] if not merge.hosted_stratum("full", case))),
                               lambda step: hosted_sample(step, *step["sample"], "tests/errors/syntax/x.py", strata={
                                   **step["sample_strata"], "path": "tests/errors/syntax/x.py"}),
                               lambda step: hosted_sample(step, *step["sample"], "tests/programs/x/missing.py", strata={
                                   **step["sample_strata"], "in": "tests/programs/x/missing.py"}),
                               lambda step: hosted_sample(step, *step["sample"], "tests/programs/../../x.py", strata={
                                   **step["sample_strata"], "in": "tests/programs/../../x.py"})]
        for group in ("gc-jit-1", "gc-aot-0", "gc-aot-1", "gc-aot-2"):
            mutations[group] = [lambda step: step.update(tests_compiler_interval=1000),
                                lambda step: step.update(tests_compiler_interval=1001),
                                lambda step: step.update(tests_interval=2),
                                lambda step: step.pop("tests_compiler_interval"),
                                lambda step: step.update(modes=["aot" if step["modes"] == ["jit"] else "jit"]),
                                lambda step: step.update(modes=[]),
                                lambda step: step.update(failed=1),
                                lambda step: step.pop("passed"),
                                lambda step: step.update(shard_index=(step["shard_index"] + 1) % step["shard_count"]),
                                lambda step: step.update(shard_index=False),
                                lambda step: step.pop("shard_index"),
                                lambda step: step.update(shard_count=step["shard_count"] + 1),
                                lambda step: step.update(shard_count=str(step["shard_count"])),
                                lambda step: step.pop("shard_count"),
                                *SAMPLE_MUTATIONS]
        for group in ("scaling",):
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
        # (scaling-0, the scaling group's first step, too)
        valid = report("scaling", groups["scaling"])
        self.assertEqual(valid["steps"][1]["name"], "scaling-0")
        for index, mutate in enumerate(mutations["scaling"]):
            data = copy.deepcopy(valid)
            mutate(data["steps"][1])
            with self.subTest(step="scaling-0", mutation=index), self.assertRaises(ValueError):
                merge.validate_report(data, "scaling", groups["scaling"])
        # Identity reports remain mandatory and validate the same evidence independently of JIT.
        for group in ("gc-ir-0", "gc-ir-1"):
            valid = report(group, groups[group])
            self.assertEqual(valid["steps"][1]["name"], group)
            for index, mutate in enumerate(GC_IR_MUTATIONS):
                data = copy.deepcopy(valid)
                mutate(data["steps"][1])
                with self.subTest(group=group, gc_ir_mutation=index), self.assertRaises(ValueError):
                    merge.validate_report(data, group, groups[group])

    def test_gc_suites_require_both_complete_gc_ir_halves(self):
        # The GC suites run code compiled by stage 2 unstressed: even a contract without the gc-ir
        # halves, or with one of them, cannot drop the stressed compiler's identity.
        aot = "gc-aot-0 bootstrap gc-aot-0\ngc-aot-1 bootstrap gc-aot-1\ngc-aot-2 bootstrap gc-aot-2\n"
        full = merge.parse_groups("all bootstrap gc-ir-0 gc-ir-1 gc-jit-0 gc-jit-1 gc-aot-0 gc-aot-1 gc-aot-2\n"
                                  "gc-ir-0 bootstrap gc-ir-0\ngc-ir-1 bootstrap gc-ir-1\n"
                                  "gc-jit-0 bootstrap gc-jit-0\ngc-jit-1 bootstrap gc-jit-1\n" + aot)
        without = merge.parse_groups("all bootstrap gc-jit-0 gc-jit-1 gc-aot-0 gc-aot-1 gc-aot-2\n"
                                     "gc-jit-0 bootstrap gc-jit-0\ngc-jit-1 bootstrap gc-jit-1\n" + aot)
        half = merge.parse_groups("all bootstrap gc-ir-0 gc-jit-0 gc-jit-1 gc-aot-0 gc-aot-1 gc-aot-2\n"
                                  "gc-ir-0 bootstrap gc-ir-0\n"
                                  "gc-jit-0 bootstrap gc-jit-0\ngc-jit-1 bootstrap gc-jit-1\n" + aot)
        alone = merge.parse_groups("all bootstrap gc-ir-0\ngc-ir-0 bootstrap gc-ir-0\n")
        for groups, error in ((full, None), (without, "gc-ir halves"), (half, "gc-ir halves"),
                              (alone, "gc-ir halves")):
            with self.subTest(groups=groups), tempfile.TemporaryDirectory() as tmp:
                directory = Path(tmp)
                for name in groups:
                    if name == "all":
                        continue
                    path = directory / f"verification-{name}" / "verification.json"
                    path.parent.mkdir()
                    path.write_text(json.dumps(report(name, groups[name])))
                if error is None:
                    merge.merge_reports(directory, groups, COMMIT)
                else:
                    with self.assertRaisesRegex(ValueError, error):
                        merge.merge_reports(directory, groups, COMMIT)

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

    def test_aot_probe_requires_symbol_controls_imports_and_both_compilers(self):
        groups = merge.load_groups()
        valid = report("contracts", groups["contracts"])
        merge.validate_report(valid, "contracts", groups["contracts"])
        for key, wrong in (("opt_in_symbols", 0), ("opt_in_symbols", True),
                           ("programs", ["plain", "python-int", "dynamic-any"]),
                           ("compilers", ["CPython-hosted"]), ("compilers", ["stage2"])):
            for missing in (False, True):
                data = copy.deepcopy(valid)
                step = next(s for s in data["steps"] if s["name"] == "aot-dead-code")
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
        for index in range(merge.DYNANY_SHARDS):
            group = f"dynany-optin-{index}"
            self.assertEqual(groups[group], ["bootstrap", group])
            valid = report(group, groups[group])
            merge.validate_report(valid, group, groups[group])
            mutations = [lambda d: d.update(shard_count=merge.DYNANY_SHARDS + 1),
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
            tail = ["annotation-widening"] if index == 2 else []
            self.assertEqual(groups[group], ["bootstrap", group, *tail])
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
                mutate(data["steps"][1]["python_int_optin"])
                with self.subTest(group=group, mutation=mutate), self.assertRaises(ValueError):
                    merge.validate_report(data, group, groups[group])

    def test_python_int_aggregate_binds_all_shards_to_one_compiler(self):
        names = [f"python-int-optin-{index}" for index in range(merge.PYTHON_INT_SHARDS)]
        # (with the tests-native suite the shards' --native-suite deferral needs)
        groups = merge.parse_groups("all bootstrap tests-native-0 tests-native-1 tests-native-2 " + " ".join(names) + "\n" +
                                    "native-0 bootstrap tests-native-0\nnative-1 bootstrap tests-native-1\nnative-2 bootstrap tests-native-2\n" +
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
        native = "native-0 bootstrap tests-native-0\nnative-1 bootstrap tests-native-1\nnative-2 bootstrap tests-native-2\n"
        full = merge.parse_groups("all bootstrap tests-native-0 tests-native-1 tests-native-2 " + " ".join(names) + "\n" + native +
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

    def test_architecture_namespaces_require_native_evidence(self):
        for group, data in self.reports.items():
            data["platform"] = {"machine": "aarch64"}
            old = self.directory / f"verification-{group}"
            old.rename(self.directory / f"aarch64-verification-{group}")
            path = self.directory / f"aarch64-verification-{group}" / "verification.json"
            path.write_text(json.dumps(data))
        merged = merge.merge_reports(self.directory, self.groups, COMMIT, "aarch64")
        self.assertEqual(merged["platform"]["machine"], "aarch64")
        self.assertEqual([step["name"] for step in merged["steps"]], self.groups["all"])
        # An x86 report cannot pass as ARM even if its artifact was renamed.
        path = self.directory / "aarch64-verification-contracts" / "verification.json"
        data = self.reports["contracts"]
        data["platform"]["machine"] = "x86_64"
        path.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, "expected aarch64 platform evidence"):
            merge.merge_reports(self.directory, self.groups, COMMIT, "aarch64")
        # The default gate still rejects namespaced reports instead of mixing platforms.
        with self.assertRaisesRegex(ValueError, "unexpected report path"):
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


class PullRequestSubsetTests(unittest.TestCase):
    """A pull request's ARM64 smoke gate accepts exactly its groups and never claims full verification."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.groups = merge.parse_groups(CONTRACT + "bootstrap bootstrap\n")
        self.reports = {group: report(group, steps) for group, steps in self.groups.items() if group != "all"}
        for data in self.reports.values():
            data["platform"] = {"machine": "aarch64"}

    def write(self, groups):
        for group in groups:
            path = self.directory / f"aarch64-verification-{group}" / "verification.json"
            path.parent.mkdir(exist_ok=True)
            path.write_text(json.dumps(self.reports[group]))

    def test_subset_requires_exactly_its_groups_and_is_never_labelled_all(self):
        self.write(["bootstrap", "contracts"])
        result = merge.merge_reports(self.directory, self.groups, COMMIT, "aarch64", ["contracts"])
        self.assertEqual(result["group"], "subset")
        self.assertEqual([step["name"] for step in result["steps"]], ["bootstrap", "check-ir"])
        self.assertEqual(result["ci"]["subset"], ["bootstrap", "contracts"])
        self.assertEqual(result["summary"]["steps"], 2)
        # Without a subset, the same artifacts remain an incomplete full matrix.
        with self.assertRaisesRegex(ValueError, r"missing report groups: \['opt-off-0'\]"):
            merge.merge_reports(self.directory, self.groups, COMMIT, "aarch64")

    def test_missing_extra_and_foreign_subset_reports_are_rejected(self):
        self.write(["contracts"])
        with self.assertRaisesRegex(ValueError, r"missing report groups: \['bootstrap'\]"):
            merge.merge_reports(self.directory, self.groups, COMMIT, "aarch64", ["contracts"])
        self.write(["bootstrap", "opt-off-0"])
        with self.assertRaisesRegex(ValueError, r"unexpected report groups: \['opt-off-0'\]"):
            merge.merge_reports(self.directory, self.groups, COMMIT, "aarch64", ["contracts"])
        self.reports["contracts"]["platform"]["machine"] = "x86_64"
        self.write(["contracts"])
        with self.assertRaisesRegex(ValueError, "expected aarch64 platform evidence"):
            merge.merge_reports(self.directory, self.groups, COMMIT, "aarch64", ["contracts", "opt-off-0"])

    def test_invalid_subsets_are_rejected_before_reading_reports(self):
        for subset in ([], ["all"], ["nope"], ["contracts", "contracts"], [""]):
            with self.subTest(subset=subset), self.assertRaisesRegex(ValueError, "invalid report subset"):
                merge.merge_reports(self.directory, self.groups, COMMIT, "aarch64", subset)

    def test_cli_labels_subset_success_and_failure(self):
        output = self.directory / "combined.json"
        self.write(["bootstrap", "contracts"])
        with mock.patch.object(merge, "load_groups", return_value=self.groups), \
                mock.patch.object(merge.subprocess, "run", return_value=mock.Mock(stdout=COMMIT)), \
                contextlib.redirect_stdout(io.StringIO()) as stdout:
            status = merge.main([str(self.directory), "--machine", "aarch64", "--groups", "contracts", "-o", str(output)])
        self.assertEqual(status, 0)
        self.assertEqual(json.loads(output.read_text())["group"], "subset")
        self.assertIn("verification subset: 2 checks passed across 2 groups", stdout.getvalue())
        with mock.patch.object(merge, "load_groups", return_value=self.groups), \
                mock.patch.object(merge.subprocess, "run", return_value=mock.Mock(stdout=COMMIT)), \
                contextlib.redirect_stderr(io.StringIO()):
            status = merge.main([str(self.directory), "--machine", "aarch64", "--groups", "", "-o", str(output)])
        self.assertEqual(status, 1)
        self.assertEqual(json.loads(output.read_text())["group"], "subset")
        self.assertEqual(json.loads(output.read_text())["result"], "fail")


class PullRequestProfileTests(unittest.TestCase):
    """Sparse evidence is exact, complete for its compact contract, and never release evidence."""

    def setUp(self):
        env = mock.patch.dict(os.environ, {"CI_BASE_SHA": ""})
        env.start()
        self.addCleanup(env.stop)
        # The opt-in validators separately test real source-digest drift. Keep this test focused
        # on aggregate scope, exact case selection, and the producer/consumer boundary.
        digest = mock.patch.object(merge.python_int_gate, "source_digest", return_value="e" * 64)
        digest.start()
        self.addCleanup(digest.stop)
        discovery = mock.patch.object(merge.annotation_widening, "discover", return_value=widening_inventory())
        discovery.start()
        self.addCleanup(discovery.stop)
        self.groups = merge.load_groups("pr")
        self.selection = merge.pr_selection()
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.corpus = hosted_corpus()
        self.native = {mode: [subprocess.run(["sh", "-c", f". tests/corpus.sh; corpus_shard {index} {count}"],
                                            cwd=merge.ROOT, check=True, capture_output=True, text=True).stdout.splitlines()
                              for index in range(count)] for mode, count in (("jit", 2), ("aot", 4))}
        self.data = {}
        for group, steps in self.groups.items():
            if group == "all":
                continue
            data = report(group, steps)
            data["profile"] = "full" if group == "bootstrap" else "pr"
            if group != "bootstrap":
                data["selection"] = copy.deepcopy(self.selection)
            data["sources"].update(corpus_cases=len(self.corpus),
                                   syntax_cases=sum(Path(case).name.startswith("syntax_") for case in self.corpus),
                                   suite_checks=merge.case_checks(self.corpus, ["jit", "aot"]),
                                   mode_checks=merge.case_checks(self.corpus, ["jit"]))
            for step in data["steps"]:
                name = step["name"]
                if name == "tests-cpython":
                    step.update(ir_cases=data["sources"]["corpus_cases"], check_cases=data["sources"]["syntax_cases"])
                if name in merge.PR_SHARDED_STEPS:
                    cases = (self.native[merge.PR_NATIVE_STEPS[name]][int(name[-1])] if name.startswith("tests-native-")
                             else self.selection["cases"])
                    step.update(selected_cases=list(cases), shard_count=merge.PR_SHARDED_STEPS[name])
                    modes = [merge.PR_NATIVE_STEPS[name]] if name in merge.PR_NATIVE_STEPS else ["jit", "aot"]
                    expected = merge.case_checks(cases, modes)
                    if name in merge.GC_STEPS:
                        mode = step["modes"][0]
                        offset = merge.GC_SAMPLE_OFFSETS[mode]
                        sample = cases[offset::merge.GC_SAMPLE_EVERY]
                        rest = [case for position, case in enumerate(cases)
                                if position % merge.GC_SAMPLE_EVERY != offset]
                        expected = merge.case_checks(rest, [mode])
                        sample_checks = merge.case_checks(sample, [mode])
                        step.update(shard_cases=len(cases), cases=len(rest))
                        step["stressed_sample"].update(cases=len(sample), expected=sample_checks, passed=sample_checks)
                    elif name == "ubsan-0":
                        expected = 2 * merge.case_checks(cases, ["jit"])
                        step.update(modes=["aot", "jit"], ir_identical=True,
                                    cflags="-fsanitize=undefined -fno-sanitize-recover=all --rtlib=compiler-rt",
                                    jit_preload="/llvm/lib/libclang_rt.ubsan_standalone-x86_64.so")
                    elif name == "python-free-0":
                        step.update(python_on_path=False, ir_identical=True, path_tools=["sh", "clang", "lli"])
                    else:
                        step.update(compiler="stage2", modes=modes)
                    step.update(expected=expected, passed=expected)
                for field, make in (("optin", optin_report), ("python_int_optin", python_int_report)):
                    if field not in step:
                        continue
                    selected = [case for case in self.selection["cases"] if case.startswith("tests/programs/")]
                    rows = {(row["case"], row["mode"]): row for index in range(3)
                            for row in make(index)["results"]}
                    rows = [rows[(case, mode)] for case in selected for mode in ("jit", "aot")]
                    step[field].update(shard_index=0, shard_count=1, subset=True, cases=selected,
                                       oracle_cases=len(selected), expected_checks=len(rows), completed_checks=len(rows),
                                       passed_checks=sum(row["result"] == "pass" for row in rows),
                                       expected_failures=sum(row["result"] == "expected-failure" for row in rows),
                                       results=rows)
            self.data[group] = data
            self.write(group, data)

    def write(self, group, data):
        path = self.directory / f"verification-{group}" / "verification.json"
        path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps(data))
        return path

    def merge(self):
        return merge.merge_reports(self.directory, self.groups, COMMIT, profile="pr")

    def test_thirteen_groups_reuse_bootstrap_and_cover_every_native_case_in_two_jit_and_four_aot_workers(self):
        result = self.merge()
        self.assertEqual(len(self.groups) - 2, 13)
        self.assertEqual(result["profile"], "pr")
        self.assertEqual(result["group"], "pr")
        self.assertEqual(result["selection"], self.selection)
        self.assertEqual([step["name"] for step in result["steps"]], self.groups["all"])
        for mode, shards in self.native.items():
            cases = [case for shard in shards for case in shard]
            self.assertEqual(Counter(cases), Counter(self.corpus), mode)
        self.assertEqual(result["steps"][0]["ci_group"], "bootstrap")
        self.assertNotIn("bootstrap_reused", result["steps"][0])
        native = [step for step in result["steps"] if step["name"] in merge.PR_NATIVE_STEPS]
        self.assertEqual(sum(step["expected"] for step in native), 2 * merge.case_checks(self.corpus, ["jit"]))
        for mode in ("jit", "aot"):
            pairs = [(case, mode) for step in native if step["modes"] == [mode] for case in step["selected_cases"]]
            self.assertEqual(Counter(pairs), Counter((case, mode) for case in self.corpus))
        for group in ("native-jit-0", "native-jit-1", "native-aot-0", "native-aot-1", "native-aot-2", "native-aot-3",
                      "safety-1", "opt-in", "cache-gc"):
            path = self.directory / f"verification-{group}" / "verification.json"
            path.unlink()
            with self.subTest(missing=group), self.assertRaisesRegex(ValueError, "missing report groups"):
                self.merge()
            self.write(group, self.data[group])

    def test_profile_selection_and_scope_cannot_be_downgraded_or_fabricated(self):
        for group, mutate in (
                ("contracts", lambda data: data.pop("profile")),
                ("contracts", lambda data: data.update(profile="full")),
                ("bootstrap", lambda data: data.update(profile="pr")),
                ("safety-0", lambda data: data["selection"].update(base_commit="f" * 40)),
                ("safety-0", lambda data: data["selection"]["cases"].pop()),
                ("native-jit-1", lambda data: data["steps"][1].update(shard_count=3)),
                ("native-aot-2", lambda data: data["steps"][1].update(shard_count=2)),
                ("native-jit-0", lambda data: data["steps"][1]["selected_cases"].pop()),
                ("native-jit-0", lambda data: data["steps"][1].update(modes=["aot"])),
                ("native-aot-0", lambda data: data["steps"][1].update(modes=["jit", "aot"])),
                ("native-aot-1", lambda data: data["steps"][1].update(compiler="CPython-hosted")),
                ("native-aot-1", lambda data: data["steps"][0].update(bootstrap_bundle_id="f" * 64)),
                ("safety-0", lambda data: data["steps"][1]["selected_cases"].reverse()),
                ("safety-0", lambda data: data["steps"][1].update(expected=1, passed=1)),
                ("safety-0", lambda data: data["steps"][2].update(python_on_path=True)),
                ("safety-1", lambda data: data["steps"][1].update(cflags="")),
                ("safety-1", lambda data: data["steps"][2]["stressed_sample"].update(expected=1, passed=1)),
                ("opt-in", lambda data: data["steps"][1]["optin"].update(subset=False)),
                ("opt-in", lambda data: data["steps"][2]["python_int_optin"]["results"].pop()),
                ("opt-in", lambda data: data["steps"][3]["widening"]["cases"].pop())):
            changed = copy.deepcopy(self.data[group])
            mutate(changed)
            self.write(group, changed)
            with self.subTest(group=group, mutate=mutate), self.assertRaises(ValueError):
                self.merge()
            self.write(group, self.data[group])
        with self.assertRaisesRegex(ValueError, "profile differs"):
            merge.validate_report(self.data["contracts"], "contracts", self.groups["contracts"])
        with self.assertRaisesRegex(ValueError, "profile differs"):
            merge.merge_reports(self.directory, self.groups, COMMIT)
        with self.assertRaisesRegex(ValueError, "requires every compact group"):
            merge.merge_reports(self.directory, self.groups, COMMIT, subset=["contracts"], profile="pr")

    def test_native_mode_coverage_rejects_duplicate_or_substituted_cases_with_unchanged_counts(self):
        for mode in ("jit", "aot"):
            changed = copy.deepcopy(self.data)
            left = changed[f"native-{mode}-0"]["steps"][1]
            right = changed[f"native-{mode}-1"]["steps"][1]
            left["selected_cases"][0] = right["selected_cases"][0]
            with self.subTest(mode=mode), self.assertRaisesRegex(ValueError, "every corpus case and mode exactly once"):
                merge.validate_pr_native_coverage(changed)
        changed = copy.deepcopy(self.data)
        changed.pop("native-aot-3")
        with self.assertRaisesRegex(ValueError, "two complete JIT halves and four AOT quarters"):
            merge.validate_pr_native_coverage(changed)

    def test_native_aot_gate_rejects_old_halves_and_forged_quarter_membership(self):
        changed = copy.deepcopy(self.data)
        for index in range(2):
            step = changed[f"native-aot-{index}"]["steps"][1]
            step.update(selected_cases=self.native["jit"][index], shard_count=2)
            step["expected"] = step["passed"] = merge.case_checks(step["selected_cases"], ["aot"])
        changed.pop("native-aot-2")
        changed.pop("native-aot-3")
        with self.assertRaisesRegex(ValueError, "four AOT quarters"):
            merge.validate_pr_native_coverage(changed)
        # All quarter names and a plausible total still cannot replace their exact case inventories.
        for index in (2, 3):
            step = copy.deepcopy(self.data[f"native-aot-{index}"]["steps"][1])
            step["selected_cases"] = self.native["jit"][index % 2]
            step["expected"] = step["passed"] = merge.case_checks(step["selected_cases"], ["aot"])
            with self.subTest(index=index), self.assertRaisesRegex(ValueError, "selected cases differ"):
                merge.validate_pr_case_step(step, self.selection, f"native-aot-{index}")


class PullRequestMatrixTests(unittest.TestCase):
    """The compact PR matrix and full main/release matrix each match their own gate contract."""

    def test_profile_matrices_match_the_harness_and_gate(self):
        text = (merge.ROOT / ".github/workflows/ci.yml").read_text()
        job = text[text.index("\n  verification:\n"):text.index("\n  pr-variants:\n")]
        matrix = re.search(r"group: \$\{\{ fromJSON\(github\.event_name == 'pull_request' && '([^']+)' \|\| '([^']+)'\) \}\}", job)
        self.assertIsNotNone(matrix, "the verification matrix's explicit PR and full group lists")
        for profile, value in zip(("pr", "full"), matrix.groups()):
            groups = merge.load_groups(profile)
            folded = {"native-jit-0", "native-jit-1"} if profile == "pr" else set()
            self.assertEqual(sorted(json.loads(value)), sorted(name for name in groups if name not in {"all", "bootstrap", *folded}))
        self.assertEqual(len(json.loads(matrix[1])), 11)
        machines = re.search(r"machine: \$\{\{ fromJSON\(github\.event_name == 'pull_request' && '([^']+)' \|\| '([^']+)'\) \}\}", job)
        self.assertIsNotNone(machines)
        self.assertEqual(json.loads(machines[1]), ["x86_64"])
        self.assertEqual(json.loads(machines[2]), ["x86_64", "aarch64"])
        self.assertIn("VERIFY_PROFILE: ${{ github.event_name == 'pull_request' && 'pr' || 'full' }}", text)
        self.assertIn('--profile "$VERIFY_PROFILE"', text)
        variants = text[text.index("\n  pr-variants:\n"):text.index("\n  qualification:\n")]
        self.assertIn('worker: [0, 1]', variants)
        self.assertIn('VERIFY_PROFILE: pr', variants)
        self.assertIn('name: x86_64-verification-native-jit-${{ matrix.worker }}', variants)
        native_run = variants.index('run: tests/verify.sh "native-jit-$VARIANT_WORKER"')
        native_upload = variants.index('name: Upload native JIT report')
        variant_run = variants.index('run: python3 tools/pr_variants.py --worker "$VARIANT_WORKER"')
        self.assertLess(native_run, native_upload)
        self.assertLess(native_upload, variant_run)
        self.assertIn('name: pr-variants-${{ matrix.worker }}', variants)
        self.assertIn('needs: [bootstrap, verification, pr-variants, qualification]', text)
        # An ambient PR setting must not silently downgrade a caller asking for full evidence.
        with mock.patch.dict(os.environ, {"VERIFY_PROFILE": "pr"}):
            self.assertEqual(merge.load_groups(), merge.load_groups("full"))


if __name__ == "__main__":
    unittest.main()
