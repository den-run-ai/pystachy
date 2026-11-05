"""Independent runtime-C cache identity and opt-in real-driver checks.

PYSTACHY_CACHE_TEST_LLVM enables the LLVM integration test. Optionally set
PYSTACHY_CACHE_TEST_COMPILER to a rebuilt native compiler; otherwise use hosted
copies with different producer identities. No performance thresholds are used.
"""
import contextlib
import io
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.pystachy_compiler import driver

ROOT = Path(__file__).resolve().parents[1]


class CacheIdentity(unittest.TestCase):
    def test_default_off_and_custom_flags_use_original_path(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(driver, "PLATFORM", "linux"):
            self.assertFalse(driver.runtime_c_cache_enabled([]))
            os.environ["PYSTACHY_RUNTIME_C_CACHE"] = "1"
            self.assertTrue(driver.runtime_c_cache_enabled([]))
            for flags in (["-O0"], ["-fsanitize=address"], ["-DPROBE"]):
                self.assertFalse(driver.runtime_c_cache_enabled(flags))
        with patch.dict(os.environ, PYSTACHY_RUNTIME_C_CACHE="bad"):
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                driver.runtime_c_cache_enabled([])

    def test_generated_directory_is_not_in_identity(self):
        def source(directory):
            return '# 1 "' + directory + '/runtime.c"\n# 1 "runtime.c"\n# 1 "' + directory + '/ryu/d2s.c"\nint x;\n'
        first = driver.runtime_c_snapshot(source("/tmp/first"), "/tmp/first")
        second = driver.runtime_c_snapshot(source("/tmp/second"), "/tmp/second")
        self.assertEqual(first, second)
        self.assertIn('# 1 "runtime.c"', first)
        self.assertIn('# 1 "ryu/d2s.c"', first)

    def test_semantic_file_name_uses_uncached_fallback(self):
        source = '# 1 "/tmp/captured/runtime.c"\nchar *name = "/tmp/captured/runtime.c";\n'
        self.assertEqual(driver.runtime_c_snapshot(source, "/tmp/captured"), "")
        literal = 'char *name = "runtime.c";\n'
        self.assertEqual(driver.runtime_c_snapshot(literal, "/tmp/captured"), literal)

    def test_header_content_tools_and_recipe_change_identity(self):
        paths = ["/llvm/clang", "/llvm/llvm-as"]
        times = ["100 10 10", "200 20 20"]
        base = driver.runtime_c_key("int probe = 1;\n", paths, times, "strip-v1")
        variants = [
            ("int probe = 2;\n", paths, times, "strip-v1"),
            ("int probe = 1;\n", ["/new/clang", paths[1]], times, "strip-v1"),
            ("int probe = 1;\n", paths, ["100 10 11", times[1]], "strip-v1"),
            ("int probe = 1;\n", paths, times, "strip-v2"),
        ]
        for arguments in variants:
            self.assertNotEqual(base, driver.runtime_c_key(*arguments))


@unittest.skipUnless(os.getenv("PYSTACHY_CACHE_TEST_LLVM"), "set PYSTACHY_CACHE_TEST_LLVM for LLVM integration")
class RealDriverCache(unittest.TestCase):
    def test_reuse_invalidation_fallback_and_failed_publish(self):
        llvm = Path(os.environ["PYSTACHY_CACHE_TEST_LLVM"]).resolve()
        with tempfile.TemporaryDirectory(prefix="pystachy C cache ' $; ") as directory:
            root = Path(directory)
            home = root / "home"
            home.mkdir()
            for name in ("lib", "ryu", "mpz"):
                (home / name).symlink_to(ROOT / name, target_is_directory=True)
            original = (ROOT / "runtime.c").read_text()
            (home / "runtime.c").write_text(original + '\n#include <cache_probe.h>\nint cache_probe(void) { return CACHE_PROBE; }\n')
            shutil.copy2(ROOT / "runtime.py", home / "runtime.py")
            headers = root / "headers"
            headers.mkdir()
            header = headers / "cache_probe.h"
            header.write_text("#define CACHE_PROBE 1\n")
            cache = root / "cache"
            temporary = root / "tmp"
            temporary.mkdir()
            tools = root / "llvm"
            tools.mkdir()
            trace = root / "clang.log"
            for name in ("llvm-as", "llvm-link", "opt"):
                (tools / name).symlink_to(llvm / name)
            wrapper = tools / "clang"
            wrapper.write_text('#!/bin/sh\nprintf \'%s\\n\' "$*" >> ' + shlex.quote(str(trace))
                               + '\nif [ "${PYSTACHY_CACHE_MUTATE_TOOL:-}" = 1 ]; then\n'
                               + ' case " $* " in *" -x cpp-output "*) touch "$0";; esac\nfi\n'
                               + "exec " + shlex.quote(str(llvm / "clang")) + ' "$@"\n')
            wrapper.chmod(0o755)
            producers = []
            native = os.getenv("PYSTACHY_CACHE_TEST_COMPILER", "")
            for index in (1, 2):
                producer = root / f"producer-{index}"
                producer.mkdir()
                if native:
                    target = producer / "pystachy"
                    shutil.copy2(native, target)
                    producers.append([str(target)])
                else:
                    target = producer / "pystachy.py"
                    target.write_text((ROOT / "pystachy.py").read_text() + f"\n# producer {index}\n")
                    (producer / "src").symlink_to(ROOT / "src", target_is_directory=True)
                    producers.append([sys.executable, str(target)])
            program = root / "program.py"
            program.write_text("print(42)\n")
            environment = {key: value for key, value in os.environ.items() if not key.startswith("PYSTACHY_")}
            environment.update(PYSTACHY_HOME=str(home), PYSTACHY_CACHE=str(cache), PYSTACHY_LLVM=str(tools),
                               PYSTACHY_RUNTIME_C_CACHE="1", PYSTACHY_TIMING="1", PYSTACHY_BUILD_JOBS="1",
                               C_INCLUDE_PATH=str(headers), TMPDIR=str(temporary))
            # Tool identity must have settled, matching the production trust rule.
            time.sleep(2.05)

            def run(producer, expected_c, **extra):
                # Always miss the producer-dependent combined runtime. The
                # independent C cache is the only permitted reuse in this test.
                for path in cache.glob("runtime-py-*.bc"):
                    path.unlink()
                trace.write_text("")
                output = root / "program"
                result = subprocess.run(producers[producer] + ["build", str(program), "-o", str(output)],
                                        env=dict(environment, **extra), cwd=ROOT, capture_output=True, text=True, timeout=90)
                calls = trace.read_text().splitlines()
                compiled = [line for line in calls if " -x cpp-output " in line or (" -x c " in line and " -E " not in line)]
                self.assertEqual(len(compiled), expected_c, (result.stderr, calls))
                self.assertFalse(list(temporary.iterdir()), result.stderr)
                return result, output, calls

            first, output, _ = run(0, 1)
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(subprocess.check_output([output]), b"42\n")
            entries = list(cache.glob("runtime-c-*.bc"))
            self.assertEqual(len(entries), 1)
            second, output, _ = run(1, 0)
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertIn("runtime.c_cache_hit", second.stderr)
            self.assertEqual(subprocess.check_output([output]), b"42\n")
            self.assertEqual(list(cache.glob("runtime-c-*.bc")), entries)
            header.write_text("#define CACHE_PROBE 2\n")
            changed, _, _ = run(1, 1)
            self.assertEqual(changed.returncode, 0, changed.stderr)
            self.assertEqual(len(list(cache.glob("runtime-c-*.bc"))), 2)
            custom, _, calls = run(1, 1, PYSTACHY_CFLAGS="-DKEEP_ORIGINAL")
            self.assertEqual(custom.returncode, 0, custom.stderr)
            self.assertFalse(any(" -E " in line for line in calls))
            self.assertEqual(len(list(cache.glob("runtime-c-*.bc"))), 2)
            header.write_text("#define CACHE_PROBE 3\n")
            mutated, _, _ = run(1, 1, PYSTACHY_CACHE_MUTATE_TOOL="1")
            self.assertEqual(mutated.returncode, 0, mutated.stderr)
            self.assertEqual(len(list(cache.glob("runtime-c-*.bc"))), 2, "changed tool must not publish")
            # Let the wrapper settle, then fail after successful preprocessing.
            time.sleep(2.05)
            (home / "runtime.c").write_text(original + "\nint broken = UNDECLARED_CACHE_SENTINEL;\n")
            failed, _, _ = run(1, 1)
            self.assertEqual(failed.returncode, 1, failed.stderr)
            self.assertIn("UNDECLARED_CACHE_SENTINEL", failed.stderr)
            self.assertEqual(len(list(cache.glob("runtime-c-*.bc"))), 2)
            self.assertFalse(list(cache.glob("runtime-c-*.bc.*")), "no partial cache entries")


if __name__ == "__main__":
    unittest.main()
