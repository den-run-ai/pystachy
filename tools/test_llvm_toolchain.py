"""The minimal LLVM toolchain recipe: what it builds, and what its check refuses."""

import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/llvm_toolchain.sh"
sys.path.insert(0, str(ROOT))

import pystachy_toolchain  # noqa: E402


def setting(name: str) -> str:
    found = re.search(rf'^{name}=(?:"([^"]*)"|\$\{{[A-Z_0-9]+:-([^}}]*)\}})$', SCRIPT.read_text(), re.M)
    if not found:
        raise AssertionError(f"{name} is not set in {SCRIPT.name}")
    return found[1] if found[1] is not None else found[2]


def run(*arguments: str, **environment: str) -> subprocess.CompletedProcess:
    return subprocess.run(["sh", str(SCRIPT), *arguments], capture_output=True, text=True, timeout=120,
                          env={**os.environ, **environment})


def fake_tool(path: Path, version: str) -> None:
    path.write_text(f"#!/bin/sh\necho 'LLVM version {version}'\n")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


class RecipeTests(unittest.TestCase):
    def test_builds_every_tool_the_driver_runs(self):
        tools = setting("TOOLS").split()
        self.assertLessEqual(set(pystachy_toolchain.TOOLS), set(tools))
        components = re.search(r'-DLLVM_DISTRIBUTION_COMPONENTS="([^"]*)"', SCRIPT.read_text())[1].split(";")
        for tool in tools:
            self.assertIn(tool, components)
        self.assertIn("LLVM", components)  # the shared libLLVM that lli loads and the JIT runner links

    def test_source_archive_is_pinned_to_one_release(self):
        self.assertRegex(setting("VERSION"), r"^[0-9]+\.[0-9]+\.[0-9]+$")
        self.assertRegex(setting("SHA256"), r"^[0-9a-f]{64}$")
        self.assertIn("llvmorg-$VERSION/llvm-project-$VERSION.src.tar.xz", SCRIPT.read_text())

    def test_uses_no_optional_host_library_and_one_target(self):
        text = SCRIPT.read_text()
        for library in ("ZLIB", "ZSTD", "LIBXML2", "TERMINFO", "LIBEDIT", "FFI", "CURL"):
            self.assertIn(f"-DLLVM_ENABLE_{library}=OFF", text)
        self.assertIn('-DLLVM_TARGETS_TO_BUILD="$TARGET"', text)


@unittest.skipUnless(sys.platform == "linux" and os.uname().machine in ("x86_64", "aarch64"), "the recipe is for Linux x86-64 and AArch64")
class CheckTests(unittest.TestCase):
    def test_name_states_release_and_architecture(self):
        result = run("name")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), f"pystachy-llvm-{setting('VERSION')}-linux-{os.uname().machine}")

    def test_usage_errors_fail(self):
        for arguments in ((), ("build",), ("check",), ("check", "a", "b"), ("install", "a")):
            with self.subTest(arguments=arguments):
                result = run(*arguments)
                self.assertEqual(result.returncode, 1)
                self.assertIn("usage:", result.stderr)

    def test_check_names_a_missing_tool(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "bin").mkdir()
            for tool in setting("TOOLS").split()[:-1]:
                fake_tool(Path(directory) / "bin" / tool, setting("VERSION"))
            result = run("check", directory)
        self.assertEqual(result.returncode, 1)
        self.assertIn(f"bin/{setting('TOOLS').split()[-1]} is missing", result.stderr)

    def test_check_refuses_another_release(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "bin").mkdir()
            for tool in setting("TOOLS").split():
                fake_tool(Path(directory) / "bin" / tool, "17.0.6")
            result = run("check", directory)
        self.assertEqual(result.returncode, 1)
        self.assertIn(f"clang is not LLVM {setting('VERSION')}", result.stderr)

    def test_check_refuses_a_toolchain_without_clang_headers(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "bin").mkdir()
            for tool in setting("TOOLS").split():
                fake_tool(Path(directory) / "bin" / tool, setting("VERSION"))
            result = run("check", directory)
        self.assertEqual(result.returncode, 1)
        self.assertIn("clang's headers are missing", result.stderr)


if __name__ == "__main__":
    unittest.main()
