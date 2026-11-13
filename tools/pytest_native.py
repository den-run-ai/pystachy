"""Collect a bounded pytest dialect and run generated typed Python test programs.

The collector is hosted Python; the generated tests and fixtures run under Pystachy.
The CLI compares original-source, real-pytest outcomes by default as an independent oracle.
"""
from __future__ import annotations

import argparse
import ast
import configparser
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
import fcntl
import hashlib
import json
import keyword
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import textwrap
import time
import tomllib

from pytest_native_codegen import (CollectionError, adapt_helper, generate, generate_conftest, match_expression,
                                   original_line, warning_filter)

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parent
CONFIGS = ("pytest.ini", ".pytest.ini", "pytest.toml", ".pytest.toml")
# Configuration that changes no test's collection or outcome: reporting, logging and paths
# the runner is given on its command line.
IGNORED_OPTIONS = {"minversion", "testpaths", "console_output_style", "cache_dir", "norecursedirs",
                   "required_plugins", "tmp_path_retention_count", "tmp_path_retention_policy",
                   "verbosity_assertions", "verbosity_test_cases", "truncation_limit_lines",
                   "truncation_limit_chars", "faulthandler_timeout", "strict_config", "strict_xfail"}
COLLECTION_DEFAULTS = {"python_files": ["test_*.py", "*_test.py"], "python_classes": ["Test"],
                       "python_functions": ["test"]}
# Command-line options in addopts that change no outcome, with whether a value follows.
QUIET_OPTIONS = {"-q": False, "--quiet": False, "-v": False, "-vv": False, "-vvv": False, "--verbose": False,
                 "-s": False, "-l": False, "--showlocals": False, "--no-header": False, "--no-summary": False,
                 "--strict-config": False, "--disable-warnings": False, "--tb": True, "--color": True,
                 "--durations": True, "--durations-min": True, "-r": True, "--code-highlight": True}
EXCLUDED_DIRS = {"build", "dist", "venv", ".venv", "__pycache__", "node_modules"}
# Tests and imports one suite may leave out because the native compiler rejects them
# (run_suite): each costs a build. Those the collector rejects cost a module's collection.
LEFT_OUT_LIMIT = 25
UNCOLLECTED_LIMIT = 500


@dataclass
class Result:
    path: str
    cases: list[str] = field(default_factory=list)
    events: list[dict] = field(default_factory=list)
    state: str = "collection-error"
    exit_code: int | None = None
    build_seconds: float = 0.0
    run_seconds: float = 0.0
    stdout: str = ""
    stderr: str = ""
    error: str = ""
    # Comparison assertions report their operands unless the native build of that
    # instrumented code failed; the suite then ran its plain assertions (first module).
    assertion_operands: bool = True
    operand_build_error: str = ""
    # conftest.py hooks the program left out, as "path: name" (first module): the
    # comparison with pytest answers for them.
    hooks: list[str] = field(default_factory=list)
    # Cases the native program does not contain, each with the compiler's reason: the
    # compiler rejected their test, which the runner then left out (leave_out()). They
    # are not in cases, and a run that has any never succeeds.
    uncompiled: dict[str, str] = field(default_factory=dict)
    # Module-level statements that bind names (imports, assignments) which the collector
    # or the compiler rejected and the runner left out, as "path:line: statement", each
    # with the reason; a conftest.py's are on the first module. The tests that use the
    # names are in uncompiled or uncollected; a run that has any never succeeds.
    unbound: dict[str, str] = field(default_factory=dict)
    # Tests the collector rejected and the runner left out, as node IDs without a
    # parametrization (path::test, path::Class::test, or path::Class for a class left
    # out whole), each with the reason. Their cases are not in cases either.
    uncollected: dict[str, str] = field(default_factory=dict)
    # Fixtures the collector rejected and the runner left out, as path::name, each with
    # the reason; a conftest.py's are on the first module. The tests that request one
    # are in uncollected.
    unavailable: dict[str, str] = field(default_factory=dict)


@dataclass
class Settings:
    """pytest's configuration under --root, as far as the runner honors it (configuration())."""
    source: str = ""
    # xfail marks without strict= fail the run when their test passes.
    xfail_strict: bool = False
    # Directories pytest adds to sys.path.
    pythonpath: list[Path] = field(default_factory=list)
    # (action, message regex, category) for warnings.filterwarnings, in the order given.
    filters: list[tuple[str, str, str]] = field(default_factory=list)
    # The same options for the isolated pytest that the comparison runs.
    ini: list[str] = field(default_factory=list)
    # The run is compared with pytest's: conftest.py hooks the program does not run are
    # accepted only then (pytest_native_codegen.VERIFIED_HOOKS).
    verified: bool = False
    # pytest's -k and -m expressions: the cases to run among those collected.
    keyword: str = ""
    markexpr: str = ""


def _warning_filter(text: str, source: Path) -> tuple[str, str, str]:
    """A filterwarnings entry (action:message:category) the compiled program can apply."""
    parsed = warning_filter(text)
    if parsed is None:
        raise CollectionError(f"pytest configuration is not supported: filterwarnings {text!r} in {source} "
                              "(an action, a message and a built-in warning class are)")
    return parsed


def configuration(paths: list[Path], root: Path) -> Settings:
    """Read the configuration pytest would use for these tests, without ignoring any of it.

    pytest takes the first configuration file from the tests' common directory upward;
    the search here stops at --root, which the comparison's pytest is rooted at. Options
    that only shape pytest's report are accepted; those that change collection or
    outcomes are honored (xfail_strict, pythonpath, filterwarnings of built-in classes,
    registered markers under --strict-markers) or rejected by name.
    """
    settings = Settings()
    if not paths:
        return settings
    directory = Path(os.path.commonpath([str(path.parent) for path in paths]))
    options = None
    while options is None and directory.is_relative_to(root):
        for name in (*CONFIGS, "pyproject.toml", "tox.ini", "setup.cfg"):
            source = directory / name
            if not source.is_file():
                continue
            try:
                if name.endswith(".toml"):
                    data = tomllib.loads(source.read_text())
                    table = data.get("tool", {}).get("pytest") if name == "pyproject.toml" else data.get("pytest")
                    if table is None:
                        continue
                    options = dict(table.get("ini_options", {})) if name == "pyproject.toml" else dict(table)
                    options.update({key: value for key, value in table.items() if key != "ini_options"}
                                   if name == "pyproject.toml" else {})
                else:
                    parser = configparser.ConfigParser(interpolation=None)
                    parser.read_string(source.read_text())
                    section = "tool:pytest" if name == "setup.cfg" else "pytest"
                    if not parser.has_section(section):
                        if name in CONFIGS:
                            options = {}
                            break
                        continue
                    options = dict(parser.items(section))
            except (OSError, UnicodeError, ValueError, configparser.Error) as error:
                raise CollectionError(f"cannot read pytest configuration {source}: {error}") from None
            break
        if options is None:
            if directory == root:
                break
            directory = directory.parent
    if options is None:
        return settings
    settings.source = str(source)

    def lines(value) -> list[str]:
        items = value if isinstance(value, list) else str(value).splitlines()
        return [str(item).strip() for item in items if str(item).strip()]

    def words(value) -> list[str]:
        return [str(item) for item in value] if isinstance(value, list) else shlex.split(str(value))

    def flag(value) -> bool:
        return value if isinstance(value, bool) else str(value).strip().lower() in {"1", "true", "yes", "on"}

    markers: list[str] = []
    strict_markers = False
    for key, value in options.items():
        if key in IGNORED_OPTIONS or key.startswith(("log_", "junit_")):
            continue
        if key == "xfail_strict":
            settings.xfail_strict = flag(value)
        elif key == "markers":
            markers = lines(value)
        elif key == "strict_markers":
            strict_markers = strict_markers or flag(value)
        elif key == "pythonpath":
            settings.pythonpath = [(directory / item).resolve() for item in words(value)]
        elif key == "filterwarnings":
            settings.filters += [_warning_filter(item, source) for item in lines(value)]
        elif key in COLLECTION_DEFAULTS:
            if sorted(words(value)) != sorted(COLLECTION_DEFAULTS[key]):
                raise CollectionError(f"pytest configuration is not supported: {key} in {source} "
                                      "(the runner collects pytest's default names)")
        elif key == "addopts":
            arguments = words(value)
            index = 0
            while index < len(arguments):
                option, _, attached = arguments[index].partition("=")
                index += 1
                if option in {"--strict-markers", "--strict"}:
                    strict_markers = True
                elif option == "-W" or (option.startswith("-W") and len(option) > 2 and not attached):
                    text = arguments[index] if option == "-W" and index < len(arguments) else option[2:]
                    index += option == "-W"
                    settings.filters.append(_warning_filter(text, source))
                elif option in QUIET_OPTIONS or (option.startswith("-r") and option[2:].isalpha()):
                    if QUIET_OPTIONS.get(option) and not attached and option != "-r":
                        index += 1
                    elif option == "-r" and not attached:
                        index += 1
                elif option in {"-k", "-m"} and not attached and index < len(arguments):
                    text = arguments[index]
                    index += 1
                    if option == "-k":
                        settings.keyword = text
                    else:
                        settings.markexpr = text
                elif option == "--import-mode" and (attached or (arguments[index:index + 1] or [""])[0]) == "prepend":
                    index += not attached
                else:
                    raise CollectionError(f"pytest configuration is not supported: addopts {arguments[index - 1]!r} "
                                          f"in {source}")
        else:
            raise CollectionError(f"pytest configuration is not supported: {key} in {source}")
    if settings.xfail_strict:
        settings.ini.append("xfail_strict = true")
    if markers:
        settings.ini += ["markers =", *("    " + marker for marker in markers)]
    if strict_markers:
        settings.ini.append("addopts = --strict-markers")
    if settings.pythonpath:
        settings.ini.append("pythonpath = " + " ".join(shlex.quote(str(item)) for item in settings.pythonpath))
    if settings.filters:
        settings.ini += ["filterwarnings =", *(f"    {action}:{message}:{category}"
                                               for action, message, category in settings.filters)]
    return settings


