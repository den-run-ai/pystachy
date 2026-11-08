"""Real exec boundaries: cached programs run once, pre-exec failures retry once."""
import errno
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CC = shutil.which("cc")
CAT = shutil.which("cat")
SETTINGS = ("PYSTACHY_PROGRAM_CACHE", "PYSTACHY_GC_STRESS", "PYSTACHY_GC_STRESS_PROGRAM",
            "PYSTACHY_PROGRAM_CACHE_LOCK", "PYSTACHY_ARGV0", "PC_EXEC_VALUE")
DRIVER = r'''
import fcntl
import json
import os
import sys
sys.path.insert(0, os.environ["PC_EXEC_ROOT"])
from src.pystachy_compiler import cached_run

arguments = sys.argv[3:]
source = sys.argv[2]
sys.argv = [sys.executable, *sys.argv]
retry = os.getenv("PYSTACHY_PROGRAM_CACHE_LOCK") == "bypass"
if os.getenv("PC_EXEC_LOCK") and not retry:
    lock = open(os.environ["PC_EXEC_LOCK"], "a+b")
    fcntl.flock(lock, fcntl.LOCK_EX)
    assert not os.get_inheritable(lock.fileno())
settings = {key: os.getenv(key) for key in (
    "PYSTACHY_PROGRAM_CACHE", "PYSTACHY_GC_STRESS", "PYSTACHY_GC_STRESS_PROGRAM",
    "PYSTACHY_PROGRAM_CACHE_LOCK", "PYSTACHY_ARGV0", "PC_EXEC_VALUE")}
record = {"argv": sys.argv, "settings": settings}
with open(os.environ["PC_EXEC_DRIVER_LOG"], "a") as stream:
    stream.write(json.dumps(record) + "\n")
if retry:
    record["input"] = sys.stdin.buffer.read().hex()
    print(json.dumps(record))
    os.write(2, b"ordinary compiler stderr\n")
    raise SystemExit(23)
if os.getenv("PC_EXEC_UNLINK") == "1":
    execute = os.execv
    def after_pin(path, arguments):
        assert path.startswith("/proc/self/fd/"), path
        assert os.path.samefile(path, os.environ["PC_EXEC_ENTRY"])
        os.unlink(os.environ["PC_EXEC_ENTRY"])
        execute(path, arguments)
    os.execv = after_pin
cached_run.execute(os.environ["PC_EXEC_ENTRY"], source, arguments)
raise AssertionError("exec returned")
'''
PROGRAM = r'''
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/file.h>
#include <unistd.h>

static void field(const char *value) {
    if (value == NULL) value = "<unset>";
    size_t size = strlen(value);
    printf("%zu:", size);
    fwrite(value, 1, size, stdout);
}

int main(int argc, char **argv) {
    FILE *count = fopen(getenv("PC_EXEC_PROGRAM_LOG"), "a");
    if (count == NULL) return 91;
    fputs("executed\n", count);
    fclose(count);
    printf("argc=%d\n", argc);
    for (int i = 0; i < argc; i++) field(argv[i]);
    const char *names[] = {"PYSTACHY_PROGRAM_CACHE", "PYSTACHY_GC_STRESS", "PYSTACHY_GC_STRESS_PROGRAM",
                          "PYSTACHY_PROGRAM_CACHE_LOCK", "PYSTACHY_ARGV0", "PC_EXEC_VALUE"};
    for (size_t i = 0; i < sizeof(names) / sizeof(names[0]); i++) field(getenv(names[i]));
    const char *path = getenv("PC_EXEC_LOCK");
    if (path != NULL) {
        int lock = open(path, O_RDONLY);
        field(lock >= 0 && flock(lock, LOCK_EX | LOCK_NB) == 0 ? "unlocked" : "held");
        if (lock >= 0) close(lock);
    } else field("no-lock");
    putchar('\n');
    char buffer[4096];
    size_t size;
    while ((size = fread(buffer, 1, sizeof(buffer), stdin)) != 0) fwrite(buffer, 1, size, stdout);
    fputs("native stderr\n", stderr);
    const char *status = getenv("PC_EXEC_STATUS");
    return status == NULL ? 0 : atoi(status);
}
'''


