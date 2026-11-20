"""The minimal LLVM toolchain recipe: what it builds, what its check refuses and how compiling is shared."""

import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/llvm_toolchain.sh"
WORKFLOW = ROOT / ".github/workflows/llvm-toolchain.yml"
DOCUMENT = ROOT / "docs/llvm-toolchain.md"
# Counts its runs, then writes the files that -o and -MF name from its last argument, the source.
COMPILER = """#!/bin/sh
echo run >> "$(dirname "$0")/runs"
while [ $# -gt 1 ]; do
  case "$1" in -o) object=$2 ;; -MF) depfile=$2 ;; esac
  shift
done
[ "$1" != broken.c ] || exit 3
echo "object of $1" > "$object"
echo "dependencies of $1" > "$depfile"
"""
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
        for arguments in ((), ("build",), ("check",), ("check", "a", "b"), ("install", "a"), ("compile", "a", "0"),
                          ("generators",), ("generators", "a", "b")):
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

    def test_compile_refuses_a_slice_outside_its_count(self):
        for slice_, count, message in (("8", "8", "slice 8 is not below 8"), ("x", "8", "I and N are numbers")):
            with self.subTest(slice=slice_), tempfile.TemporaryDirectory() as directory:
                result = run("compile", directory, slice_, count)
                self.assertEqual(result.returncode, 1)
                self.assertIn(message, result.stderr)
                self.assertEqual(os.listdir(directory), [])


@unittest.skipUnless(sys.platform == "linux" and os.uname().machine in ("x86_64", "aarch64"), "the recipe is for Linux x86-64 and AArch64")
class LaunchTests(unittest.TestCase):
    def setUp(self):
        self.directory = Path(self.enterContext(tempfile.TemporaryDirectory()))
        (self.directory / "store").mkdir()
        (self.directory / "compiler").write_text(COMPILER)
        (self.directory / "compiler").chmod(0o755)

    def launch(self, *arguments: str, stamp: str = "one") -> subprocess.CompletedProcess:
        return run("launch", str(self.directory / "store"), str(self.directory / "compiler"), *arguments,
                   LLVM_TOOLCHAIN_STAMP=stamp)

    def command(self, source: str = "source.c", flag: str = "-O2") -> tuple:
        return (flag, "-MD", "-MF", str(self.directory / "out.d"), "-o", str(self.directory / "out.o"), "-c", source)

    def runs(self) -> int:
        return len((self.directory / "runs").read_text().splitlines())

    def test_same_command_compiles_once_and_gets_its_object_and_dependencies_back(self):
        self.assertEqual(self.launch(*self.command()).returncode, 0)
        for name in ("out.o", "out.d"):
            (self.directory / name).unlink()
        result = self.launch(*self.command())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.runs(), 1)
        self.assertEqual((self.directory / "out.o").read_text(), "object of source.c\n")
        self.assertEqual((self.directory / "out.d").read_text(), "dependencies of source.c\n")

    def test_another_flag_source_or_stamp_compiles_again(self):
        self.launch(*self.command())
        for count, arguments, stamp in ((2, self.command(flag="-O1"), "one"), (3, self.command("other.c"), "one"),
                                        (4, self.command(), "two")):
            with self.subTest(arguments=arguments, stamp=stamp):
                self.assertEqual(self.launch(*arguments, stamp=stamp).returncode, 0)
                self.assertEqual(self.runs(), count)
        self.assertEqual((self.directory / "out.o").read_text(), "object of source.c\n")

    def test_failed_compile_fails_and_keeps_nothing(self):
        self.assertEqual(self.launch(*self.command("broken.c")).returncode, 3)
        self.assertEqual(os.listdir(self.directory / "store"), [])
        self.assertEqual(self.launch(*self.command("broken.c")).returncode, 3)
        self.assertEqual(self.runs(), 2)


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        # BaseLoader keeps "on" and the slices as text.
        self.workflow = yaml.load(WORKFLOW.read_text(), Loader=yaml.BaseLoader)

    def test_one_job_compiles_each_slice_of_the_count_it_passes(self):
        job = self.workflow["jobs"]["compile"]
        commands = "".join(step.get("run", "") for step in job["steps"])
        count = int(re.search(r"llvm_toolchain\.sh compile '\$OUT' '\$SLICE' ([0-9]+)", commands)[1])
        self.assertEqual(job["strategy"]["matrix"]["slice"], [str(number) for number in range(count)])
        self.assertIn(f"of {count})", job["name"])

    def test_every_slice_waits_for_the_table_generators_and_starts_with_their_objects(self):
        generators, job = self.workflow["jobs"]["generators"], self.workflow["jobs"]["compile"]
        self.assertEqual(job["needs"], "generators")
        self.assertIn("llvm_toolchain.sh generators '$OUT'", "".join(step.get("run", "") for step in generators["steps"]))
        upload = generators["steps"][-1]["with"]
        steps = job["steps"]
        download = next(number for number, step in enumerate(steps) if "download-artifact" in step.get("uses", ""))
        compile_ = next(number for number, step in enumerate(steps) if "llvm_toolchain.sh compile" in step.get("run", ""))
        self.assertLess(download, compile_)
        self.assertEqual(steps[download]["with"]["name"], upload["name"])
        self.assertEqual(steps[download]["with"]["path"], upload["path"].rstrip("/"))
        self.assertEqual(upload["path"], steps[-1]["with"]["path"])

    def test_packing_waits_for_every_slice_and_reads_their_objects(self):
        package = self.workflow["jobs"]["package"]
        self.assertEqual(package["needs"], "compile")
        upload = self.workflow["jobs"]["compile"]["steps"][-1]["with"]
        download = next(step["with"] for step in package["steps"] if "download-artifact" in step.get("uses", ""))
        self.assertEqual(upload["name"], "llvm-objects-${{ matrix.slice }}")
        self.assertEqual((download["pattern"], download["merge-multiple"]), ("llvm-objects-*", "true"))
        self.assertEqual(upload["path"].rstrip("/"), download["path"])
        commands = "".join(step.get("run", "") for step in package["steps"])
        self.assertIn('LLVM_TOOLCHAIN_OBJECTS="$OUT/objects"', commands)
        self.assertEqual(download["path"], "${{ env.OUT }}/objects")

    def test_workflow_builds_in_the_documented_image(self):
        self.assertIn(self.workflow["env"]["IMAGE"], DOCUMENT.read_text())


if __name__ == "__main__":
    unittest.main()