def parse_targets(arguments: list[str], root: Path, configured: bool = False) -> dict[Path, list[str]] | None:
    """Node IDs (path::name or path::name[id]) by module, in first-seen order, or None.

    As in pytest's arguments, cases run in the order given and a repeated node ID runs
    once. Paths cannot be mixed with node IDs, and one module's node IDs must be adjacent.
    """
    if not any("::" in str(argument) for argument in arguments):
        return None
    selections: dict[Path, list[str]] = {}
    previous = None
    for argument in map(str, arguments):
        location, _, selector = argument.partition("::")
        if not selector:
            raise CollectionError(f"give node IDs (path::name) for every argument, not a path: {argument}")
        path = Path(location).resolve()
        if path in selections and path != previous:
            raise CollectionError(f"node IDs of one module must be given together: {argument}")
        names = selections.setdefault(path, [])
        if selector not in names:
            names.append(selector)
        previous = path
    for path in selections:
        if path.suffix != ".py":
            raise CollectionError(f"expected a Python test module: {path}")
        discover([path], root, configured)
    return selections


def outcome_counts(results: list[Result]) -> dict[str, int]:
    """Count cases as pytest's summary does: setup or call outcome, plus teardown errors."""
    counts: dict[str, int] = {}
    for result in results:
        phases: dict[str, dict[str, str]] = {}
        for event in result.events:
            if event["phase"] == "subtest":
                # pytest counts a subtest that failed as a failure, and the others apart.
                name = {"failed": "failed", "passed": "subtests passed"}.get(event["outcome"],
                                                                             "subtests " + event["outcome"])
                counts[name] = counts.get(name, 0) + 1
                continue
            phases.setdefault(event["nodeid"], {})[event["phase"]] = event["outcome"]
        for case in result.cases:
            seen = phases.get(case, {})
            setup = seen.get("setup", "")
            outcome = seen.get("call", "") if setup == "passed" else setup
            outcome = "error" if outcome == "error" or (setup != "passed" and outcome == "failed") else outcome
            if outcome:
                counts[outcome] = counts.get(outcome, 0) + 1
            if seen.get("teardown") in {"failed", "error"}:
                counts["error"] = counts.get("error", 0) + 1
    return counts


def compiler_command(text: str) -> list[str]:
    """Anchor explicit executable and Python script paths before changing cwd.

    PATH commands, module names, options and compiler arguments retain their
    meaning. Preserve symlinks, notably virtual-environment Python executables.
    """
    command = shlex.split(text)
    if not command:
        return command

    def anchor(index: int) -> None:
        path = Path(command[index])
        # Missing paths must still fail at the caller's location, not resolve
        # to an unrelated file after the runner changes to the suite root.
        if not path.is_absolute():
            command[index] = str(path.absolute())

    if os.sep in command[0]:
        anchor(0)
    if not re.fullmatch(r"(?:python|pypy)(?:\d+(?:\.\d+)*)?(?:\.exe)?", Path(command[0]).name):
        return command
    index = 1
    while index < len(command):
        part = command[index]
        if part == "--":
            index += 1
            break
        if part in {"-c", "-m", "-"}:
            return command
        if part in {"-W", "-X", "--check-hash-based-pycs"}:
            index += 2
        elif part.startswith(("-W", "-X", "--check-hash-based-pycs=")):
            index += 1
        elif part.startswith("-"):
            # Unknown options may consume the next token; never guess it is a script.
            if not set(part[1:]) <= set("bBdEiIOPqRsSuvx"):
                return command
            index += 1
        else:
            break
    if index < len(command) and command[index] != "-":
        anchor(index)
    return command


def discover(paths: list[Path], root: Path, configured: bool = False) -> list[Path]:
    """Select test modules without importing them.

    Tests may sit in packages and in several directories; layout() works out how
    pytest imports each and which conftest.py files apply to it. A caller that has
    not read pytest's configuration (configuration()) must not run tests under one:
    it is rejected here unless configured says the caller applies it.
    """
    files: set[Path] = set()
    for path in paths:
        path = path.resolve()
        if not path.exists():
            raise CollectionError(f"path does not exist: {path}")
        if not path.is_relative_to(root):
            raise CollectionError(f"path is outside --root {root}: {path}")
        if path.is_file():
            if path.suffix != ".py" or path.name == "conftest.py":
                raise CollectionError(f"expected a Python test module: {path}")
            files.add(path)
        else:
            for directory, dirs, names in os.walk(path):
                dirs[:] = sorted(d for d in dirs if not d.startswith(".") and d not in EXCLUDED_DIRS)
                base = Path(directory)
                for name in sorted(names):
                    if name.endswith(".py") and (name.startswith("test_") or name.endswith("_test.py")):
                        files.add(base / name)
    checked: set[Path] = set()
    for path in sorted(files) if not configured else []:
        for parent in path.parents:
            if not parent.is_relative_to(root) or parent in checked:
                break
            checked.add(parent)
            for name in CONFIGS:
                if (parent / name).exists():
                    raise CollectionError(f"pytest configuration is not supported: {parent / name}")
            for name, marker in (("pyproject.toml", "[tool.pytest"), ("tox.ini", "[pytest]"),
                                 ("setup.cfg", "[tool:pytest]")):
                config = parent / name
                if config.exists() and marker in config.read_text():
                    raise CollectionError(f"pytest configuration is not supported: {config}")
    return sorted(files)


@dataclass
class Layout:
    """How pytest imports the selected tests, which the generated program's files mirror.

    pytest imports a module of a package (a directory with __init__.py) under its
    dotted name from the directory above the outermost package, and any other module
    under its file's name from its own directory. A conftest.py applies to the tests
    of its directory and those below.
    """
    # Every generated file's module name: the tests, then the conftest.py files.
    modules: dict[Path, str]
    # conftest.py files that apply to a selected test, an outer directory's first.
    conftests: list[Path]
    # The directories pytest puts on sys.path for these tests, in first-use order.
    bases: list[Path]
    # The outermost package directories the tests are in.
    packages: list[Path]
    # Packages and modules of the source tree that a test class's base class was read
    # from (resolver): the program imports adapted copies of them.
    sources: list[Path] = field(default_factory=list)

    def above(self, path: Path) -> list[Path]:
        """The conftest.py files whose fixtures a module of this directory can request."""
        return [conftest for conftest in self.conftests
                if path.parent.is_relative_to(conftest.parent) and conftest != path]


def import_root(path: Path, root: Path) -> Path:
    """The directory above a module's outermost package, or the module's own."""
    directory = path.parent
    while (directory / "__init__.py").is_file():
        if directory == root or not directory.is_relative_to(root):
            raise CollectionError(f"--root is inside a package of the tests: {directory / '__init__.py'}")
        directory = directory.parent
    return directory