@unittest.skipUnless(sys.platform == "linux", "direct cached exec uses Linux /proc/self/fd")
class CachedRunExecTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        temporary = tempfile.TemporaryDirectory(prefix="pystachy-cache-exec-fixtures-")
        cls.addClassCleanup(temporary.cleanup)
        cls.fixtures = Path(temporary.name)
        cls.runner = cls.fixtures / "compiler.py"
        cls.runner.write_text(DRIVER)
        if CC:
            source = cls.fixtures / "program.c"
            source.write_text(PROGRAM)
            cls.native = cls.fixtures / "native"
            cls.missing_interpreter = cls.fixtures / "missing-interpreter"
            for output, flags in ((cls.native, []), (cls.missing_interpreter,
                                  ["-Wl,--dynamic-linker=" + str(cls.fixtures / "absent-loader")])):
                built = subprocess.run([CC, "-std=c11", "-Wall", "-Wextra", "-Werror", str(source),
                                        "-o", str(output), *flags], capture_output=True, timeout=30)
                if built.returncode:
                    raise AssertionError(built.stderr.decode())

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="pystachy-cache-exec-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = str(self.root / "app 'quoted' $literal `literal`\nα.py")
        self.serial = 0

    def launch(self, entry, arguments=(), data=b"", changes=None):
        self.serial += 1
        driver_log = self.root / f"driver-{self.serial}.jsonl"
        program_log = self.root / f"program-{self.serial}.log"
        environment = {key: value for key, value in os.environ.items()
                       if not key.startswith(("PYSTACHY_", "PC_EXEC_"))}
        environment.update(PYSTACHY_PROGRAM_CACHE="1", PYSTACHY_GC_STRESS="1000",
                           PYSTACHY_GC_STRESS_PROGRAM="1", PYSTACHY_PROGRAM_CACHE_LOCK="owned",
                           PYSTACHY_ARGV0="original argv0", PC_EXEC_VALUE="env '\n$(touch env-injected)",
                           PC_EXEC_ROOT=str(ROOT), PC_EXEC_ENTRY=str(entry),
                           PC_EXEC_DRIVER_LOG=str(driver_log), PC_EXEC_PROGRAM_LOG=str(program_log))
        for key, value in (changes or {}).items():
            if value is None:
                environment.pop(key, None)
            else:
                environment[key] = value
        command = [sys.executable, str(self.runner), "run", self.source, *arguments]
        result = subprocess.run(command, cwd=self.root, env=environment, input=data,
                                capture_output=True, timeout=10)
        self.assertTrue(driver_log.exists(), result.stderr)
        runs = [json.loads(line) for line in driver_log.read_text().splitlines()]
        executions = program_log.read_text() if program_log.exists() else ""
        return result, runs, executions, environment, command

    def expected_native(self, arguments, data, environment):
        settings = {key: environment.get(key) for key in SETTINGS}
        settings["PYSTACHY_PROGRAM_CACHE_LOCK"] = None
        if environment.get("PYSTACHY_GC_STRESS_PROGRAM"):
            settings["PYSTACHY_GC_STRESS"] = environment["PYSTACHY_GC_STRESS_PROGRAM"]
        values = [self.source, *arguments, *settings.values(),
                  "unlocked" if "PC_EXEC_LOCK" in environment else "no-lock"]
        output = f"argc={len(arguments) + 1}\n".encode()
        for value in values:
            data_field = ("<unset>" if value is None else value).encode()
            output += str(len(data_field)).encode() + b":" + data_field
        return output + b"\n" + data

    def assert_retry(self, entry, changes=None):
        arguments = ["space here", "'quoted'", "$(touch retry-injected)", "line\nbreak", ""]
        data = b"unconsumed stdin\x00\xff\n"
        result, runs, executions, environment, command = self.launch(entry, arguments, data, changes)
        self.assertEqual((result.returncode, result.stderr), (23, b"ordinary compiler stderr\n"))
        self.assertEqual(len(runs), 2, runs)
        self.assertEqual([run["argv"] for run in runs], [command, command])
        expected = {key: environment.get(key) for key in SETTINGS}
        self.assertEqual(runs[0]["settings"], expected)
        expected["PYSTACHY_PROGRAM_CACHE_LOCK"] = "bypass"
        self.assertEqual(runs[1]["settings"], expected)
        self.assertEqual(json.loads(result.stdout), {"argv": command, "settings": expected, "input": data.hex()})
        self.assertEqual(executions, "")
        self.assertFalse((self.root / "retry-injected").exists())

    @unittest.skipUnless(CAT, "cat is required for the byte-stream exec control")
    def test_stdin_and_stdout_bytes_cross_a_real_exec(self):
        data = b"line\r\n\x00\xff\n" * 700
        result, runs, _, _, _ = self.launch(CAT, data=data)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, data, b""))
        self.assertEqual(len(runs), 1)

    @unittest.skipUnless(CC, "a C compiler is required to observe native argv[0]")
    def test_native_argv0_arguments_environment_and_streams(self):
        arguments = ["space here", "$(touch injected)", "a'b", "`touch injected`", "α\nβ", ""]
        data = b"stdin\x00\xff\n"
        result, runs, executions, environment, _ = self.launch(self.native, arguments, data)
        self.assertEqual((result.returncode, result.stderr), (0, b"native stderr\n"))
        self.assertEqual(result.stdout, self.expected_native(arguments, data, environment))
        self.assertEqual(len(runs), 1)
        self.assertEqual(executions, "executed\n")
        self.assertFalse((self.root / "injected").exists())
        self.assertFalse((self.root / "env-injected").exists())

    @unittest.skipUnless(CC, "a C compiler is required for native exit-status controls")
    def test_program_exit_126_and_127_never_trigger_a_second_execution(self):
        for status in (126, 127):
            with self.subTest(status=status):
                result, runs, executions, environment, _ = self.launch(self.native, changes={"PC_EXEC_STATUS": str(status)})
                self.assertEqual((result.returncode, result.stderr), (status, b"native stderr\n"))
                self.assertEqual(result.stdout, self.expected_native([], b"", environment))
                self.assertEqual(len(runs), 1)
                self.assertEqual(executions, "executed\n")

    @unittest.skipUnless(CC, "a C compiler is required for program environment controls")
    def test_success_preserves_unset_empty_and_explicit_runtime_settings(self):
        variants = [
            {"PYSTACHY_PROGRAM_CACHE": None, "PYSTACHY_GC_STRESS": None, "PYSTACHY_GC_STRESS_PROGRAM": None},
            {"PYSTACHY_PROGRAM_CACHE": "", "PYSTACHY_GC_STRESS": "", "PYSTACHY_GC_STRESS_PROGRAM": ""},
            {"PYSTACHY_PROGRAM_CACHE": "0", "PYSTACHY_GC_STRESS": "1000", "PYSTACHY_GC_STRESS_PROGRAM": "0"},
        ]
        for changes in variants:
            with self.subTest(changes=changes):
                result, runs, executions, environment, _ = self.launch(self.native, changes=changes)
                self.assertEqual((result.returncode, result.stderr), (0, b"native stderr\n"))
                self.assertEqual(result.stdout, self.expected_native([], b"", environment))
                self.assertEqual((len(runs), executions), (1, "executed\n"))

    @unittest.skipUnless(CC and Path("/usr/bin/flock").is_file(), "native lock check requires cc and flock")
    def test_bucket_lock_is_released_before_the_program_runs(self):
        result, runs, executions, environment, _ = self.launch(self.native, changes={"PC_EXEC_LOCK": str(self.root / "bucket")})
        self.assertEqual((result.returncode, result.stderr), (0, b"native stderr\n"))
        self.assertEqual(result.stdout, self.expected_native([], b"", environment))
        self.assertEqual((len(runs), executions), (1, "executed\n"))

    @unittest.skipUnless(CAT, "cat is required for the pinned-entry control")
    def test_open_entry_survives_unlink_after_pin_before_exec(self):
        entry = self.root / "pinned"
        shutil.copy2(CAT, entry)
        result, runs, _, _, _ = self.launch(entry, data=b"pinned bytes\n", changes={"PC_EXEC_UNLINK": "1"})
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, b"pinned bytes\n", b""))
        self.assertEqual(len(runs), 1)
        self.assertFalse(entry.exists())

    def test_missing_nonexecutable_and_malformed_elf_retry_once(self):
        for kind in ("missing", "nonexecutable", "malformed ELF"):
            with self.subTest(kind=kind):
                entry = self.root / kind
                if kind != "missing":
                    entry.write_bytes(b"\x7fELFmalformed\n")
                    entry.chmod(0o600 if kind == "nonexecutable" else 0o700)
                self.assert_retry(entry)

    def test_failure_restores_absent_and_empty_cache_and_gc_settings(self):
        entry = self.root / "unusable"
        entry.write_bytes(b"\x7fELFmalformed\n")
        entry.chmod(0o700)
        for cache, stress in ((None, None), ("", ""), ("0", None)):
            with self.subTest(cache=cache, stress=stress):
                self.assert_retry(entry, {"PYSTACHY_PROGRAM_CACHE": cache,
                                  "PYSTACHY_GC_STRESS": stress, "PYSTACHY_GC_STRESS_PROGRAM": "1"})

    @unittest.skipUnless(CC, "a C compiler is required for a missing PT_INTERP control")
    def test_missing_elf_interpreter_retries_once(self):
        self.assertTrue(self.missing_interpreter.is_file())
        self.assert_retry(self.missing_interpreter)

    @unittest.skipUnless(CC, "a C compiler is required for the ETXTBSY control")
    def test_executable_open_for_writing_retries_once(self):
        entry = self.root / "busy"
        shutil.copy2(self.native, entry)
        with entry.open("r+b"):
            with self.assertRaises(OSError) as failed:
                subprocess.run([str(entry)], input=b"", capture_output=True, timeout=5,
                               env=os.environ | {"PC_EXEC_PROGRAM_LOG": str(self.root / "precondition.log")})
            self.assertEqual(failed.exception.errno, errno.ETXTBSY)
            self.assert_retry(entry)


if __name__ == "__main__":
    unittest.main()
