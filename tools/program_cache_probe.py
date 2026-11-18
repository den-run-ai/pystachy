"""Exercise the default native-program cache and measure complete launches.

The correctness checks have no timing gates. LLVM wrappers count actual work;
each hit must omit both the frontend trace and every wrapped tool invocation.
All sources, caches, wrappers and fault injections live in a private directory.

    python tools/program_cache_probe.py --compiler ./pystachy --llvm /path/to/bin \
        --output build/program-cache-checks.json
    python tools/program_cache_probe.py --compiler ./pystachy --llvm /path/to/bin \
        --benchmark-only --rounds 5 --output build/program-cache-times.json

The benchmark includes startup, validation, compilation on misses and execution.
Its prebuilt AOT comparison uses the ordinary build command and is a separate
code-quality tier. Cold-program samples remove only program manifests, executables
and staging directories, retaining warmed runtime artifacts and static identity
hashes. Each workload also records one first-use fill with the whole program-cache
subtree empty and runtime artifacts warm, exposing the initial toolchain-hash cost.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import platform
import select
import shlex
import shutil
import signal
import statistics
import subprocess
import sys
import tempfile
import time
import traceback

from jitprobe import COROUTINE_SOURCE, SOURCE


ROOT = Path(__file__).resolve().parent.parent
TRACE = b"pystachy program cache: "
TOOLS = ("clang", "opt", "lli", "llvm-link", "llvm-as", "llc")
TOOL_ENV = ("CPATH", "C_INCLUDE_PATH", "CPLUS_INCLUDE_PATH", "OBJC_INCLUDE_PATH",
            "LIBRARY_PATH", "COMPILER_PATH", "GCC_EXEC_PREFIX", "SDKROOT",
            "CCC_OVERRIDE_OPTIONS", "CLANG_CONFIG_FILE_SYSTEM_DIR",
            "CLANG_CONFIG_FILE_USER_DIR", "LD_PRELOAD", "LD_LIBRARY_PATH",
            "LD_AUDIT", "LD_RUN_PATH", "LD_HWCAP_MASK", "GLIBC_TUNABLES",
            "LDEMULATION", "GNUTARGET")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def clean_stderr(data: bytes) -> tuple[bytes, list[str]]:
    ordinary = []
    events = []
    for line in data.splitlines(keepends=True):
        if line.startswith(TRACE):
            events.append(line[len(TRACE):].decode("utf-8", errors="replace").strip())
        else:
            ordinary.append(line)
    return b"".join(ordinary), events


@dataclass
class Run:
    command: list[str]
    status: int
    stdout: bytes
    stderr: bytes
    seconds: float
    tools: list[str]
    timed_out: bool = False

    @property
    def events(self) -> list[str]:
        return clean_stderr(self.stderr)[1]

    @property
    def observable(self) -> tuple[int, bytes, bytes]:
        return self.status, self.stdout, clean_stderr(self.stderr)[0]

    def record(self) -> dict:
        return {"command": self.command, "status": self.status,
                "stdout": self.stdout.decode("utf-8", errors="backslashreplace"),
                "stderr": self.stderr.decode("utf-8", errors="backslashreplace"),
                "stdout_sha256": digest(self.stdout), "stderr_sha256": digest(self.stderr),
                "seconds": self.seconds, "tools": dict(Counter(self.tools)),
                "events": self.events, "timed_out": self.timed_out}


def kill_owned_group(process: subprocess.Popen) -> None:
    # The leader may have exited while a backend child still owns its pipes.
    # Every caller created a fresh session, so this group belongs to this probe.
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


class Probe:
    def __init__(self, args: argparse.Namespace, directory: Path):
        self.args = args
        self.directory = directory
        self.home = Path(args.home).resolve()
        self.command = shlex.split(args.compiler)
        if not self.command:
            raise ValueError("--compiler must name a native compiler")
        executable = shutil.which(self.command[0])
        if executable is None:
            raise ValueError(f"compiler not found: {self.command[0]}")
        self.command[0] = str(Path(executable).absolute())
        self.python = shlex.split(args.python)
        self.cache = directory / "cache"
        self.cache.mkdir()
        self.bindir = directory / "llvm"
        self.bindir.mkdir()
        self.log = directory / "tool-calls"
        self.fail = directory / "fail-codegen"
        self.pause = directory / "pause-codegen"
        self.ready = directory / "codegen-ready"
        self.runs: list[dict] = []
        self.checks: list[dict] = []
        self.sources: list[dict] = []
        self.assertions = 0
        self.env = {k: v for k, v in os.environ.items()
                    if not k.startswith("PYSTACHY_") and k not in TOOL_ENV}
        self.env.update({"PYSTACHY_HOME": str(self.home),
                         "PYSTACHY_LLVM": str(self.bindir),
                         "PYSTACHY_CACHE": str(self.cache),
                         "PYSTACHY_PROGRAM_CACHE_TRACE": "1"})
        llvm = Path(args.llvm).absolute() if args.llvm else None
        self.real: dict[str, str] = {}
        for name in TOOLS:
            tool = shutil.which(str(llvm / name) if llvm else name)
            if tool is None:
                raise ValueError(f"cannot find LLVM tool {name}; pass --llvm")
            self.real[name] = str(Path(tool).absolute())
            code = ("#!/bin/sh\n"
                    f"printf '%s\\n' {shlex.quote(name)} >> {shlex.quote(str(self.log))}\n")
            if name == "clang":
                # Only the program's backend is stopped. Runtime setup and
                # header/link identity probes must remain ordinary commands.
                code += ("case \" $* \" in *' -disable-llvm-passes '*)\n"
                         f"  if [ -f {shlex.quote(str(self.fail))} ]; then exit 86; fi\n"
                         f"  if [ -f {shlex.quote(str(self.pause))} ]; then\n"
                         f"    : > {shlex.quote(str(self.ready))}\n"
                         f"    while [ -f {shlex.quote(str(self.pause))} ]; do sleep 0.02; done\n"
                         "  fi\n"
                         "esac\n")
            code += f"exec {shlex.quote(self.real[name])} \"$@\"\n# identity-marker-A\n"
            path = self.bindir / name
            path.write_text(code)
            path.chmod(0o755)
        # The driver cannot infer arbitrary shell-wrapper dependencies. Declare
        # the exact ELF tools and their loader inputs explicitly for these
        # transparent counting wrappers, rather than benchmark a weaker key.
        inputs = set(self.real.values())
        shared = subprocess.run(["ldd", *self.real.values()], capture_output=True,
                                text=True, timeout=30, check=False)
        for word in shared.stdout.split():
            if word.startswith("/") and Path(word).is_file():
                inputs.add(word)
        self.env["PYSTACHY_PROGRAM_CACHE_INPUTS"] = ":".join(sorted(inputs))
        # The existing runtime cache intentionally distrusts newly written
        # tools for two seconds. Do not confuse that rule with a cache defect.
        time.sleep(2.05)

    def check(self, condition: bool, description: str) -> None:
        self.assertions += 1
        if not condition:
            raise AssertionError(description)

    def calls(self) -> list[str]:
        return self.log.read_text().splitlines() if self.log.exists() else []

    def environment(self, changes: dict[str, str | None] | None = None) -> dict[str, str]:
        env = self.env.copy()
        for key, value in (changes or {}).items():
            if value is None:
                env.pop(key, None)
            else:
                env[key] = value
        return env

    def write(self, path: Path, source: str) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source)
        self.sources.append({"path": str(path), "text": source,
                             "sha256": digest(source.encode())})
        return path

    def source(self, name: str, source: str) -> Path:
        return self.write(self.directory / "sources" / name / "main.py", source)

    def same_size_edit(self, path: Path, old: bytes, new: bytes) -> None:
        self.check(len(old) == len(new), "invalid same-size test edit")
        before = path.stat()
        content = path.read_bytes()
        self.check(content.count(old) == 1, f"edit target must occur once: {path}")
        path.write_bytes(content.replace(old, new, 1))
        os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
        after = path.stat()
        self.check(after.st_size == before.st_size and after.st_mtime_ns == before.st_mtime_ns,
                   f"test failed to preserve size and mtime: {path}")
        self.sources.append({"path": str(path), "edit_from": old.decode(errors="backslashreplace"),
                             "edit_to": new.decode(errors="backslashreplace"),
                             "sha256": digest(path.read_bytes()), "preserved_mtime": True})

    def launch(self, label: str, command: list[str], *, stdin: bytes = b"",
               changes: dict[str, str | None] | None = None,
               cwd: Path | None = None) -> Run:
        env = self.environment(changes)
        before = len(self.calls())
        start = time.perf_counter()
        process = subprocess.Popen(command, cwd=cwd or self.directory, env=env,
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, start_new_session=True)
        timed_out = False
        try:
            try:
                stdout, stderr = process.communicate(stdin, timeout=self.args.timeout)
            except subprocess.TimeoutExpired:
                timed_out = True
                kill_owned_group(process)
                stdout, stderr = process.communicate()
        except BaseException:
            kill_owned_group(process)
            process.communicate()
            raise
        result = Run(command, process.returncode, stdout, stderr,
                     time.perf_counter() - start, self.calls()[before:], timed_out)
        self.runs.append({"label": label, "environment_changes": changes or {},
                          "stdin": stdin.decode("utf-8", errors="backslashreplace"),
                          "cwd": str(cwd or self.directory), **result.record()})
        return result

    def run(self, label: str, path: Path, arguments: list[str] | None = None, **kwargs) -> Run:
        return self.launch(label, self.command + ["run", str(path), *(arguments or [])], **kwargs)

    def oracle(self, path: Path, arguments: list[str] | None = None, **kwargs) -> Run:
        return self.launch("cpython-reference", self.python + [str(path), *(arguments or [])], **kwargs)

    def matches(self, actual: Run, expected: Run, label: str) -> None:
        self.check(not actual.timed_out, f"{label}: timed out")
        self.check(actual.observable == expected.observable,
                   f"{label}: output/status differs; actual={actual.observable!r}, "
                   f"expected={expected.observable!r}")

    def hit(self, result: Run, label: str) -> None:
        self.check("hit" in result.events, f"{label}: no hit trace: {result.events}")
        self.check("frontend" not in result.events, f"{label}: frontend ran on a hit")
        self.check(not result.tools, f"{label}: LLVM ran on a hit: {result.tools}")

    def miss(self, result: Run, label: str) -> None:
        self.check("miss" in result.events and "hit" not in result.events,
                   f"{label}: expected a miss: {result.events}")
        self.check("frontend" in result.events, f"{label}: missing frontend trace")
        self.check(bool(result.tools), f"{label}: a miss ran no LLVM tools")

    def pair(self, path: Path, label: str, *, arguments: list[str] | None = None,
             reference: Run | None = None, **kwargs) -> tuple[Run, Run]:
        expected = reference or self.oracle(path, arguments, **kwargs)
        cold = self.run(label + ":miss", path, arguments, **kwargs)
        self.matches(cold, expected, label + " miss")
        self.miss(cold, label)
        warm = self.run(label + ":hit", path, arguments, **kwargs)
        self.matches(warm, expected, label + " hit")
        self.hit(warm, label)
        return cold, warm

    def entry_files(self) -> list[Path]:
        # The cache reserves its own subtree; never delete runtime caches.
        base = self.cache / "program-v2"
        return sorted(p for p in base.rglob("*") if p.is_file()) if base.exists() else []

    def remove_entries(self, *, keep_identity: bool = False) -> None:
        path = self.cache / "program-v2"
        if not path.exists():
            return
        if not keep_identity:
            shutil.rmtree(path)
            return
        for entry in path.iterdir():
            if entry.suffix in (".manifest", ".exe") or entry.name.startswith("stage-"):
                if entry.is_dir() and not entry.is_symlink():
                    shutil.rmtree(entry)
                else:
                    entry.unlink()

    def run_check(self, name: str, function) -> None:
        start = time.perf_counter()
        count = self.assertions
        try:
            function(self)
        except Exception as error:
            self.checks.append({"name": name, "passed": False, "error": str(error),
                                "traceback": traceback.format_exc(),
                                "assertions": self.assertions - count,
                                "seconds": time.perf_counter() - start})
            print(f"FAIL {name}: {error}", flush=True)
        else:
            self.checks.append({"name": name, "passed": True,
                                "assertions": self.assertions - count,
                                "seconds": time.perf_counter() - start})
            print(f"PASS {name}", flush=True)
        finally:
            self.fail.unlink(missing_ok=True)
            self.pause.unlink(missing_ok=True)
            self.ready.unlink(missing_ok=True)


def check_reuse(p: Probe) -> None:
    source = p.source("reuse", '''import os
import sys
def defined() -> int:
    print("definition effect")
    return 17
def unused(x: int = defined()) -> int:
    return x
print("module effect")
print(sys.argv)
print(os.getenv("CACHE_PROBE_VALUE", "missing"))
print(os.getenv("PYSTACHY_PROGRAM_CACHE_LOCK", "absent"))
with open("/dev/null") as stream:
    print("first file descriptor", stream.fileno())
print(input())
''')
    arguments = ["space here", "'quoted$argument`", "--", "-o"]
    p.pair(source, "fresh effects", arguments=arguments, stdin=b"first input\n",
           changes={"CACHE_PROBE_VALUE": "first", "PYSTACHY_ARGV0": "/caller/not-the-compiler"})
    changes = {"CACHE_PROBE_VALUE": "second", "PYSTACHY_GC_STRESS_PROGRAM": "1"}
    expected = p.oracle(source, ["changed argument"], stdin=b"second input\n", changes=changes)
    result = p.run("fresh runtime inputs", source, ["changed argument"],
                   stdin=b"second input\n", changes=changes)
    p.matches(result, expected, "fresh argv, stdin, environment and GC setting")
    p.hit(result, "runtime inputs do not invalidate native code")
    inherited = p.run("inherited argv0 on a hit", source, ["changed argument"], stdin=b"second input\n",
                      changes={**changes, "PYSTACHY_ARGV0": "/caller/not-the-program"})
    p.matches(inherited, expected, "inherited argv0 cannot replace the source path")
    p.hit(inherited, "inherited argv0 does not invalidate native code")


def check_source_content(p: Probe) -> None:
    source = p.source("content", "print(111)\n")
    p.pair(source, "original source")
    p.same_size_edit(source, b"111", b"222")
    p.pair(source, "same-size source edit")
    p.write(source.parent / "unrelated.py", "print('unrelated')\n")
    unchanged = p.run("unrelated source appeared", source)
    p.matches(unchanged, p.oracle(source), "unrelated source")
    p.hit(unchanged, "unrelated files do not invalidate")
    alias = source.parent / "alias.py"
    alias.symlink_to(source)
    expected = p.oracle(alias)
    result = p.run("source alias", alias)
    p.matches(result, expected, "source alias")
    p.miss(result, "source spelling changes")


def check_imports(p: Probe) -> None:
    source = p.source("imports", "import helper\nprint(helper.value())\n")
    helper = p.write(source.parent / "helper.py", "import nested\ndef value() -> int:\n    return nested.VALUE\n")
    nested = p.write(source.parent / "nested.py", "VALUE = 111\n")
    p.pair(source, "transitive import")
    p.same_size_edit(nested, b"111", b"222")
    # CPython's ordinary timestamp pycs deliberately cannot serve as the oracle
    # for preserved-mtime edits. Remove them before the independent reference.
    shutil.rmtree(source.parent / "__pycache__", ignore_errors=True)
    p.pair(source, "transitive content edit")
    p.check(helper.exists(), "helper source disappeared")

    shadow = p.source("shadow", "import chosen\nprint(chosen.VALUE)\n")
    lower = p.directory / "lower-priority"
    p.write(lower / "chosen.py", "VALUE = 31\n")
    env = {"PYSTACHY_PATH": str(lower), "PYTHONPATH": str(lower)}
    p.pair(shadow, "lower-priority import", changes=env)
    p.write(shadow.parent / "chosen.py", "VALUE = 32\n")
    p.pair(shadow, "new shadowing module", changes=env)
    p.write(shadow.parent / "chosen" / "__init__.py", "VALUE = 33\n")
    p.pair(shadow, "new shadowing package", changes=env)

    optional = p.source("optional", '''try:
    import optional_cache_probe
    print(optional_cache_probe.VALUE)
except ImportError:
    print("missing")
''')
    p.pair(optional, "missing optional import")
    p.write(optional.parent / "optional_cache_probe.py", "VALUE = 44\n")
    p.pair(optional, "optional import appears")

    namespace = p.source("namespace", "import cache_ns.item\nprint(cache_ns.item.VALUE)\n")
    first = p.directory / "namespace-first"
    last = p.directory / "namespace-last"
    first.mkdir()
    p.write(last / "cache_ns" / "item.py", "VALUE = 51\n")
    env = {"PYSTACHY_PATH": f"{first}:{last}", "PYTHONPATH": f"{first}:{last}"}
    p.pair(namespace, "namespace import", changes=env)
    p.write(first / "cache_ns" / "item.py", "VALUE = 52\n")
    p.pair(namespace, "new namespace portion", changes=env)
    p.write(last / "cache_ns" / "__init__.py", "# regular package takes priority\n")
    p.pair(namespace, "namespace becomes regular package", changes=env)

    # Only a directory is a namespace portion (#1166). Probes record each candidate's
    # kind, so a path that stays present but changes kind must miss.
    extless = p.source("extensionless", '''try:
    import plainname
    print("imported")
except ImportError:
    print("fallback")
''')
    p.pair(extless, "missing extensionless candidate")
    plain = p.write(extless.parent / "plainname", "not a module\n")
    p.pair(extless, "extensionless file appears")
    plain.unlink()
    plain.mkdir()
    p.pair(extless, "extensionless file becomes namespace directory")
    plain.rmdir()
    p.write(plain, "not a module\n")
    p.pair(extless, "namespace directory becomes extensionless file")

    ffi = p.source("ffi-shadow", 'import ffi\nprint("ok")\n')
    ordinary = p.run("builtin ffi reference", ffi, changes={"PYSTACHY_PROGRAM_CACHE": "0"})
    p.check(ordinary.status == 0 and ordinary.stdout == b"ok\n", "builtin ffi reference failed")
    p.pair(ffi, "builtin ffi", reference=ordinary)
    p.write(ffi.parent / "ffi.py", 'print("shadow")\n')
    p.pair(ffi, "new ffi shadow")

    nested.unlink()
    missing = p.run("import removed", source)
    p.check(missing.status != 0 and "hit" not in missing.events,
            "removed import used stale native code")


def check_regular_import_files(p: Probe) -> None:
    # Both source spellings must ignore directories/FIFOs and accept symlinks to
    # regular files (#1183). Every kind flip invalidates the previous executable.
    source = p.source("regular-import-files", "import chosenmod\nimport chosenpkg\n"
                      "print(chosenmod.VALUE, chosenpkg.VALUE)\n")
    lower = p.directory / "regular-import-lower"
    p.write(lower / "chosenmod.py", "VALUE = 31\n")
    p.write(lower / "chosenpkg" / "__init__.py", "VALUE = 32\n")
    target = p.write(p.directory / "regular-import-target.py", "VALUE = 33\n")
    candidates = [source.parent / "chosenmod.py", source.parent / "chosenpkg" / "__init__.py"]
    for candidate in candidates:
        candidate.mkdir(parents=True)
    environment = {"PYSTACHY_PATH": str(lower), "PYTHONPATH": str(lower)}
    p.pair(source, "source candidates are directories", changes=environment)
    for candidate in candidates:
        candidate.rmdir()
        os.mkfifo(candidate)
    p.pair(source, "source candidates become FIFOs", changes=environment)
    for candidate in candidates:
        candidate.unlink()
        candidate.symlink_to(target)
    p.pair(source, "source candidates become regular-file symlinks", changes=environment)

    # A non-regular ffi source must not remove the compiler's builtin module.
    # Its independent reference is an ordinary uncached launch with no shadow.
    ffi = p.source("regular-ffi-files", 'import ffi\nprint("ok")\n')
    reference = p.run("unshadowed builtin ffi", ffi, changes={"PYSTACHY_PROGRAM_CACHE": "0"})
    p.check(reference.status == 0 and reference.stdout == b"ok\n", "builtin ffi reference failed")
    candidates = [ffi.parent / "ffi.py", ffi.parent / "ffi" / "__init__.py"]
    for candidate in candidates:
        candidate.mkdir(parents=True)
    p.pair(ffi, "ffi candidates are directories", reference=reference)
    for candidate in candidates:
        candidate.rmdir()
        os.mkfifo(candidate)
    p.pair(ffi, "ffi candidates become FIFOs", reference=reference)
    target = p.write(p.directory / "regular-ffi-target.py", 'print("shadow")\n')
    for candidate in candidates:
        candidate.unlink()
        candidate.symlink_to(target)
    p.pair(ffi, "ffi candidates become regular-file symlinks")


def check_semantics(p: Probe) -> None:
    source = p.source("callbacks", SOURCE)
    p.write(source.parent / "jitprobe_module.py", 'print("import effect")\n')
    p.pair(source, "callbacks, exceptions and layout", arguments=["literal $`'"])
    stressed = p.run("callback GC hit", source, ["literal $`'"],
                     changes={"PYSTACHY_GC_STRESS_PROGRAM": "1"})
    p.matches(stressed, p.oracle(source, ["literal $`'"]), "callback GC hit")
    p.hit(stressed, "callback GC hit")
    p.pair(p.source("generator", COROUTINE_SOURCE), "coroutine finalization")
    floating = p.source("float", (p.home / "tests/programs/numbers/float_power_rounding.py").read_text())
    data = (p.home / "tests/programs/numbers/float_power_rounding.in").read_bytes()
    p.pair(floating, "runtime floating-point inputs", stdin=data)
    dynamic = p.source("dynamic-json", (p.home / "tests/programs/inference/dynany_json_bigints.py").read_text())
    reference = p.oracle(dynamic)
    p.pair(dynamic, "dynamic JSON and promoted integers", reference=reference)
    stressed = p.run("dynamic JSON GC hit", dynamic,
                     changes={"PYSTACHY_GC_STRESS_PROGRAM": "1"})
    p.matches(stressed, reference, "dynamic JSON GC hit")
    p.hit(stressed, "dynamic JSON GC hit")
    status = p.source("status", 'import sys\nprint("before exit")\nsys.exit(7)\n')
    p.pair(status, "nonzero program status")
    raised = p.source("uncaught", 'print("before raise")\nraise ValueError("same error")\n')
    ordinary = p.run("uncached error reference", raised, changes={"PYSTACHY_PROGRAM_CACHE": "0"})
    p.check(ordinary.status != 0 and b"ValueError: same error" in ordinary.stderr,
            "uncached exception reference did not fail as expected")
    p.pair(raised, "uncaught error", reference=ordinary)


def check_corruption(p: Probe) -> None:
    sys.path.insert(0, str(ROOT))
    from src.pystachy_compiler import program_cache as pc

    source = p.source("corruption", '''import os
import sys
with open(sys.argv[1], "a") as effect:
    effect.write("executed\\n")
print(57)
print("policy", os.getenv("PYSTACHY_PROGRAM_CACHE", "unset"))
print("lock", os.getenv("PYSTACHY_PROGRAM_CACHE_LOCK", "absent"))
print("environment", os.getenv("CACHE_EXEC_ENV", "absent"))
print(sys.argv[2])
print(sys.stdin.read(), end="")
print("program stderr", file=sys.stderr)
sys.exit(7)
''')
    effects = p.directory / "corruption-effects"
    arguments = [str(effects), "literal $`'"]
    stdin = b"stdin survives failed exec\n"
    p.remove_entries()
    p.pair(source, "corruption prime", arguments=arguments, stdin=stdin)
    entries = p.entry_files()
    executables = [x for x in entries if x.read_bytes()[:4] == b"\x7fELF"]
    p.check(len(executables) == 1, f"expected one new cached executable, found {executables}")
    executable = executables[0]
    data = executable.read_bytes()
    before_stat = executable.stat()
    executable.write_bytes(b"!" + data[1:])
    os.utime(executable, ns=(before_stat.st_atime_ns, before_stat.st_mtime_ns))
    p.pair(source, "corrupt executable", arguments=arguments, stdin=stdin)
    metadata = [x for x in p.entry_files() if x.suffix == ".manifest"]
    p.check(bool(metadata), "no manifest found beside cached executable")
    for path in metadata:
        path.write_bytes(b"incomplete\n")
    p.pair(source, "incomplete manifest", arguments=arguments, stdin=stdin)
    for path in p.entry_files():
        if path.suffix == ".exe":
            path.unlink()
    p.pair(source, "missing executable", arguments=arguments, stdin=stdin)

    metadata = [x for x in p.entry_files() if x.suffix == ".manifest"]
    p.check(len(metadata) == 1, "exec-failure control requires one complete manifest")
    index = metadata[0]
    original_manifest = index.read_text()
    fields = pc._document(str(index), pc.MAGIC)
    p.check(len(fields) >= 2, "exec-failure control could not decode the complete manifest")
    executable = index.with_name(index.stem + "-" + fields[1] + ".exe")
    data = executable.read_bytes()
    p.check(data[:6] == b"\x7fELF\x02\x01", "exec-failure control requires a little-endian ELF64 executable")
    # Keep the ELF otherwise valid while pointing its interpreter at a guaranteed
    # missing descriptor. This exercises ENOENT separately from truncated ENOEXEC.
    missing_interpreter = bytearray(data)
    phoff = int.from_bytes(data[32:40], "little")
    phsize = int.from_bytes(data[54:56], "little")
    phcount = int.from_bytes(data[56:58], "little")
    replaced = False
    for i in range(phcount):
        header = data[phoff + i * phsize:phoff + (i + 1) * phsize]
        if int.from_bytes(header[:4], "little") == 3:  # PT_INTERP
            offset = int.from_bytes(header[8:16], "little")
            size = int.from_bytes(header[32:40], "little")
            interpreter = b"/proc/self/fd/-1\0"
            p.check(size >= len(interpreter) and offset + size <= len(data),
                    "ELF interpreter field is too short or outside the executable")
            missing_interpreter[offset:offset + size] = interpreter.ljust(size, b"\0")
            replaced = True
            break
    p.check(replaced, "cached executable has no ELF interpreter to invalidate")
    for label, damaged, policy in (
            ("malformed ELF default", b"\x7fELFmalformed\n", None),
            ("malformed ELF explicit", b"\x7fELFmalformed\n", "1"),
            ("missing ELF interpreter", bytes(missing_interpreter), "")):
        # Both checksums and the filename agree, so lookup must accept the entry.
        # Failure happens only at the real kernel exec in the native driver.
        broken_fields = fields.copy()
        broken_fields[1] = pc.fnv(damaged.decode("latin-1"))
        broken = index.with_name(index.stem + "-" + broken_fields[1] + ".exe")
        broken.write_bytes(damaged)
        broken.chmod(0o700)
        payload = pc._pack(broken_fields)
        index.write_text(pc.MAGIC + pc.fnv(payload) + "\n" + payload)
        changes = {"PYSTACHY_PROGRAM_CACHE": policy, "CACHE_EXEC_ENV": label + " $`'"}
        expected = p.oracle(source, arguments, stdin=stdin, changes=changes)
        effects.write_bytes(b"")
        result = p.run(label, source, arguments, stdin=stdin, changes=changes)
        p.matches(result, expected, label)
        p.check(result.events == ["hit"], f"{label}: entry was not accepted before exec: {result.events}")
        p.check(result.tools.count("lli") == 1, f"{label}: ordinary fallback must execute exactly once")
        p.check(effects.read_bytes() == b"executed\n", f"{label}: duplicated or omitted program effects")

    executable.write_bytes(data)
    executable.chmod(0o700)
    index.write_text(original_manifest)
    expected = p.oracle(source, arguments, stdin=stdin)
    effects.write_bytes(b"")
    recovered = p.run("valid hit after exec failures", source, arguments, stdin=stdin)
    p.matches(recovered, expected, "valid hit after exec failures")
    p.hit(recovered, "valid hit after exec failures")
    p.check(effects.read_bytes() == b"executed\n", "recovered cached program did not execute exactly once")


def check_bypass(p: Probe) -> None:
    source = p.source("bypass", "import sys\nprint(sys.argv)\nprint(63)\n")
    expected = p.oracle(source)
    p.pair(source, "bypass prime", reference=expected)
    default = p.run("enabled by default", source, changes={"PYSTACHY_PROGRAM_CACHE": None})
    p.matches(default, expected, "default execution")
    p.hit(default, "unset setting enables caching")
    for flag in ("", "1"):
        selected = p.run("explicit cache setting", source, changes={"PYSTACHY_PROGRAM_CACHE": flag})
        p.matches(selected, expected, "explicit cache setting")
        p.hit(selected, "empty and explicit settings keep caching enabled")
    variants = [
        ("disabled", {"PYSTACHY_PROGRAM_CACHE": "0", "PYSTACHY_ARGV0": "/caller/not-the-compiler"}),
        ("custom C flags", {"PYSTACHY_CFLAGS": "-DCACHE_PROBE=1"}),
        ("IR checker", {"PYSTACHY_IRCHECK": "1"}),
        ("-O0 code generation", {"PYSTACHY_JIT_CODEGEN": "0", "PYSTACHY_ARGV0": "/caller/not-the-compiler"}),
    ]
    for label, env in variants:
        result = p.run(label, source, changes=env)
        p.matches(result, expected, label)
        p.check("hit" not in result.events and bool(result.tools),
                f"{label}: unexpectedly used native-program cache")
    output = p.directory / "ordinary-aot"
    built = p.launch("build bypass", p.command + ["build", str(source), "-o", str(output)])
    p.check(built.status == 0 and "hit" not in built.events and bool(built.tools),
            "ordinary build did not bypass the program cache")
    arguments = ["space here", "'quoted$argument`", ""]
    aot = p.launch("ordinary AOT", [str(output), *arguments], changes={"PYSTACHY_ARGV0": "/caller/not-the-program"})
    reference = p.launch("ordinary AOT argv reference", p.python + [
        "-c", "import sys; print(sys.argv[1:]); print(63)", str(output), *arguments])
    p.matches(aot, reference, "ordinary AOT keeps its actual argv with inherited PYSTACHY_ARGV0")
    extension = p.directory / "main.abi3.so"
    built = p.launch("extension bypass", p.command + ["ext", str(source), "-o", str(extension)])
    p.check(built.status == 0 and extension.is_file() and "hit" not in built.events and bool(built.tools),
            "extension build did not bypass the program cache")


def check_settings(p: Probe) -> None:
    # #1168: a hit must reproduce what its settings compile, and their errors.
    # Line tables get an entry of their own. An empty setting is not an unset
    # one: it fails as uncached compilation does instead of reusing that entry.
    source = p.source("settings", "def twice(n: int) -> int:\n    return n * 2\n\n\nprint(twice(21))\n")
    expected = p.oracle(source)
    p.pair(source, "settings prime", reference=expected)
    before = set(p.entry_files())
    p.pair(source, "line tables", reference=expected, changes={"PYSTACHY_DEBUG_LINES": "1"})
    added = [path for path in set(p.entry_files()) - before if path.suffix == ".exe"]
    p.check(len(added) == 1 and b".debug_line\0" in added[0].read_bytes(),
            f"line tables: expected one new executable with .debug_line: {added}")
    # (LLVM's -O2 pipeline in place of the JIT's cleanup: an entry of its own, which a default run
    # never reuses)
    p.pair(source, "JIT -O2 pipeline", reference=expected, changes={"PYSTACHY_JIT_OPT": "2"})
    scratch = p.directory / "settings-tmp"
    scratch.mkdir()
    for key in ("PYSTACHY_JIT_INLINE", "PYSTACHY_JIT_OPT", "PYSTACHY_RUNTIME_C_CACHE"):
        changes = {key: "", "TMPDIR": str(scratch)}
        for attempt in range(2):
            uncached = p.run(f"empty {key} uncached {attempt}", source, changes={**changes, "PYSTACHY_PROGRAM_CACHE": "0"})
            p.check(uncached.status == 1 and key.encode() in uncached.stderr,
                    f"uncached compilation accepted an empty {key}: {uncached.observable!r}")
            p.check(not list(scratch.iterdir()), f"empty {key} uncached: temporary files remain")
            result = p.run(f"empty {key} {attempt}", source, changes=changes)
            p.matches(result, uncached, f"empty {key}")
            p.check("hit" not in result.events, f"empty {key}: a hit hid the uncached error")
            p.check(not list(scratch.iterdir()), f"empty {key}: temporary files remain")


def check_tool_identity(p: Probe) -> None:
    source = p.source("tool", "print(71)\n")
    p.pair(source, "tool identity prime")
    p.same_size_edit(p.bindir / "opt", b"# identity-marker-A", b"# identity-marker-B")
    time.sleep(2.05)
    p.pair(source, "tool same-size edit")


def check_compiler_identity(p: Probe) -> None:
    source = p.source("compiler", "print(73)\n")
    original = p.command
    copy = p.directory / "compiler-copy"
    data = Path(original[0]).read_bytes()
    p.check(data[:4] == b"\x7fELF", "compiler identity check requires a native ELF executable")
    copy.write_bytes(data + b"\nPROGRAM_CACHE_COMPILER_A\n")
    copy.chmod(0o755)
    p.command = [str(copy), *original[1:]]
    time.sleep(2.05)
    try:
        p.pair(source, "copied compiler")
        p.same_size_edit(copy, b"PROGRAM_CACHE_COMPILER_A", b"PROGRAM_CACHE_COMPILER_B")
        time.sleep(2.05)
        p.pair(source, "compiler same-size edit")
    finally:
        p.command = original


def check_runtime_identity(p: Probe) -> None:
    source = p.source("runtime", "print(79)\n")
    home = p.directory / "runtime-home"
    home.mkdir()
    for name in ("runtime.c", "runtime.py", "VERSION", "REVISION", "pyembed.c", "pyext.c"):
        if (p.home / name).exists():
            shutil.copy2(p.home / name, home / name)
    for name in ("ryu", "mpz"):
        shutil.copytree(p.home / name, home / name)
    (home / "lib").symlink_to(p.home / "lib", target_is_directory=True)
    runtime = home / "runtime.c"
    runtime.write_bytes(runtime.read_bytes() + b"\n/* program-cache-runtime-A */\n")
    changes = {"PYSTACHY_HOME": str(home)}
    p.pair(source, "runtime identity prime", changes=changes)
    p.same_size_edit(runtime, b"program-cache-runtime-A", b"program-cache-runtime-B")
    p.pair(source, "runtime same-size edit", changes=changes)


def check_failures(p: Probe) -> None:
    source = p.source("failure", "print(undefined_cache_probe)\n")
    failed = p.run("failed frontend", source)
    p.check(failed.status != 0 and "hit" not in failed.events,
            "invalid source was executed or accepted")
    p.write(source, "print(83)\n")
    p.pair(source, "recovered frontend failure")
    backend = p.source("backend-failure", 'import os\nprint(89)\nprint(os.getenv("PYSTACHY_PROGRAM_CACHE", "unset"))\nprint(os.getenv("PYSTACHY_PROGRAM_CACHE_LOCK", "absent"))\n')
    p.fail.touch()
    result = p.run("failed cache codegen", backend)
    p.fail.unlink()
    p.check("hit" not in result.events, "failed build unexpectedly hit")
    if result.status == 0:
        p.matches(result, p.oracle(backend), "failed cache build fallback")
    p.pair(backend, "recovered backend failure")


def check_concurrency(p: Probe) -> None:
    source = p.source("concurrent", "print(97)\n")
    expected = p.oracle(source)
    command = p.command + ["run", str(source)]
    processes = []
    events = []
    started = time.perf_counter()
    try:
        for _ in range(2):
            processes.append(subprocess.Popen(command, cwd=p.directory, env=p.environment(),
                                              stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                              stderr=subprocess.PIPE, start_new_session=True))
        for index, process in enumerate(processes):
            stdout, stderr = process.communicate(timeout=p.args.timeout)
            result = Run(command, process.returncode, stdout, stderr,
                         time.perf_counter() - started, [])
            p.runs.append({"label": f"concurrent miss {index}", **result.record()})
            p.matches(result, expected, f"concurrent miss {index}")
            events.extend(result.events)
    finally:
        for process in processes:
            kill_owned_group(process)
            process.communicate()
    p.check(events.count("frontend") == 1, "concurrent identical misses compiled more than once")
    p.check(events.count("stored") == 1 and events.count("hit") == 1,
            f"waiter did not reuse the completed entry: {events}")
    result = p.run("hit after concurrent publication", source)
    p.matches(result, expected, "concurrent publication")
    p.hit(result, "concurrent publication")


def check_signals(p: Probe) -> None:
    source = p.source("signal", 'import time\nprint("ready", flush=True)\ntime.sleep(30.0)\n')
    for index in range(2):
        command = p.command + ["run", str(source)]
        before = len(p.calls())
        start = time.perf_counter()
        process = subprocess.Popen(command, cwd=p.directory, env=p.environment(),
                                   stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, start_new_session=True)
        output = b""
        try:
            deadline = time.monotonic() + p.args.timeout
            while b"ready\n" not in output and time.monotonic() < deadline:
                readable, _, _ = select.select([process.stdout], [], [], 0.1)
                if readable:
                    part = os.read(process.stdout.fileno(), 4096)
                    if not part:
                        break
                    output += part
            p.check(b"ready\n" in output, "signal fixture did not reach runtime")
            process.send_signal(signal.SIGTERM)
            stdout, stderr = process.communicate(timeout=10)
            result = Run(command, process.returncode, output + stdout, stderr,
                         time.perf_counter() - start, p.calls()[before:])
            p.runs.append({"label": f"signal {'hit' if index else 'miss'}", **result.record()})
            p.check(result.status == -signal.SIGTERM, "signal status did not survive exec")
            p.check(result.stdout == b"ready\n", "signal fixture duplicated initialization")
            if index:
                p.hit(result, "signal hit")
            else:
                p.miss(result, "signal miss")
        finally:
            kill_owned_group(process)
            process.communicate()


def check_source_race(p: Probe) -> None:
    source = p.source("source-race", "import racing\nprint(racing.VALUE)\n")
    helper = p.write(source.parent / "racing.py", "VALUE = 111\n")
    p.ready.unlink(missing_ok=True)
    p.pause.touch()
    command = p.command + ["run", str(source)]
    process = subprocess.Popen(command, cwd=p.directory, env=p.environment(),
                               stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, start_new_session=True)
    start = time.perf_counter()
    try:
        deadline = time.monotonic() + p.args.timeout
        while not p.ready.exists() and process.poll() is None and time.monotonic() < deadline:
            time.sleep(0.02)
        p.check(p.ready.exists(), "source-race control did not reach native codegen")
        p.same_size_edit(helper, b"111", b"222")
        p.pause.unlink()
        stdout, stderr = process.communicate(timeout=p.args.timeout)
        result = Run(command, process.returncode, stdout, stderr, time.perf_counter() - start, [])
        p.runs.append({"label": "dependency changed during codegen", **result.record()})
        p.check(result.status == 0 and result.stdout == b"111\n",
                "in-flight build did not execute its captured source")
    finally:
        p.pause.unlink(missing_ok=True)
        kill_owned_group(process)
        process.communicate()
    shutil.rmtree(source.parent / "__pycache__", ignore_errors=True)
    p.pair(source, "source after race")


def check_interruption(p: Probe) -> None:
    source = p.source("interrupted", "print(101)\n")
    p.ready.unlink(missing_ok=True)
    p.pause.touch()
    command = p.command + ["run", str(source)]
    process = subprocess.Popen(command, cwd=p.directory, env=p.environment(),
                               stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, start_new_session=True)
    start = time.perf_counter()
    try:
        deadline = time.monotonic() + p.args.timeout
        while not p.ready.exists() and process.poll() is None and time.monotonic() < deadline:
            time.sleep(0.02)
        p.check(p.ready.exists(), "interruption control did not reach native codegen")
        kill_owned_group(process)
        stdout, stderr = process.communicate(timeout=10)
        result = Run(command, process.returncode, stdout, stderr, time.perf_counter() - start, [])
        p.runs.append({"label": "killed during native codegen", **result.record()})
        p.check(result.status != 0 and "hit" not in result.events, "killed build was accepted")
    finally:
        p.pause.unlink(missing_ok=True)
        kill_owned_group(process)
        process.communicate()
    p.pair(source, "recovered interrupted build")


CHECKS = {
    "reuse": check_reuse,
    "source": check_source_content,
    "imports": check_imports,
    "regular-import-files": check_regular_import_files,
    "semantics": check_semantics,
    "corruption": check_corruption,
    "bypass": check_bypass,
    "settings": check_settings,
    "tool": check_tool_identity,
    "compiler": check_compiler_identity,
    "runtime": check_runtime_identity,
    "failures": check_failures,
    "concurrency": check_concurrency,
    "signals": check_signals,
    "source-race": check_source_race,
    "interruption": check_interruption,
}


def benchmark(p: Probe) -> list[dict]:
    tiny = p.source("bench-tiny", "print(1)\n")
    padded = p.source("bench-padded", "\n".join(
        f"def helper_{i}(x: int) -> int:\n    return x + {i}\n" for i in range(600))
        + "print(helper_599(4))\n")
    imports = p.source("bench-imports", '''import re
import textwrap
import json
import fnmatch
print(textwrap.fill("one two three four five", width=9))
print(re.findall("[a-z]+", "one1two2three3"))
print(json.dumps([1, 2, 3]))
print(fnmatch.fnmatchcase("worker.py", "*.py"))
''')
    rules = p.write(p.directory / "rules.txt", "api.* backend\nworker.* jobs\n*.error errors\n")
    events = p.write(p.directory / "events.txt", "".join(
        f"{name}\tpayload {i}\n" for i in range(250)
        for name in ("api.read", "worker.run", "app.error", "ignored")))
    workloads = [("tiny", tiny, []), ("padded-helper", padded, []),
                 ("import-heavy", imports, []),
                 ("router-1000-events", p.home / "examples/route/route.py",
                  [str(rules), str(events), "--names"])]
    output = []
    for name, path, arguments in workloads:
        expected = p.oracle(path, arguments)
        p.check(expected.status == 0 and not expected.stderr, f"{name}: CPython reference failed")
        # The checked-toolchain and ordinary runtime entries have separate
        # lineages. Warm both before measuring cold program entries.
        warmup = p.run(name + ":runtime-warmup", path, arguments,
                       changes={"PYSTACHY_PROGRAM_CACHE": "0"})
        p.matches(warmup, expected, name + " warmup")
        executable = p.directory / ("aot-" + name)
        built = p.launch(name + ":aot-build", p.command + ["build", str(path), "-o", str(executable)],
                         changes={"PYSTACHY_PROGRAM_CACHE": "0"})
        p.check(built.status == 0 and executable.is_file(), f"{name}: AOT build failed")
        cached_warmup = p.run(name + ":checked-runtime-warmup", path, arguments)
        p.matches(cached_warmup, expected, name + " checked runtime warmup")
        # One separately reported fill includes the initial identity hashing.
        # Recurring misses below retain that memo, as subsequent programs do.
        p.remove_entries()
        first_use = p.run(name + ":first-use-fill", path, arguments)
        p.matches(first_use, expected, name + " first-use fill")
        p.miss(first_use, name + " first-use fill")
        p.check("llvm-as" not in first_use.tools, name + ": first-use sample unexpectedly rebuilt the runtime")
        modes: dict[str, list[float]] = {k: [] for k in ("uncached-run", "cold-program", "cache-hit", "prebuilt-aot")}
        for round_number in range(p.args.rounds):
            # Reverse the non-cache controls on alternating rounds. Cold/hit
            # remain adjacent so the hit always has a known, checked producer.
            order = ["uncached-run", "cache-pair", "prebuilt-aot"]
            if round_number & 1:
                order.reverse()
            for mode in order:
                if mode == "cache-pair":
                    p.remove_entries(keep_identity=True)
                    cold, hit = p.pair(path, f"{name}:round-{round_number}",
                                       arguments=arguments, reference=expected)
                    modes["cold-program"].append(cold.seconds)
                    modes["cache-hit"].append(hit.seconds)
                elif mode == "uncached-run":
                    result = p.run(f"{name}:round-{round_number}:uncached", path, arguments,
                                   changes={"PYSTACHY_PROGRAM_CACHE": "0"})
                    p.matches(result, expected, name + " uncached")
                    modes[mode].append(result.seconds)
                else:
                    result = p.launch(f"{name}:round-{round_number}:aot", [str(executable), *arguments])
                    p.matches(result, expected, name + " AOT")
                    modes[mode].append(result.seconds)
        row = {"name": name, "source": str(path), "source_sha256": digest(path.read_bytes()),
               "arguments": arguments, "samples_seconds": modes,
               "median_seconds": {k: statistics.median(v) for k, v in modes.items()},
               "first_use_fill_seconds": first_use.seconds,
               "first_use_fill_tools": dict(Counter(first_use.tools)),
               "aot_build_seconds": built.seconds}
        row["paired_hit_speedup"] = statistics.median(
            a / b for a, b in zip(modes["uncached-run"], modes["cache-hit"], strict=True))
        output.append(row)
        print(f"BENCH {name}: {row['median_seconds']}", flush=True)
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", default=str(ROOT / "pystachy"))
    parser.add_argument("--llvm", default=os.environ.get("PYSTACHY_LLVM", ""))
    parser.add_argument("--home", default=str(ROOT))
    parser.add_argument("--python", default=shlex.quote(sys.executable))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--checks", nargs="+", choices=tuple(CHECKS))
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--benchmark", action="store_true")
    parser.add_argument("--benchmark-only", action="store_true")
    parser.add_argument("--rounds", type=int, default=5)
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--cpu", type=int)
    parser.add_argument("--keep-temp", action="store_true")
    args = parser.parse_args()
    if args.list:
        print("\n".join(CHECKS))
        return 0
    if args.rounds < 1 or args.timeout <= 0:
        parser.error("--rounds and --timeout must be positive")
    if args.output is None:
        parser.error("--output is required so raw validation evidence is retained")
    if args.cpu is not None:
        os.sched_setaffinity(0, {args.cpu})
    directory = Path(tempfile.mkdtemp(prefix="pystachy-program-cache-"))
    report: dict = {"schema": "pystachy-program-cache-probe-v1", "platform": platform.platform(),
                    "python": sys.version, "cpu_affinity": sorted(os.sched_getaffinity(0)),
                    "temporary_directory": str(directory), "rounds": args.rounds,
                    "benchmarks": [], "setup_error": None, "completed": False,
                    "expected_checks": [] if args.benchmark_only else list(args.checks or CHECKS),
                    "benchmark_scopes": {
                        "first_use_fill": "One sample per workload: program-v2 empty; runtime artifacts warm.",
                        "cold_program": "Manifests, executables and stages removed; static-hashes and runtime artifacts warm.",
                        "cache_hit": "Fresh process after a checked cold-program producer; no frontend or LLVM calls.",
                        "uncached_run": "Program cache disabled; runtime artifacts warm.",
                        "prebuilt_aot": "Fresh process from the ordinary AOT tier; its build time is reported separately.",
                    }}
    probe = None
    try:
        probe = Probe(args, directory)
        report["compiler"] = probe.command
        report["compiler_sha256"] = digest(Path(probe.command[0]).read_bytes())
        report["home"] = str(probe.home)
        report["llvm"] = probe.real
        report["declared_toolchain_inputs"] = probe.env["PYSTACHY_PROGRAM_CACHE_INPUTS"].split(":")
        report["llvm_version"] = subprocess.check_output([probe.real["clang"], "--version"], text=True)
        if not args.benchmark_only:
            for name in args.checks or CHECKS:
                probe.run_check(name, CHECKS[name])
        if args.benchmark or args.benchmark_only:
            report["benchmarks"] = benchmark(probe)
        report["completed"] = True
    except Exception as error:
        report["setup_error"] = str(error)
        report["traceback"] = traceback.format_exc()
        print(f"ERROR: {error}", file=sys.stderr)
    finally:
        if probe is not None:
            report.update({"checks": probe.checks, "runs": probe.runs,
                           "source_inputs": probe.sources, "assertions": probe.assertions})
        report["passed"] = (report["completed"] and report["setup_error"] is None
                            and [c["name"] for c in report.get("checks", [])] == report["expected_checks"]
                            and all(c["passed"] for c in report.get("checks", [])))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n")
        if not args.keep_temp:
            shutil.rmtree(directory)
    print(f"{'PASS' if report['passed'] else 'FAIL'}: {report.get('assertions', 0)} assertions; {args.output}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