def layout(paths: list[Path], root: Path) -> Layout:
    modules: dict[Path, str] = {}
    bases: list[Path] = []
    packages: list[Path] = []
    conftests: set[Path] = set()
    for path in paths:
        directory = path.parent
        while directory.is_relative_to(root):
            if (directory / "conftest.py").is_file():
                conftests.add(directory / "conftest.py")
            if directory == root:
                break
            directory = directory.parent
    ordered = sorted(conftests, key=lambda conftest: (len(conftest.parts), conftest))
    flat = [conftest for conftest in ordered if not (conftest.parent / "__init__.py").is_file()]
    taken: dict[str, Path] = {}
    for index, path in enumerate([*paths, *ordered]):
        base = import_root(path, root)
        parts = path.relative_to(base).with_suffix("").parts
        if len(parts) > 1:
            if any(not part.isidentifier() or keyword.iskeyword(part) for part in parts):
                raise CollectionError(f"a package module's path must be made of identifiers: {path}")
            name = ".".join(parts)
            if base / parts[0] not in packages:
                packages.append(base / parts[0])
        elif path.name == "conftest.py":
            # (Test modules may import the one conftest.py beside them by its name.)
            name = "conftest" if len(flat) == 1 else f"_pyn_conftest_file_{index}"
        else:
            stem = path.stem
            usable = (stem.isidentifier() and not keyword.iskeyword(stem) and not stem.startswith("_pyn_")
                      and stem not in ("pytest_native_support", "pytest_native_fixtures", "pytest_native_logging",
                                       "pytest_native_capture", "conftest"))
            name = stem if usable else f"_pyn_module_{index}"
        if name.split(".")[0] in taken and taken[name.split(".")[0]] != base / parts[0] or name in modules.values():
            # pytest imports one file under a name and fails on the next ("import file mismatch").
            raise CollectionError(f"two test modules would be imported as {name.split('.')[0]}: {path} and "
                                  f"{taken[name.split('.')[0]]}; make their directories packages")
        taken[name.split(".")[0]] = base / parts[0]
        modules[path] = name
        if base not in bases:
            bases.append(base)
    # pytest puts each test's directory first on sys.path as it imports that test, so a
    # name in two of them means a different module to each. A compiled program has one.
    importable: dict[str, Path] = {}
    for base in bases:
        names = {path.stem for path in base.glob("*.py") if path.stem != "conftest"}
        names |= {path.parent.name for path in base.glob("*/__init__.py")}
        for name in sorted(names):
            if name in importable and (importable[name] / name) not in packages:
                raise CollectionError(f"modules named {name} are importable from both {importable[name]} and "
                                      f"{base}, which pytest resolves by the importing test's directory; "
                                      "rename one or make the directories packages")
            importable.setdefault(name, base)
    return Layout(modules, ordered, bases, packages)


def resolver(tree: Layout, root: Path, roots: tuple[Path, ...] | list[Path] = ()):
    """Find the module beside the tests that `from module import name` reads (Generator.resolve).

    Only modules the generated program has adapted copies of are read: those of the
    tests' packages, those in the tests' own directories, and those of the source tree
    that the tests import from --root or a configured pythonpath directory (roots).
    The last are noted in tree.sources, for mirror() to copy.
    """
    roots = [directory for directory in dict.fromkeys([*roots, root]) if directory.is_relative_to(root)]

    def resolve(importer, level, module, name):
        importer = Path(importer)
        if level:
            directory = importer.parent
            for _ in range(level - 1):
                directory = directory.parent
            starts = [directory]
        else:
            starts = [*tree.bases, *(directory for directory in roots if directory not in tree.bases)]
        parts = module.split(".") if module else []
        for start in starts:
            target = start.joinpath(*parts)
            for candidate in ([target.with_suffix(".py")] if parts else []) + [target / "__init__.py"]:
                if not candidate.is_file() or not candidate.is_relative_to(root):
                    continue
                inside = any(candidate.is_relative_to(package) for package in [*tree.packages, *tree.sources])
                if not inside and candidate.parent not in tree.bases:
                    if level or start not in roots or not parts or not all(
                            part.isidentifier() and not keyword.iskeyword(part) for part in parts):
                        continue
                    # A module of the source tree: its outermost package, or the module itself.
                    top = start / parts[0]
                    source = top if (top / "__init__.py").is_file() else top.with_suffix(".py")
                    if not source.exists() or source.name in (
                            "pytest_native_support.py", "pytest_native_fixtures.py", "pytest_native_logging.py",
                            "pytest_native_capture.py"):
                        continue
                    tree.sources.append(source)
                base = import_root(candidate, root)
                dotted = ".".join(candidate.relative_to(base).with_suffix("").parts).removesuffix(".__init__")
                try:
                    return candidate.read_text(), candidate.relative_to(root).as_posix(), str(candidate), dotted
                except (OSError, UnicodeError):
                    return None
        return None

    return resolve


def mirror(work: Path, tree: Layout, generated: set[Path], root: Path,
           roots: tuple[Path, ...] | list[Path] = ()) -> dict[str, str]:
    """Write the modules beside the tests where the generated ones import them.

    A package's generated tests replace their files in a copy of the package, so the
    rest of it is copied too, each module adapted as adapt_helper() describes. Beside
    tests that are in no package, only modules that need adapting are written (the
    others are imported from their own directory). Returns {written file: source file}.
    """
    written: dict[str, str] = {}
    resolve = resolver(tree, root, roots)

    def adapted(path: Path, name: str, target: Path, always: bool) -> None:
        try:
            text = path.read_text()
        except (OSError, UnicodeError):
            return
        try:
            result = adapt_helper(text, path.relative_to(root).as_posix() if path.is_relative_to(root) else path.name,
                                  str(path), name, resolve)
        except (CollectionError, SyntaxError, RecursionError):
            result = text  # (as written: the compiler reports it if the tests import it)
        if always or result != text:
            write_changed(target, result)
            written[str(target)] = str(path)

    for module in tree.sources:
        if module.is_file():
            adapted(module, module.stem, work / module.name, True)
    for package in [*tree.packages, *(source for source in tree.sources if source.is_dir())]:
        expected = set()
        for directory, dirs, names in os.walk(package):
            dirs[:] = sorted(d for d in dirs if not d.startswith(".") and d not in EXCLUDED_DIRS)
            for name in sorted(names):
                path = Path(directory) / name
                if not name.endswith(".py"):
                    continue
                relative = path.relative_to(package.parent)
                expected.add(work / relative)
                if path not in generated:
                    adapted(path, ".".join(relative.with_suffix("").parts), work / relative, True)
        # A module removed from the package must not stay importable from an earlier run.
        for directory, _, names in os.walk(work / package.name):
            for name in names:
                if name.endswith(".py") and Path(directory) / name not in expected:
                    (Path(directory) / name).unlink()
    for directory in dict.fromkeys(path.parent for path in generated):
        if (directory / "__init__.py").is_file():
            continue
        for path in sorted(directory.glob("*.py")):
            if path not in generated and path.name != "conftest.py" and path.stem.isidentifier():
                adapted(path, path.stem, work / path.name, False)
    return written


