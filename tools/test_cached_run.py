"""Fail-closed input collection and request identity for cached native runs."""
from contextlib import ExitStack
import os
from pathlib import Path
import re
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.pystachy_compiler import cached_run

ROOT = Path(__file__).resolve().parent.parent
# The settings a cached program's identity spells exactly (docs/program-cache.md).
KEYED = ["PYSTACHY_OPT", "PYSTACHY_JIT_INLINE", "PYSTACHY_JIT_OPT", "PYSTACHY_DEBUG_LINES", "PYSTACHY_RUNTIME_C_CACHE",
         "PYSTACHY_PATH", "PYSTACHY_PROGRAM_CACHE_INPUTS", "PATH", "HOME", "XDG_CONFIG_HOME"]


class DependencyInputsTests(unittest.TestCase):
    def test_make_escaped_prerequisites(self):
        # Clang -M -MT cache, including a wrapped line and the Make spelling of
        # literal dollars/hash/whitespace. No shell evaluates these paths.
        text = ("cache: /src/a\\ b.c \\\n"
                " /usr/include/stdio.h /inc/a\\#b.h /inc/c$$d.h "
                "/inc/slash\\\\name.h /inc/tab\\\tname.h /inc/colon:name.h\n")
        self.assertEqual(cached_run.dep_paths(text), [
            "/src/a b.c", "/usr/include/stdio.h", "/inc/a#b.h", "/inc/c$d.h",
            "/inc/slash\\name.h", "/inc/tab\tname.h", "/inc/colon:name.h",
        ])

    def test_bad_target_or_unterminated_escape_does_not_supply_inputs(self):
        for text in ("", "notcache: /x\n", "cache:", "cache: /x\\", "cache: \\\n"):
            with self.subTest(text=text):
                self.assertEqual(cached_run.dep_paths(text), [])

    def test_link_trace_keeps_opened_inputs_and_excludes_ephemeral_objects(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            paths = [base / name for name in ("program.o", "runtime.o", "crt.o", "lib m.so")]
            for path in paths:
                path.touch()
            log = base / "link-inputs"
            log.write_text("\n".join(str(p) for p in paths) + "\n")
            with patch.object(cached_run.pc, "track_static") as track:
                self.assertTrue(cached_run.link_inputs(str(log), str(paths[0]), str(paths[1])))
            self.assertEqual([x.args[0] for x in track.call_args_list], [str(p) for p in paths[2:]])

    def test_incomplete_or_unsupported_link_trace_cannot_validate(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            obj, runtime = str(base / "program.o"), str(base / "runtime.o")
            log = base / "link-inputs"
            for text in ("", obj + "\n" + runtime + "\n", "relative.so\n",
                         str(base / "missing.so") + "\n", "(archive.a)member.o\n"):
                with self.subTest(text=text), patch.object(cached_run.pc, "track_static"):
                    log.write_text(text)
                    self.assertFalse(cached_run.link_inputs(str(log), obj, runtime))


class EligibilityTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.dict(os.environ, {
            "PYSTACHY_PROGRAM_CACHE": "1", "PYSTACHY_CACHE": "/private/cache",
        }, clear=True))
        self.stack.enter_context(patch.object(cached_run, "PLATFORM", "linux"))
        self.native = self.stack.enter_context(patch.object(cached_run, "native_compiler", return_value=True))
        self.stack.enter_context(patch.object(cached_run, "declared_tools", return_value=True))
        self.admit = self.stack.enter_context(patch.object(cached_run.pc, "_cache_dir", return_value="/private/cache/program-v2"))
        self.acquire = self.stack.enter_context(patch.object(cached_run, "acquire", return_value=True))
        self.layout = self.stack.enter_context(patch.object(cached_run.cache_toolchain, "capture", return_value={"/headers": "record"}))
        self.stack.enter_context(patch.object(cached_run.pc, "track_layout"))
        self.stack.enter_context(patch.object(cached_run.pc, "VALID", [True]))
        self.stack.enter_context(patch.object(cached_run.os.path, "exists", return_value=True))
        self.stack.enter_context(patch.object(cached_run.os.path, "isfile", return_value=True))
        self.stack.enter_context(patch.object(cached_run.os.path, "realpath", side_effect=lambda p: p))
        self.listdir = self.stack.enter_context(patch.object(cached_run.os, "listdir", return_value=[]))
        self.cwd = self.stack.enter_context(patch.object(cached_run.os, "getcwd", return_value="/work"))
        self.read = self.stack.enter_context(patch.object(cached_run, "read_raw", return_value="vendor_id: test\nflags: one two\n"))
        self.stop = self.stack.enter_context(patch.object(cached_run.pc, "stop"))
        self.start = self.stack.enter_context(patch.object(cached_run.pc, "start"))
        self.lookup = self.stack.enter_context(patch.object(cached_run.pc, "lookup_in", return_value="/cache/native.exe"))
        self.inputs = self.stack.enter_context(patch.object(cached_run, "tool_inputs", return_value=True))
        self.trace = self.stack.enter_context(patch.object(cached_run, "trace"))

    @staticmethod
    def prepare(cmd="run", source="main.py", dirs=None, llvm="/llvm/bin"):
        return cached_run.prepare(cmd, source, "/compiler/pystachy", "/compiler",
                                  [".", "/compiler/lib"] if dirs is None else dirs,
                                  llvm, ["mpz/mpz.c"])

    def test_disabled_and_other_commands_never_look_up_or_collect(self):
        for command in ("build", "ext", "ir", "check", "rt"):
            self.assertEqual(self.prepare(cmd=command), ("", "", ""))
        for flag in ("0", "unexpected"):
            with patch.dict(os.environ, {"PYSTACHY_PROGRAM_CACHE": flag}):
                self.assertEqual(self.prepare(), ("", "", ""))
        self.lookup.assert_not_called()
        self.inputs.assert_not_called()

    def test_unset_and_empty_setting_enable_the_default(self):
        for present in (False, True):
            with patch.dict(os.environ, {"PYSTACHY_PROGRAM_CACHE": ""}):
                if not present:
                    del os.environ["PYSTACHY_PROGRAM_CACHE"]
                self.assertEqual(self.prepare()[2], "/cache/native.exe")

    def test_nondefault_settings_fail_closed(self):
        variants = [
            ("PYSTACHY_CFLAGS", "-fsanitize=address"), ("PYSTACHY_JIT_CODEGEN", "0"),
            ("PYSTACHY_IRCHECK", "1"), ("PYSTACHY_IRFX", "1"),
            ("PYSTACHY_UNICODE_AUDIT", "1"),
        ] + [(key, "/external/input") for key in cached_run.BUILD_ENV]
        for key, value in variants:
            with self.subTest(key=key), patch.dict(os.environ, {key: value}):
                self.assertEqual(self.prepare(), ("", "", ""))
        self.lookup.assert_not_called()
        self.inputs.assert_not_called()

    def test_platform_hosted_relative_tools_and_configurations_bypass(self):
        with patch.object(cached_run, "PLATFORM", "darwin"):
            self.assertEqual(self.prepare(), ("", "", ""))
        self.native.return_value = False
        self.assertEqual(self.prepare(), ("", "", ""))
        self.native.return_value = True
        self.assertEqual(self.prepare(llvm="relative/bin"), ("", "", ""))
        self.listdir.return_value = ["clang.cfg"]
        self.assertEqual(self.prepare(), ("", "", ""))
        self.lookup.assert_not_called()

    def test_unavailable_cpu_identity_bypasses(self):
        self.read.return_value = "processor: 0\n"
        self.assertEqual(self.prepare(), ("", "", ""))
        self.read.side_effect = OSError("unreadable")
        self.assertEqual(self.prepare(), ("", "", ""))
        self.lookup.assert_not_called()

    def test_hit_needs_no_llvm_collection_or_frontend_state(self):
        root, context, executable = self.prepare()
        self.assertEqual((root, executable), ("/private/cache", "/cache/native.exe"))
        self.assertTrue(context)
        self.start.assert_not_called()
        self.inputs.assert_not_called()
        self.layout.assert_not_called()
        self.trace.assert_called_once_with("hit")
        self.admit.assert_called_once_with("/private/cache")
        self.acquire.assert_called_once_with("/private/cache/program-v2", context)
        self.lookup.assert_called_once_with("/private/cache/program-v2", context)

    def test_miss_collects_actual_inputs_and_collection_failure_bypasses(self):
        self.lookup.return_value = ""
        root, context, executable = self.prepare()
        self.assertEqual((root, executable), ("/private/cache", ""))
        self.assertTrue(context)
        self.start.assert_called_once_with()
        self.inputs.assert_called_once_with("/compiler", "/llvm/bin", "/compiler/pystachy", ["/compiler/mpz/mpz.c"])
        self.inputs.return_value = False
        self.assertEqual(self.prepare(), ("", "", ""))
        self.trace.assert_called_with("bypass toolchain inputs unavailable")

    def test_runtime_inputs_do_not_change_identity(self):
        before = self.prepare()[1]
        with patch.dict(os.environ, {"APPLICATION_VALUE": "new", "PYSTACHY_GC_STRESS_PROGRAM": "1"}):
            after = self.prepare()[1]
        self.assertEqual(before, after)

    def test_source_spelling_directory_order_flags_and_generated_inputs_change_identity(self):
        baseline = self.prepare()[1]
        self.assertNotEqual(baseline, self.prepare(source="./main.py")[1])
        self.assertNotEqual(baseline, self.prepare(dirs=["/compiler/lib", "."])[1])
        self.cwd.return_value = "/other"
        self.assertNotEqual(baseline, self.prepare()[1])
        self.cwd.return_value = "/work"
        for key, value in [("PYSTACHY_OPT", "-all"), ("PYSTACHY_JIT_INLINE", "0"), ("PYSTACHY_JIT_OPT", "2"),
                           ("PYSTACHY_DEBUG_LINES", "1"), ("PYSTACHY_RUNTIME_C_CACHE", "1"),
                           ("PYSTACHY_PROGRAM_CACHE_INPUTS", "/generated/config.json"),
                           ("PYSTACHY_PATH", "/new/imports"), ("PATH", "/different/tools"),
                           ("HOME", "/other/home"), ("XDG_CONFIG_HOME", "/other/config")]:
            with self.subTest(key=key), patch.dict(os.environ, {key: value}):
                self.assertNotEqual(baseline, self.prepare()[1])

    def test_empty_settings_are_not_unset(self):
        # #1168: uncached compilation rejects an empty PYSTACHY_JIT_INLINE or
        # PYSTACHY_RUNTIME_C_CACHE, and GNU ld rejects an empty GNUTARGET. A hit
        # stored without the setting must not serve such a launch.
        seen = {self.prepare()[1]}
        for key in KEYED + cached_run.BUILD_ENV:
            with self.subTest(key=key), patch.dict(os.environ, {key: ""}):
                context = self.prepare()[1]
                self.assertTrue(context)
                self.assertNotIn(context, seen)
                seen.add(context)
        self.assertEqual(sorted(KEYED), sorted(cached_run.KEYED_ENV))


class SettingsDocumentationTests(unittest.TestCase):
    def test_every_compiler_setting_is_classified(self):
        # A setting read while compiling is keyed, bypasses the cache or is
        # documented as one that leaves the executable unchanged.
        names = set(cached_run.KEYED_ENV + cached_run.BUILD_ENV)
        for path in (ROOT / "src/pystachy_compiler").glob("*.py"):
            names.update(re.findall(r'os\.getenv\("([A-Z0-9_]+)"', path.read_text(encoding="utf-8")))
        guide = (ROOT / "docs/program-cache.md").read_text(encoding="utf-8")
        self.assertIn("PYSTACHY_DEBUG_LINES", names)
        self.assertEqual(sorted(name for name in names if f"`{name}`" not in guide), [])


class NativeLockTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(cached_run, "NATIVE", True))
        self.bucket = self.stack.enter_context(patch.object(cached_run.pc, "_bucket_lock", return_value="/cache/lock-aa"))
        self.lock = self.stack.enter_context(patch.object(cached_run, "try_lock", return_value=1))
        self.sleep = self.stack.enter_context(patch.object(cached_run.time, "sleep"))
        self.clock = self.stack.enter_context(patch.object(cached_run.time, "monotonic"))
        self.stack.enter_context(patch.object(cached_run.pc, "_sh", side_effect=AssertionError("unexpected shell")))
        self.stack.enter_context(patch.object(cached_run.os, "execv", side_effect=AssertionError("unexpected restart")))

    def test_missing_native_primitive_bypasses_without_descriptor_redirects(self):
        with patch.object(cached_run, "NATIVE", False):
            self.assertFalse(cached_run.acquire("/cache", "context"))
        self.lock.assert_not_called()
        self.sleep.assert_not_called()

    def test_uncontended_native_lock_needs_no_restart_or_wait(self):
        self.assertTrue(cached_run.acquire("/cache", "context"))
        self.lock.assert_called_once_with("/cache/lock-aa")
        self.sleep.assert_not_called()
        self.clock.assert_not_called()

    def test_busy_native_lock_waits_for_the_existing_writer(self):
        self.lock.side_effect = [0, 0, 1]
        self.clock.side_effect = [0.0, 0.0, 1.0]
        self.assertTrue(cached_run.acquire("/cache", "context"))
        self.assertEqual(self.lock.call_count, 3)
        self.assertEqual(self.sleep.call_count, 2)

    def test_timeout_and_unusable_lock_bypass_without_restart(self):
        self.lock.return_value = 0
        self.clock.side_effect = [0.0, 31.0]
        self.assertFalse(cached_run.acquire("/cache", "context"))
        self.sleep.assert_not_called()
        self.lock.return_value = -1
        self.clock.reset_mock(side_effect=True)
        self.assertFalse(cached_run.acquire("/cache", "context"))
        self.clock.assert_not_called()
        self.bucket.return_value = ""
        self.lock.reset_mock()
        self.assertFalse(cached_run.acquire("/cache", "context"))
        self.lock.assert_not_called()


