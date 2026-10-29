"""Exercise the real GC verification shell with deterministic compiler/test doubles: the bounded
self-compilation, the gc-ir halves (the compiler collecting every 1000 allocations against stage 2,
through the real tools/irsame.sh) and the program-stressed suites, each with its compiler-stressed
sample drawn from its own balanced shard; and the CI gate (merge_verification) on their reports."""
from collections import Counter
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest

import merge_verification as merge
from test_verify_case_weights import reference_shards

ROOT = Path(__file__).resolve().parent.parent
TIMEOUT = shutil.which("timeout")
# The cases the doubles single out, and programs enough that each AOT third holds more than
# GC_SAMPLE_OFFSETS["aot"] cases, so that every shard's sample has a case
NAMED = ["tests/programs/x/example.py", "tests/programs/x/syntax_example.py", "tests/deviations/example.py",
         "tests/errors/x/example.py", "tests/errors/x/syntax_example.py"]
FILLERS = [f"tests/programs/x/fill_{index:02d}.py" for index in range(40)]
CASES = NAMED + FILLERS
# tests/case_weights.txt of the fixture: varied weights, so that a shard's order (heaviest first) is not
# its C order, and the sample is seen to be taken in shard_cases's order
DEFAULTS = {"program": 1000, "rejection": 4}
WEIGHTS = {"tests/programs/x/example.py": 2600, "tests/deviations/example.py": 1500, "tests/errors/x/example.py": 7,
           **{case: 300 + index * 397 % 1700 for index, case in enumerate(FILLERS)}}


def checks(case):
    """The checks tests/run.sh makes of CASE in one mode (tests/verify.sh's checks)."""
    return 2 if case.rsplit("/", 1)[1].startswith("syntax_") else 1


def shards(count):
    """corpus_shard's shards of the fixture's corpus, each heaviest first."""
    return reference_shards(CASES, WEIGHTS, DEFAULTS, count)[0]


def split(group):
    """GC suite GROUP's mode, shard, stressed sample and program-stressed rest, as tests/verify.sh means
    to select them: the shard's cases at positions OFFSET modulo EVERY, and its others, in its order."""
    mode = "aot" if group.startswith("gc-aot") else "jit"
    shard = shards(merge.SHARDED_STEPS[group])[int(group[-1])]
    offset, every = merge.GC_SAMPLE_OFFSETS[mode], merge.GC_SAMPLE_EVERY
    return (mode, shard, [case for i, case in enumerate(shard) if i % every == offset],
            [case for i, case in enumerate(shard) if i % every != offset])


def half(case):
    """The gc-ir half that compiles CASE."""
    return next(index for index, shard in enumerate(shards(2)) if case in shard)


GC_STEPS = ["gc-self", "gc-ir-0", "gc-ir-1", "gc-jit-0", "gc-jit-1", "gc-aot-0", "gc-aot-1", "gc-aot-2"]
# group, mode and its steps after bootstrap
SUITES = [("gc-jit-0", "jit", ["gc-ir-0", "gc-jit-0"]), ("gc-jit-1", "jit", ["gc-ir-1", "gc-jit-1"]),
          ("gc-aot-0", "aot", ["gc-aot-0"]), ("gc-aot-1", "aot", ["gc-aot-1"]), ("gc-aot-2", "aot", ["gc-aot-2"])]
# The gate's contract for these groups alone (tests/verify.sh --list's, without the other groups)
CONTRACT = ("all bootstrap gc-ir-0 gc-ir-1 gc-jit-0 gc-jit-1 gc-aot-0 gc-aot-1 gc-aot-2\n" +
            "".join(f"{group} bootstrap {' '.join(steps)}\n" for group, _, steps in SUITES))