def write_changed(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists() or path.read_text() != content:
        path.write_text(content)
        # CPython timestamp pycs can accept stale generated code when an edit
        # keeps the same byte count within one second. Invalidate only our
        # generated module's cache whenever its content changes.
        cache = path.parent / "__pycache__"
        if path.suffix == ".py" and cache.is_dir():
            for compiled in cache.iterdir():
                if compiled.name.startswith(path.stem + ".") and compiled.suffix == ".pyc":
                    compiled.unlink()


@contextmanager
def lock_work_directory(work: Path):
    """Keep generated sources and reports stable across a complete CLI run."""
    work.mkdir(parents=True, exist_ok=True)
    with (work / ".lock").open("a") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise CollectionError("work directory is in use; choose a different --work-dir") from None
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def read_report(path: Path, cases: list[str], returncode: int) -> list[dict]:
    """Missing, malformed or partial reports are execution errors, never passes."""
    try:
        records = [json.loads(line) for line in path.read_text().splitlines()]
    except (OSError, UnicodeError, ValueError) as error:
        raise ValueError(f"cannot read completed report: {error}") from error
    if not records or not isinstance(records[-1], dict) or records[-1] != {
        "complete": True, "exit_code": returncode,
    }:
        raise ValueError("missing completion record or exit status mismatch")
    events = records[:-1]
    expected = set(cases)
    if not expected:
        if events or returncode != 5:
            raise ValueError("empty module must complete with no events and exit 5")
        return []
    if len(expected) != len(cases):
        raise ValueError("duplicate collected test IDs")
    seen: dict[str, list[str]] = {}
    setups: dict[str, str] = {}
    for event in events:
        if not isinstance(event, dict) or set(event) != {"nodeid", "phase", "outcome", "detail"}:
            raise ValueError("malformed event")
        if not all(isinstance(value, str) for value in event.values()):
            raise ValueError("non-string event field")
        if event["nodeid"] not in expected or event["phase"] not in {"setup", "subtest", "call", "teardown"}:
            raise ValueError("unknown test or phase in report")
        if event["outcome"] not in {"passed", "failed", "error", "skipped", "xfailed", "xpassed"}:
            raise ValueError("unknown outcome in report")
        phases = seen.setdefault(event["nodeid"], [])
        if event["phase"] == "subtest":
            # A unittest case reports its subtests between its setup and its call.
            if phases != ["setup"] or event["outcome"] not in {"passed", "failed", "skipped"}:
                raise ValueError("subtest outside a test's call in report")
            continue
        if event["phase"] in phases or (phases and event["phase"] == "setup"):
            raise ValueError("duplicate or out-of-order phase in report")
        phases.append(event["phase"])
        if event["phase"] == "setup":
            if event["outcome"] in {"xpassed"}:
                raise ValueError("invalid setup outcome")
            setups[event["nodeid"]] = event["outcome"]
    if set(seen) != expected:
        raise ValueError("missing test results")
    for nodeid, phases in seen.items():
        needed = ["setup", "call", "teardown"] if setups.get(nodeid) == "passed" else ["setup", "teardown"]
        if phases != needed:
            raise ValueError(f"incomplete phases for {nodeid}")
    failed = any(event["outcome"] in {"failed", "error"} for event in events)
    if returncode not in (0, 1) or bool(returncode) != failed:
        raise ValueError("test outcomes disagree with exit status")
    return events


def environment(paths: list[Path]) -> dict[str, str]:
    env = os.environ.copy()
    for key in ("PYTHONPATH", "PYSTACHY_PATH"):
        previous = env.get(key, "")
        env[key] = os.pathsep.join([*(str(path) for path in paths), *([previous] if previous else [])])
    return env


def translate(text: str, sources: dict[str, tuple[str, object]]) -> str:
    """Name the test source line beside each generated line in compiler diagnostics.

    sources maps a generated file to its test file's name and GeneratedModule.
    """
    def original(match):
        name, module = sources[match.group(1)]
        line = original_line(module, int(match.group(2)))
        if line is None:
            return match.group(0)
        return f"{name}:{line} [generated {Path(match.group(1)).name}:{match.group(2)}]"
    if not sources:
        return text
    pattern = "(" + "|".join(re.escape(generated) for generated in sorted(sources, key=len, reverse=True)) + r"):(\d+)"
    return re.sub(pattern, original, text)


def blamed_lines(text: str, files: dict[str, int]) -> list[tuple[int, int]]:
    """The generated test-module lines a compiler diagnostic names, as (module, line).

    files maps each generated test module's file to its position. The lines come in the
    diagnostic's own order: where the error is, then the calls that had the compiler
    compile that code, innermost first.
    """
    if not files:
        return []
    pattern = "(" + "|".join(re.escape(file) for file in sorted(files, key=len, reverse=True)) + r"):(\d+)"
    return [(files[match.group(1)], int(match.group(2))) for match in re.finditer(pattern, text)]


def test_region(source: str, line: int, cases: list[str] | None) -> tuple[int, int, str] | None:
    """The test that a line of a test module belongs to, as (first line, last line, name), or None.

    A test is a module-level function or a method that some collected case names; a line
    of such a class outside its test methods (a hook, a helper method, a class
    attribute) belongs to all of the class's tests. Decorators belong to their test. The
    name is the test's node ID after its module: test, Class::test, or Class.

    cases is None for a module the collector rejects, which has no cases yet: a test
    is then what pytest collects by name, a function or method whose name starts with
    test, and the class is any class a line is in.
    """
    functions, methods, classes = set(), set(), set()
    for case in cases or ():
        parts = case.partition("[")[0].split("::")[1:]
        if len(parts) == 1:
            functions.add(parts[0])
        elif len(parts) > 1:
            classes.add(parts[0])
            methods.add(parts[-1])
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError, RecursionError):
        return None

    def span(node):
        return min([node.lineno, *(decorator.lineno for decorator in node.decorator_list)]), node.end_lineno

    def named(name, known):
        return name.startswith("test") if cases is None else name in known

    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        first, last = span(node)
        if not first <= line <= last:
            continue
        if not isinstance(node, ast.ClassDef):
            return (first, last, node.name) if named(node.name, functions) else None
        for member in node.body:
            if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)) and named(member.name, methods):
                inner = span(member)
                if inner[0] <= line <= inner[1]:
                    return inner[0], inner[1], f"{node.name}::{member.name}"
        return (first, last, node.name) if cases is None or node.name in classes else None
    return None


# Names pytest reads from a module by itself: leaving their statement out would change
# what the other tests do with nothing to show for it (a module's marks, its plugins).
PYTEST_READS = re.compile(r"pytest$|pytest_|pytestmark$|collect_ignore|__")


def binding_region(source: str, line: int, name: str | None = None) -> tuple[int, int, list[str], str] | None:
    """The module-level statement a line is in that only binds names, to leave out: an import or an assignment.

    Returns its lines, the names that go, and what replaces it: `pass`, or the statement
    without name where it is one of several that a from-import lists. A star import, a
    __future__ import and a statement that binds a name pytest reads by itself are none.
    """
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError, RecursionError):
        return None
    for node in tree.body:
        if not (isinstance(node, (ast.Import, ast.ImportFrom, ast.Assign, ast.AnnAssign))
                and node.lineno <= line <= node.end_lineno):
            continue
        replacement = "pass"
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if not all(isinstance(target, ast.Name) for target in targets):
                return None
            names = [target.id for target in targets]
        elif isinstance(node, ast.ImportFrom) and (node.module == "__future__" or node.names[0].name == "*"):
            return None
        else:
            going = [alias for alias in node.names if alias.name == name]
            names = [alias.asname or alias.name.split(".")[0] for alias in node.names]
            if isinstance(node, ast.ImportFrom) and going and len(going) < len(node.names):
                names = [alias.asname or alias.name for alias in going]
                node.names = [alias for alias in node.names if alias.name != name]
                replacement = ast.unparse(node)
        if any(PYTEST_READS.match(bound) for bound in names):
            return None
        return node.lineno, node.end_lineno, names, replacement
    return None


def fixture_region(source: str, line: int) -> tuple[int, int, str] | None:
    """The module-level fixture function a line is in, as (first line, last line, fixture name), or None.

    An autouse fixture is none to leave out: every test would run without what it sets up.
    """
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError, RecursionError):
        return None
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        first = min([node.lineno, *(decorator.lineno for decorator in node.decorator_list)])
        if not first <= line <= node.end_lineno:
            continue
        for decorator in node.decorator_list:
            target = decorator.func if isinstance(decorator, ast.Call) else decorator
            if (target.attr if isinstance(target, ast.Attribute) else getattr(target, "id", "")) != "fixture":
                continue
            keywords = {keyword.arg: keyword.value for keyword in getattr(decorator, "keywords", [])}
            if None in keywords or not (isinstance(keywords.get("autouse", ast.Constant(False)), ast.Constant)
                                        and keywords.get("autouse", ast.Constant(False)).value is False):
                return None
            name = keywords.get("name")
            if name is not None and not (isinstance(name, ast.Constant) and isinstance(name.value, str)):
                return None
            return first, node.end_lineno, name.value if name is not None else node.name
        return None
    return None


def derived_classes(source: str, names: set[str]) -> list[tuple[int, int, str]]:
    """The module-level classes that name one of names among their bases: (first line, last line, name)."""
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError, RecursionError):
        return []
    return [(min([node.lineno, *(decorator.lineno for decorator in node.decorator_list)]), node.end_lineno, node.name)
            for node in tree.body if isinstance(node, ast.ClassDef)
            and any(isinstance(part, ast.Name) and part.id in names for base in node.bases for part in ast.walk(base))]


def blanked(source: str, first: int, last: int, replacement: str = "pass") -> str:
    """source with lines first..last replaced by one statement, every other line where it was."""
    lines = source.split("\n")
    indent = lines[first - 1][:len(lines[first - 1]) - len(lines[first - 1].lstrip())]
    lines[first - 1:last] = [indent + replacement, *[""] * (last - first)]
    return "\n".join(lines)


