"""Online native specialization must keep one live program and its state.

The first tier is Linux AOT with one reference-union argument and an int result.
Set PYSTACHY_ONLINE_TEST_COMPILER to a host compiler command (hosted by default),
and PYSTACHY_ONLINE_COMPILER to the absolute native compiler used at runtime.
"""
import ast
import csv
import json
import os
from pathlib import Path
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
        self.fail = False
    def read(self) -> str:
        self.calls += 1
        if self.fail:
            raise ValueError("hot")
        return "h"

class Cold:
    def __init__(self) -> None:
        self.calls = 0
        self.fail = False
    def read(self) -> str:
        self.calls += 1
        if self.fail:
            raise ValueError("cold")
        return "c"
"""
CALLS = """
def consume(stream) -> int:
    return len(stream.read())
def dispatch(stream: Hot | Cold) -> int:
    return consume(stream)
"""
MONOMORPHIC = "import sys\n" + CLASSES + CALLS + """
hot = Hot()
items: list[Hot | Cold] = [hot, Cold()]
total = 0
for i in range(int(sys.argv[1])):
    total += dispatch(items[0])
print(total, hot.calls)
"""


@unittest.skipUnless(sys.platform.startswith("linux"), "online tier currently supports Linux AOT")
class StreamOnlineTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="pystachy-online-test-")
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.program = self.directory / "case.py"
        self.executable = self.directory / "program"
        self.stats = self.directory / "online.tsv"
        self.log = self.directory / "compiler.jsonl"
        self.compiler = shlex.split(os.environ["PYSTACHY_ONLINE_TEST_COMPILER"]) if os.environ.get(
            "PYSTACHY_ONLINE_TEST_COMPILER") else [sys.executable, "-m", "pystachy"]
        self.child_compiler = str(Path(os.environ.get("PYSTACHY_ONLINE_COMPILER", ROOT / "pystachy")).resolve())
        self.env = dict(os.environ, PYSTACHY_HOME=str(ROOT), PYSTACHY_CLOSED_UNIONS="1",
                        PYSTACHY_REFERENCE_UNIONS="1", PYSTACHY_FEEDBACK_FUNCTION="consume")
        for name in list(self.env):
            if name.startswith("PYSTACHY_ONLINE_") or name in [
                "PYSTACHY_ONLINE", "PYSTACHY_FEEDBACK_PROFILE", "PYSTACHY_FEEDBACK_RECORD",
                "PYSTACHY_FEEDBACK_COUNTERS", "PYSTACHY_FEEDBACK_OUT", "PYSTACHY_SKEW_PROFILE",
                "PYSTACHY_IRFX", "PYSTACHY_GC_STRESS", "PYSTACHY_GC_STRESS_PROGRAM",
            ]:
                self.env.pop(name, None)

    def write(self, source):
        self.program.write_text(textwrap.dedent(source), encoding="utf-8")

    def build(self, *, online=True, compiler=None):
        env = dict(self.env, PYSTACHY_ONLINE="1" if online else "0",
                   PYSTACHY_ONLINE_COMPILER=compiler or self.child_compiler)
        result = subprocess.run([*self.compiler, "build", str(self.program), "-o", str(self.executable)],
                                cwd=ROOT, env=env, capture_output=True, text=True, timeout=180)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def expected(self, *arguments, shlex_oracle=False):
        command = [sys.executable, str(self.program), *map(str, arguments)]
        if shlex_oracle:
            code = ("from pathlib import Path; import sys; p=Path(sys.argv[1]); "
                    "sys.argv=sys.argv[1:]; "
                    "exec(compile(p.read_text().replace('_stream=stream', 'instream=stream'), str(p), 'exec'))")
            command = [sys.executable, "-c", code, str(self.program), *map(str, arguments)]
        return subprocess.run(command, cwd=self.directory, capture_output=True, text=True,
                              check=True, timeout=30).stdout

    def run_program(self, *arguments, compiler=None, stress=False):
        self.stats.unlink(missing_ok=True)
        self.log.unlink(missing_ok=True)
        env = dict(self.env, PYSTACHY_ONLINE_COMPILER=compiler or self.child_compiler,
                   PYSTACHY_ONLINE_STATS=str(self.stats))
        if stress:
            env["PYSTACHY_GC_STRESS"] = "1"
        result = subprocess.run([str(self.executable), *map(str, arguments)], cwd=self.directory,
                                env=env, capture_output=True, text=True, timeout=180)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result.stdout

    def row(self):
        lines = self.stats.read_text(encoding="utf-8").splitlines()
        self.assertEqual(lines[0], "pystachy-online-v1")
        rows = list(csv.DictReader(lines[1:], delimiter="\t"))
        self.assertEqual(len(rows), 1, rows)
        row = rows[0]
        for name in ["calls", "attempts", "installs", "hits", "misses", "trigger_call", "compiler_pid"]:
            row[name] = int(row[name])
        for name in ["compile_wall_s", "compile_cpu_s", "load_wall_s"]:
            row[name] = float(row[name])
            self.assertGreaterEqual(row[name], 0.0)
        self.assertEqual(row["calls"], row["hits"] + row["misses"])
        return row

    def installed(self, calls, hits):
        row = self.row()
        self.assertEqual((row["calls"], row["attempts"], row["installs"], row["hits"], row["trigger_call"]),
                         (calls, 1, 1, hits, 100), row)
        self.assertGreater(row["compiler_pid"], 0)
        self.assertGreater(row["compile_wall_s"], 0.0)
        self.assertIn(row["failure"], ["", "0", "none", "ok", "-"])
        return row

    def wrapper(self, action="exec"):
        # This is an executable path, deliberately containing spaces. Runtime
        # launch must pass argv directly and retain the child PID through exec.
        path = self.directory / "compiler wrapper.py"
        body = f"""#!{sys.executable}
