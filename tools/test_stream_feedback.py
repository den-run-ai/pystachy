"""Reference unions and native offline feedback preserve observable semantics.

Run with PYSTACHY_LLVM set. PYSTACHY_STREAM_TEST_COMPILER can select the native
compiler after bootstrapping; by default these checks use the hosted compiler.
"""
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[1]

CLASSES = """
class Hot:
    def __init__(self) -> None:
        self.calls = 0
    def read(self, amount: int = 1) -> str:
        self.calls += 1
        return "h" * amount

class Cold:
    def __init__(self) -> None:
        self.calls = 0
    def read(self, amount: int = 1) -> str:
        self.calls += 1
        return "c" * amount
"""

CALLS = """
def consume(stream, amount: int = 1) -> str:
    return stream.read(amount)

def dispatch(stream: Hot | Cold, amount: int = 1) -> str:
    return consume(stream, amount)
"""


class StreamFeedbackTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="pystachy-stream-test-")
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.program = self.directory / "case.py"
        self.profile = self.directory / "case.profile"
        self.counters = self.directory / "counters.profile"
        self.compiler = shlex.split(os.environ["PYSTACHY_STREAM_TEST_COMPILER"]) if os.environ.get(
            "PYSTACHY_STREAM_TEST_COMPILER") else [sys.executable, "-m", "pystachy"]
        self.env = dict(os.environ, PYSTACHY_HOME=str(ROOT), PYSTACHY_CLOSED_UNIONS="1",
                        PYSTACHY_REFERENCE_UNIONS="1", PYSTACHY_FEEDBACK_FUNCTION="consume")
        for name in ["PYSTACHY_FEEDBACK_PROFILE", "PYSTACHY_FEEDBACK_RECORD",
                     "PYSTACHY_FEEDBACK_COUNTERS", "PYSTACHY_FEEDBACK_OUT",
                     "PYSTACHY_SKEW_PROFILE", "PYSTACHY_IRFX"]:
            self.env.pop(name, None)

    def write(self, source):
        self.program.write_text(textwrap.dedent(source), encoding="utf-8")

    def invoke(self, *arguments, mode="baseline", successful=True):
        env = dict(self.env)
        if mode == "record":
            env["PYSTACHY_FEEDBACK_RECORD"] = "1"
        elif mode == "optimized":
            env["PYSTACHY_FEEDBACK_PROFILE"] = str(self.profile)
            env["PYSTACHY_FEEDBACK_COUNTERS"] = "1"
        result = subprocess.run([*self.compiler, *map(str, arguments)], cwd=ROOT, env=env,
                                capture_output=True, text=True, timeout=120)
        if successful:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def execute(self, executable, *arguments, output=None, stress=False):
        env = dict(self.env)
        if output is not None:
            env["PYSTACHY_FEEDBACK_OUT"] = str(output)
        if stress:
            env["PYSTACHY_GC_STRESS"] = "1"
        result = subprocess.run([str(executable), *map(str, arguments)], cwd=self.directory,
                                env=env, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result.stdout

    def expected(self, *arguments):
        return subprocess.run([sys.executable, str(self.program), *map(str, arguments)],
                              cwd=self.directory, capture_output=True, text=True,
                              check=True, timeout=30).stdout

    @staticmethod
    def rows(path):
        lines = path.read_text(encoding="utf-8").splitlines()
        if not lines or lines[0] != "pystachy-feedback-v1":
            raise AssertionError("invalid native feedback header")
        return [(site, member, int(count)) for site, member, count in
                (line.split("\t") for line in lines[1:])]

    def variants(self, *, stress=False):
        expected = self.expected("check")
        for mode in ["baseline", "record", "optimized"]:
            executable = self.directory / mode
            self.invoke("build", self.program, "-o", executable, mode=mode)
            if mode == "record":
                self.assertEqual(self.execute(executable, "train", output=self.profile),
                                 self.expected("train"))
                self.assertGreaterEqual(sum(row[2] for row in self.rows(self.profile)), 100)
            self.assertEqual(self.execute(executable, "check", output=(
                self.counters if mode == "optimized" else None), stress=stress), expected)
        return expected

    def test_native_recording_and_shifted_distribution_take_hot_and_fallback(self):
        self.write("import sys\n" + CLASSES + CALLS + """
hot = Hot()
cold = Cold()
items: list[Hot | Cold] = [hot, cold]
train = sys.argv[1] == "train"
total = 0
for i in range(200 if train else 12):
    index = (1 if i == 199 else 0) if train else (0 if i == 11 else 1)
    total += len(dispatch(items[index], 2))
print(total, hot.calls, cold.calls)
""")
        self.assertEqual(self.variants(stress=True), "24 1 11\n")
        observed = {member: count for _, member, count in self.rows(self.profile)}
        self.assertEqual(observed, {"Hot": 199, "Cold": 1})
        counts = {member: count for _, member, count in self.rows(self.counters)}
        self.assertEqual(counts, {"<hot>": 1, "<miss>": 11})
        # JIT and AOT consume the same observed profile and preserve output.
        self.assertEqual(self.invoke("run", self.program, "check", mode="optimized").stdout,
                         self.expected("check"))

    def test_defaults_and_explicit_arguments_are_evaluated_once(self):
        self.write("import sys\n" + CLASSES + """
evaluations = 0
def default() -> int:
    print("default")
    return 2
def argument() -> int:
    global evaluations
    evaluations += 1
    return 3
def consume(stream, amount: int = default()) -> str:
    return stream.read(amount)
def dispatch(stream: Hot | Cold, explicit: bool) -> str:
    if explicit:
        return consume(amount=argument(), stream=stream)
    return consume(stream)
hot = Hot()
cold = Cold()
items: list[Hot | Cold] = [hot, cold]
train = sys.argv[1] == "train"
total = 0
for i in range(200 if train else 4):
    index = 0 if train else i % 2
    total += len(dispatch(items[index], i % 2 == 0))
print(total, evaluations, hot.calls, cold.calls)
""")
        self.assertEqual(self.variants(), "default\n10 2 2 2\n")
        self.assertEqual(sum(n for _, member, n in self.rows(self.counters) if member == "<hot>"), 2)
        self.assertEqual(sum(n for _, member, n in self.rows(self.counters) if member == "<miss>"), 2)

    def test_imported_classes_with_the_same_name_have_distinct_profile_identities(self):
        for module, marker in [("alpha", "a"), ("beta", "b")]:
            (self.directory / (module + ".py")).write_text(
                "class Stream:\n    def read(self, amount: int = 1) -> str:\n"
                f'        return "{marker}" * amount\n', encoding="utf-8")
        self.write("""
import sys
from alpha import Stream as Hot
from beta import Stream as Cold
""" + CALLS + """
items: list[Hot | Cold] = [Hot(), Cold()]
train = sys.argv[1] == "train"
result = ""
for i in range(200 if train else 2):
    index = (1 if i == 199 else 0) if train else i
    result += dispatch(items[index])
print(result)
""")
        self.assertEqual(self.variants(), "ab\n")
        self.assertEqual({member: count for _, member, count in self.rows(self.profile)},
                         {"alpha$Stream": 199, "beta$Stream": 1})
        self.assertEqual({member: count for _, member, count in self.rows(self.counters)},
                         {"<hot>": 1, "<miss>": 1})

    def test_exceptions_do_not_replay_side_effects(self):
        source = CLASSES.replace('return "h" * amount',
                                 'if amount < 0:\n            raise ValueError("hot")\n        return "h" * amount')
        source = source.replace('return "c" * amount',
                                'if amount < 0:\n            raise ValueError("cold")\n        return "c" * amount')
        self.write("import sys\n" + source + CALLS + """
hot = Hot()
cold = Cold()
items: list[Hot | Cold] = [hot, cold]
train = sys.argv[1] == "train"
for i in range(100 if train else 2):
    try:
        print(dispatch(items[0 if train else i], 1 if train else -1))
    except ValueError as error:
        print("caught", error)
    finally:
        if not train:
            print("finally")
print("calls", hot.calls, cold.calls)
""")
        self.assertEqual(self.variants(), "caught hot\nfinally\ncaught cold\nfinally\ncalls 1 1\n")
        self.assertEqual({member: count for _, member, count in self.rows(self.counters)},
                         {"<hot>": 1, "<miss>": 1})

    def test_optional_none_records_a_miss_without_dereferencing_null(self):
        self.write("import sys\n" + CLASSES + CALLS.replace(
            "stream: Hot | Cold", "stream: Hot | Cold | None") + """
hot = Hot()
items: list[Hot | Cold | None] = [hot, Cold(), None]
train = sys.argv[1] == "train"
for i in range(100 if train else 3):
    try:
        result = dispatch(items[0 if train else i])
        if not train:
            print(result)
    except AttributeError:
        print("none")
print(hot.calls)
""")
        self.assertEqual(self.variants(), "h\nc\nnone\n1\n")
        self.assertEqual({member: count for _, member, count in self.rows(self.counters)},
                         {"<hot>": 1, "<miss>": 2})

    def test_reference_storage_narrowing_identity_and_mutation(self):
        self.write(CLASSES + CALLS + """
class Holder:
    def __init__(self, stream: Hot | Cold) -> None:
        self.stream = stream
def check() -> None:
    hot = Hot()
    cold = Cold()
    items: list[Hot | Cold] = [hot, cold, hot]
    for item in items:
        holder = Holder(item)
        alias = holder.stream
        print(dispatch(alias, 2))
        if isinstance(alias, Hot):
            print(alias is hot, alias.calls)
        else:
            print(alias is cold, alias.calls)
    print(hot.calls, cold.calls)
check()
""")
        executable = self.directory / "storage"
        self.invoke("build", self.program, "-o", executable)
        self.assertEqual(self.execute(executable, stress=True), self.expected())

    def test_native_file_and_stringio_keep_shared_cursor_through_storage(self):
        self.write("""
from io import StringIO
from typing import TextIO
class Holder:
    def __init__(self, stream: TextIO | StringIO) -> None:
        self.stream = stream
def consume(stream) -> str:
    return stream.read(1)
def dispatch(stream: TextIO | StringIO) -> str:
    return consume(stream)
with open("input.txt", "w") as output:
    output.write("disk")
memory = StringIO("memory")
disk = open("input.txt")
items: list[TextIO | StringIO] = [memory, disk, memory, disk]
for item in items:
    holder = Holder(item)
    print(dispatch(holder.stream))
print(memory.read(2), disk.read(2))
disk.close()
memory.close()
""")
        executable = self.directory / "streams"
        self.invoke("build", self.program, "-o", executable)
        self.assertEqual(self.execute(executable, stress=True), "m\nd\ne\ni\nmo sk\n")
        self.assertEqual(self.execute(executable), self.expected())

    def test_constructor_local_alias_is_separate_from_parameter_reassignment(self):
        self.write(CLASSES + """
class Holder:
    def __init__(self, stream) -> None:
        original = stream
        stream = Cold()
        self.stream: Hot | Cold = original
def consume(stream) -> str:
    return Holder(stream).stream.read(1)
def dispatch(stream: Hot | Cold) -> str:
    return consume(stream)
hot = Hot()
items: list[Hot | Cold] = [hot, Cold()]
print(dispatch(items[0]), hot.calls)
""")
        executable = self.directory / "alias"
        self.invoke("build", self.program, "-o", executable)
        self.assertEqual(self.execute(executable), self.expected())

    def test_incompatible_method_results_are_rejected_before_feedback(self):
        self.write(CLASSES.replace('return "c" * amount', "return amount").replace(
            'def read(self, amount: int = 1) -> str:\n        self.calls += 1\n        return amount',
            'def read(self, amount: int = 1) -> int:\n        self.calls += 1\n        return amount') + CALLS + """
items: list[Hot | Cold] = [Hot(), Cold()]
print(dispatch(items[0]))
""")
        baseline = self.invoke("ir", self.program, successful=False)
        self.assertNotEqual(baseline.returncode, 0)
        self.assertIn("identical return types", baseline.stderr)
        self.profile.write_text("pystachy-feedback-v1\nignored\tHot\t100\n", encoding="utf-8")
        optimized = self.invoke("ir", self.program, mode="optimized", successful=False)
        self.assertEqual(optimized.returncode, baseline.returncode)
        self.assertEqual(optimized.stderr, baseline.stderr)

    def test_profile_cannot_make_alias_reassignment_reject_a_valid_baseline(self):
        bodies = [
            "    alias = stream\n    alias = Cold()\n    return alias.read(1)\n",
            "    first = stream\n    alias = first\n    alias = Cold()\n    return alias.read(1)\n",
            "    alias = stream\n    alias: Hot | Cold = Cold()\n    return alias.read(1)\n",
        ]
        for body in bodies:
            with self.subTest(body=body):
                self.profile.unlink(missing_ok=True)
                self.write("import sys\n" + CLASSES + "def consume(stream) -> str:\n" + body + """
def dispatch(stream: Hot | Cold) -> str:
    return consume(stream)
items: list[Hot | Cold] = [Hot(), Cold()]
train = sys.argv[1] == "train"
total = 0
for i in range(100 if train else 2):
    total += len(dispatch(items[0 if train else i]))
print(total)
""")
                # A profile must never turn a valid generic program into a type error.
                # It is acceptable to retain only the baseline for this unsafe clone.
                expected = self.expected("check")
                recording = self.directory / "recording"
                self.invoke("build", self.program, "-o", recording, mode="record")
                self.assertEqual(self.execute(recording, "train", output=self.profile), self.expected("train"))
                optimized = self.directory / "optimized"
                self.invoke("build", self.program, "-o", optimized, mode="optimized")
                self.assertEqual(self.execute(optimized, "check"), expected)

    def test_malformed_or_ineligible_profiles_leave_ir_unchanged(self):
        self.write(CLASSES + CALLS + """
items: list[Hot | Cold] = [Hot(), Cold()]
for item in items:
    print(dispatch(item))
""")
        baseline = self.invoke("ir", self.program).stdout
        recorded = self.invoke("ir", self.program, mode="record").stdout
        # Obtain the actual call-site identity without duplicating its encoding.
        site_strings = re.findall(r'c"([^"\n]*:consume:stream)\\00"', recorded)
        self.assertEqual(len(site_strings), 1)
        site = site_strings[0]
        rows = [
            "bad-header\n" + site + "\tHot\t100\n",
            "pystachy-feedback-v1\nmalformed\n",
            "pystachy-feedback-v1\n" + site + "\tHot\t-1\n",
            "pystachy-feedback-v1\n" + site + "\tHot\t99\n",
            "pystachy-feedback-v1\n" + site + "\tHot\t89\n" + site + "\tCold\t11\n",
            "pystachy-feedback-v1\n" + site + "\tHot\t100\n" + site + "\tHot\t100\n",
            "pystachy-feedback-v1\n" + site + "\tMissing\t100\n",
            "pystachy-feedback-v1\n" + "x" * 65537,
        ]
        for contents in rows:
            with self.subTest(profile=contents[:180]):
                self.profile.write_text(contents, encoding="utf-8")
                self.assertEqual(self.invoke("ir", self.program, mode="optimized").stdout, baseline)
        self.profile.unlink()
        self.assertEqual(self.invoke("ir", self.program, mode="optimized").stdout, baseline)


if __name__ == "__main__":
    unittest.main()