def run_suite(paths: list[Path], root: Path, work: Path, mode: str, compiler: list[str],
              python: str, timeout: float, selections: dict[Path, list[str]] | None = None,
              settings: Settings | None = None) -> list[Result]:
    """Preflight every module, import all of them, then execute in one process.

    Per-file processes would lose pytest's shared imported-module state and could
    turn a failing suite green. Empty modules must be imported too. selections holds
    node-ID selectors by module (parse_targets). The conftest.py of the tests'
    directory supplies fixtures to every module.

    A test that the native compiler rejects is left out of the program, with every case
    it has, and the build is tried again: the other tests still run. Result.uncompiled
    names those cases. Nothing has run when a build fails, so no test runs twice. A test
    that the collector rejects is left out before any build (Result.uncollected). So
    are a fixture that is not autouse (Result.unavailable) and an import or an assignment
    of a module (Result.unbound) that either rejects, also of a conftest.py.
    """
    results = [Result(path=path.relative_to(root).as_posix()) for path in paths]
    if not results:
        return []
    settings = settings or Settings()
    try:
        tree = layout(paths, root)
    except CollectionError as error:
        for result in results:
            result.error = str(error)
        return results
    conftest_names = [conftest.relative_to(root).as_posix() for conftest in tree.conftests]
    aliases = {conftest: f"_pyn_conftest_{index}" for index, conftest in enumerate(tree.conftests)}
    texts: dict[Path, str] = {}
    # Names whose module-level statements were left out, with the reasons (unbind).
    unbound: dict[str, str] = {}
    # Per conftest.py or test module, the fixtures left out of it, with the reasons (unfixture).
    left_fixtures: dict[Path, dict[str, str]] = {}
    resolve = resolver(tree, root, settings.pythonpath)

    def unbind(path, filename, line, reason, result, name=None):
        """Leave out the import or the assignment at a line of a conftest.py or a test module: the names, or None.

        What uses a name it bound is rejected for the name in its turn, by the collector
        or the compiler: a test is then left out, and anything else fails as before.
        """
        found = binding_region(texts[path], line, name)
        if found is None:
            return None
        first, last, names, replacement = found
        statement = " ".join(entry.strip() for entry in texts[path].split("\n")[first - 1:last])
        statement = statement if len(statement) <= 100 else statement[:97] + "..."
        texts[path] = blanked(texts[path], first, last, replacement)
        result.unbound[f"{filename}:{first}: {statement}" + (f" ({', '.join(names)})" if replacement != "pass" else "")] = reason
        for bound in names:
            unbound[bound] = reason
        return names

    def unfixture(path, filename, line, reason, result):
        """Leave out the fixture a line of a conftest.py or a test module is in; False if it is in none.

        The fixture's lines are blanked, and its name is kept for the modules that could
        request it (the generator's unavailable): a test that does is rejected, and so
        left out in its turn, also where a wider conftest.py or pytest itself has a
        fixture of that name, which the test would otherwise silently get.
        """
        region = fixture_region(texts[path], line)
        if region is None:
            return False
        texts[path] = blanked(texts[path], region[0], region[1])
        left_fixtures.setdefault(path, {})[region[2]] = reason
        result.unavailable[f"{filename}::{region[2]}"] = reason
        return True

    def uncollect(path, filename, message, result, tests=True):
        """Leave out what a collection error of a test module or a conftest.py names; False if nothing can be.

        The collector rejects a module at the first line it cannot preserve. Where that
        line is in a test (a function, a method, or a class outside its test methods),
        the test is blanked in the text the module is generated from, as leave_out()
        does for a test the compiler rejects. Likewise a statement that only binds names
        (unbind) and a fixture that is not autouse (unfixture), also of a conftest.py.
        A line of anything else rejects the module as before.
        """
        match = re.match(re.escape(filename) + r":(\d+): ", message)
        if match is None:
            return False
        line = int(match.group(1))

        def orphans(names):
            # The classes that derive from what was left out go with it: their bases are gone.
            names = set(names)
            while tests:
                found = derived_classes(texts[path], names)
                if not found:
                    return
                first, last, name = found[0]
                texts[path] = blanked(texts[path], first, last)
                result.uncollected[f"{filename}::{name}"] = "its base class was left out: " + message
                names.add(name)

        region = test_region(texts[path], line, None) if tests else None
        if region is not None:
            texts[path] = blanked(texts[path], region[0], region[1])
            result.uncollected[f"{filename}::{region[2]}"] = message
            if "::" not in region[2] and not region[2].startswith("test"):
                orphans([region[2]])
            return True
        # (One name of several: "unsupported unittest import: mock".)
        lacking = re.search(r"unsupported (?:pytest|unittest) import: (\w+)$", message)
        names = unbind(path, filename, line, message, result, lacking.group(1) if lacking else None)
        if names is not None:
            orphans(names)
            return True
        return unfixture(path, filename, line, message, result)

    def build(operands: bool):
        """Every module's generated source, or the collection errors on results."""
        exported: dict[Path, dict] = {}
        modules = []

        def context(path):
            # The conftest.py files above a module: their fixtures and how it imports them.
            above = tree.above(path)
            return ([exported[conftest] for conftest in above],
                    [(tree.modules[conftest], aliases[conftest]) for conftest in above],
                    (path.parent / "__init__.py").is_file())

        def gone(path):
            # The fixtures left out of the conftest.py files above a module and of the module
            # itself; a nearer conftest.py that defines one of the name provides it again.
            names: dict[str, str] = {}
            for conftest in tree.above(path):
                names = {name: reason for name, reason in names.items() if name not in exported[conftest]}
                names.update(left_fixtures.get(conftest, {}))
            names.update(left_fixtures.get(path, {}))
            return names

        for conftest, name in zip(tree.conftests, conftest_names):
            try:
                if conftest not in texts:
                    texts[conftest] = conftest.read_text()
                shared, imports, package = context(conftest)
                for attempt in range(UNCOLLECTED_LIMIT + 1):
                    try:
                        module, exported[conftest] = generate_conftest(
                            texts[conftest], name, operands, str(conftest), tree.modules[conftest], shared, imports,
                            package, aliases[conftest], resolve, settings.xfail_strict, settings.verified,
                            gone(conftest))
                        break
                    except CollectionError as error:
                        if attempt == UNCOLLECTED_LIMIT or not uncollect(conftest, name, str(error), results[0], False):
                            raise
                modules.append(module)
            except (CollectionError, OSError, UnicodeError, SyntaxError) as error:
                for result in results:
                    result.error = str(error)
                return None

        def one(index, session_end):
            path = paths[index]
            shared, imports, package = context(path)
            return generate(texts[path], results[index].path, operands, selections.get(path) if selections else None,
                            shared, session_end, str(path), tree.modules[path], imports, package, resolve,
                            settings.xfail_strict, settings.verified, settings.keyword, settings.markexpr,
                            gone(path))

        generated = []
        for index, (path, result) in enumerate(zip(paths, results)):
            try:
                if path not in texts:
                    texts[path] = path.read_text()
                for _ in range(UNCOLLECTED_LIMIT):
                    try:
                        module = one(index, False)
                        break
                    except CollectionError as error:
                        if not uncollect(path, result.path, str(error), result):
                            raise
                else:
                    module = one(index, False)
                generated.append(module)
                result.cases = module.cases
                result.state = "collected"
            except (CollectionError, OSError, UnicodeError, SyntaxError) as error:
                result.error = str(error)
        if any(result.state == "collection-error" for result in results):
            for result in results:
                if result.state == "collected":
                    result.state = "collection-error"
                    result.error = "suite aborted before execution because another module failed collection"
            return None
        # The last module with cases ends the session scope in its last case.
        last = max((index for index, module in enumerate(generated) if module.cases), default=None)
        if last is not None:
            generated[last] = one(last, True)
        return modules + generated

    instrumented = build(True)
    if instrumented is None:
        return results
    results[0].hooks = [f"{name}: {hook}" for name, module in zip(conftest_names, instrumented)
                        for hook in module.hooks]
    identity = "\n".join(result.path for result in results)
    suite_work = work / hashlib.sha256(identity.encode()).hexdigest()[:16]
    names = [tree.modules[path] for path in paths]
    # Generated files in the order build() returns their modules: conftest.py files first.
    generated_names = [tree.modules[conftest] for conftest in tree.conftests] + names
    generated_files = [suite_work.joinpath(*name.split(".")).with_suffix(".py") for name in generated_names]
    if suite_work.is_dir():
        # Earlier runs wrote other modules there, which a test's own import would find first.
        current = {str(file) for file in generated_files}
        for stale in [suite_work / "suite.py", suite_work / "suite", suite_work / "pytest_native_fixtures.py",
                      suite_work / "pytest_native_logging.py", suite_work / "pytest_native_capture.py",
                      *suite_work.glob("*.py")]:
            if str(stale) not in current and stale.name not in ("_pyn_suite.py", "pytest_native_support.py"):
                stale.unlink(missing_ok=True)
    imports = [f"import {tree.modules[conftest]}" for conftest in tree.conftests]
    calls = []
    reports = []
    for index, name in enumerate(names):
        report = suite_work / f"events-{index}.jsonl"
        reports.append(report)
        imports.append(f"import {name}")
        calls += [f"    _pyn_code = {name}._pyn_run({str(report)!r})",
                  "    if _pyn_code == 1:", "        _pyn_failed = True"]
    marker = suite_work / "started"
    # (A reserved name: a test package called tmp is mirrored beside it.)
    temporary = suite_work / "_pyn_tmp"
    builtin = any(module.builtin_fixtures for module in instrumented)
    if builtin:
        # tmp_path directories live under one directory that this run owns and removes.
        imports = ["import pytest_native_fixtures as _pyn_fixtures",
                   f"_pyn_fixtures.tmp_base[0] = {str(temporary)!r}", *imports]
    if settings.filters:
        # The configuration's filterwarnings, before any test module is imported.
        imports = ["import warnings as _pyn_warnings",
                   *(f"_pyn_warnings.filterwarnings({action!r}, {message!r}, {category})"
                     for action, message, category in settings.filters), *imports]
    source = suite_work / "_pyn_suite.py"

    def write_driver():
        # The marker is written before any test module's code runs: without it, a failed
        # native command never started the program, and nothing observable happened.
        # (The exit status counts the program's cases, which leaving a test out changes.)
        count = sum(len(result.cases) for result in results)
        write_changed(source, "\n".join([
            "import sys", f"open({str(marker)!r}, 'w').close()", *imports, "",
            "def _pyn_main() -> int:", "    _pyn_failed = False", *calls,
            "    if _pyn_failed:", "        return 1", f"    return {0 if count else 5}", "",
            "sys.exit(_pyn_main())", ""]))

    write_changed(suite_work / "pytest_native_support.py", (TOOLS / "pytest_native_support.py").read_text())
    if builtin:
        write_changed(suite_work / "pytest_native_fixtures.py", (TOOLS / "pytest_native_fixtures.py").read_text())
    for name in sorted({name for module in instrumented for name in module.support_modules}):
        write_changed(suite_work / f"{name}.py", (TOOLS / f"{name}.py").read_text())
    # The modules beside the tests, where the generated ones import them.
    mirror(suite_work, tree, {*paths, *tree.conftests}, root, settings.pythonpath)
    env = environment([suite_work, *tree.bases, *settings.pythonpath, root])
    # Suite-level cost/output is attached to the first result, not multiplied by
    # the number of modules. The JSON records this execution model explicitly.
    first = results[0]
    origins = conftest_names + [result.path for result in results]

    def sources_of(modules):
        # The compiler names generated lines; translate() shows the test's own beside them.
        if mode == "python":
            return {}
        return {str(file): (origin, module) for file, origin, module in zip(generated_files, origins, modules)}

    def attempt(modules):
        write_driver()
        for file, module in zip(generated_files, modules):
            write_changed(file, module.source)
        for report in reports:
            report.unlink(missing_ok=True)
        marker.unlink(missing_ok=True)
        shutil.rmtree(temporary, ignore_errors=True)
        if builtin:
            temporary.mkdir(parents=True)
        try:
            return execute_suite()
        finally:
            shutil.rmtree(temporary, ignore_errors=True)

    def execute_suite():
        if mode == "python":
            command = [python, str(source)]
        elif mode == "jit":
            command = [*compiler, "run", str(source)]
        else:
            executable = suite_work / "_pyn_suite"
            started = time.perf_counter()
            try:
                built = subprocess.run([*compiler, "build", str(source), "-o", str(executable)],
                                       env=env, cwd=root, capture_output=True, text=True, timeout=timeout)
            except (OSError, subprocess.TimeoutExpired) as error:
                first.build_seconds += time.perf_counter() - started
                return "build-error", str(error)
            first.build_seconds += time.perf_counter() - started
            if built.returncode:
                return "build-failed", built
            command = [str(executable)]
        started = time.perf_counter()
        try:
            ran = subprocess.run(command, env=env, cwd=root, capture_output=True, text=True, timeout=timeout)
        except (OSError, subprocess.TimeoutExpired) as error:
            first.run_seconds += time.perf_counter() - started
            return "run-error", str(error)
        first.run_seconds += time.perf_counter() - started
        if mode != "python" and ran.returncode and not marker.exists():
            return "not-started", ran
        return "ran", ran

    plain_record = suite_work / "plain-assertions"

    def attempts(instrumented):
        """Run the program, with plain assertions where only those compile: (status, value, modules)."""
        # Assertion operands add code that the compiler may not accept (an operand's repr or
        # its temporary's type). Such a build is retried once with plain assertions, which
        # runs no test code twice, and the choice is kept until the instrumented code changes.
        used = instrumented
        fingerprint = hashlib.sha256("\0".join([shlex.join(compiler), *(module.source for module in instrumented)])
                                     .encode()).hexdigest()
        plain = None
        first.assertion_operands, first.operand_build_error = True, ""
        if mode != "python" and plain_record.is_file() and plain_record.read_text() == fingerprint:
            plain = used = build(False)
            first.assertion_operands = False
        status, value = attempt(used)
        if status in ("build-failed", "not-started") and plain is None:
            plain = build(False)
            if [module.source for module in plain] != [module.source for module in instrumented]:
                first.assertion_operands = False
                first.operand_build_error = translate(value.stderr or value.stdout, sources_of(instrumented))[-4000:]
                used = plain
                status, value = attempt(plain)
                if status not in ("build-failed", "not-started"):
                    plain_record.write_text(fingerprint)
                else:
                    # Both builds failed: the plain one's error is the module's own.
                    first.assertion_operands, first.operand_build_error = True, ""
        return status, value, used

    def leave_out(value, used):
        """Leave out the test that a failed build's diagnostic blames: the modules without it, or None.

        The diagnostic names the line it rejects and the calls that led the compiler
        there; the first of those lines that is in a test blames it. The test's lines are
        blanked in the text the modules are generated from, so the program is the one
        its file would make without that test, and each case this removes is recorded
        with the diagnostic. An error in no test (a module's own statement, a helper or a
        fixture that no call leads to from a test, the package under test) blames none.

        Where no test is blamed, a fixture that is not autouse is, of a test module or a
        conftest.py (unfixture), and else the statement the diagnostic is at, where it
        only binds names: an import of a module the compiler does not have or of a name
        it does not provide, an assignment (unbind). The tests that request the fixture
        or use the names are then rejected for that, and left out in their turn.
        """
        text = value.stderr or value.stdout
        offset = len(tree.conftests)
        files = {str(file): position for position, file in enumerate(generated_files)}
        reason = next((entry for entry in translate(text, sources_of(used)).splitlines() if "error:" in entry),
                      text.strip())[:2000]

        def place(position):
            # The file a generated module was made from: (path, its name, the result that records it).
            if position < offset:
                return tree.conftests[position], conftest_names[position], results[0]
            return paths[position - offset], results[position - offset].path, results[position - offset]

        def snapshot():
            return (dict(texts), [(result.cases, result.state, result.error, dict(result.uncollected),
                                   dict(result.unbound), dict(result.unavailable)) for result in results],
                    dict(unbound), {key: dict(names) for key, names in left_fixtures.items()})

        def restore(kept):
            texts.clear()
            texts.update(kept[0])
            for result, (cases, state, error, uncollected, statements, fixtures) in zip(results, kept[1]):
                result.cases, result.state, result.error = cases, state, error
                result.uncollected, result.unbound, result.unavailable = uncollected, statements, fixtures
            unbound.clear()
            unbound.update(kept[2])
            left_fixtures.clear()
            left_fixtures.update(kept[3])

        # A name whose statement was left out: that statement's reason is the cause.
        missing = re.search(r"error: name '(\w+)' is not defined", reason)
        if missing and missing.group(1) in unbound:
            reason += "; what binds it was left out: " + unbound[missing.group(1)]
        blamed = [(position, original_line(used[position], line)) for position, line in blamed_lines(text, files)]
        blamed = [(position, line) for position, line in blamed if line]
        for position, line in blamed:
            if position < offset:
                continue
            path, _, result = place(position)
            region = test_region(texts[path], line, result.cases)
            if region is None:
                continue
            kept = snapshot()
            texts[path] = blanked(texts[path], region[0], region[1])
            rebuilt = build(True)
            if rebuilt is None or all(set(result.cases) >= set(entry[0]) for result, entry in zip(results, kept[1])):
                # (What is left is not a module the runner collects, or has every case still.)
                restore(kept)
                continue
            for result, entry in zip(results, kept[1]):
                for case in entry[0]:
                    if case not in result.cases and not left_out([result], [case]):
                        result.uncompiled[case] = reason
            return rebuilt
        # No test: a fixture that is not autouse, whose tests the collector then leaves out.
        for position, line in blamed:
            kept = snapshot()
            if unfixture(*place(position)[:2], line, reason, place(position)[2]):
                rebuilt = build(True)
                if rebuilt is not None:
                    return rebuilt
                restore(kept)
        # Nor a fixture: the statement the diagnostic is at, where it only binds names.
        own = re.search("(" + "|".join(re.escape(file) for file in sorted(files, key=len, reverse=True))
                        + r"):(\d+): error:", text) if files else None
        line = original_line(used[files[own.group(1)]], int(own.group(2))) if own else None
        if line:
            kept = snapshot()
            # (One name of several, where the module lacks only that one.)
            lacking = re.search(r"error: cannot import name '(\w+)' from ", reason)
            path, filename, result = place(files[own.group(1)])
            if unbind(path, filename, line, reason, result, lacking.group(1) if lacking else None) is not None:
                rebuilt = build(True)
                if rebuilt is not None:
                    return rebuilt
                restore(kept)
        return None

    status, value, used = attempts(instrumented)
    left = 0
    while status in ("build-failed", "not-started") and left < LEFT_OUT_LIMIT:
        remaining = leave_out(value, used)
        if remaining is None:
            break
        left += 1
        status, value, used = attempts(remaining)
    if status == "build-error" or status == "run-error":
        for result in results:
            result.state = "compile-error" if status == "build-error" else "execution-error"
            result.error = value
        return results
    sources = sources_of(used)
    if status == "build-failed":
        for result in results:
            result.state, result.exit_code = "compile-error", value.returncode
        first.stdout, first.stderr = value.stdout, translate(value.stderr, sources)
        return results
    ran = value
    first.stdout, first.stderr = ran.stdout, translate(ran.stderr, sources)
    for result, report in zip(results, reports):
        try:
            records = report.read_text().splitlines()
            code = json.loads(records[-1])["exit_code"] if records else None
            if type(code) is not int:
                raise ValueError("invalid module completion status")
            result.events = read_report(report, result.cases, code)
            result.exit_code = code
            result.state = "empty" if code == 5 else "passed" if code == 0 else "test-failed"
        except (OSError, UnicodeError, ValueError, KeyError, IndexError, TypeError) as error:
            result.state, result.error = "execution-error", str(error)
    expected_exit = (1 if any(result.state == "test-failed" for result in results)
                     else 0 if any(result.cases for result in results) else 5)
    if ran.returncode != expected_exit or any(result.state == "execution-error" for result in results):
        # An import failure, crash, interrupt or incomplete report is never a
        # passing suite, even if earlier modules happened to finish.
        for result in results:
            result.state = "execution-error"
            result.error = result.error or f"suite execution did not complete (exit {ran.returncode})"
    return results