@unittest.skipUnless(TIMEOUT, "GNU timeout is required by verification")
class GCVerificationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in ("tests", "tests/programs", "tests/programs/x", "tests/deviations", "tests/errors",
                     "tests/errors/x", "src", "lib", "ryu", "mpz", "bin", "tools"):
            (self.root / name).mkdir()
        for name in ("tests/verify.sh", "tests/corpus.sh", "tools/irsame.sh"):
            shutil.copy(ROOT / name, self.root / name)
        for name in ("pystachy.py", "runtime.py", "runtime.c", "tests/programs/x/example.py",
                     "tests/programs/x/syntax_example.py", "tests/deviations/example.py", *FILLERS):
            (self.root / name).write_text("# fixture\n")
        (self.root / "tests/errors/x/example.py").write_text("# error: mock rejection\n")
        (self.root / "tests/errors/x/syntax_example.py").write_text("# error: syntax_example.py: mock syntax\n")
        (self.root / "tests/case_weights.txt").write_text(
            "# fixture\n" + "".join(f"default {kind} {weight}\n" for kind, weight in DEFAULTS.items()) +
            "".join(f"{weight} {case}\n" for case, weight in WEIGHTS.items()))
        compiler = self.root / "bin/compiler"
        compiler.write_text(f"#!{sys.executable}\n" + '''import os
import signal
if os.environ.get("VERIFY_MOCK_MODE") == "timeout-kill" and os.environ.get("PYSTACHY_GC_STRESS") == "5000":
    signal.signal(signal.SIGTERM, signal.SIG_IGN)   # before the other imports: TERM must find it ignored
from pathlib import Path
import shutil
import sys
import time
args = sys.argv[1:]
if args == ["-"]:
    os.execv(sys.executable, [sys.executable, "-"])
if args == ["--version"]:
    print("mock compiler")
    sys.exit(0)
if not args:  # (tools/irsame.sh asks the usage whether rt exists)
    print("usage: pystachy run FILE.py\\n       pystachy rt runtime.py [-o OUT.ll]", file=sys.stderr)
    sys.exit(2)
mode = os.environ.get("VERIFY_MOCK_MODE", "")
stress = os.environ.get("PYSTACHY_GC_STRESS", "")
if args[0] in ("ir", "rt", "check") and (args[1].startswith("tests/") or (args[0] == "rt" and stress == "1000")):
    # a case of the corpus, or runtime.py, compiled by stage 2 or by it collecting every 1000 (gc-ir)
    assert stress in ("", "1000"), stress
    case = args[1]
    if args[0] != "check":
        assert os.environ.get("PYSTACHY_IRCHECK") == "1"
    with open("compiles.log", "a") as log:
        print(args[0], case, stress or "-", file=log)
    stressed = stress == "1000"
    target = {"gc-ir-differs": "tests/programs/x/example.py", "gc-msg-differs": "tests/errors/x/syntax_example.py",
              "gc-status-differs": "tests/deviations/example.py", "gc-check-differs": "tests/programs/x/syntax_example.py",
              "gc-rt-differs": "runtime.py"}.get(mode)
    differs = stressed and case == target and (args[0] == "check") == (mode == "gc-check-differs")
    if "/errors/" in case:
        print(f"{case}:1: error: mock {'stressed ' if differs else ''}rejection", file=sys.stderr)
        sys.exit(1)
    if args[0] == "check":
        print(" (stressed)" if differs else "", end="")
        sys.exit(0)
    output = Path(args[args.index("-o") + 1])
    if case == "runtime.py":
        output.write_text("wrong runtime IR\\n" if differs else "fixed point\\n")
        sys.exit(0)
    output.write_text(f"IR of {case}{' (stressed)' if differs and mode == 'gc-ir-differs' else ''}\\n")
    sys.exit(3 if differs and mode == "gc-status-differs" else 0)
if args[0] == "pystachy.py":
    args = args[1:]
output = Path(args[args.index("-o") + 1])
if args[0] == "build":
    shutil.copy(__file__, output)
    output.chmod(0o755)
else:
    text = "fixed point\\n"
    if stress:
        assert stress == "5000", stress
        assert os.environ["PYSTACHY_GC"] == "stats"
        Path("gc-child.pid").write_text(str(os.getpid()))
        if mode in ("timeout", "timeout-kill", "signal"):
            time.sleep(30)
        if mode == "failure":
            print("mock compiler failed", file=sys.stderr)
            sys.exit(7)
        if mode == "mismatch":
            text = "wrong IR\\n"
        print("gc statistics", file=sys.stderr)
    output.write_text(text)
''')
        compiler.chmod(0o755)
        suite = self.root / "tests/run.sh"
        # (a program-stressed run of a shard's cases, or its sample with the compiler stressed too;
        # VERIFY_MOCK_RUN="MODE KIND FIRST" fails the run of that mode and kind whose first case is FIRST)
        suite.write_text('''#!/bin/sh
[ "$PYSTACHY_GC_STRESS_PROGRAM" = 1 ] || exit 9
case $PYSTACHY_CACHE in */build/verify/gc-cache) ;; *) exit 9 ;; esac
case ${PYSTACHY_GC_STRESS-unset} in 1000) kind=sample ;; unset) kind=suite ;; *) exit 9 ;; esac
mode=$2; shift 2
[ "$LC_ALL" = C.UTF-8 ] && [ $# -gt 0 ] || exit 9
case "$mode" in jit|aot) ;; *) echo "invalid mode: $mode"; exit 9 ;; esac
echo "suite: $mode $kind"
echo "$mode $kind $*" >> runs.log
checks=0
for file; do
  echo "selected: $file"
  case "$file" in
    tests/programs/x/syntax_example.py|tests/errors/x/syntax_example.py) checks=$((checks + 2)) ;;
    tests/programs/x/*.py|tests/deviations/example.py|tests/errors/x/example.py) checks=$((checks + 1)) ;;
    *) exit 9 ;;
  esac
done
if [ "$VERIFY_MOCK_MODE" = run-failure ] && [ "$VERIFY_MOCK_RUN" = "$mode $kind $1" ]; then
  echo "$((checks - 1)) passed, 1 failed"
  exit 1
fi
if [ "$VERIFY_MOCK_MODE" = "short-$kind" ]; then
  echo "$((checks - 1)) passed, 0 failed"
  exit 0
fi
echo "$checks passed, 0 failed"
''')
        suite.chmod(0o755)
        timeout = self.root / "bin/timeout"
        timeout.write_text(f"#!{sys.executable}\n" + f'''import os
import sys
assert sys.argv[1:4] == ["--verbose", "--kill-after=10s", "10m"]
mode = os.environ["VERIFY_MOCK_MODE"]
# timeout-kill's mock must ignore TERM before it comes: 0.2s is less than a cold Python's start
limit = "3s" if mode == "timeout-kill" else "0.2s" if mode.startswith("timeout") else "10s"
os.execv({TIMEOUT!r}, [{TIMEOUT!r}, "--verbose", "--kill-after=0.2s", limit, *sys.argv[4:]])
''')
        timeout.chmod(0o755)
        self.env = {**os.environ, "PY": str(compiler), "LC_ALL": "C.UTF-8",
                    "PATH": str(self.root / "bin") + os.pathsep + os.environ["PATH"]}
        for name in ("PYSTACHY_GC_STRESS", "PYSTACHY_GC_STRESS_PROGRAM", "PYSTACHY_CACHE", "PYSTACHY_JOBS",
                     "VERIFY_MOCK_RUN"):
            self.env.pop(name, None)

    def run_group(self, group, mode="pass", run=None):
        for name in ("compiles.log", "runs.log"):
            (self.root / name).unlink(missing_ok=True)
        env = {**self.env, "VERIFY_MOCK_MODE": mode}
        if run is not None:
            env["VERIFY_MOCK_RUN"] = run
        result = subprocess.run(["sh", "tests/verify.sh", group], cwd=self.root, env=env,
                                text=True, capture_output=True, timeout=60)
        report = json.loads((self.root / "build/verification.json").read_text())
        logs = {step["name"]: (self.root / step["log"]).read_text() for step in report["steps"]}
        return result, report, logs

    def runs(self):
        """The suite runs, in order: (mode, sample or suite, cases)."""
        path = self.root / "runs.log"
        return [(line.split()[0], line.split()[1], line.split()[2:])
                for line in (path.read_text().splitlines() if path.exists() else [])]

    def compiles(self):
        """The corpus compilations of gc-ir: (command, file, stress)."""
        path = self.root / "compiles.log"
        return [tuple(line.split()) for line in (path.read_text().splitlines() if path.exists() else [])]

    def mutate_verify(self, old, new):
        """Replace OLD, which tests/verify.sh holds once, with NEW in the fixture's copy."""
        path = self.root / "tests/verify.sh"
        text = path.read_text()
        self.assertEqual(text.count(old), 1, old)
        path.write_text(text.replace(old, new))

    def gate(self, reports):
        """The CI gate on these groups' reports (as one checkout's: the fixture is no git repository)."""
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            for group, report in reports.items():
                report["git"]["commit"] = "a" * 40
                (directory / f"verification-{group}").mkdir()
                (directory / f"verification-{group}" / "verification.json").write_text(json.dumps(report))
            return merge.merge_reports(directory, merge.parse_groups(CONTRACT))

    def test_fixture_shards_hold_samples_in_their_own_order(self):
        # (the preconditions of the tests below: each shard's sample has a case, and is not its C order)
        for group, _, _ in SUITES:
            mode, shard, sample, rest = split(group)
            self.assertTrue(sample and rest, group)
            self.assertNotEqual(shard, sorted(shard), group)

    def test_self_compile_preserves_ir_stress_and_gc_diagnostics(self):
        result, report, logs = self.run_group("gc-self")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(report["result"], "pass")
        self.assertEqual([step["name"] for step in report["steps"]], ["bootstrap", "gc-self"])
        step = report["steps"][-1]
        self.assertTrue(step["ir_identical"])
        self.assertEqual(step["compiler_interval"], 5000)
        self.assertNotIn("expected", step)
        for text in ("gc-self: started", "limit 10m", "gc-self: finished after", "gc statistics"):
            self.assertIn(text, logs["gc-self"])

    def test_each_suite_runs_its_shard_once_with_program_stress_and_its_sample_compiler_stressed_first(self):
        observed, samples, reports = {"jit": [], "aot": []}, {"jit": set(), "aot": set()}, {}
        for group, mode, steps in SUITES:
            with self.subTest(group=group):
                result, report, logs = self.run_group(group)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(report["result"], "pass")
                self.assertEqual([step["name"] for step in report["steps"]], ["bootstrap", *steps])
                step = report["steps"][-1]
                self.assertEqual(step["modes"], [mode])
                self.assertEqual((step["tests_compiler_interval"], step["tests_interval"]), (0, 1))
                count = 3 if mode == "aot" else 2
                self.assertEqual((step["shard_index"], step["shard_count"]), (int(group[-1]), count))
                self.assertEqual(report["sources"]["mode_checks"], sum(map(checks, CASES)))
                # the sample first, with the compiler stressed too, then the shard's other cases
                self.assertEqual([(m, kind) for m, kind, _ in self.runs()], [(mode, "sample"), (mode, "suite")])
                stressed, rest = self.runs()[0][2], self.runs()[1][2]
                _, shard, sample, others = split(group)
                self.assertEqual((stressed, rest), (sample, others))
                # (in the shard, each of its cases once: in the sample or in the rest)
                self.assertLessEqual(set(stressed), set(shard))
                self.assertEqual(Counter(stressed + rest), Counter(shard))
                sample_step = step["stressed_sample"]
                self.assertEqual((sample_step["every"], sample_step["offset"], sample_step["cases"]),
                                 (merge.GC_SAMPLE_EVERY, merge.GC_SAMPLE_OFFSETS[mode], len(stressed)))
                self.assertEqual((step["shard_cases"], step["cases"]), (len(shard), len(rest)))
                self.assertEqual((sample_step["tests_compiler_interval"], sample_step["tests_interval"]), (1000, 1))
                self.assertEqual((sample_step["passed"], sample_step["failed"], sample_step["expected"]),
                                 (sum(map(checks, stressed)), 0, sum(map(checks, stressed))))
                self.assertEqual((step["passed"], step["failed"], step["expected"]),
                                 (sum(map(checks, rest)), 0, sum(map(checks, rest))))
                self.assertLess(logs[group].index(f"suite: {mode} sample"), logs[group].index(f"suite: {mode} suite"))
                self.assertFalse((self.root / "gc-child.pid").exists())
                merge.validate_report({**report, "git": {"commit": "a" * 40}}, group, ["bootstrap", *steps])
                observed[mode] += stressed + rest
                samples[mode] |= set(stressed)
                reports[group] = report
        for mode, cases in observed.items():  # each case once in each mode
            self.assertEqual(Counter(cases), Counter(CASES), mode)
        self.assertFalse(samples["jit"] & samples["aot"])   # (the modes stress different cases here)
        self.gate(reports)   # the reports together pass the CI gate

    def test_negative_controls_a_sample_outside_its_shard_or_a_case_run_twice_or_never(self):
        # tests/verify.sh's selection broken three ways: the sample drawn from another shard (as the
        # positional sample of shard_cases would leave a balanced shard), the sample's cases run by the
        # program-stressed run too, or a case of the shard in neither run. Each AOT third's runs then
        # hold its cases other than once each, which the test above would see, and the gate rejects
        # its report, which the verification itself passes.
        select = ('''  awk -v every=$GC_SAMPLE_EVERY -v offset="$offset" -v sample="$V/$gc_group-sample-cases.log" \\\n'''
                  '''    '(NR - 1) % every == offset { print > sample; next } { print }' ''')
        mutations = {
            "outside": (select + '"$V/$gc_group-shard.log" > "$V/$gc_group-cases.log"\n',
                        '  shard_cases "$(((shard + 1) % gc_shards))" "$gc_shards" "$V/$gc_group-other.log"\n'
                        '''  awk -v every=$GC_SAMPLE_EVERY -v offset="$offset" '(NR - 1) % every == offset' '''
                        '"$V/$gc_group-other.log" > "$V/$gc_group-sample-cases.log"\n'
                        '  grep -vxF -f "$V/$gc_group-sample-cases.log" "$V/$gc_group-shard.log" > "$V/$gc_group-cases.log"\n'),
            "twice": ("{ print > sample; next } { print }'", "{ print > sample } { print }'"),
            "never": ("{ print > sample; next } { print }'", "{ print > sample; next } NR > 1 { print }'"),
        }
        for name, (old, new) in mutations.items():
            with self.subTest(mutation=name):
                shutil.copy(ROOT / "tests/verify.sh", self.root / "tests/verify.sh")
                self.mutate_verify(old, new)
                for group, _, _ in SUITES[2:]:   # (the AOT thirds: no gc-ir, so quicker)
                    result, report, _ = self.run_group(group)
                    self.assertEqual((result.returncode, report["result"]), (0, "pass"), result.stdout + result.stderr)
                    stressed, rest = (cases for _, _, cases in self.runs())
                    _, shard, _, _ = split(group)
                    self.assertFalse(set(stressed) <= set(shard) and Counter(stressed + rest) == Counter(shard), group)
                    with self.assertRaisesRegex(ValueError, "the sample must be the shard's cases"):
                        merge.validate_report({**report, "git": {"commit": "a" * 40}}, group, ["bootstrap", group])

    def test_gc_ir_halves_compile_every_case_once_stressed_as_stage2_does(self):
        compiled = []
        for group, index in (("gc-jit-0", 0), ("gc-jit-1", 1)):
            with self.subTest(group=group):
                result, report, logs = self.run_group(group)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                step = report["steps"][1]
                cases = shards(2)[index]
                syntax = [case for case in cases if "/syntax_" in case]
                self.assertEqual(step["name"], f"gc-ir-{index}")
                self.assertEqual((step["ir_cases"], step["ir_identical"], step["runtime_identical"]),
                                 (len(cases), True, True))
                self.assertEqual((step["check_cases"], step["check_identical"]), (len(syntax), True))
                self.assertEqual((step["compiler_interval"], step["reference"]), (1000, "stage2"))
                self.assertEqual((step["shard_index"], step["shard_count"]), (index, 2))
                self.assertEqual((report["sources"]["corpus_cases"], report["sources"]["syntax_cases"]), (len(CASES), 2))
                self.assertIn(f"{len(cases)} programs identical", logs[f"gc-ir-{index}"])
                self.assertIn("1 programs identical", logs[f"gc-ir-{index}"])   # (runtime.py)
                if syntax:
                    self.assertIn(f"== check of the {len(syntax)} syntax_*.py cases", logs[f"gc-ir-{index}"])
                # each case of the half by both compilers (rt for runtime.py), syntax cases checked by both
                calls = self.compiles()
                for case in cases:
                    for stress in ("-", "1000"):
                        self.assertEqual(calls.count(("ir", case, stress)), 1, (case, stress))
                        self.assertEqual(calls.count(("check", case, stress)), int(case in syntax), (case, stress))
                self.assertEqual(calls.count(("rt", "runtime.py", "1000")), 1)
                compiled += [case for command, case, stress in calls if command == "ir" and stress == "1000"]
        self.assertEqual(Counter(compiled), Counter(CASES))   # the halves: every case once, stressed

    def test_gc_ir_differences_and_missing_cases_cannot_pass(self):
        for mode, target, field, text in (
                ("gc-ir-differs", "tests/programs/x/example.py", "ir_identical", "DIFF tests/programs/x/example.py"),
                ("gc-msg-differs", "tests/errors/x/syntax_example.py", "ir_identical",
                 "DIFF tests/errors/x/syntax_example.py"),
                ("gc-status-differs", "tests/deviations/example.py", "ir_identical", "exit status 0 -> 3"),
                ("gc-check-differs", "tests/programs/x/syntax_example.py", "check_identical",
                 "DIFF tests/programs/x/syntax_example.py"),
                ("gc-rt-differs", None, "runtime_identical", "DIFF runtime.py"),
                ("gc-ir-missing", None, "ir_identical", "programs identical")):
            with self.subTest(mode=mode):
                index = half(target) if target else 1
                group, cases = f"gc-jit-{index}", shards(2)[index]
                irsame = self.root / "tools/irsame.sh"
                if mode == "gc-ir-missing":   # irsame drops the half's last case and finds the others identical
                    irsame.rename(self.root / "tools/irsame-real.sh")
                    irsame.write_text('#!/bin/sh\n[ "$1" = --check ] || [ $# -le 3 ] || { n=$#; i=0; for a; do '
                                      'i=$((i + 1)); [ $i = 1 ] && set --; [ $i = $n ] || set -- "$@" "$a"; done; }\n'
                                      'exec sh "$(dirname "$0")/irsame-real.sh" "$@"\n')
                    irsame.chmod(0o755)
                result, report, logs = self.run_group(group, mode)
                if mode == "gc-ir-missing":
                    (self.root / "tools/irsame-real.sh").replace(irsame)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(report["result"], "fail")
                step = report["steps"][1]
                self.assertEqual((step["name"], step["result"]), (f"gc-ir-{index}", "fail"))
                self.assertIs(step[field], False)
                self.assertIn(text, logs[step["name"]])
                if mode == "gc-ir-missing":   # (all but one of the half's cases compared, and runtime.py)
                    self.assertEqual((step["ir_cases"], step["runtime_identical"]), (len(cases) - 1, True))
                    self.assertIn(f"{len(cases) - 1} programs identical", logs[step["name"]])
                    self.assertEqual(sum(1 for command, _, stress in self.compiles()
                                         if command == "ir" and stress == "1000"), len(cases) - 1)
                self.assertEqual(report["steps"][-1]["result"], "pass")   # (the suite still runs)

    def test_local_aliases_run_all_selected_gc_checks(self):
        for group, expected in (("gc-stress", GC_STEPS), ("gc-ir", GC_STEPS[1:3]), ("gc-jit", GC_STEPS[1:5]),
                                ("gc-aot", GC_STEPS[5:])):
            with self.subTest(group=group):
                result, report, logs = self.run_group(group)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(report["result"], "pass")
                self.assertEqual([step["name"] for step in report["steps"]], ["bootstrap", *expected])
                if group == "gc-stress":
                    self.assertIn("gc statistics", logs["gc-self"])
                for suite, mode, _ in SUITES:
                    if suite not in expected:
                        continue
                    self.assertIn(f"suite: {mode} sample", logs[suite])
                    self.assertIn(f"suite: {mode} suite", logs[suite])
                if "gc-ir-0" in expected:
                    self.assertEqual(Counter(case for command, case, stress in self.compiles()
                                             if command == "ir" and stress == "1000"), Counter(CASES))

    def test_failure_timeout_and_mismatched_ir_cannot_pass(self):
        for mode, text in (("failure", "mock compiler failed"),
                           ("timeout", "sending signal TERM"),
                           ("timeout-kill", "sending signal KILL"),
                           ("mismatch", "differ")):
            with self.subTest(mode=mode):
                result, report, logs = self.run_group("gc-self", mode)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(report["result"], "fail")
                self.assertEqual(report["steps"][-1]["result"], "fail")
                self.assertIn(text, logs["gc-self"])

    def test_failed_and_incomplete_suites_and_samples_cannot_pass(self):
        for group, mode, _ in SUITES:
            _, _, sample, rest = split(group)
            for failure, run in (("run-failure", f"{mode} suite {rest[0]}"), ("run-failure", f"{mode} sample {sample[0]}"),
                                 ("short-suite", None), ("short-sample", None)):
                with self.subTest(group=group, failure=failure, run=run):
                    result, report, _ = self.run_group(group, failure, run)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(report["result"], "fail")
                    self.assertEqual(report["steps"][-1]["result"], "fail")

    def test_local_alias_reports_failure_and_still_runs_remaining_modes(self):
        for failure, group, kind in (("failure", None, None), ("gc-ir-differs", None, None),
                                     ("run-failure", "gc-jit-0", "suite"), ("run-failure", "gc-jit-1", "sample"),
                                     ("run-failure", "gc-aot-0", "suite"), ("run-failure", "gc-aot-2", "sample")):
            run = None
            if group is not None:
                mode, _, sample, rest = split(group)
                run = f"{mode} {kind} {(sample if kind == 'sample' else rest)[0]}"
            with self.subTest(failure=failure, run=run):
                result, report, logs = self.run_group("gc-stress", failure, run)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(report["result"], "fail")
                self.assertEqual([step["name"] for step in report["steps"]], ["bootstrap", *GC_STEPS])
                for suite, mode, _ in SUITES:
                    self.assertIn(f"suite: {mode} suite", logs[suite])
                    self.assertEqual(next(step for step in report["steps"] if step["name"] == suite)["result"],
                                     "fail" if suite == group else "pass")

    def test_cancellation_terminates_the_background_compiler(self):
        process = subprocess.Popen(["sh", "tests/verify.sh", "gc-self"], cwd=self.root,
                                   env={**self.env, "VERIFY_MOCK_MODE": "signal"},
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                   start_new_session=True)
        try:
            deadline = time.monotonic() + 5
            pidfile = self.root / "gc-child.pid"
            while not pidfile.exists() and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertTrue(pidfile.exists())
            child = int(pidfile.read_text())
            process.terminate()
            process.communicate(timeout=5)
            self.assertEqual(process.returncode, 130)
            with self.assertRaises(ProcessLookupError):
                os.kill(child, 0)
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
                process.communicate()


if __name__ == "__main__":
    unittest.main()