import json
import os
from pathlib import Path
import sys
directory = Path({str(self.directory)!r})
marker = directory / "completed.txt"
entry = {{"pid": os.getpid(), "parent_pid": os.getppid(), "argv": sys.argv[1:],
         "completed": marker.read_text() if marker.exists() else None}}
with open({str(self.log)!r}, "a", encoding="utf-8") as output:
    output.write(json.dumps(entry) + "\\n")
"""
        if action == "exec":
            body += f"os.execv({self.child_compiler!r}, [{self.child_compiler!r}, *sys.argv[1:]])\n"
        elif action == "fail":
            body += "sys.exit(37)\n"
        elif action == "invalid_library":
            body += "Path(sys.argv[sys.argv.index('-o') + 1]).write_text('not a shared library')\n"
        else:
            raise AssertionError(action)
        path.write_text(body, encoding="utf-8")
        path.chmod(0o755)
        return str(path)

    def test_threshold_compiles_and_installs_in_the_same_live_process(self):
        self.write("import os\nimport sys\n" + CLASSES + CALLS + """
pid = os.getpid()
with open("host-pid.txt", "w") as output:
    output.write(str(pid))
hot = Hot()
items: list[Hot | Cold] = [hot, Cold()]
total = 0
for i in range(int(sys.argv[1])):
    with open("completed.txt", "w") as output:
        output.write(str(hot.calls))
    total += dispatch(items[0])
