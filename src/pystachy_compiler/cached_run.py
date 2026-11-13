"""Bounded Linux native-program cache integration for the CLI driver."""
from __future__ import annotations
import os
import sys
import tempfile
import time
from src.pystachy_compiler import cache_toolchain, program_cache as pc
from src.pystachy_compiler.specs import PLATFORM
try:
    from _pystachy_cache import NATIVE, try_lock  # type: ignore[import-not-found]
except ImportError:
    NATIVE = False

    def try_lock(path: str) -> int:
        return -1


# These can add unrecorded compiler/linker inputs. Ordinary program environment
# variables remain runtime inputs and are deliberately absent from the key.
BUILD_ENV: list[str] = [
    "CPATH", "C_INCLUDE_PATH", "CPLUS_INCLUDE_PATH", "OBJC_INCLUDE_PATH",
    "LIBRARY_PATH", "COMPILER_PATH", "GCC_EXEC_PREFIX", "SDKROOT",
    "CCC_OVERRIDE_OPTIONS", "CLANG_CONFIG_FILE_SYSTEM_DIR",
    "CLANG_CONFIG_FILE_USER_DIR", "LD_PRELOAD", "LD_LIBRARY_PATH",
    "LD_AUDIT", "LD_RUN_PATH", "LD_HWCAP_MASK", "GLIBC_TUNABLES",
    "LDEMULATION", "GNUTARGET",
]
# Settings that change what a miss builds, or whether it builds at all. A hit
# must reproduce uncached results and errors, and an empty value can differ
# from an unset one (PYSTACHY_JIT_INLINE= is rejected), so the key spells each
# as its environment entry, NAME=VALUE, or as NAME alone when it is unset.
# docs/program-cache.md classifies every setting a compilation reads.
KEYED_ENV: list[str] = [
    "PYSTACHY_OPT", "PYSTACHY_JIT_INLINE", "PYSTACHY_JIT_OPT", "PYSTACHY_DEBUG_LINES",
    "PYSTACHY_RUNTIME_C_CACHE", "PYSTACHY_PATH", "PYSTACHY_PROGRAM_CACHE_INPUTS",
    "PATH", "HOME", "XDG_CONFIG_HOME",
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


def acquire(program_root: str, context: str) -> bool:
    # A bounded set of permanent flock files avoids both stale PID ownership
    # and unlinking a lock while another process is waiting on its inode.
    # program_root has already passed the private-directory admission check.
    bucket = pc.fnv(context)[:2]
    lock = pc._bucket_lock(program_root, bucket)
    if lock == "":
        return False
    if NATIVE:
        result = try_lock(lock)
        if result != 0:
            return result == 1
        deadline = time.monotonic() + 30.0
        while time.monotonic() < deadline:
            time.sleep(0.01)
            result = try_lock(lock)
            if result != 0:
                return result == 1
        return False
    # prepare() already requires the native compiler. Without its private
    # lock primitive, bypass caching rather than assigning an inherited fd.
    return False


def declared_tools(llvm: str) -> bool:
    if os.getenv("PYSTACHY_PROGRAM_CACHE_INPUTS", "") != "":
        return True  # Explicit contract for wrappers and their hidden inputs.
    try:
        for name in ["clang", "opt", "llvm-as", "llvm-link", "lli"]:
            f = open(llvm + "/" + name, "r", encoding="latin-1", newline="")
            first = f.read(4)
            f.close()
            if first != "\x7fELF":
                return False
        return True
    except (OSError, ValueError):
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
                status = os.system("/usr/bin/ldd " + " ".join([quote(p) for p in tools]) + " > " + quote(shared) + " 2> /dev/null")
                loaded = 0
                for line in read_raw(shared).split("\n"):
                    for word in line.split():
                        if word.startswith("/") and os.path.isfile(word):
                            pc.track_static(word)
                            loaded += 1
                for p in tools:
                    pc.track_static(p)
                for p in os.getenv("PYSTACHY_PROGRAM_CACHE_INPUTS", "").split(":"):
                    if p != "":
                        pc.track_static(p)
                ok = loaded > 0 and (status == 0 or os.getenv("PYSTACHY_PROGRAM_CACHE_INPUTS", "") != "")
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
    if (cmd != "run" or os.getenv("PYSTACHY_PROGRAM_CACHE", "") not in ["", "1"]
            or os.getenv("PYSTACHY_PROGRAM_CACHE_LOCK", "") == "bypass"):
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
        if not declared_tools(llvm):
            trace("bypass undeclared tool wrapper")
            return ("", "", "")
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
        fields = ["jit-executable-v3", source, os.getcwd(), me, os.path.realpath(me),
                  home, os.path.realpath(home), llvm, os.path.realpath(llvm)]
        for d in dirs:
            fields += [d, os.path.realpath(d)]
        # BUILD_ENV's nonempty values bypassed above. Tools treat an empty one
        # as set too: GNU ld rejects GNUTARGET= and adds a RUNPATH for LD_RUN_PATH=.
        for k in KEYED_ENV + BUILD_ENV:
            v = os.getenv(k, "\0")  # (no environment value holds a NUL: unset)
            fields.append(k if v == "\0" else k + "=" + v)
        fields += [line for line in cpu]
        # Length delimiters keep arbitrary source/import path spelling distinct.
        context = "".join([str(len(x)) + ":" + x for x in fields])
        root = os.getenv("PYSTACHY_CACHE", "") or home + "/build"
        program_root = pc._cache_dir(root)
        if program_root == "" or not acquire(program_root, context):
            trace("bypass cache lock unavailable")
            return ("", "", "")
        hit = pc.lookup_in(program_root, context)
        if hit != "":
            trace("hit")
            return (root, context, hit)
        pc.start()
        pc.track_layout(cache_toolchain.capture(llvm))
        if not pc.VALID[0]:
            pc.stop()
            trace("bypass toolchain search layout unavailable")
            return ("", "", "")
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
    # Pin before releasing the bucket. Direct exec exposes ENOEXEC, EACCES,
    # ETXTBSY and a missing ELF interpreter as OSError, before any program runs.
    # A shell's exec special builtin exits instead and cannot perform fallback.
    stress = os.getenv("PYSTACHY_GC_STRESS_PROGRAM", "")
    saved_stress = os.getenv("PYSTACHY_GC_STRESS", "\0")
    try:
        f = open(executable, "r", encoding="latin-1", newline="")
        try:
            # Acquisition marks its own lock descriptor close-on-exec. The
            # kernel opens the pinned ELF before closing the lock.
            os.environ.pop("PYSTACHY_PROGRAM_CACHE_LOCK", "")
            if stress != "":
                os.environ.__setitem__("PYSTACHY_GC_STRESS", stress)
            os.execv("/proc/self/fd/" + str(f.fileno()), [source] + args)
        finally:
            f.close()
    except (OSError, ValueError):
        if saved_stress == "\0":
            os.environ.pop("PYSTACHY_GC_STRESS", "")
        else:
            os.environ.__setitem__("PYSTACHY_GC_STRESS", saved_stress)
        os.environ.__setitem__("PYSTACHY_PROGRAM_CACHE_LOCK", "bypass")
        os.execv(sys.argv[0], sys.argv)
