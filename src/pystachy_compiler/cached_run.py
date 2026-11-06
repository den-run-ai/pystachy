"""Bounded Linux native-program cache integration for the CLI driver."""
from __future__ import annotations
import os
import sys
import tempfile
from src.pystachy_compiler import program_cache as pc
from src.pystachy_compiler.specs import PLATFORM


# These can add unrecorded compiler/linker inputs. Ordinary program environment
# variables remain runtime inputs and are deliberately absent from the key.
BUILD_ENV: list[str] = [
    "CPATH", "C_INCLUDE_PATH", "CPLUS_INCLUDE_PATH", "OBJC_INCLUDE_PATH",
    "LIBRARY_PATH", "COMPILER_PATH", "GCC_EXEC_PREFIX", "SDKROOT",
    "CCC_OVERRIDE_OPTIONS", "CLANG_CONFIG_FILE_SYSTEM_DIR",
    "CLANG_CONFIG_FILE_USER_DIR", "LD_PRELOAD", "LD_LIBRARY_PATH",
]
CPU_FIELDS: list[str] = [
    "vendor_id", "cpu family", "model", "model name", "stepping", "flags",
    "CPU implementer", "CPU architecture", "CPU variant", "CPU part",
    "CPU revision", "Features",
]


def quote(s: str) -> str:
    return "'" + s.replace("'", "'\\''") + "'"


def trace(message: str) -> None:
    if os.getenv("PYSTACHY_PROGRAM_CACHE_TRACE", "") == "1":
        print("pystachy program cache: " + message, file=sys.stderr)


def read_raw(path: str) -> str:
    f = open(path, "r", encoding="latin-1", newline="")
    text = f.read()
    f.close()
    return text


def native_compiler(me: str) -> bool:
    try:
        return not me.endswith(".py") and "/" in me and os.path.samefile(me, "/proc/self/exe")
    except OSError:
        return False


def dep_paths(text: str) -> list[str]:
    # clang -M's one fixed target, followed by Make-escaped prerequisites. This
    # parser handles spaces, backslashes and continuations without using a shell.
    if not text.startswith("cache:"):
        return []
    paths: list[str] = []
    word = ""
    i = 6
    while i < len(text):
        c = text[i]
        if c == "\\":
            i += 1
            if i == len(text):
                return []
            if text[i] != "\n":
                word += text[i]
        elif c.isspace():
            if word != "":
                paths.append(word)
                word = ""
        elif c == "$" and i + 1 < len(text) and text[i + 1] == "$":
            word += "$"
            i += 1
        else:
            word += c
        i += 1
    if word != "":
        paths.append(word)
    return paths


def tool_inputs(home: str, llvm: str, me: str, parts: list[str]) -> bool:
    # Record the default toolchain's actual headers and loaded shared libraries
    # on a miss. A hit checks these records without invoking LLVM or the loader.
    tmp = tempfile.mkdtemp()
    ok = False
    deps = tmp + "/headers"
    shared = tmp + "/shared"
    try:
        cmd = quote(llvm + "/clang") + " -M -MT cache " + quote(home + "/runtime.c")
        if os.system(cmd + " > " + quote(deps) + " 2> /dev/null") == 0:
            paths = dep_paths(read_raw(deps))
            if len(paths) > 0:
                for p in [me, home + "/runtime.py", "/usr/bin/ld"] + parts + paths:
                    pc.track_static(p)
                # ldd reports a nonzero status for a transparent tool wrapper;
                # its file remains an input. Extra wrapper dependencies may be
                # declared through PYSTACHY_PROGRAM_CACHE_INPUTS.
                tools = [me] + [llvm + "/" + t for t in ["clang", "opt", "llvm-as", "llvm-link", "lli"]]
                os.system("ldd " + " ".join([quote(p) for p in tools]) + " > " + quote(shared) + " 2> /dev/null")
                for line in read_raw(shared).split("\n"):
                    for word in line.split():
                        if word.startswith("/") and os.path.isfile(word):
                            pc.track_static(word)
                for p in tools:
                    pc.track_static(p)
                for p in os.getenv("PYSTACHY_PROGRAM_CACHE_INPUTS", "").split(":"):
                    if p != "":
                        pc.track_static(p)
                ok = True
    except (OSError, ValueError):
        ok = False
    for p in [deps, shared]:
        if os.path.exists(p):
            os.remove(p)
    os.rmdir(tmp)
    return ok