def run_module(path: Path, root: Path, work: Path, mode: str, compiler: list[str],
               python: str, timeout: float) -> Result:
    return run_suite([path], root, work, mode, compiler, python, timeout)[0]


ORACLE_PLUGIN = '''import json
import os

_path = os.environ["PYSTACHY_PYTEST_ORACLE_REPORT"]

def _write(event):
    with open(_path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(event) + "\\n")

def pytest_collection_finish(session):
    _write({"collection": [item.nodeid for item in session.items]})

def pytest_runtest_logreport(report):
    outcome = report.outcome
    if hasattr(report, "wasxfail"):
        outcome = "xfailed" if report.skipped else "xpassed" if report.passed else outcome
    # (A unittest subTest block reports apart from its test's own call.)
    phase = "subtest" if type(report).__name__ == "SubtestReport" else report.when
    _write({"nodeid": report.nodeid, "phase": phase, "outcome": outcome,
            "detail": str(report.longrepr) if report.longrepr else ""})

def pytest_sessionfinish(session, exitstatus):
    _write({"complete": True, "exit_code": int(exitstatus)})
'''


def oracle(paths: list[Path], root: Path, work: Path, python: str, timeout: float,
           selections: dict[Path, list[str]] | None = None, settings: Settings | None = None) -> dict:
    # pytest reads the conftest.py files layout() finds: those from --root down to the
    # tests. --confcutdir keeps those above --root out, as --noconftest does without any.
    conftest = bool(paths) and bool(layout(paths, root).conftests)
    write_changed(work / "_pyn_oracle.py", ORACLE_PLUGIN)
    # Its configuration is the part of the project's that the runner honors (configuration()).
    write_changed(work / "empty.ini", "\n".join(["[pytest]", *(settings.ini if settings else [])]) + "\n")
    report = work / "oracle.jsonl"
    report.unlink(missing_ok=True)
    env = environment([work, root])
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    env["PYSTACHY_PYTEST_ORACLE_REPORT"] = str(report)
    for key in ("PYTEST_ADDOPTS", "PYTEST_PLUGINS"):
        env.pop(key, None)
    command = [python, "-m", "pytest", "-q", "-p", "_pyn_oracle", "-p", "no:cacheprovider",
               *(["--confcutdir", str(root)] if conftest else ["--noconftest"]),
               "--basetemp", str(work / "oracle-tmp"), "--rootdir", str(root), "-c", str(work / "empty.ini"),
               *(["-k", settings.keyword] if settings and settings.keyword else []),
               *(["-m", settings.markexpr] if settings and settings.markexpr else []),
               *([f"{path}::{selector}" for path in paths for selector in selections[path]]
                 if selections else [str(path) for path in paths])]
    start = time.perf_counter()
    ran = None
    try:
        ran = subprocess.run(command, env=env, cwd=root, capture_output=True, text=True, timeout=timeout)
        if not report.exists():
            raise ValueError("pytest did not start")
        records = [json.loads(line) for line in report.read_text().splitlines()]
        if not records or records[-1] != {"complete": True, "exit_code": ran.returncode}:
            raise ValueError("incomplete pytest oracle report")
        collections = [record["collection"] for record in records if "collection" in record]
        if len(collections) != 1 or ran.returncode not in (0, 1, 5):
            raise ValueError(f"pytest oracle did not complete collection/execution (exit {ran.returncode})")
        return {"cases": collections[0], "events": [record for record in records if "nodeid" in record],
                "exit_code": ran.returncode, "seconds": time.perf_counter() - start,
                "stdout": ran.stdout, "stderr": ran.stderr}
    except (OSError, subprocess.TimeoutExpired, ValueError) as error:
        message = str(error)
        stderr = ran.stderr if ran is not None else ""
        if "No module named pytest" in stderr:
            message = (f"pytest is not installed for {python}; install tools/requirements-dev.txt "
                       "or select another interpreter with --python")
        elif ran is not None and (stderr.strip() or ran.stdout.strip()):
            message += " (pytest: " + (stderr.strip() or ran.stdout.strip()).splitlines()[-1] + ")"
        return {"error": message, "seconds": time.perf_counter() - start,
                "stdout": ran.stdout if ran is not None else "", "stderr": stderr}