print(total, hot.calls, os.getpid() == pid)
""")
        wrapper = self.wrapper()
        self.build(compiler=wrapper)
        self.assertEqual(self.run_program(99, compiler=wrapper), "99 99 True\n")
        before = self.row()
        self.assertEqual((before["attempts"], before["installs"], before["hits"]), (0, 0, 0))
        self.assertFalse(self.log.exists(), "compiler ran below the threshold")
        self.assertEqual(self.run_program(105, compiler=wrapper), "105 105 True\n")
        row = self.installed(105, 6)
        entries = [json.loads(line) for line in self.log.read_text().splitlines()]
        self.assertEqual(len(entries), 1)
        entry = entries[0]
        self.assertEqual(entry["completed"], "99", "threshold call must execute its body once, after compilation")
        self.assertEqual(entry["pid"], row["compiler_pid"])
        self.assertEqual(entry["parent_pid"], int((self.directory / "host-pid.txt").read_text()))
        self.assertEqual(entry["argv"][0], "trace")
        self.assertIn("-o", entry["argv"])

    def test_balanced_types_do_not_trigger_a_speculative_compile(self):
        self.write(MONOMORPHIC.replace("dispatch(items[0])", "dispatch(items[i % 2])"))
        self.build()
        self.assertEqual(self.run_program(120), self.expected(120))
        row = self.row()
        self.assertEqual((row["calls"], row["attempts"], row["installs"], row["hits"]), (120, 0, 0, 0))

    def test_loaded_code_shares_globals_defaults_identity_and_gc_heap(self):
        self.write("from typing import Callable\n" + CLASSES.replace('return "h"', 'return ("h" + str(self.calls)) * 64').replace(
            'return "c"', 'return ("c" + str(self.calls)) * 64') + """
seen: list[str] = []
audit: list[int] = []
literals: list[str] = []
callbacks: list[Callable[[str], int]] = []
def callback(value: str) -> int:
    return len(value)
def default_storage() -> list[str]:
    print("default")
    return ["seed"]
def remember(value: str, storage: list[str] = default_storage()) -> int:
    storage.append(value)
    seen.append(value)
    audit.append(len(storage))
    literals.append("literal shared across the online boundary")
    callbacks.append(callback)
    return len(value)
def consume(stream) -> int:
    return remember(stream.read())
def dispatch(stream: Hot | Cold) -> int:
    return consume(stream)
hot = Hot()
cold = Cold()
items: list[Hot | Cold] = [hot, cold]
total = 0
for i in range(112):
    total += dispatch(items[0 if i < 110 else 1])
print(total, hot.calls, cold.calls, len(seen), audit[-1])
print(seen[0] == "h1" * 64, seen[99] == "h100" * 64, seen[-1] == "c2" * 64)
print(literals[0] is literals[99], literals[99] is literals[-1], callbacks[0] is callbacks[99])
""")
        expected = self.expected()
        self.build()
        self.assertEqual(self.run_program(stress=True), expected)
        self.assertEqual(expected.count("default\n"), 1)
        self.installed(112, 11)

    def test_transition_and_loaded_exceptions_do_not_replay_arguments_or_body(self):
        self.write(CLASSES + """
evaluations = 0
def argument(stream: Hot | Cold) -> Hot | Cold:
    global evaluations
    evaluations += 1
    return stream
def consume(stream) -> int:
    return len(stream.read())
def dispatch(stream: Hot | Cold) -> int:
    return consume(argument(stream))
hot = Hot()
cold = Cold()
cold.fail = True
items: list[Hot | Cold] = [hot, cold]
total = 0
caught = 0
finished = 0
for i in range(106):
    hot.fail = i == 99 or i == 103
    try:
        total += dispatch(items[0 if i < 105 else 1])
    except ValueError as error:
        print("caught", error)
        caught += 1
    finally:
        finished += 1
print(total, hot.calls, cold.calls, evaluations, caught, finished)
""")
        expected = self.expected()
        self.build()
        self.assertEqual(self.run_program(stress=True), expected)
        self.installed(106, 6)

    def test_none_and_reversed_distribution_keep_the_generic_fallback(self):
        self.write(CLASSES + CALLS.replace("stream: Hot | Cold", "stream: Hot | Cold | None") + """
hot = Hot()
cold = Cold()
items: list[Hot | Cold | None] = [hot, cold, None]
total = 0
for i in range(113):
    index = 0 if i < 100 or i == 112 else 1 if i < 111 else 2
    try:
        total += dispatch(items[index])
    except AttributeError:
        print("none")