def prepare(cmd: str, source: str, me: str, home: str, dirs: list[str], llvm: str,
            parts: list[str]) -> tuple[str, str, str]:
    pc.stop()
    if cmd != "run" or os.getenv("PYSTACHY_PROGRAM_CACHE", "") != "1":
        return ("", "", "")
    reason = ""
    if PLATFORM != "linux":
        reason = "Linux only"
    elif not native_compiler(me):
        reason = "native compiler path required"
    elif not llvm.startswith("/"):
        reason = "absolute LLVM directory required"
    elif os.getenv("PYSTACHY_JIT_CODEGEN", "2") != "2":
        reason = "default ORC tier required"
    elif os.getenv("PYSTACHY_CFLAGS", "") != "":
        reason = "custom CFLAGS"
    elif any(os.getenv(k, "") != "" for k in ["PYSTACHY_IRCHECK", "PYSTACHY_IRFX", "PYSTACHY_UNICODE_AUDIT"]):
        reason = "compiler diagnostics requested"
    elif any(os.getenv(k, "") != "" for k in BUILD_ENV):
        reason = "custom build environment"
    elif not os.path.exists("/proc/cpuinfo") or not os.path.isfile("/usr/bin/ld"):
        reason = "host identity unavailable"
    if reason != "":
        trace("bypass " + reason)
        return ("", "", "")
    try:
        # A clang configuration file can introduce flags/inputs absent above.
        if any(p.endswith(".cfg") for p in os.listdir(os.path.realpath(llvm))):
            trace("bypass clang configuration")
            return ("", "", "")
        cpu: dict[str, bool] = {}
        for line in read_raw("/proc/cpuinfo").split("\n"):
            if line.split(":")[0].strip() in CPU_FIELDS:
                cpu[line] = True
        if len(cpu) == 0:
            trace("bypass CPU identity unavailable")
            return ("", "", "")
        fields = ["jit-executable-v1", source, os.getcwd(), me, os.path.realpath(me),
                  home, os.path.realpath(home), llvm, os.path.realpath(llvm)]
        for d in dirs:
            fields += [d, os.path.realpath(d)]
        for k in ["PYSTACHY_OPT", "PYSTACHY_JIT_INLINE", "PYSTACHY_PATH", "PATH", "PYSTACHY_PROGRAM_CACHE_INPUTS"]:
            fields += [k, os.getenv(k, "")]
        fields += [line for line in cpu]
        # Length delimiters keep arbitrary source/import path spelling distinct.
        context = "".join([str(len(x)) + ":" + x for x in fields])
        root = os.getenv("PYSTACHY_CACHE", "") or home + "/build"
        hit = pc.lookup(root, context)
        if hit != "":
            trace("hit")
            return (root, context, hit)
        pc.start()
        if not tool_inputs(home, llvm, me, [home + "/" + p for p in parts]):
            pc.stop()
            trace("bypass toolchain inputs unavailable")
            return ("", "", "")
        trace("miss")
        return (root, context, "")
    except (OSError, ValueError):
        pc.stop()
        trace("bypass cache unavailable")
        return ("", "", "")


def link_inputs(path: str, obj: str, runtime: str) -> bool:
    # GNU ld --trace reports opened inputs, including CRT objects, linker scripts,
    # libc, libm and libgcc. Ephemeral program/runtime objects are already keyed
    # by their compiler/source inputs and are not dependencies of later launches.
    try:
        found = 0
        for line in read_raw(path).split("\n"):
            if line == "" or line == obj or line == runtime:
                continue
            if not line.startswith("/") or not os.path.isfile(line):
                return False
            pc.track_static(line)
            found += 1
        return found > 0
    except (OSError, ValueError):
        return False


def same_link_inputs(first: str, second: str) -> bool:
    try:
        return read_raw(first) == read_raw(second)
    except (OSError, ValueError):
        return False


def execute(executable: str, source: str, args: list[str]) -> None:
    # The shell becomes the executable: output, exit status, signals and stdin
    # belong to a fresh program process, as with the ordinary lli launch.
    stress = os.getenv("PYSTACHY_GC_STRESS_PROGRAM", "")
    env = "PYSTACHY_GC_STRESS=" + quote(stress) + " " if stress != "" else ""
    command = env + "PYSTACHY_ARGV0=" + quote(source) + " exec " + quote(executable)
    command += " " + " ".join([quote(a) for a in args])
    os.execv("/bin/sh", ["sh", "-c", command])
