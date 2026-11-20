"""The minimal LLVM toolchain recipe: what it builds, what its check refuses and how compiling is shared."""

import hashlib
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
# Stands in for cmake: writes $COMMANDS as the compile commands of the build directory that -B names.
CMAKE = """#!/bin/sh
echo configuring
while [ $# -gt 1 ]; do
  case "$1" in -B) build=$2 ;; esac
  shift
done
mkdir -p "$build"
printf '%s' "$COMMANDS" > "$build/compile_commands.json"
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
                          ("generators",), ("generators", "a", "b"), ("fingerprint",), ("fingerprint", "a", "b")):
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


@unittest.skipUnless(sys.platform == "linux" and os.uname().machine in ("x86_64", "aarch64"), "the recipe is for Linux x86-64 and AArch64")
class FingerprintTests(unittest.TestCase):
    def setUp(self):
        self.directory = Path(self.enterContext(tempfile.TemporaryDirectory()))
        (self.directory / "bin").mkdir()
        for name, text in (("cmake", CMAKE), ("compiler", '#!/bin/sh\necho "$COMPILER"\n')):
            (self.directory / "bin" / name).write_text(text)
            (self.directory / "bin" / name).chmod(0o755)
        self.outputs = 0

    def archive(self, name: str) -> Path:
        """A source archive with the four directories the recipe extracts, and `name` in one of them."""
        source = self.directory / name / "llvm-project-0.0.0.src"
        for part in ("llvm", "clang", "cmake", "third-party"):
            (source / part).mkdir(parents=True)
            (source / part / "CMakeLists.txt").write_text(name)
        subprocess.run(["tar", "-cJf", "source.tar.xz", source.name], cwd=source.parent, check=True)
        return source.parent / "source.tar.xz"

    def fingerprint(self, commands: str = "[one]", compiler: str = "cc 14.2", source: str = "sources") -> subprocess.CompletedProcess:
        archive = self.directory / source / "source.tar.xz"
        if not archive.exists():
            self.archive(source)
        self.outputs += 1
        tool = str(self.directory / "bin" / "compiler")
        return run("fingerprint", str(self.directory / f"out{self.outputs}"), COMMANDS=commands, COMPILER=compiler, CC=tool, CXX=tool,
                   PATH=f"{self.directory / 'bin'}:{os.environ['PATH']}", LLVM_TOOLCHAIN_VERSION="0.0.0",
                   LLVM_TOOLCHAIN_SOURCE=str(archive), LLVM_TOOLCHAIN_SHA256=hashlib.sha256(archive.read_bytes()).hexdigest())

    def test_same_inputs_give_one_hash_and_nothing_else_is_printed(self):
        first, second = self.fingerprint(), self.fingerprint()
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertRegex(first.stdout, r"\A[0-9a-f]{64}\n\Z")
        self.assertEqual(first.stdout, second.stdout)
        self.assertIn("configuring", first.stderr)

    def test_another_command_compiler_or_source_gives_another_hash(self):
        hashes = {self.fingerprint().stdout, self.fingerprint(commands="[two]").stdout,
                  self.fingerprint(compiler="cc 15.1").stdout, self.fingerprint(source="other").stdout}
        self.assertEqual(len(hashes), 4)
        self.assertNotIn("", hashes)

    def test_no_compile_commands_fail(self):
        result = self.fingerprint(commands="")
        self.assertEqual((result.returncode, result.stdout), (1, ""))
        self.assertIn("no compile_commands.json", result.stderr)


class NoticesTests(unittest.TestCase):
    def test_third_party_terms_are_files_and_the_comments_before_the_code(self):
        paths = setting("THIRD_PARTY").split()
        self.assertEqual(len(paths), 8)
        with tempfile.TemporaryDirectory() as directory:
            for path in paths:
                file = Path(directory) / path
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_text(f"terms of {path}\n" if not path.endswith(".cpp") else
                                f"// {path}\n\n/*\nterms of {path}\nwithout a marker\n*/\n\n  /* one line */\n"
                                "#include <x>\n// a later comment\nint code;\n")
            result = run("notices", directory)
            self.assertEqual((result.returncode, result.stderr), (0, ""))
            sections = result.stdout.split("==== ")[1:]
            self.assertEqual([section.split(" ====\n")[0] for section in sections], paths)
            for path, section in zip(paths, sections, strict=True):
                self.assertIn(f"terms of {path}\n", section)
                if path.endswith(".cpp"):
                    self.assertTrue(section.endswith("without a marker\n*/\n\n  /* one line */\n\n"), section)
            # A release that drops or moves one of them fails the build.
            (Path(directory) / paths[-1]).write_text("")
            result = run("notices", directory)
            self.assertEqual(result.returncode, 1)
            self.assertIn(f"no third-party notice in {paths[-1]}", result.stderr)


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
        self.assertEqual(package["needs"], ["generators", "compile"])
        upload = self.workflow["jobs"]["compile"]["steps"][-1]["with"]
        download = next(step["with"] for step in package["steps"] if "download-artifact" in step.get("uses", ""))
        self.assertEqual(upload["name"], "llvm-objects-${{ matrix.slice }}")
        self.assertEqual((download["pattern"], download["merge-multiple"]), ("llvm-objects-*", "true"))
        self.assertEqual(upload["path"].rstrip("/"), download["path"])
        commands = "".join(step.get("run", "") for step in package["steps"])
        self.assertIn('LLVM_TOOLCHAIN_OBJECTS="$OUT/objects"', commands)
        self.assertEqual(download["path"], "${{ env.OUT }}/objects")

    def test_cached_objects_replace_the_compiling(self):
        jobs = self.workflow["jobs"]
        generators, package = jobs["generators"], jobs["package"]
        steps = generators["steps"]
        hashing = next(step for step in steps if "llvm_toolchain.sh fingerprint '$OUT'" in step.get("run", ""))
        lookup = next(step for step in steps if step.get("uses", "").startswith("actions/cache/restore@"))
        self.assertEqual(generators["outputs"], {"key": f"${{{{ steps.{hashing['id']}.outputs.key }}}}",
                                                 "cached": f"${{{{ steps.{lookup['id']}.outputs.cache-hit }}}}"})
        self.assertEqual(lookup["with"], {"path": "${{ env.OUT }}/objects", "key": generators["outputs"]["key"], "lookup-only": "true"})
        # With the objects cached nothing compiles, and the jobs after the skipped slices still run.
        after = steps[steps.index(lookup) + 1:]
        self.assertEqual(len(after), 2)
        for step in after:
            self.assertEqual(step["if"], f"steps.{lookup['id']}.outputs.cache-hit != 'true'")
        self.assertEqual(jobs["compile"]["if"], "needs.generators.outputs.cached != 'true'")
        self.assertIn("needs.compile.result == 'skipped'", package["if"])
        self.assertIn("needs.package.result == 'success'", jobs["bootstrap"]["if"])

        # package reads the cache or the jobs' objects, and writes the cache after a build that compiled.
        names = [step.get("uses", "").split("@")[0] for step in package["steps"]]
        build = next(number for number, step in enumerate(package["steps"]) if "llvm_toolchain.sh build" in step.get("run", ""))
        restore, download, save = (names.index(name) for name in ("actions/cache/restore", "actions/download-artifact", "actions/cache/save"))
        self.assertLess(max(restore, download), build)
        self.assertLess(build, save)
        restore, download, save = (package["steps"][number] for number in (restore, download, save))
        self.assertEqual(restore["if"], "needs.generators.outputs.cached == 'true'")
        self.assertEqual(restore["with"], {"path": lookup["with"]["path"], "key": "${{ needs.generators.outputs.key }}",
                                           "fail-on-cache-miss": "true"})
        self.assertEqual(save["with"], {"path": download["with"]["path"], "key": restore["with"]["key"]})
        for step in (download, save):
            self.assertEqual(step["if"], "needs.generators.outputs.cached != 'true'")

    def test_workflow_builds_in_the_documented_image(self):
        self.assertIn(self.workflow["env"]["IMAGE"], DOCUMENT.read_text())


if __name__ == "__main__":
    unittest.main()