LEFT_OUT = ("the native program is not all of the suite: the collector or the compiler rejected tests or imports of "
            "the test modules, which the runner left out")


def left_out(results: list[Result], cases: list[str]) -> dict[str, str]:
    """pytest's cases that the program lacks because the runner left their tests out, each with how.

    A case the compiler rejected is named whole; a test the collector rejected is named
    without its parametrization, and a class left out whole by its own name.
    """
    uncompiled = {case for result in results for case in result.uncompiled}
    uncollected = [name for result in results for name in result.uncollected]
    found = {}
    for case in cases:
        if case in uncompiled:
            found[case] = "not compiled"
        elif any(case == name or case.startswith((name + "[", name + "::")) for name in uncollected):
            found[case] = "not collected"
    return found


def compare(results: list[Result], reference: dict) -> list[str]:
    """How the run differs from pytest's; tests and imports left out of the program are one
    difference (LEFT_OUT), and the others are then compared without those tests' cases."""
    if "error" in reference:
        return ["oracle: " + reference["error"]]
    errors = []
    left = left_out(results, reference["cases"])
    partial = any(result.uncompiled or result.unbound or result.uncollected or result.unavailable
                  for result in results)
    cases = [case for result in results for case in result.cases]
    if (cases != [case for case in reference["cases"] if case not in left]
            or any(case not in left for result in results for case in result.uncompiled)):
        errors.append("collected test IDs/order differ from pytest")
    events = [event for result in results for event in result.events]
    reference = {**reference, "events": [event for event in reference["events"] if event["nodeid"] not in left]}
    def key(event):
        # A setup/teardown failure is an ERROR in the native summary, but pytest's
        # report API calls it failed and uses its phase to distinguish it.
        outcome = "failed" if event["outcome"] == "error" else event["outcome"]
        return event["nodeid"], event["phase"], outcome
    if [key(event) for event in events] != [key(event) for event in reference["events"]]:
        errors.append("setup/call/teardown outcomes differ from pytest")
    if any(result.state not in {"passed", "test-failed", "empty"} for result in results):
        errors.append("native collection/build/execution did not complete")
    if partial:
        errors.append(LEFT_OUT)
    return errors


def outcome_differences(results: list[Result], reference: dict) -> list[str]:
    """Each test and phase whose collection or outcome differs from pytest's."""
    if "error" in reference:
        return []
    native_cases = [case for result in results for case in result.cases]
    left = left_out(results, reference["cases"])
    lines = [f"{case}: collected natively, not by pytest"
             for case in [*native_cases, *(case for result in results for case in result.uncompiled)]
             if case not in reference["cases"]]
    lines += [f"{case}: collected by pytest, not natively" for case in reference["cases"]
              if case not in native_cases and case not in left]
    if not lines and native_cases != [case for case in reference["cases"] if case not in left]:
        lines.append("collection order differs: pytest " + ", ".join(reference["cases"]))
    if any(result.state not in {"passed", "test-failed", "empty"} for result in results):
        return lines  # (no native outcomes to set beside pytest's)

    def outcomes(events):
        found = {}
        subtests: dict[str, int] = {}
        for event in events:
            phase = event["phase"]
            if phase == "subtest":
                subtests[event["nodeid"]] = subtests.get(event["nodeid"], 0) + 1
                phase = f"subtest {subtests[event['nodeid']]}"
            found[event["nodeid"], phase] = "failed" if event["outcome"] == "error" else event["outcome"]
        return found
    native = outcomes(event for result in results for event in result.events)
    original = outcomes(reference["events"])
    for case in reference["cases"]:
        if case in left:
            # (pytest's outcome for the case: its call's, or its setup's where that did not pass)
            lines.append(f"{case}: pytest {original.get((case, 'call'), original.get((case, 'setup'), 'absent'))}, "
                         f"native {left[case]}")
    for key in dict.fromkeys([*original, *native]):
        if key[0] not in left and original.get(key) != native.get(key):
            lines.append(f"{key[0]} [{key[1]}]: pytest {original.get(key, 'absent')}, "
                         f"native {native.get(key, 'absent')}")
    return lines