print(total, hot.calls, cold.calls)
""")
        self.build()
        self.assertEqual(self.run_program(), self.expected())
        self.installed(113, 2)

    def test_compiler_or_loader_failure_falls_back_once_without_retries(self):
        self.write(MONOMORPHIC)
        expected = self.expected(150)
        for action in ["fail", "invalid_library", "missing"]:
            with self.subTest(action=action):
                compiler = str(self.directory / "missing compiler") if action == "missing" else self.wrapper(action)
                self.build(compiler=compiler)
                self.assertEqual(self.run_program(150, compiler=compiler), expected)
                row = self.row()
                self.assertEqual((row["calls"], row["attempts"], row["installs"], row["hits"]), (150, 1, 0, 0))
                self.assertNotIn(row["failure"], ["", "0", "none", "ok", "-"])
                if action != "missing":
                    self.assertEqual(len(self.log.read_text().splitlines()), 1)

    def test_changed_source_cannot_install_an_incompatible_object_layout(self):
        self.write(MONOMORPHIC)
        expected = self.expected(105)
        self.build()
        self.write(MONOMORPHIC.replace("self.calls = 0", "self.padding = 8675309\n        self.calls = 0"))
        self.assertEqual(self.run_program(105), expected)
        row = self.row()
        self.assertEqual((row["calls"], row["attempts"], row["installs"], row["hits"]), (105, 1, 0, 0))
        self.assertNotIn(row["failure"], ["", "0", "none", "ok", "-"])

    def test_original_shlex_parser_crosses_the_online_boundary(self):
        benchmark = (ROOT / "bench/stream_skew.py").read_text(encoding="utf-8")
        document_assignment = next(
            node for node in ast.parse(benchmark).body if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "DOCUMENT" for target in node.targets))
        # The benchmark repeats a literal block. Evaluate only those two literal
        # operands, and retain its exact assignment text in the compiled fixture.
        expression = document_assignment.value
        self.assertIsInstance(expression, ast.BinOp)
        self.assertIsInstance(expression.op, ast.Mult)
        document = ast.literal_eval(expression.left) * ast.literal_eval(expression.right)
        self.assertEqual(len(document.encode("utf-8")), 9440)
        oracle = shlex.shlex(document, posix=True)
        oracle.whitespace_split = True
        expected_tokens = list(oracle)
        self.assertEqual(len(expected_tokens), 544)
        assignment = ast.get_source_segment(benchmark, document_assignment)
        self.assertIsNotNone(assignment)
        self.write('''
from io import StringIO
from shlex import shlex
from typing import TextIO
''' + assignment + "\nEXPECTED = " + repr(expected_tokens) + '''
seen: list[str] = []
def remember(token: str) -> int:
    seen.append(token)
    return len(token)
def consume(stream) -> int:
    lexer = shlex(posix=True, _stream=stream)
    lexer.whitespace_split = True
    result: int = 0
    while True:
        token = lexer.read_token()
        if token is None:
            break
        result += remember(token)
    return result
def dispatch(stream: TextIO | StringIO) -> int:
    return consume(stream)
with open("input.txt", "w") as output:
    output.write(DOCUMENT)
memory = StringIO(DOCUMENT)
disk = open("input.txt")
items: list[TextIO | StringIO] = [memory, disk]
total = 0
for i in range(110):
    memory.seek(0)
    disk.close()
    disk = open("input.txt")
    items[1] = disk
    seen.clear()
    total += dispatch(items[0 if i < 105 or i % 2 == 0 else 1])
    # Observe the exact tokens produced by consume itself on every call:
    # baseline calls 1..99, loaded code from 100, and held-out file fallbacks.
    assert seen == EXPECTED
print(total, len(seen))
print(seen == EXPECTED)
disk.close()
memory.close()
''')
        expected = self.expected(shlex_oracle=True)
        self.build()
        self.assertEqual(self.run_program(), expected)
        self.assertEqual(expected.splitlines()[-1], "True")
        self.installed(110, 8)


if __name__ == "__main__":
    unittest.main()