class ProcessTests(unittest.TestCase):
    def test_native_identity_requires_the_running_file(self):
        with patch.object(cached_run.os.path, "samefile", return_value=True) as same:
            self.assertTrue(cached_run.native_compiler("/bin/pystachy"))
            same.assert_called_once_with("/bin/pystachy", "/proc/self/exe")
        with patch.object(cached_run.os.path, "samefile", side_effect=AssertionError("must not inspect")):
            self.assertFalse(cached_run.native_compiler("pystachy"))
            self.assertFalse(cached_run.native_compiler("/compiler/pystachy.py"))
        with patch.object(cached_run.os.path, "samefile", side_effect=OSError("unavailable")):
            self.assertFalse(cached_run.native_compiler("/bin/pystachy"))

    def test_execution_keeps_shell_metacharacters_as_data_and_maps_program_gc(self):
        source = "/path/a '$`\n.py"
        args = ["space here", "$(touch should-not-exist)", "a'b", "line\nbreak", ""]
        with patch.dict(os.environ, {"PYSTACHY_GC_STRESS_PROGRAM": "1"}, clear=True), \
                patch.object(cached_run.sys, "argv", ["/bin/sh", "-c", "exit 119"]), \
                patch.object(cached_run.pc, "_sh", return_value=True), \
                patch.object(cached_run.os, "execv") as execute:
            cached_run.execute("/usr/bin/printf", source, ["%s\\n", *args])
            self.assertEqual(os.environ["PYSTACHY_GC_STRESS"], "1")
            self.assertNotIn("PYSTACHY_PROGRAM_CACHE_LOCK", os.environ)
        path, argv = execute.call_args.args
        self.assertTrue(path.startswith("/proc/self/fd/"))
        self.assertEqual(argv, [source, "%s\\n", *args])

    def test_missing_and_failed_exec_retry_preserves_user_cache_setting(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "entry"
            retry = ["/compiler/pystachy", "run", "main.py", "argument"]
            for create in (False, True):
                if create:
                    path.write_text("unusable")
                    path.chmod(0o600)
                failure = [PermissionError("cannot execute"), None] if create else [None]
                with patch.dict(os.environ, {"PYSTACHY_PROGRAM_CACHE": "1", "PYSTACHY_GC_STRESS_PROGRAM": "1"}, clear=True), \
                        patch.object(cached_run.sys, "argv", retry), \
                        patch.object(cached_run.pc, "_sh", return_value=True), \
                        patch.object(cached_run.os, "execv", side_effect=failure) as execute:
                    cached_run.execute(str(path), "main.py", [])
                    self.assertEqual(os.environ["PYSTACHY_PROGRAM_CACHE"], "1")
                    self.assertEqual(os.environ["PYSTACHY_PROGRAM_CACHE_LOCK"], "bypass")
                    self.assertNotIn("PYSTACHY_GC_STRESS", os.environ)
                execute.assert_called_with(retry[0], retry)

    def test_native_execution_leaves_unlock_to_close_on_exec(self):
        with patch.object(cached_run, "NATIVE", True), \
                patch.object(cached_run.pc, "_sh", side_effect=AssertionError("unexpected shell")), \
                patch.object(cached_run.os, "execv") as execute:
            cached_run.execute("/usr/bin/printf", "source.py", ["argument"])
        self.assertTrue(execute.call_args.args[0].startswith("/proc/self/fd/"))
        self.assertEqual(execute.call_args.args[1], ["source.py", "argument"])


if __name__ == "__main__":
    unittest.main()