def clipped(text: str, lines: int = 40) -> str:
    """The end of a long failure report, where pytest puts the failing line and error."""
    kept = text.rstrip("\n").splitlines()
    if len(kept) <= lines:
        return "\n".join(kept)
    return "\n".join([f"... ({len(kept) - lines} earlier lines in the JSON report)", *kept[-lines:]])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+",
                        help="test modules or directories, or node IDs: path::test or path::test[id]")
    parser.add_argument("--root", type=Path, default=Path.cwd(),
                        help="directory that test IDs are relative to (default: the current directory)")
    parser.add_argument("--mode", choices=("python", "jit", "aot"), default="jit",
                        help="python runs the generated code under CPython; jit (default) and aot run it natively")
    parser.add_argument("--compiler", help="Pystachy command (default: this checkout's hosted compiler; "
                        "./pystachy after make reuses its program cache)")
    parser.add_argument("--python", default=sys.executable, help="CPython executable for generated/original tests")
    parser.add_argument("--work-dir", type=Path, default=REPO / "build" / "pytest-native",
                        help="generated sources, programs and reports; one run at a time uses it")
    parser.add_argument("--compare", action=argparse.BooleanOptionalAction, default=True,
                        help="compare phase outcomes with real pytest (default); --no-compare is unverified")
    parser.add_argument("-k", dest="keyword", metavar="EXPRESSION",
                        help="run the cases whose names match, as pytest's -k: names, and, or, not, parentheses")
    parser.add_argument("-m", dest="markexpr", metavar="EXPRESSION",
                        help="run the cases whose marks match, as pytest's -m")
    parser.add_argument("--json", type=Path, help="write complete machine-readable evidence")
    parser.add_argument("--timeout", type=float, default=120,
                        help="seconds allowed for each build, run and pytest process (default: 120)")
    args = parser.parse_args(argv)
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    args.hosted_default = args.compiler is None
    if args.compiler is None:
        args.compiler = shlex.join([sys.executable, str(REPO / "pystachy.py")])
    try:
        args.compiler = shlex.join(compiler_command(args.compiler))
        with lock_work_directory(args.work_dir.resolve()):
            return execute(args)
    except (CollectionError, OSError) as error:
        print(f"runner error: {error}", file=sys.stderr)
        return 2


def execute(args) -> int:
    started = time.perf_counter()
    root, work = args.root.resolve(), args.work_dir.resolve()
    if not args.compare:
        print("UNVERIFIED: pytest oracle comparison is disabled (--no-compare). "
              "Use only for previously qualified, unchanged inputs.", file=sys.stderr)
    if getattr(args, "hosted_default", False) and args.mode != "python":
        print("note: the default hosted compiler compiles every run again; after make, "
              "--compiler ./pystachy reuses the native program cache", file=sys.stderr)
    try:
        selections = parse_targets(args.paths, root, True)
        paths = (list(selections) if selections is not None
                 else discover([Path(path) for path in args.paths], root, True))
        settings = configuration(paths, root)
        settings.verified = args.compare
        # (The command line's expressions replace the configuration's, as pytest's last option does.)
        settings.keyword = settings.keyword if args.keyword is None else args.keyword
        settings.markexpr = settings.markexpr if args.markexpr is None else args.markexpr
        for option, text in (("-k", settings.keyword), ("-m", settings.markexpr)):
            match_expression(text, option)
    except (CollectionError, OSError, UnicodeError) as error:
        print(f"collection error: {error}", file=sys.stderr)
        return 2
    results = run_suite(paths, root, work, args.mode, shlex.split(args.compiler), args.python, args.timeout,
                        selections, settings)
    collected = not any(result.state == "collection-error" for result in results)
    # A module the runner cannot collect is an error already; running pytest would only
    # report the consequences as differences.
    reference = (oracle(paths, root, work, args.python, args.timeout, selections, settings)
                 if args.compare and paths and collected else None)
    differences = compare(results, reference) if reference is not None else []
    mismatches = outcome_differences(results, reference) if reference is not None else []
    uncompiled = sum(len(result.uncompiled) for result in results)
    unbound = sum(len(result.unbound) for result in results)
    uncollected = sum(len(result.uncollected) for result in results)
    unavailable = sum(len(result.unavailable) for result in results)
    if (differences or uncompiled or unbound or uncollected or unavailable
            or any(result.state in {"collection-error", "compile-error", "execution-error"} for result in results)):
        status = 2
    elif not any(result.cases for result in results):
        status = 5
    else:
        status = int(any(result.state == "test-failed" for result in results))
    # (partial: what the program has matches pytest, and it lacks tests or imports that pytest runs.)
    qualification = ("unverified" if not args.compare else "not-compared" if not collected
                     else "partial" if differences == [LEFT_OUT]
                     else "pytest-mismatch" if differences else "pytest-matched" if reference is not None
                     else "no-tests")
    evidence = {"mode": args.mode, "qualification": qualification,
                "execution": "one process; suite timings/output on first module", "root": str(root),
                "results": [asdict(result) for result in results],
                "oracle": reference, "differences": differences, "mismatches": mismatches, "exit_code": status}
    if args.json:
        write_changed(args.json.resolve(), json.dumps(evidence, indent=2) + "\n")
    expected = {(event["nodeid"], event["phase"]): event
                for event in (reference or {}).get("events", [])}
    for result in results:
        lacking = "".join(f", {len(entries)} {what}" for entries, what in (
            (result.uncompiled, "not compiled"), (result.uncollected, "tests not collected")) if entries)
        print(f"{result.path}: {result.state} ({len(result.cases)} cases{lacking})")
        for name, reason in result.unavailable.items():
            print(f"NOT AVAILABLE {name} (fixture)")
            print(textwrap.indent(clipped(reason), "    "))
        for name, reason in result.uncollected.items():
            print(f"NOT COLLECTED {name}")
            print(textwrap.indent(clipped(reason), "    "))
        reasons: dict[str, list[str]] = {}
        for case, reason in result.uncompiled.items():
            reasons.setdefault(reason, []).append(case)
        for statement, reason in result.unbound.items():
            print(f"NOT BOUND {statement}")
            print(textwrap.indent(clipped(reason), "    "))
        for reason, cases in reasons.items():
            for case in cases:
                print(f"NOT COMPILED {case}")
            print(textwrap.indent(clipped(reason), "    "))
        for event in result.events:
            if event["outcome"] in {"failed", "error"}:
                print(f"{'FAILED' if event['outcome'] == 'failed' else 'ERROR'} {event['nodeid']} [{event['phase']}]")
                if event["detail"]:
                    print(textwrap.indent(clipped(event["detail"]), "    "))
                original = expected.get((event["nodeid"], event["phase"]))
                if original and original["outcome"] == "failed" and original["detail"]:
                    print("  pytest (CPython) report:")
                    print(textwrap.indent(clipped(original["detail"]), "    "))
        if result.error:
            print(result.error, file=sys.stderr)
        if result.state in {"compile-error", "execution-error"} and result.stderr:
            print(result.stderr, file=sys.stderr, end="")
        if result.state != "passed" and result.stdout:
            print(result.stdout, end="")
    if results and not results[0].assertion_operands:
        print("note: assertion operands are not shown: the native compiler rejected the code that keeps "
              "them (operand_build_error in --json)", file=sys.stderr)
    for difference in differences:
        print(difference, file=sys.stderr)
    for mismatch in mismatches:
        print("MISMATCH " + mismatch, file=sys.stderr)
    if differences and results and results[0].hooks:
        print("note: the native program does not run these conftest.py hooks, which may explain a difference: "
              + ", ".join(results[0].hooks), file=sys.stderr)
    if args.compare and reference is not None and not differences:
        print("pytest collection and phase outcomes match")
    elif differences == [LEFT_OUT]:
        print("pytest collection and phase outcomes match for the cases the program has")
    if status == 5:
        print("no tests collected")
    counts = outcome_counts(results)
    summary = ", ".join(f"{counts[name]} {name + 's' if name == 'error' and counts[name] > 1 else name}"
                        for name in ("failed", "passed", "skipped", "xfailed", "xpassed", "error", "subtests passed",
                                     "subtests skipped") if counts.get(name))
    if uncollected:
        summary += (", " if summary else "") + f"{uncollected} test{'s' if uncollected > 1 else ''} not collected"
    if uncompiled:
        summary += (", " if summary else "") + f"{uncompiled} not compiled"
    if unbound:
        summary += (", " if summary else "") + f"{unbound} statement{'s' if unbound > 1 else ''} left out"
    if unavailable:
        summary += (", " if summary else "") + f"{unavailable} fixture{'s' if unavailable > 1 else ''} left out"
    if summary:
        verdict = ("; UNVERIFIED" if not args.compare else "" if differences == [LEFT_OUT]
                   else "; pytest comparison failed" if differences or reference is None else "")
        print(f"{summary} in {time.perf_counter() - started:.2f}s ({args.mode}{verdict})")
    return status


if __name__ == "__main__":
    raise SystemExit(main())
