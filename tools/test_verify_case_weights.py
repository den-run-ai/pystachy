"""The corpus's balanced shards (tests/corpus.sh's corpus_shard), the weights that balance them
(tools/case_weights.py) and the per-case times they come from (tests/run.sh's PYSTACHY_CASE_TIMES):
whatever the weights, every case runs in exactly one shard, and the same one on every runner."""
from pathlib import Path
import random
import statistics
import subprocess
import tempfile
import unittest

import case_weights

ROOT = Path(__file__).resolve().parent.parent


def reference_shards(cases, weights, defaults, shards):
    """corpus_shard's assignment, independently: greedy longest-processing-time, heaviest first."""
    def weight(case):
        if case in weights:
            return weights[case]
        return defaults["rejection" if case.startswith("tests/errors/") else "program"]
    order = sorted(cases, key=lambda case: (-weight(case), case.encode()))
    loads, parts = [0] * shards, [[] for _ in range(shards)]
    for case in order:
        least = min(range(shards), key=lambda index: (loads[index], index))
        loads[least] += weight(case)
        parts[least].append(case)
    return parts, loads


class CorpusShardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.write("tests/corpus.sh", (ROOT / "tests/corpus.sh").read_text())
        self.write("tools/shard_cases.sh", (ROOT / "tools/shard_cases.sh").read_text())
        generator = random.Random(970)
        self.cases = []
        for index in range(60):
            area = generator.choice(["a", "b", "c"])
            self.cases.append(f"tests/programs/{area}/p{index:02d}.py")
        self.cases += [f"tests/deviations/d{index}.py" for index in range(5)]
        self.cases += [f"tests/errors/{generator.choice(['x', 'y'])}/r{index:02d}.py" for index in range(40)]
        for case in self.cases:
            self.write(case, "# case\n")
        self.weights = {case: generator.randint(1, 30000) for case in self.cases[::2]}
        self.weights.update({self.cases[1]: 30000, self.cases[3]: 30000})   # (ties, broken by path)

    def write(self, relative, text):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def write_table(self, extra=""):
        lines = [f"{weight} {case}" for case, weight in self.weights.items()]
        self.write("tests/case_weights.txt", "# comment line\ndefault program 1500\ndefault rejection 20\n" +
                   "\n".join(lines) + "\n" + extra)

    def shard(self, index, count, table=None):
        command = f'. tests/corpus.sh; corpus_shard {index} {count}' + (f' "{table}"' if table else "")
        # (the caller's locale must not change the shards: corpus_shard sets C itself)
        result = subprocess.run(["sh", "-c", command], cwd=self.root, text=True, capture_output=True,
                                env={"PATH": "/usr/bin:/bin", "LC_ALL": "en_US.UTF-8"}, check=True, timeout=30)
        return result.stdout.splitlines()

    def test_shards_are_the_reference_assignment_disjoint_and_complete(self):
        self.write_table()
        defaults = {"program": 1500, "rejection": 20}
        for count in (1, 2, 3, 4, 5):
            with self.subTest(count=count):
                parts = [self.shard(index, count) for index in range(count)]
                expected, loads = reference_shards(self.cases, self.weights, defaults, count)
                self.assertEqual(parts, expected)
                every = [case for part in parts for case in part]
                self.assertEqual(len(every), len(set(every)))   # disjoint
                self.assertCountEqual(every, self.cases)        # complete
                # balanced: no shard exceeds another by more than its heaviest case
                heaviest = max(self.weights.values())
                self.assertLessEqual(max(loads) - min(loads), heaviest)
                for part in parts:   # heaviest first, for tests/run.sh's workers
                    weights = [self.weights.get(case, 20 if "/errors/" in case else 1500) for case in part]
                    self.assertEqual(weights, sorted(weights, reverse=True))

    def test_stale_malformed_or_missing_weights_cost_balance_never_coverage(self):
        stale = ("123 tests/programs/gone/old.py\n7 not a weight line\nxyz tests/programs/a/p00.py\n"
                 "1234567890 tests/programs/a/p02.py\n-5 tests/errors/x/r00.py\ndefault program x\n"
                 "default other 5\n\n   \n")
        for table in ("absent", "empty", "stale"):
            with self.subTest(table=table):
                if table == "empty":
                    self.write("tests/case_weights.txt", "")
                elif table == "stale":
                    self.write_table(stale)
                for count in (2, 3):
                    parts = [self.shard(index, count) for index in range(count)]
                    every = [case for part in parts for case in part]
                    self.assertEqual(len(every), len(set(every)))
                    self.assertCountEqual(every, self.cases)
                    self.assertNotIn("tests/programs/gone/old.py", every)
        # each malformed line counts for nothing: the table reads as if it were absent from it
        self.write_table()
        clean = [self.shard(index, 3) for index in range(3)]
        self.write_table(stale)
        self.assertEqual([self.shard(index, 3) for index in range(3)], clean)

    def test_an_explicit_table_and_tools_shard_cases_agree(self):
        self.write_table()
        moved = self.root / "elsewhere.txt"
        moved.write_text((self.root / "tests/case_weights.txt").read_text())
        (self.root / "tests/case_weights.txt").unlink()
        explicit = [self.shard(index, 3, moved) for index in range(3)]
        self.write_table()
        for index in range(3):
            result = subprocess.run(["sh", "tools/shard_cases.sh", f"{index}/3"], cwd=self.root, text=True,
                                    capture_output=True, env={"PATH": "/usr/bin:/bin"}, check=True, timeout=30)
            self.assertEqual(result.stdout.splitlines(), explicit[index])
        for argument in ("3/3", "x/2", "1", "0/0"):
            result = subprocess.run(["sh", "tools/shard_cases.sh", argument], cwd=self.root, text=True,
                                    capture_output=True, env={"PATH": "/usr/bin:/bin"}, timeout=30)
            self.assertEqual(result.returncode, 2, argument)

    def test_the_repository_table_shards_the_whole_corpus(self):
        # (an entry of a case since removed only costs balance, until tools/case_weights.py refreshes it)
        cases = case_weights.corpus()
        weights, defaults = case_weights.read_table(ROOT / case_weights.TABLE)
        self.assertEqual(set(defaults), {"program", "rejection"})
        self.assertGreater(len(set(weights) & set(cases)), len(cases) // 2)
        result = subprocess.run(["sh", "-c", ". tests/corpus.sh; corpus_shard 0 2; corpus_shard 1 2"], cwd=ROOT,
                                text=True, capture_output=True, check=True, timeout=60)
        self.assertCountEqual(result.stdout.splitlines(), cases)


class CaseWeightsToolTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.dir = Path(self.temp.name)
        self.programs = [f"tests/programs/a/p{index:02d}.py" for index in range(case_weights.MIN_PROGRAMS + 1)]
        self.cases = self.programs + ["tests/deviations/d.py", "tests/errors/x/r.py", "tests/errors/x/s.py"]

    def times(self, name, pairs):
        path = self.dir / name
        path.write_text("".join(f"{ms} {case}\n" for case, ms in pairs))
        return path

    def test_each_file_is_scaled_by_its_median_program_and_cases_take_the_median(self):
        # the same costs timed on a runner twice as slow, and by another file; one program timed twice
        fast = [(case, 100 * (index + 1)) for index, case in enumerate(self.programs)]
        median = 100 * (len(self.programs) // 2 + 1)
        fast += [("tests/deviations/d.py", 3 * median), ("tests/errors/x/r.py", median // 50),
                 ("tests/programs/gone/old.py", 99)]
        slow = [(case, 2 * ms) for case, ms in fast[:len(self.programs)]] + [("tests/errors/x/r.py", 0)]
        weights = case_weights.weigh([self.times("fast", fast), self.times("slow", slow)], self.cases)
        self.assertEqual(weights[self.programs[len(self.programs) // 2]], 1000)
        self.assertEqual(weights[self.programs[0]], round(100_000 / median))
        self.assertEqual(weights["tests/deviations/d.py"], 3000)
        self.assertEqual(weights["tests/errors/x/r.py"], 10)   # (the median of 20 and 0)
        self.assertNotIn("tests/programs/gone/old.py", weights)   # outside the corpus
        self.assertNotIn("tests/errors/x/s.py", weights)          # never timed: its kind's default
        text = case_weights.table(weights)
        default = round(statistics.median(w for case, w in weights.items() if "/errors/" not in case))
        self.assertIn(f"default program {default}\ndefault rejection 10\n", text)
        table = self.dir / "table.txt"
        table.write_text(text)
        self.assertEqual(case_weights.read_table(table), (weights, {"program": default, "rejection": 10}))
        listed = [line.split()[1] for line in text.splitlines() if line[:1].isdigit()]
        self.assertEqual(listed, sorted(listed, key=str.encode))
        # --keep: a case no file timed keeps its weight; a timed one takes its new weight
        kept = case_weights.weigh([self.times("fast", fast)], self.cases,
                                  {"tests/errors/x/s.py": 77, self.programs[0]: 5, "tests/programs/gone/old.py": 1})
        self.assertEqual(kept["tests/errors/x/s.py"], 77)
        self.assertEqual(kept[self.programs[0]], round(100_000 / median))
        self.assertNotIn("tests/programs/gone/old.py", kept)

    def test_malformed_or_unscalable_times_fail(self):
        good = [(case, 1000) for case in self.programs]
        for name, text in (("malformed", "12 tests/programs/a/p00.py\n12\n"), ("negative", "-3 tests/errors/x/r.py\n"),
                           ("float", "1.5 tests/programs/a/p00.py\n")):
            with self.subTest(name=name):
                path = self.dir / name
                path.write_text("".join(f"{ms} {case}\n" for case, ms in good) + text)
                with self.assertRaises(ValueError):
                    case_weights.weigh([path], self.cases)
        few = self.times("few", good[:case_weights.MIN_PROGRAMS - 1])
        with self.assertRaisesRegex(ValueError, "too few"):
            case_weights.weigh([few], self.cases)
        zero = self.times("zero", [(case, 0) for case in self.programs])
        with self.assertRaisesRegex(ValueError, "median time is 0"):
            case_weights.weigh([zero], self.cases)

    def test_the_tool_writes_the_table_from_files(self):
        programs = [case for case in case_weights.corpus() if case.startswith("tests/programs/")]
        times = self.times("times", [(case, 1000) for case in programs[:case_weights.MIN_PROGRAMS]])
        output = self.dir / "weights.txt"
        self.assertEqual(case_weights.main([str(times), "-o", str(output)]), 0)
        weights, defaults = case_weights.read_table(output)
        self.assertEqual(len(weights), case_weights.MIN_PROGRAMS)
        self.assertEqual(set(weights.values()), {1000})
        self.assertEqual(defaults, {"program": 1000, "rejection": 1000})
        self.assertEqual(case_weights.main([str(self.dir / "missing"), "-o", str(output)]), 1)


class CaseTimesTests(unittest.TestCase):
    """tests/run.sh's PYSTACHY_CASE_TIMES, with `true` for a compiler (only the times matter)."""
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in ("tests/corpus.sh", "tests/run.sh", "tests/prepare_path.sh"):
            self.write(name, (ROOT / name).read_text())
        self.cases = ["tests/programs/b/two.py", "tests/errors/a/rej.py", "tests/programs/a/one.py",
                      "tests/deviations/dev.py"]
        for case in self.cases:
            self.write(case, "# error: no\n" if "/errors/" in case else "pass\n")
            if "/programs/" in case:
                self.write(case[:-3] + ".out", "[exit 0]\n")

    def write(self, relative, text):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def run_suite(self, path=None, **env):
        return subprocess.run(["sh", "tests/run.sh", "true", "jit", *self.cases], cwd=self.root, text=True,
                              capture_output=True, timeout=60,
                              env={"PATH": path or "/usr/bin:/bin", "LC_ALL": "C", "PYSTACHY_JOBS": "2", **env})

    def test_each_case_has_its_time_in_the_reports_order(self):
        times = self.root / "times.log"
        times.write_text("5 tests/programs/a/one.py\n")   # (appended to, as by opt-off's settings)
        result = self.run_suite(PYSTACHY_CASE_TIMES=str(times))
        self.assertIn("selected 4 cases", result.stdout)
        lines = times.read_text().splitlines()
        self.assertEqual(lines[0], "5 tests/programs/a/one.py")
        self.assertEqual([line.split(" ", 1)[1] for line in lines[1:]], self.cases)
        for line in lines[1:]:
            self.assertRegex(line, r"^[0-9]+ ")
        self.assertEqual(len(case_weights.read_times(times)), 5)

    def test_no_times_without_the_setting_or_gnu_date(self):
        result = self.run_suite()
        self.assertIn("selected 4 cases", result.stdout)
        self.assertEqual(list(self.root.glob("*.log")), [])
        # a date without %N: the suite runs as before, without times, and says why
        self.write("bin/date", "#!/bin/sh\necho 1700000000N\n")
        (self.root / "bin/date").chmod(0o755)
        times = self.root / "times.log"
        plain = self.run_suite()
        result = self.run_suite(path=f"{self.root / 'bin'}:/usr/bin:/bin", PYSTACHY_CASE_TIMES=str(times))
        self.assertIn("PYSTACHY_CASE_TIMES needs date +%s%N", result.stderr)
        self.assertEqual((result.returncode, result.stdout.splitlines()[-2:]),
                         (plain.returncode, plain.stdout.splitlines()[-2:]))
        self.assertFalse(times.exists())


if __name__ == "__main__":
    unittest.main()
