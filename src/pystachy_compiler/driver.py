"""Driver component of the self-hosting Pystachy compiler."""
from __future__ import annotations
import os
import sys
import tempfile
import time
from src.pystachy_compiler import cached_run, diagnostics, program_cache
from src.pystachy_compiler.diagnostics import MAXNEST, RAW, NeedSliceEH, Rejoin, fail
from src.pystachy_compiler.gen import Gen
from src.pystachy_compiler.lexer import Lexer
from src.pystachy_compiler.loader import Loader
from src.pystachy_compiler.lower_module import OBJHOOKS, OBJHOOKS_MAIN, address_runtime_ir, jit_alloc
from src.pystachy_compiler.names import RENAMED
from src.pystachy_compiler.parser import Parser
from src.pystachy_compiler.specs import JIT_INLINE, LIBS, LINKDL, MODULES, OPTS, PLATFORM
from src.pystachy_compiler.syntax import LAMBDAS
from src.pystachy_compiler.utils import optimizations, timing_end, timing_start
try:
    # A native-only primitive; the CPython-hosted compiler asks its signal module.
    from _pystachy_cache import ignored_signals as native_ignored_signals  # type: ignore[import-not-found]
except ImportError:
    def native_ignored_signals() -> int:
        return 0


JOINS = 8  # the passes after the first that a program's joins may take (see compile_program)
# allocelide's late step (#1017), for an AOT build or extension module whose IR calls pys_new: once
# -O2 has deleted the allocations whose objects nothing keeps, opt's forceattrs makes runtime.c's
# out-of-line pys_new always inline, and always-inline puts it, the allocator's fast path, into each
# call that -O2 left. A runtime compiled with PYSTACHY_CFLAGS=-O0 gives pys_new optnone as well,
# which LLVM allows only beside noinline: forceattrs removes both, optnone first. LLVM 23's
# forceattrs adds an attribute before it removes one, skips alwaysinline beside noinline or optnone,
# and keeps noinline beside optnone, so the first of two passes removes them and the second adds
# alwaysinline (where LLVM 18 to 22 do all in the first): LATE_PASSES
LATE_INLINE = ("-force-remove-attribute=pys_new:optnone -force-remove-attribute=pys_new:noinline"
               " -force-attribute=pys_new:alwaysinline")
LATE_PASSES = "forceattrs,forceattrs,always-inline"

# Every hosted component contributes to runtime-cache identity and startup trust.
COMPILER_SOURCES: list[str] = [
    'lib/_pystachy_cache.py',
    'src/__init__.py',
    'src/pystachy_compiler/__init__.py',
    'src/pystachy_compiler/analysis.py',
    'src/pystachy_compiler/argparse_schema.py',
    'src/pystachy_compiler/ctypes_schema.py',
    'src/pystachy_compiler/bigints.py',
    'src/pystachy_compiler/builtins.py',
    'src/pystachy_compiler/calls.py',
    'src/pystachy_compiler/cached_run.py',
    'src/pystachy_compiler/cache_toolchain.py',
    'src/pystachy_compiler/containers.py',
    'src/pystachy_compiler/conversions.py',
    'src/pystachy_compiler/declarations.py',
    'src/pystachy_compiler/diagnostics.py',
    'src/pystachy_compiler/driver.py',
    'src/pystachy_compiler/dynamic.py',
    'src/pystachy_compiler/dynamic_proof.py',
    'src/pystachy_compiler/emission.py',
    'src/pystachy_compiler/exceptions.py',
    'src/pystachy_compiler/expressions.py',
    'src/pystachy_compiler/flow.py',
    'src/pystachy_compiler/functions.py',
    'src/pystachy_compiler/callbacks.py',
    'src/pystachy_compiler/generators.py',
    'src/pystachy_compiler/gen.py',
    'src/pystachy_compiler/ir.py',
    'src/pystachy_compiler/ircheck.py',
    'src/pystachy_compiler/lexer.py',
    'src/pystachy_compiler/llvm_abi.py',
    'src/pystachy_compiler/loader.py',
    'src/pystachy_compiler/local_versions.py',
    'src/pystachy_compiler/lower_module.py',
    'src/pystachy_compiler/lowering.py',
    'src/pystachy_compiler/memory_ir.py',
    'src/pystachy_compiler/module.py',
    'src/pystachy_compiler/names.py',
    'src/pystachy_compiler/optimizations.py',
    'src/pystachy_compiler/parser.py',
    'src/pystachy_compiler/patterns.py',
    'src/pystachy_compiler/program.py',
    'src/pystachy_compiler/program_cache.py',
    'src/pystachy_compiler/reflection.py',
    'src/pystachy_compiler/scalar_ir.py',
    'src/pystachy_compiler/scope.py',
    'src/pystachy_compiler/source_lines.py',
    'src/pystachy_compiler/specs.py',
    'src/pystachy_compiler/statements.py',
    'src/pystachy_compiler/structs.py',
    'src/pystachy_compiler/syntax.py',
    'src/pystachy_compiler/templates.py',
    'src/pystachy_compiler/union_arithmetic.py',
    'src/pystachy_compiler/union_proof.py',
    'src/pystachy_compiler/union_state.py',
    'src/pystachy_compiler/unions.py',
    'src/pystachy_compiler/utils.py',
    'src/pystachy_compiler/variables.py',
]


def compile_program(path: str, src: str, dirs: list[str], ext: str) -> str:
    # the program's IR: where a join finds a location's inferred type too narrow for a value the
    # program stores to it (Gen.join_hint), the program is compiled again with the union of both
    # types, as if annotated, until no join widens one (at most JOINS passes after the first).
    # Where a comparison method's call with an Any value does not compile, it is compiled again
    # without that call (Gen.xnot: each such pass adds a method, so these passes count toward no
    # limit). Unsupported iteration protocol bodies use the same per-method retry
    # registry, but their replacement arms raise an explicit compatibility error.
    hints: dict[str, str] = {}
    xnot: dict[str, bool] = {}
    lambdas = LAMBDAS[0]
    libs = len(LIBS)
    linkdl = len(LINKDL)
    passes = 0
    # In a program that uses dynamic Any, the code of modules that neither opt in nor are imported
    # by one that does tracks no numeric identity (Gen.identity_modules), until a pass finds a
    # crossing that could carry one (Gen.identity_event): the program is then compiled from the
    # start with every module tracking it (idfull), as if that split had never been tried.
    idfull = False
    idtry = True
    slice_eh = False
    while True:
        attempt = timing_start()
        g = Gen()
        g.ext = ext
        g.eh = slice_eh
        g.libdir = dirs[-1] if len(dirs) > 0 else ""
        g.prefix = os.path.realpath(dirs[-1] + "/..") if len(dirs) > 0 else ""
        g.hints = hints
        g.xnot = xnot
        g.final = passes >= JOINS
        g.idfull = idfull
        g.idtry = idtry
        ld = Loader(dirs)
        ld.ext = ext
        try:
            loaded = timing_start()
            mods = ld.program(path, src)
            timing_end("program.load", loaded)
            return g.program(mods)
        except Rejoin as retry:
            if isinstance(retry, NeedSliceEH):
                slice_eh = True
            elif g.idevent != "" and not idfull:
                if idtry and len(g.idhint) > 0:
                    idtry = False  # retry today's dependency closure before full tracking
                else:
                    idfull = True
                hints = {}
                xnot = {}
                passes = 0
            else:
                for k in g.newhints:
                    hints[k] = g.newhints[k]
                if len([k for k in g.newx if k not in xnot]) == 0:
                    passes += 1
                for k in g.newx:
                    xnot[k] = True
            # (as parsing and lowering found them: the next pass numbers lambdas and
            # lists C libraries as the first did; Loader.program rebuilds its file-index space)
            LAMBDAS[0] = lambdas
            RENAMED.clear()
            while len(LIBS) > libs:
                LIBS.pop()
            while len(LINKDL) > linkdl:
                LINKDL.pop()
        finally:
            timing_end("program.attempt", attempt)


def runtime_ir(path: str, src: str, cache: bool) -> str:
    # runtime.py (path, whose text, read as RAW, is src): the part of the runtime written in the
    # subset. Its pys_* functions are defined under their C names, with runtime.c's types, and
    # llvm-link joins them to runtime.c's code (runtime.c keeps a prototype of each). It imports only
    # builtin modules, and nothing runs its module code, so it holds only functions.
    g = Gen()
    g.rtmode = True
    g.rtcache = cache  # (the driver's: then PYSTACHY_IRFX prints the program's summaries only)
    had_rt = "_rt" in MODULES
    old_rt = MODULES.get("_rt", False)
    MODULES["_rt"] = True
    try:
        ld = Loader([])
        ld.rtmode = True
        loaded = timing_start()
        mods = ld.program(path, src)
        timing_end("runtime.load", loaded)
        return g.program(mods)
    finally:
        # A failed hosted compilation must not admit runtime-only imports in the
        # next program. Nested callers retain their own temporary configuration.
        if had_rt:
            MODULES["_rt"] = old_rt
        else:
            del MODULES["_rt"]


def address_sanitized(flags: list[str]) -> bool:
    # Clang applies enabling/disabling sanitizer lists from left to right. Do not
    # mistake kernel-address, recovery options or a disabled ASan for address.
    enabled = False
    for flag in flags:
        if flag.startswith("-fsanitize=") and "address" in flag[11:].split(","):
            enabled = True
        elif flag.startswith("-fno-sanitize=") and any(x in ["address", "all"] for x in flag[14:].split(",")):
            enabled = False
    return enabled


def q(s: str) -> str:
    return "'" + s.replace("'", "'\\''") + "'"


def sh(cmd: str) -> int:
    st = os.system(cmd)
    return st >> 8 if st & 255 == 0 else 1


def timed_sh(name: str, cmd: str) -> int:
    started = timing_start()
    code = sh(cmd)
    timing_end(name, started)
    return code


# the lines of /proc/cpuinfo that tell which CPU -march=native compiles for (x86-64's, AArch64's)
CPUID: list[str] = ["vendor_id", "cpu family", "model", "model name", "stepping", "flags", "CPU implementer", "CPU architecture",
                    "CPU variant", "CPU part", "CPU revision", "Features"]
# The JIT tier's allocations: the program's module carries the allocator's fast path for pys_alloc
# and pys_new (lower_module's jit_alloc and JITFAST), both noinline through the cleanup pipeline,
# whose last step inlines them, as LATE_INLINE does for AOT builds (with LATE_PASSES, for LLVM 23)
JITLATE = (" -force-remove-attribute=pys_new:noinline -force-attribute=pys_new:alwaysinline"
           " -force-remove-attribute=pys_alloc:noinline -force-attribute=pys_alloc:alwaysinline")


# the files that runtime.c includes from beside it, each DIR/NAME (ryu/: Ryu's d2s, a float's shortest
# digits, ryu/README.md; mpz/: packed integer arithmetic): the runtime is built from their bytes too
RTPARTS: list[str] = ["ryu/d2s.c", "ryu/ryu.h", "ryu/common.h", "ryu/digit_table.h", "ryu/d2s_intrinsics.h",
                      "ryu/d2s_small_table.h", "mpz/mpz.c"]
# On Linux, pystachy run's lli loads the runtime as a shared library (-dlopen) rather than linking the
# runtime's machine code into each run (-extra-object), which cost about 35 ms a run (#704). The
# library is the cached runtime's .o, linked with RTSO: the runtime calls back into the program
# for objects' ==, order and repr (pys_obj_eq, pys_obj_cmp, pys_obj_repr, which every program defines,
# lower_module), which no library can name, so RTSO's stand-ins call what the program hands them first,
# from a constructor that each run adds to the program's IR (lower_module's OBJHOOKS), or to lli's main
# module where llc compiles the program (OBJHOOKS_MAIN)
RTSO = """typedef long long I;
static I (*eq)(I, I, I);
static I (*cmp)(I, I, I, I);
static void *(*repr)(I, I, I);
I pys_obj_eq(I c, I a, I b) { return eq(c, a, b); }
I pys_obj_cmp(I c, I op, I a, I b) { return cmp(c, op, a, b); }
void *pys_obj_repr(I c, I a, I b) { return repr(c, a, b); }
void pys_obj_hooks(I (*e)(I, I, I), I (*c)(I, I, I, I), void *(*r)(I, I, I)) { eq = e; cmp = c; repr = r; }
"""


def fnv(s: str) -> str:
    # FNV-1a, 64 bits wide, of s's characters (in a file read as RAW, its bytes, whose hash both
    # compilers agree on), in hex: computed in two 32-bit halves, as an int has 64 bits and no product
    # may overflow it (the prime is 2**40 + 0x1B3, whose 2**40 moves the low half's bits to the high half)
    hi = 0xCBF29CE4
    lo = 0x84222325
    for c in s:
        lo ^= ord(c)
        m = lo * 0x1B3
        hi = (hi * 0x1B3 + (lo << 8) + (m >> 32)) & 0xFFFFFFFF
        lo = m & 0xFFFFFFFF
    return f"{hi:08x}{lo:08x}"


def stat3(p: str) -> str:
    # what every change to file p changes, "" if there is no p: its size, mtime and ctime. A write
    # sets both times; touch -r sets the mtime back, but nothing sets a ctime back, and a file renamed
    # over p brings its own (Linux sets the ctime of a renamed file)
    try:
        return f"{os.path.getsize(p)} {os.path.getmtime(p)} {os.path.getctime(p)}"
    except OSError:
        return ""


def runtime_c_cache_enabled(flags: list[str]) -> bool:
    value = os.getenv("PYSTACHY_RUNTIME_C_CACHE", "0")
    if value != "0" and value != "1":
        fail("PYSTACHY_RUNTIME_C_CACHE must be 0 or 1", 0)
    # Keep custom flags, instrumentation and their diagnostic ordering on the
    # existing path. This first cache is deliberately limited to Linux defaults.
    return value == "1" and PLATFORM == "linux" and len(flags) == 0


def runtime_c_snapshot(source: str, directory: str) -> str:
    # Normalize only preprocessor line markers for our captured source tree.
    # An expanded __FILE__/__BASE_FILE__ containing that directory is semantic:
    # retain the ordinary build rather than rewriting a C string literal.
    # Unlike __FILE__, these expand during semantic analysis, after -E.
    # Their filename still depends on the original line markers.
    if "__builtin_FILE" in source or "__builtin_source_location" in source:
        return ""
    out: list[str] = []
    directory = directory.replace("\\", "\\\\").replace('"', '\\"')
    for line in source.split("\n"):
        if directory + "/" in line:
            if not line.startswith("# "):
                return ""
            line = line.replace('"' + directory + "/", '"')
        out.append(line)
    return "\n".join(out)


def retag_runtime_lists(ll: str) -> str:
    # runtime.c's IR (clang's -S output) with the TBAA access tags of its accesses through struct List
    # and struct Slot replaced by those that lowering gives the same memory (Gen.list_tag, under the
    # fieldtbaa root: lower_module's tbaa_nodes, "@list" and "@slot"). clang gives them types under a
    # root of its own, which LLVM tells apart from no other root's: an item that inlined runtime code
    # stores (pys_list_set) made compiled code reload every list's length and items pointer, and an
    # object's field store made inlined runtime code reload them. Every other access keeps clang's
    # tag, which a struct holding a List (Taken) uses too; ll is unchanged where it names neither type.
    # It is part of runtime_c_key's recipe: a change to what it writes bumps that key's schema
    lines = ll.split("\n")
    types: dict[str, str] = {}  # (clang's struct type node of each, by its name, as "!N")
    top = 0
    for line in lines:
        if not line.startswith("!") or line.find(" = ") < 0:
            continue
        name = line[1 : line.find(" ")]
        if not name.isdigit():
            continue
        top = max(top, int(name))
        if line.find(' = !{!"List", ') > 0:
            types["!" + name] = "@list"
        elif line.find(' = !{!"Slot", ') > 0:
            types["!" + name] = "@slot"
    if len(types) == 0:
        return ll
    root = top + 1
    out: list[str] = []
    for line in lines:
        at = line.find(" = !{!")
        if line.startswith("!") and at > 0 and line.endswith("}"):
            ops = line[at + 5 : len(line) - 1].split(", ")
            if len(ops) >= 3 and ops[0] in types and ops[2].startswith("i64 "):
                # an access tag: its base type, its access type, the offset there, (a constant flag)
                off = int(ops[2][4:])
                if types[ops[0]] == "@list":
                    ops[0] = f"!{root + 3}"
                    ops[1] = f"!{root + 2}" if off >= 16 else f"!{root + 1}"
                else:
                    ops[0] = f"!{root + 4}"
                    ops[1] = f"!{root + 1}"
                line = line[: at + 4] + "{" + ", ".join(ops) + "}"
        out.append(line)
    out.append(f'!{root} = !{{!"pystachy fields"}}')
    out.append(f'!{root + 1} = !{{!"int", !{root}, i64 0}}')
    out.append(f'!{root + 2} = !{{!"pointer", !{root}, i64 0}}')
    out.append(f'!{root + 3} = !{{!"@list", !{root + 1}, i64 0, !{root + 1}, i64 8, !{root + 2}, i64 16, !{root + 2}, i64 24}}')
    out.append(f'!{root + 4} = !{{!"@slot", !{root + 1}, i64 0}}')
    return "\n".join(out) + "\n"


def retag_runtime_file(path: str) -> int:
    # retag_runtime_lists of the IR file at path, in place: 0, or 1 where it cannot be written. A file
    # that cannot be read (clang wrote none) stays as it is, for llvm-as to report
    text = ""
    try:
        f = open(path, "r", encoding=RAW, newline="")
        text = f.read()
        f.close()
    except OSError:
        return 0
    try:
        f = open(path, "w", encoding=RAW, newline="")
        f.write(retag_runtime_lists(text))
        f.close()
    except OSError:
        return 1
    return 0


def runtime_c_key(source: str, paths: list[str], times: list[str], strip: str) -> str:
    # Preprocessing captures included headers, environment include paths and
    # target macros. Compile those exact bytes, rather than reopening headers.
    # No Pystachy executable, hosted source, runtime.py or typed-IR option belongs
    # here: they do not produce this C bitcode. Bump the schema for recipe changes.
    identity = ["runtime-c-v3", PLATFORM, "-O2 -fexceptions -x cpp-output", strip, "retag_runtime_lists"]
    identity = identity + [os.path.realpath(p) for p in paths[:2]] + times[:2]
    return fnv("\n".join(identity) + "\n" + source)


def settled(st: str, now: float) -> bool:
    # did st's file last change more than 2 s before now? A file system keeps times at a coarse grain
    # (the kernel's clock tick, or a second on some), so a file changed again within it may show st
    # still: what it holds then is known only from reading it (git's "racily clean" files)
    t = st.split(" ")
    return len(t) == 3 and now - max(float(t[1]), float(t[2])) > 2


def hashed(p: str, memo: dict[str, str], now: float, need: bool) -> tuple[str, str]:
    # (the bytes of file p, read as RAW, one character each, and their fnv(); "" for both if p cannot
    # be read). memo maps the fnv() of p's real path to that hash with p's stat3() as it was read,
    # kept if it had settled: while p shows it still, p holds those bytes, which are then read only
    # if need is set
    st = stat3(p)
    k = fnv(os.path.realpath(p))
    m = memo.get(k, "")
    if not need and st != "" and m[17:] == st:
        return ("", m[:16])
    s = ""
    try:
        f = open(p, "r", encoding=RAW, newline="")
        s = f.read()
        f.close()
    except OSError:
        return ("", "")
    h = fnv(s)
    if st != "" and stat3(p) == st and settled(st, now):
        if k in memo:
            del memo[k]  # (to the end: the cache file keeps the 64 hashes learnt last)
        memo[k] = f"{h} {st}"
    return (s, h)


def llvm_dir() -> str:
    # Keep a versioned apt/Homebrew toolchain together; an explicit override wins.
    llvm = os.getenv("PYSTACHY_LLVM", "\0")
    if llvm != "\0":
        return llvm.rstrip("/") if llvm != "/" else "/"  # an explicit empty override selects PATH
    for d in ["/usr/lib/llvm-18/bin", "/opt/homebrew/opt/llvm@20/bin", "/usr/local/opt/llvm@20/bin",
              "/home/linuxbrew/.linuxbrew/opt/llvm@18/bin"]:
        if all([os.path.exists(d + "/" + t) for t in ["clang", "opt", "lli", "llvm-link", "llvm-as"]]):
            return d
    return ""  # otherwise use the unversioned tools on PATH


def compiler_home() -> str:
    home = os.getenv("PYSTACHY_HOME", "")
    if home == "":
        s = sys.argv[0].rfind("/")
        home = sys.argv[0][:s] if s >= 0 else "."
        if not os.path.exists(home + "/runtime.c"):
            home = home + "/.."
    return home


def compiler_version(home: str) -> str:
    # Metadata is adjacent to the runtime, so one native compiler can be packaged
    # for an exact release without recompiling it or requiring Python, Git or LLVM.
    version = "unknown"
    revision = "unknown"
    try:
        f = open(home + "/VERSION", "r", encoding="utf-8")
        version = f.read().strip()
        f.close()
    except OSError:
        pass
    try:
        f = open(home + "/REVISION", "r", encoding="utf-8")
        revision = f.read().strip()
        f.close()
    except OSError:
        pass
    return f"pystachy {version} (commit {revision})"


def output_alias(first: str, second: str) -> bool:
    if os.path.realpath(first) == os.path.realpath(second):
        return True
    try:
        return os.path.samefile(first, second)
    except OSError:
        return False


def check_retained_ir(path: str, source: str, output: str) -> None:
    if output_alias(path, source) or output_alias(path, output):
        fail("--emit-ir must name a different file from the source and executable", 0)
    if os.path.isdir(path):
        fail("--emit-ir must name a file, not a directory", 0)


def retained_ir_path(cmd: str, source: str, args: list[str]) -> str:
    # run's remaining arguments belong to the program, not the compiler.
    if cmd == "run":
        return ""
    path = ""
    default_output = source[:-3] if source.endswith(".py") else source + ".exe"
    output = default_output
    i = 0
    while i < len(args):
        if args[i] == "-o" and i + 1 < len(args):
            output = args[i + 1] or default_output
            i += 2
        elif args[i] == "--emit-ir":
            if cmd != "build" or path != "" or i + 1 >= len(args) or args[i + 1] == "" or args[i + 1] == "-o" or args[i + 1] == "--emit-ir":
                fail("--emit-ir requires one file path and is only supported by build", 0)
            path = args[i + 1]
            i += 2
        else:
            i += 1
    if path != "":
        check_retained_ir(path, source, output)
    return path


def publish_retained_ir(path: str, source: str, output: str, ir: str, own: str) -> None:
    # A private sibling directory keeps the final replace on one filesystem,
    # without following an existing output symlink or overwriting a partial file.
    # Publication is called only after the executable has linked successfully.
    check_retained_ir(path, source, output)
    staging = path + ".tmp." + own
    os.mkdir(staging, 0o700)
    part = staging + "/ir"
    try:
        f = open(part, "w", encoding=RAW)
        f.write(ir)
        f.close()
        os.replace(part, path)
    finally:
        if os.path.exists(part):
            os.remove(part)
        os.rmdir(staging)


def ignored_signals() -> int:
    # The standard signals this process ignores, bit s-1 for signal s. An exec keeps them ignored
    # and sets caught ones to their defaults, so these are all that lli inherits before LLVM's
    # handlers replace them, for the program's runtime to restore (runtime.c's jit_handoff).
    if sys.implementation.name != "pystachy":
        import signal
        mask = 0
        for number in range(1, 32):
            if signal.getsignal(number) == signal.SIG_IGN:
                mask |= 1 << (number - 1)
        return mask
    return native_ignored_signals()


def aot_optimization() -> str:
    value = os.getenv("PYSTACHY_AOT_OPT", "2")
    if value != "0" and value != "1" and value != "2":
        fail("PYSTACHY_AOT_OPT must be 0, 1 or 2", 0)
    return value


# The LLVM versions whose C API lljit.c declares (two changes are gated at 21), for which the driver
# builds Pystachy's JIT runner; another version runs lli. And what the runner's -self-check writes, at
# each level of code generation it is checked at
LLJIT_LLVM: list[str] = ["18", "19", "20", "21", "22", "23"]
LLJIT_CHECK = "two\nlljit\n"


def text_of(p: str) -> str:
    # file p's text, "" if it cannot be read
    try:
        f = open(p, "r", encoding=RAW)
        s = f.read()
        f.close()
        return s
    except OSError:
        return ""


def jit_launcher(runner: str, home: str, cache: str, lli: str, clang: str, src: tuple[str, str], memo: dict[str, str],
                 now: float, tmp: str, own: str, build: bool) -> tuple[str, str]:
    # What runs a JIT program: (the JIT runner's path, "") or ("", the reason lli runs it). The runner is
    # lljit.c, built at first use with the selected toolchain's clang, linked to the libLLVM that its lli
    # loads, of an LLVM in LLJIT_LLVM, and cached beside the runtime as lljit-<L>-<K>: K is the fnv() of
    # lljit.c's bytes and of the files of lli, clang and that libLLVM (through symbolic links), with their
    # stat3(), and L of the names of lljit.c, lli and clang; publishing a runner removes the others of its
    # L. lljit-<L>-<K0>.llvm, K0 being K without libLLVM, holds that libLLVM and its LLVM version, found
    # once (ldd lli, lli --version), or why there is none ("- REASON"). A runner that cannot be built, or
    # that fails its -self-check, leaves lljit-<L>-<K>.fail (what failed, then its log), and later runs
    # go to lli at once; as for the runtime, nothing is published unless the tools are as they were and
    # had settled. Without build (the program cache, whose miss builds an executable instead), nothing
    # is found or built: a runner built before runs the cache's fallback. Nothing goes to stderr: the
    # reason is the name of a PYSTACHY_TIMING record (main)
    if runner != "auto":
        return ("", "forced")
    if PLATFORM != "linux":
        return ("", "platform")  # (macOS keeps lli: the runner is untested there)
    if src[1] == "":
        return ("", "no-source")
    st = [stat3(lli) if lli != "" else "", stat3(clang) if clang != "" else ""]
    if "" in st:
        return ("", "no-toolchain")
    names = "\n".join([os.path.realpath(home + "/lljit.c"), os.path.realpath(lli), os.path.realpath(clang)])
    lin = fnv(names)[8:]
    base = fnv("\n".join(["lljit-v1", names] + st + [src[1]]))
    stem = f"{cache}/lljit-{lin}-"
    llvmf = stem + base + ".llvm"
    # the complete entries of this L but those named, removed (no partial file: its run may yet use it)
    old = f"{q(cache)}/lljit-{lin}-{'?' * 16}"
    stable = settled(st[0], now) and settled(st[1], now)
    found = text_of(llvmf).split("\n")[0]
    if found == "":
        if not build:
            return ("", "program-cache")
        # (ldd first: an lli that is a script, as a wrapper may be, is not run. A shell without ldd or
        # sed, which may have them another time, finds nothing it keeps)
        out = tmp + "/lljit.llvm"
        code = sh(f"command -v ldd > /dev/null && command -v sed > /dev/null || exit 3; "
                  f"l=$(ldd {q(lli)} 2> /dev/null | sed -n 's/^[[:space:]]*libLLVM[^ ]* => \\(.*\\) (0x[0-9a-f]*)$/\\1/p' | sed 1q); v=; "
                  f"[ -z \"$l\" ] || v=$({q(lli)} --version 2> /dev/null | sed -n 's/.*LLVM version \\([0-9][0-9]*\\)\\..*/\\1/p' | sed 1q); "
                  f"printf '%s\\n%s\\n' \"$v\" \"$l\" > {q(out)}")
        got = text_of(out).split("\n") + ["", ""]
        if os.path.exists(out):
            os.remove(out)
        if code != 0:
            return ("", "no-ldd")
        found = "- no-libLLVM" if got[1] == "" else f"{got[0]} {got[1]}" if got[0] in LLJIT_LLVM else "- llvm-version"
        if stable and [stat3(lli), stat3(clang)] == st:
            lp = f"{llvmf}.{os.getpid()}.{own}"
            try:
                f = open(lp, "w", encoding=RAW)
                f.write(found + "\n")
                f.close()
                sh(f"mv -f {q(lp)} {q(llvmf)} 2> /dev/null")
            except OSError:
                pass  # (a cache that cannot be written: found again)
            if os.path.exists(lp):
                os.remove(lp)
    if found.startswith("- "):
        return ("", found[2:])
    major = found.split(" ")[0]
    lib = found[len(major) + 1 :]
    real = os.path.realpath(lib)
    lst = stat3(real)
    if lst == "":
        return ("", "no-libLLVM")
    exe = stem + fnv(base + "\n" + real + "\n" + lst)
    if os.path.isfile(exe):
        return (exe, "")
    failed = text_of(exe + ".fail").split("\n")[0]
    if failed != "":
        return ("", failed)
    if not build:
        return ("", "program-cache")
    # the bytes hashed, compiled from a file of this run's
    sb = hashed(home + "/lljit.c", memo, now, True)
    if sb[1] != src[1]:
        return ("", "unsettled")
    c = tmp + "/lljit.c"
    log = tmp + "/lljit.log"
    chk = tmp + "/lljit.out"
    part = f"{exe}.{os.getpid()}.{own}"
    try:
        f = open(c, "w", encoding=RAW, newline="")
        f.write(sb[0])
        f.close()
        f = open(part, "w", encoding=RAW)  # (a cache that cannot be written gets no runner)
        f.close()
    except OSError:
        for p in [c, part]:
            if os.path.exists(p):
                os.remove(p)
        return ("", "cache")
    # linked to that libLLVM, which its directory supplies before LD_LIBRARY_PATH's (DT_RPATH), then run
    # at -O0 and -O2 on its own module: 1 if it cannot be built, 2 if it fails (126: it may not be
    # executed there, as on a cache mounted noexec)
    d = lib[: lib.rfind("/")] if "/" in lib else "."
    started = timing_start()
    code = sh(f"{{ {q(clang)} -O2 -std=c11 -D_GNU_SOURCE -DLLVM_VERSION_MAJOR={major} -w {q(c)} {q(lib)} -ldl -o {q(part)}"
              f" -Xlinker --disable-new-dtags -Xlinker -rpath -Xlinker {q(d)} || exit 1; for o in -O0 -O2; do"
              f" {q(part)} -profile-guided-section-prefix=false $o -self-check || exit 2; done > {q(chk)}; }} > {q(log)} 2>&1")
    timing_end("runtime.jit_launcher_build", started)
    why = "build" if code != 0 and code != 2 else "self-check" if code == 2 or text_of(chk) != LLJIT_CHECK + LLJIT_CHECK else ""
    if stable and settled(lst, now) and [stat3(lli), stat3(clang), stat3(real)] == st + [lst]:
        if why == "":
            sh(f"{{ mv -f {q(part)} {q(exe)} && for f in {old} {old}.llvm {old}.fail; do case $f in {q(exe)} | {q(llvmf)}) ;; *) rm -f \"$f\" ;; esac; done; }} 2> /dev/null")
        else:
            fp = f"{exe}.fail.{os.getpid()}.{own}"
            try:
                f = open(fp, "w", encoding=RAW)
                f.write(why + "\n" + text_of(log) + text_of(chk))
                f.close()
                sh(f"{{ mv -f {q(fp)} {q(exe + '.fail')} && for f in {old} {old}.llvm {old}.fail; do case $f in {q(exe + '.fail')} | {q(llvmf)}) ;; *) rm -f \"$f\" ;; esac; done; }} 2> /dev/null")
            except OSError:
                pass
            if os.path.exists(fp):
                os.remove(fp)
    for p in [c, log, chk, part]:
        if os.path.exists(p):
            os.remove(p)
    if why == "" and os.path.isfile(exe):
        return (exe, "")
    return ("", why if why != "" else "unsettled")


def main() -> None:
    # the parser and the code generator recurse for each level of nesting (at most MAXNEST), a
    # dozen calls deep each: more than CPython's default limit of 1,000 calls when it runs this file
    total = timing_start()
    sys.setrecursionlimit(MAXNEST * 40)
    argv = sys.argv
    if len(argv) == 2 and (argv[1] == "--version" or argv[1] == "-V"):
        print(compiler_version(compiler_home()))
        return
    if len(argv) < 3 or (argv[1] != "run" and argv[1] != "build" and argv[1] != "ext" and argv[1] != "ir" and argv[1] != "check" and argv[1] != "rt"):
        print("usage: pystachy run FILE.py [ARGS...]   JIT-compile and run (LLVM ORC)", file=sys.stderr)
        print("       pystachy build FILE.py [-o EXE]  compile ahead of time to a native executable", file=sys.stderr)
        print("                    [--emit-ir RAW.ll] retain raw IR after a successful build", file=sys.stderr)
        print("       pystachy ext NAME.py [-o NAME.abi3.so]  compile to a CPython extension module (abi3, CPython 3.12+)", file=sys.stderr)
        print("       pystachy ir FILE.py [-o OUT.ll]  emit LLVM IR", file=sys.stderr)
        print("       pystachy check FILE.py           only parse it, with the checks CPython makes before running it", file=sys.stderr)
        print("       pystachy rt runtime.py [-o OUT.ll] emit the LLVM IR of the runtime's part written in the subset", file=sys.stderr)
        print("       pystachy --version               show version and source commit", file=sys.stderr)
        sys.exit(2)
    cmd = argv[1]
    diagnostics.SRC = argv[2]
    if not os.path.exists(diagnostics.SRC):
        fail("file not found", 0)
    retained = retained_ir_path(cmd, diagnostics.SRC, argv[3:])
    aotopt = aot_optimization() if cmd == "build" else "2"
    jitflags = ""
    codegen = "2"
    runner = ""
    jitinline = JIT_INLINE
    if cmd == "run":
        # PYSTACHY_JIT_CODEGEN=0: -O0 code generation, which the JIT runner does itself, and for which
        # lli's ORC, which ignores -O, links an object of llc's (below). Keep this startup/execution
        # tradeoff opt-in, independently of the IR inlining budget.
        codegen = os.getenv("PYSTACHY_JIT_CODEGEN", "2")
        if codegen != "0" and codegen != "2":
            fail(f"PYSTACHY_JIT_CODEGEN: {codegen} is not 0 (-O0 code generation) or 2 (the default)", 0)
        # what runs the program (jit_launcher), read before the program cache, so that a hit rejects
        # what a run without it rejects
        runner = os.getenv("PYSTACHY_JIT_LAUNCHER", "auto")
        if runner != "auto" and runner != "lli":
            fail(f"PYSTACHY_JIT_LAUNCHER: {runner} is not auto (Pystachy's JIT runner where it can be built, else lli) or lli", 0)
        # Reject settings before acquiring cache locks or creating temporary files.
        # Keep both checks: isdigit() and int() accept different Unicode digits.
        lim = os.getenv("PYSTACHY_JIT_INLINE", str(JIT_INLINE))
        if not lim.isdigit():
            fail(f"PYSTACHY_JIT_INLINE: {lim} is no number of lines (0 turns the JIT's inliner off)", 0)
        jitinline = int(lim)
        # cold functions (a function that only raises: cold noinline) stay in .text: where some
        # went to .text.unlikely, lli's ORC in LLVM 18 lost the landing pads that the inliner had
        # moved into main, and a try statement there missed what it should have caught (the JIT
        # runner takes the same flag, and needs it as much)
        jitflags = " -profile-guided-section-prefix=false"
    if cmd == "check":
        f = open(diagnostics.SRC, "r", encoding=RAW)
        Parser(Lexer(f.read(), 1).file()).module()
        f.close()
        timing_end("driver.total", total)
        return
    if cmd == "rt":
        f = open(diagnostics.SRC, "r", encoding=RAW)
        frontend = timing_start()
        ir = runtime_ir(diagnostics.SRC, f.read(), False)
        timing_end("runtime.frontend", frontend)
        f.close()
        if len(argv) == 5 and argv[3] == "-o":
            f = open(argv[4], "w", encoding=RAW)
            f.write(ir)
            f.close()
        else:
            print(ir, end="")
        timing_end("driver.total", total)
        return
    # the compiler that runs, for the runtime's cache (below): when named by its path, or a script
    # that CPython runs, its file's stat3() as the driver starts, and when that is
    me = argv[0]
    t0 = time.time()
    born = stat3(me) if "/" in me or me.endswith(".py") else ""
    # CPython has loaded the components before main: require their files to have settled
    # before startup, and remain unchanged until a runtime cache entry is published.
    sources: list[str] = []
    if me.endswith(".py"):
        realme = os.path.realpath(me)
        compdir = realme[: realme.rfind("/")]
        sources = [compdir + "/" + p for p in COMPILER_SOURCES]
    sourceborn = [stat3(p) for p in sources]
    home = compiler_home()
    # where imported modules are found: the directory of the program's real path (symbolic links
    # resolved, as CPython's sys.path[0]; spelled as given where that is the same), PYSTACHY_PATH,
    # lib/ of the checkout
    s = diagnostics.SRC.rfind("/")
    d = diagnostics.SRC[:s] if s > 0 else "/" if s == 0 else "."
    real = os.path.realpath(diagnostics.SRC)
    if os.path.realpath(d).rstrip("/") + "/" + diagnostics.SRC[s + 1 :] != real:
        d = real[: real.rfind("/")] if real.rfind("/") > 0 else "/"
    dirs = [d]
    for d in os.getenv("PYSTACHY_PATH", "").split(":"):
        if d != "":
            dirs.append(d)
    dirs.append(home + "/lib")
    cache_start = timing_start()
    pcroot, pccontext, pcexe = cached_run.prepare(cmd, diagnostics.SRC, me, home, dirs, llvm_dir(), RTPARTS)
    timing_end("program.cache_lookup", cache_start)
    if pcexe != "":
        timing_end("driver.prepare_run", total)
        cached_run.execute(pcexe, diagnostics.SRC, argv[3:])
    for d in dirs[:-1]:
        if program_cache.tracked_isfile(d + "/ffi.py") or program_cache.tracked_isfile(d + "/ffi/__init__.py"):
            del MODULES["ffi"]  # (the program's own ffi module comes first, as under CPython: Pystachy's is not imported then)
            break
    f = open(diagnostics.SRC, "r", encoding=RAW)
    ext = diagnostics.SRC[diagnostics.SRC.rfind("/") + 1 : -3] if cmd == "ext" and diagnostics.SRC.endswith(".py") else ""
    if pcroot != "":
        cached_run.trace("frontend")
    frontend = timing_start()
    ir = compile_program(diagnostics.SRC, f.read(), dirs, ext)
    timing_end("program.frontend", frontend)
    f.close()
    # a program that opts in to neither dynamic Any nor promoting ints: pys_plain, below (read now, as
    # building the runtime compiles runtime.py as a program of its own, which has no opt-in)
    plain = not diagnostics.dynamic_program() and not diagnostics.int_program()
    out = ""
    abi = "abi3"  # pystachy ext: abi3 (CPython 3.12+, GIL builds) or abi3t (3.15+, GIL and free-threaded)
    rest: list[str] = []
    i = 3
    while i < len(argv):
        if argv[i] == "-o" and i + 1 < len(argv) and cmd != "run":
            out = argv[i + 1]
            i += 2
        elif argv[i] == "--emit-ir" and cmd == "build":
            i += 2  # validated before compiling; publish only after the native build
        elif argv[i] == "--abi" and i + 1 < len(argv) and cmd == "ext" and (argv[i + 1] == "abi3" or argv[i + 1] == "abi3t"):
            abi = argv[i + 1]
            i += 2
        else:
            rest.append(argv[i])
            i += 1
    embed = "python" in LIBS  # (lib/pyobj.py: pyembed.c is linked in, which ends the CPython it starts)
    if pcroot != "" and (len(LIBS) > 0 or len(LINKDL) > 0):
        cached_run.trace("bypass external native libraries")
        program_cache.stop()
        pcroot = ""
    for i in range(len(LIBS)):
        if LIBS[i] == "python":  # (lib/pyobj.py's: the libpython to embed; an extension's host has it)
            LIBS[i] = os.getenv("PYSTACHY_LIBPYTHON", "") if cmd != "ext" else "-"
            if LIBS[i] == "" and cmd != "ir":
                fail("the program embeds CPython (it imports pyobj): set PYSTACHY_LIBPYTHON to its libpython3.X.so", 0)
            v = os.path.realpath(LIBS[i]) if LIBS[i] != "" and LIBS[i] != "-" else ""
            v = v[v.rfind("/") + 12 :] if v[v.rfind("/") + 1 :].startswith("libpython3.") else ""
            k = 0
            while k < len(v) and v[k].isdigit():
                k += 1
            if k > 0 and int(v[:k]) < 12 and cmd != "ir":
                # (below the stable ABI lib/pyobj.py uses: the linker or lli would name a missing symbol)
                fail(f"the program embeds CPython (it imports pyobj), which needs CPython 3.12 or later: PYSTACHY_LIBPYTHON is CPython 3.{v[:k]}'s ({LIBS[i]})", 0)
    if cmd == "ir":
        if out == "":
            print(ir, end="")
        else:
            f = open(out, "w", encoding=RAW)
            f.write(ir)
            f.close()
        timing_end("driver.total", total)
        return
    cache_start = timing_start()
    rtc = home + "/runtime.c"
    rtpy = home + "/runtime.py"
    if not os.path.exists(rtc) or not os.path.exists(rtpy):
        fail("cannot find runtime.c and runtime.py next to the compiler; set PYSTACHY_HOME to the directory that holds them", 0)
    # PYSTACHY_CFLAGS: extra clang flags (e.g. -fsanitize=undefined) for the runtime and the AOT link.
    # AddressSanitizer also instruments an AOT/extension program's generated definitions,
    # separately from the cached runtime so its already-instrumented code is not processed twice.
    # The runtime is compiled with them and then -fexceptions (so they cannot drop it): a raise unwinds
    # through runtime functions to compiled code's landing pads, which -O2 would turn back into calls
    # if clang marked them nounwind. runtime.py goes through the optimizations on the IR as programs
    # do, so the ones PYSTACHY_OPT turns off count too: the cached runtime's key (below) has both
    flags = os.getenv("PYSTACHY_CFLAGS", "").split()
    cache_c = runtime_c_cache_enabled(flags)
    asan = address_sanitized(flags)
    on = optimizations()
    off = [o for o in OPTS if o not in on]
    keyed = flags + ["-fexceptions"]
    if os.getenv("PYSTACHY_DEBUG_LINES", "") == "1":
        keyed = keyed + ["PYSTACHY_DEBUG_LINES=1"]
    runtime_inputs = [program_cache.runtime_key()] if pcroot != "" else []
    if len(off) > 0:
        keyed = keyed + ["PYSTACHY_OPT=-" + ",-".join(off)]
    cflags = "".join([" " + q(a) for a in flags])
    # Every module we instrument separately needs ungrouped ASan constructors:
    # llvm-link renames duplicate local symbols but retains their COMDAT names.
    # A separately sanitized native object could otherwise discard a constructor
    # whose init-array entry survived under its renamed symbol.
    ctorflags = " -mllvm -asan-with-comdat=0" if asan else ""
    # the AOT tier compiles bitcode whose runtime part is instrumented already, so the sanitizer flags
    # go to its link alone (which adds their runtime libraries): ASan's pass would instrument it again
    ccflags = "".join([" " + q(a) for a in flags if not a.startswith("-fsanitize") and not a.startswith("-fno-sanitize")])
    llvm = llvm_dir()  # optional override, standard apt/Homebrew installation, or PATH
    if llvm != "" and not llvm.endswith("/"):
        llvm = llvm + "/"
    # strip clang's target-cpu/features attributes so LLVM can inline runtime helpers into our code
    strip = "sed -E 's/ \"(target-cpu|target-features|tune-cpu)\"=\"[^\"]*\"//g'"
    cache = os.getenv("PYSTACHY_CACHE", "") or home + "/build"
    if not os.path.exists(cache):
        sh(f"mkdir -p {q(cache)}")
    # intermediate files go to a private directory (mode 0700, honours TMPDIR), removed on every path below
    tmp = tempfile.mkdtemp()
    # The cached runtime: runtime.c's bitcode linked to runtime.py's, which the compiler that runs
    # compiles, in build/runtime-py-<L>-<K>.bc, with the JIT tier's machine code from it in its .o. K is
    # the fnv() of all they are made from: the bytes of runtime.c, of the files it includes (RTPARTS),
    # of runtime.py and of the compiler (its executable, or pystachy.py under CPython: another compiler
    # may compile runtime.py differently, and the bootstrap checks that its stages do not), the flags
    # above, the files of clang, llvm-as, llvm-link and opt (through symbolic links: another LLVM is
    # other files), with their stat3(), and with a flag that asks for the native CPU, the host's
    # (CPUID). L is the fnv() of the same but the bytes and times: publishing a runtime removes the
    # others of its L, so that build/ keeps one per compiler, flag set and LLVM. (Older compilers run
    # with the same home keep theirs under other names: runtime-py-<hash of the flags>.bc, and
    # runtime.bc or runtime-<hash>.bc before runtime.py.)
    # The tools are PYSTACHY_LLVM's, or where the shell's own search of PATH finds them (command -v,
    # which skips directories and files that are not executable), and so is this compiler when it was
    # run by name; CPython opens a script in the current directory, with no search. The runtime is
    # built with the files found, not after a second search
    tools = ["clang", "llvm-as", "llvm-link", "opt"]
    paths = [llvm + t for t in tools]
    # (and for pystachy run, the lli whose libLLVM the JIT runner links: jit_launcher)
    lli = llvm + "lli" if cmd == "run" else ""
    ask = [t for t in tools if llvm == ""] + (["lli"] if llvm == "" and cmd == "run" else [])
    comp = me if "/" in me or me.endswith(".py") else ""
    byname = comp == "" and not me.startswith("-")
    if byname:
        ask.append(me)
    if len(ask) > 0:
        pf = tmp + "/paths"
        sh(f"for t in {' '.join([q(a) for a in ask])}; do command -v \"$t\" || echo; done > {q(pf)}")
        got: list[str] = []
        try:
            f = open(pf, "r", encoding="utf-8")
            got = f.read().split("\n")
            f.close()
        except (OSError, ValueError):
            got = []  # (ValueError: CPython reads a path that is no UTF-8: nothing is found)
        if os.path.exists(pf):
            os.remove(pf)
        got = got + ["" for a in ask]
        if llvm == "":
            paths = got[: len(tools)]
            if cmd == "run":
                lli = got[len(tools)]
        if byname:
            comp = got[len(ask) - 1]
    now = time.time()
    lines = [os.path.realpath(comp) if comp != "" else "", " ".join(keyed)]
    if pcroot != "":
        # Keep checked-toolchain runtime artifacts separate from ordinary JIT
        # artifacts so switching the program-cache policy cannot evict either.
        lines.append("program-cache-inputs-v2")
    times: list[str] = []
    for p in paths:
        lines.append(os.path.realpath(p) if p != "" else "")
        times.append(stat3(p) if p != "" else "")
    if len([a for a in flags if a.endswith("=native")]) > 0 and os.path.exists("/proc/cpuinfo"):
        cpu: dict[str, bool] = {}
        f = open("/proc/cpuinfo", "r", encoding=RAW)
        for x in f.read().split("\n"):
            if x.split(":")[0].strip() in CPUID:
                cpu[x] = True
        f.close()
        lines = lines + [x for x in cpu]
    lin = fnv("\n".join(lines))[8:]
    # Hashing the 2 MB compiler would cost a third of a JIT start: runtime-py.hashes keeps the hashes
    # of the files (see hashed()), written whole and renamed over the old (concurrent runs may each
    # drop what another added, which is then hashed again)
    hf = cache + "/runtime-py.hashes"
    memo: dict[str, str] = {}
    try:
        f = open(hf, "r", encoding=RAW)
        for x in f.read().split("\n"):
            if len(x) > 17:
                memo[x[:16]] = x[17:]
        f.close()
    except OSError:
        memo = {}
    known = "".join([f"{k} {memo[k]}\n" for k in memo])
    rc = hashed(rtc, memo, now, False)
    rs = [hashed(home + "/" + p, memo, now, False) for p in RTPARTS]
    rp = hashed(rtpy, memo, now, False)
    # (the JIT runner's source, hashed here so that runtime-py.hashes keeps its hash too)
    rj = hashed(home + "/lljit.c", memo, now, False) if runner == "auto" and PLATFORM == "linux" else ("", "")
    rm = ("", "")
    if comp != "":
        rm = hashed(comp, memo, now, False)
    component_hashes = [hashed(p, memo, now, False)[1] for p in sources]
    cst = stat3(comp) if comp != "" else ""
    # The compiler's file must hold the code that runs: when named by its path, or a script, it has not
    # changed since the driver started, and a script had not changed for 2 s then, which covers its
    # reading by CPython. Otherwise, or without a tool, the runtime is built for this run alone
    trusted = rm[1] != "" and cst != "" and (born == "" or cst == born) and "" not in times
    if me.endswith(".py"):
        trusted = trusted and settled(born, t0) and "" not in component_hashes
        trusted = trusted and [stat3(p) for p in sources] == sourceborn
        trusted = trusted and len([st for st in sourceborn if not settled(st, t0)]) == 0
    key = fnv("\n".join(lines + times + [rc[1], rp[1], rm[1]] + component_hashes + [x[1] for x in rs] + runtime_inputs))
    rtb = f"{cache}/runtime-py-{lin}-{key}.bc"
    rtir = ""
    timing_end("runtime.cache_lookup", cache_start)
    if not trusted or not os.path.exists(rtb):
        # the bytes of runtime.c, of the files it includes and of runtime.py, read once: the runtime is
        # built from them, and named by their hash, so that an edit while it is built names another
        # runtime, which a later run builds
        rc = hashed(rtc, memo, now, True)
        rs = [hashed(home + "/" + p, memo, now, True) for p in RTPARTS]
        rp = hashed(rtpy, memo, now, True)
        key = fnv("\n".join(lines + times + [rc[1], rp[1], rm[1]] + component_hashes + [x[1] for x in rs] + runtime_inputs))
        rtb = f"{cache}/runtime-py-{lin}-{key}.bc"
        if (not trusted or not os.path.exists(rtb)) and rc[1] != "" and rp[1] != "" and "" not in [x[1] for x in rs]:
            # (an error in runtime.py exits: the private directory is made again after it)
            os.rmdir(tmp)
            src = diagnostics.SRC
            diagnostics.SRC = rtpy
            frontend = timing_start()
            rtir = runtime_ir(rtpy, rp[0].replace("\r\n", "\n").replace("\r", "\n"), True)
            timing_end("runtime.frontend", frontend)
            diagnostics.SRC = src
            tmp = tempfile.mkdtemp()
    ll = tmp + "/prog.ll"
    abc = tmp + "/prog-asan.bc"
    bc = tmp + "/prog.bc"
    obj = tmp + "/prog.o"
    jobj = tmp + "/prog-O0.o"  # (PYSTACHY_JIT_CODEGEN=0: llc's object, and lli's main module beside it)
    jmain = tmp + "/main.ll"
    obc = tmp + "/prog-opt.bc"  # (allocelide's late step, below: -O2's module, and that module once
    lbc = tmp + "/prog-late.bc"  # pys_new is inlined into it)
    pcout = tmp + "/program"
    pclink = tmp + "/program-link"
    pclink2 = tmp + "/program-link-final"
    pcerror = tmp + "/program-error"
    rcc = tmp + "/runtime.c"
    rll = tmp + "/runtime.ll"
    rsl = tmp + "/runtime-s.ll"
    rcb = tmp + "/runtime-c.bc"
    rpl = tmp + "/rtpy.ll"
    rpb = tmp + "/rtpy.bc"
    lnk = tmp + "/runtime-l.bc"
    rso = tmp + "/runtime-so.c"
    rto = rtb[:-3] + ".o"  # the runtime as machine code, for the JIT tier
    rts = rtb[:-3] + ".so"  # and that as a shared library, which it loads on Linux (RTSO)
    # the runtime's bitcode and machine code are written to names of this process's own in the
    # cache's directory, then renamed over the cache once complete (in one file system, so that the
    # rename is atomic). The process ID alone is no such name: processes in separate PID namespaces
    # share it (each container's first process is 1), so tmp's random name is in it too
    own = tmp[tmp.rfind("/") + 1 :]
    part = f"{rtb}.{os.getpid()}.{own}"
    parto = f"{rto}.{os.getpid()}.{own}"
    partso = f"{rts}.{os.getpid()}.{own}"
    f = open(ll, "w", encoding=RAW)
    f.write(address_runtime_ir(ir) if asan and cmd != "run" else ir)
    if cmd == "build":
        # runtime.c's pys_plain, which -O2 reads with the runtime as one module: 1 removes the code
        # that only values of those opt-ins reach (opt_in()), before it is optimized; the JIT tier
        # and extension modules keep the runtime's weak 0
        f.write(f"@pys_plain = constant i64 {1 if plain else 0}\n")
    # compiled code's objects that hold no reference from pys_new (allocelide, lowering's
    # alloc_call, which declares it only where it calls it): an AOT build or extension module is
    # optimized with pys_new out of line (runtime.c), so that LLVM deletes the allocations whose
    # objects nothing keeps; then LATE_INLINE puts pys_new, the allocator's fast path, into the
    # calls left (the JIT tier calls the shared runtime's pys_new, which it never inlines)
    newalloc = (cmd == "build" or cmd == "ext") and "@pys_new(" in ir
    f.close()
    tc = [q(paths[i]) if paths[i] != "" else tools[i] for i in range(len(tools))]
    msg = ""
    code = 0
    usebc = rtb  # the runtime this run links: the cache's, or the one it builds (part, parto, partso)
    useo = rto
    useso = ""  # (the shared library this run loads, if any: lli links useo without one)
    if rtir != "":
        f = open(rpl, "w", encoding=RAW)
        f.write(address_runtime_ir(rtir) if asan else rtir)
        f.close()
        # clang compiles the bytes hashed: runtime.c's (behind #line, so that its messages, UBSan's too,
        # say runtime.c) from a file of this run's, and beside it, as beside runtime.c, those of the
        # files it includes, where its quoted includes find them (read from clang's standard input,
        # runtime.c would look for them in the current directory)
        f = open(rcc, "w", encoding=RAW, newline="")
        f.write('#line 1 "runtime.c"\n' + rc[0])
        f.close()
        sub: list[str] = []
        for p in RTPARTS:
            if p[: p.rfind("/")] not in sub:
                sub.append(p[: p.rfind("/")])
        sh("mkdir " + " ".join([q(tmp + "/" + d) for d in sub]))
        for i in range(len(RTPARTS)):
            f = open(tmp + "/" + RTPARTS[i], "w", encoding=RAW, newline="")
            f.write(rs[i][0])
            f.close()
        # one module, optimized once: LLVM inlines runtime.c's helpers into runtime.py's code. No
        # pipes: a step that fails must fail the build, not hand the next one an empty module
        # IR input needs sanitize_address attributes as well as the ASan pass.
        # Clang supplies the selected target/layout and sanitizer options (including
        # recovery), then instruments only the subset module: running ASan over
        # the combined module would instrument runtime.c a second time. Keep the
        # ASan constructors outside COMDAT groups in all modules (ctorflags),
        # including C and the extension glue, as the user module is linked first.
        modules = f"{q(rpl)} {q(rcb)}"
        sanitize = ""
        if asan:
            modules = f"{q(rcb)} {q(rpb)}"
            sanitize = f"{tc[0]} -O2 -emit-llvm -c -x ir {q(rpl)} -o {q(rpb)} -Wno-override-module -Wno-unused-command-line-argument{cflags} -mllvm -asan-with-comdat=0 -fexceptions && "
        cstarted = timing_start()
        cbuild = f"{tc[0]} -O2 -S -emit-llvm -x c {q(rcc)} -o {q(rll)} -Wno-unused-command-line-argument{cflags}{ctorflags} -fexceptions && {strip} {q(rll)} > {q(rsl)}"
        ccached = ""
        cline = ""
        chit = False
        if cache_c and "" not in paths[:2] and "" not in times[:2] and all(settled(t, now) for t in times[:2]):
            # Capture headers and target macros once; compile those same bytes.
            # Warnings, semantic temporary paths and unstable tools use the
            # original path so diagnostics and instrumentation stay unchanged.
            pre = tmp + "/runtime.i"
            perr = tmp + "/runtime-preprocess.err"
            prepared = timed_sh("runtime.c_preprocess", f"{tc[0]} -O2 -E -x c {q(rcc)} -o {q(pre)} -fexceptions 2> {q(perr)}")
            if prepared == 0 and os.path.getsize(perr) == 0 and [stat3(p) for p in paths[:2]] == times[:2]:
                f = open(pre, "r", encoding=RAW, newline="")
                captured = runtime_c_snapshot(f.read(), tmp)
                f.close()
                if captured != "":
                    cline = fnv("\n".join([os.path.realpath(p) for p in paths[:2]]))
                    ccached = cache + "/runtime-c-" + cline + "-" + runtime_c_key(captured, paths, times, strip) + ".bc"
                    f = open(pre, "w", encoding=RAW, newline="")
                    f.write(captured)
                    f.close()
                    # Readers take a private copy before validation; another
                    # build may replace/prune the entry at any point. A missing,
                    # unreadable or malformed entry is a miss, not a build error.
                    chit = timed_sh("runtime.c_cache_read", f"(test -f {q(ccached)} && test ! -L {q(ccached)} && cp {q(ccached)} {q(rcb)} && {tc[3]} -passes=verify -disable-output {q(rcb)}) 2> /dev/null") == 0
                    cbuild = f"{tc[0]} -O2 -S -emit-llvm -x cpp-output {q(pre)} -o {q(rll)} -Wno-unused-command-line-argument -fexceptions && {strip} {q(rll)} > {q(rsl)}"
        code = 0 if chit else timed_sh("runtime.c", sanitize + cbuild)
        if code == 0 and not chit:
            # (between clang and llvm-as: the bitcode cached and linked holds the shared list tags)
            code = retag_runtime_file(rsl)
            if code == 0:
                code = timed_sh("runtime.c_assemble", f"{tc[1]} {q(rsl)} -o {q(rcb)}")
        if code == 0:
            code = timed_sh("runtime.link_optimize", f"{tc[2]} {modules} -o {q(lnk)} && {tc[3]} -O2 {q(lnk)} -o {q(part)}")
        if code == 0 and ccached != "" and not chit and [stat3(p) for p in paths[:2]] == times[:2]:
            # Stage privately on the cache filesystem; rename only a complete
            # file. Publication failure cannot invalidate the successful build.
            # Keep one entry per tool pair; concurrent readers tolerate pruning.
            stage = ccached + "." + own
            old = q(cache) + "/runtime-c-" + cline + "-" + "?" * 16 + ".bc"
            sh(f"""(umask 077; mkdir {q(stage)} && {{ test ! -d {q(ccached)} && cp {q(rcb)} {q(stage + '/entry')} && mv -f {q(stage + '/entry')} {q(ccached)} && for f in {old}; do [ "$f" = {q(ccached)} ] || rm -f "$f"; done; rm -f {q(stage + '/entry')}; rmdir {q(stage)}; }}) 2> /dev/null""")
        timing_end("runtime.llvm_build", cstarted)
        for p in RTPARTS:
            os.remove(tmp + "/" + p)
        for d in sub:
            os.rmdir(tmp + "/" + d)
        usebc = part
    elif not trusted or not os.path.exists(rtb):
        code = 1  # (runtime.c, a file it includes or runtime.py cannot be read)
    if code == 0 and cmd == "run" and (rtir != "" or not os.path.exists(rto)):
        # (from the bitcode, so runtime.py's part is in it; sanitizer passes instrumented the runtime already.
        # -x ir: clang would take a name not ending in .bc, as part's, for a linker input, and do nothing)
        code = timed_sh("runtime.codegen", f"{tc[0]} -O2 -fPIC -c -x ir {q(usebc)} -o {q(parto)} -Wno-unused-command-line-argument{ccflags}")
        useo = parto
    if code == 0 and cmd == "run" and PLATFORM == "linux" and pcroot == "":
        # the shared library: the cache's, made from the cache's .o, or one of this run's (from its own
        # .o, or from the cache's where no library is cached: published as the .o is). -Bsymbolic: the
        # runtime's calls of its own functions go to them, not through the PLT; libm and libdl are the
        # C library functions runtime.c calls, and pys_obj_hooks is all the program calls of RTSO. A
        # cache that cannot be written, or whose file system runs nothing (mounted noexec: lli could
        # map no library from it, which a script there shows first), gets none, nor does a link that
        # fails, and a run that may not execute the library it finds uses none (see opt's shell
        # below): lli links the .o then, as elsewhere
        useso = rts
        if useo == parto or not os.path.exists(rts):
            f = open(rso, "w", encoding=RAW)
            f.write(RTSO)
            f.close()
            xp = f"{rts}.x.{os.getpid()}.{own}"
            useso = partso if timed_sh("runtime.shared_link", f"{{ printf '#!/bin/sh\\n' > {q(xp)} && chmod +x {q(xp)} && {q(xp)} && {tc[0]} -shared -fPIC -O2 -x c {q(rso)} -x none {q(useo)} -o {q(partso)} -Wl,-Bsymbolic -lm -ldl -Wno-unused-command-line-argument{ccflags}; }} 2> /dev/null") == 0 else ""
            sh(f"rm -f {q(xp)}")
    # pystachy ext links two more C files, compiled as runtime.c is and cached beside it by the same
    # rules: pyembed.c (CPython in the process, hosting an extension module: its stdio hooks) and
    # pyext.c for the ABI; a program that embeds CPython (lib/pyobj.py) links pyembed.c alone. Each is
    # named by the fnv() of the runtime's key, its tag and its bytes, runtime-py-<L>-<G>.<tag>.bc, and
    # built under a name of its own (not part, which may hold this run's runtime): [tag, cached name,
    # the name this run links, partial name]
    glue: list[list[str]] = []
    if code == 0 and (cmd == "ext" or embed):
        cs = [["pyembed", "pyembed.c", ""]] + ([[f"pyext-{abi}", "pyext.c", " -DPYX_ABI3T" if abi == "abi3t" else ""]] if cmd == "ext" else [])
        for g in cs:
            gs = hashed(home + "/" + g[1], memo, now, False)
            gb = f"{cache}/runtime-py-{lin}-{fnv(key + ' ' + g[0] + ' ' + gs[1])}.{g[0]}.bc"
            if trusted and gs[1] != "" and os.path.exists(gb):
                glue.append([g[0], gb, gb, ""])
                continue
            gs = hashed(home + "/" + g[1], memo, now, True)
            gb = f"{cache}/runtime-py-{lin}-{fnv(key + ' ' + g[0] + ' ' + gs[1])}.{g[0]}.bc"
            gp = f"{gb}.{os.getpid()}.{own}"
            glue.append([g[0], gb, gp, gp])
            if gs[1] == "":
                code = 1  # (it cannot be read)
                break
            f = open(tmp + "/" + g[1], "w", encoding=RAW, newline="")
            f.write(f'#line 1 "{g[1]}"\n' + gs[0])
            f.close()
            code = sh(f"{tc[0]} -O2 -fPIC -S -emit-llvm -x c - -o {q(rll)} -Wno-unused-command-line-argument{cflags}{ctorflags} -fexceptions{g[2]} < {q(tmp + '/' + g[1])} && {strip} {q(rll)} > {q(rsl)} && {tc[1]} {q(rsl)} -o {q(gp)}")
            if code != 0:
                break
    # pystachy run of a program that embeds CPython: pyembed.c's machine code too, which lli loads
    # (-extra-object), cached beside its bitcode as the runtime's is: [cached name, the name this run
    # loads, partial name]
    peo = ["", "", ""]
    if code == 0 and embed and cmd == "run":
        pc = glue[0][1][:-3] + ".o"
        if trusted and glue[0][3] == "" and os.path.exists(pc):
            peo = [pc, pc, ""]
        else:
            peo = [pc, f"{pc}.{os.getpid()}.{own}", f"{pc}.{os.getpid()}.{own}"]
            code = sh(f"{tc[0]} -O2 -fPIC -c -x ir {q(glue[0][2])} -o {q(peo[2])} -Wno-unused-command-line-argument{ccflags}")
    # what this run built is published if the tools' times had settled and they and the compiler are
    # as they were (else it uses it alone), with the hashes learnt
    mvs: list[str] = []
    pub = code == 0 and trusted and len([t for t in times if not settled(t, now)]) == 0 and [stat3(p) for p in paths] == times and stat3(comp) == cst and [stat3(p) for p in sources] == sourceborn
    if pub and (usebc == part or useo == parto or useso == partso):
        if usebc == part:
            mvs.append(f"mv -f {q(part)} {q(rtb)}")
        if useo == parto:
            mvs.append(f"mv -f {q(parto)} {q(rto)}")
        if useso == partso:
            mvs.append(f"mv -f {q(partso)} {q(rts)}")
        old = f"{q(cache)}/runtime-py-{lin}-{'?' * 16}"
        mvs.append(f"for f in {old}.bc {old}.o {old}.so {old}.target; do case $f in {q(rtb)} | {q(rto)} | {q(rts)} | {q(rtb[:-3] + '.target')}) ;; *) rm -f \"$f\" ;; esac; done")
    for g in glue:
        if pub and g[3] != "":
            old = f"{q(cache)}/runtime-py-{lin}-{'?' * 16}.{g[0]}.bc"
            mvs.append(f"mv -f {q(g[3])} {q(g[1])}; for f in {old}; do [ \"$f\" = {q(g[1])} ] || rm -f \"$f\"; done")
    if pub and peo[2] != "":
        old = f"{q(cache)}/runtime-py-{lin}-{'?' * 16}.pyembed.o"
        mvs.append(f"mv -f {q(peo[2])} {q(peo[0])}; for f in {old}; do [ \"$f\" = {q(peo[0])} ] || rm -f \"$f\"; done")
    learnt = "".join([f"{k} {memo[k]}\n" for k in [k for k in memo][-64:]])
    hp = f"{hf}.{os.getpid()}.{own}"
    if learnt != known:
        try:
            f = open(hp, "w", encoding=RAW)
            f.write(learnt)
            f.close()
            mvs.append(f"mv -f {q(hp)} {q(hf)}")
        except OSError:
            pass  # (a cache that cannot be written: the hashes are made again)
    if len(mvs) > 0:
        sh("; ".join(mvs))
        if usebc == part and not os.path.exists(part):
            usebc = rtb
        if useo == parto and not os.path.exists(parto):
            useo = rto
        if useso == partso and not os.path.exists(partso):
            useso = rts
        for g in glue:
            if g[2] == g[3] and not os.path.exists(g[3]):
                g[2] = g[1]
        if peo[1] == peo[2] and peo[2] != "" and not os.path.exists(peo[2]):
            peo[1] = peo[0]
    llvm = q(llvm) if llvm != "" else ""  # shell prefix: preserve spaces and literal metacharacters
    program = ll
    if code == 0 and asan and cmd != "run":
        # Clang needs both sanitize_address attributes and the sanitizer flag for
        # LLVM input. Instrument only the generated module, before linking the
        # already-instrumented runtime/glue. Ungrouped constructors avoid the
        # COMDAT collision described for runtime.py above. The retained IR stays
        # the frontend's original, target-independent output.
        code = timed_sh("program.asan", f"{llvm}clang -O{aotopt} -emit-llvm -c -x ir {q(ll)} -o {q(abc)} -Wno-override-module -Wno-unused-command-line-argument{cflags} -mllvm -asan-with-comdat=0 -fexceptions")
        program = abc
        if code != 0:
            msg = "cannot instrument generated program with AddressSanitizer (see PYSTACHY_LLVM, PYSTACHY_CFLAGS)"
    link = f"{llvm}llvm-link --only-needed {q(program)} {q(usebc)} -o {q(bc)}"
    if embed and cmd == "build":
        link = f"{llvm}llvm-link {q(program)} {q(glue[0][2])} -o {q(lnk)} && {llvm}llvm-link --only-needed {q(lnk)} {q(usebc)} -o {q(bc)}"
    libs = "".join([" " + (q(x) + " " + q("-Wl,-rpath," + x[: x.rfind("/")]) if "/" in x else q("-l:" + x)) for x in LIBS if x != "-"])  # (libpython)
    libs += " -ldl" if len(LINKDL) > 0 or embed or cmd == "ext" else ""  # (dlopen, dlsym: @ffi.extern, pyembed.c)
    if code != 0:
        if msg == "":
            msg = "cannot build the runtime (install LLVM 18 on Linux or LLVM 20 on macOS; see PYSTACHY_LLVM, PYSTACHY_CFLAGS)"
    elif cmd == "ext":
        # a CPython extension module: program, pyext.c, pyembed.c and runtime as one module, of which
        # only PyInit_<name> stays visible (the C files' bitcode is cached as the runtime's is: glue)
        entry = "PyModExport_" if abi == "abi3t" else "PyInit_"
        if out == "":
            out = diagnostics.SRC[:-3] + "." + abi + ".so"
        # (allocelide: pys_new stays visible through -O2, then the late step inlines it and hides it
        # as the rest)
        public = f"{entry}{ext}" + (",pys_new" if newalloc else "")
        inline = (f" && {llvm}opt -passes='{LATE_PASSES},internalize,globaldce' {LATE_INLINE}"
                  f" -internalize-public-api-list={entry}{ext} {q(bc)} -o {q(bc)}") if newalloc else ""
        code = timed_sh("extension.backend", f"{llvm}llvm-link {q(program)} {q(glue[1][2])} {q(glue[0][2])} -o {q(lnk)} && {llvm}llvm-link --only-needed {q(lnk)} {q(usebc)} -o {q(bc)}"
                  + f" && {llvm}opt -passes='internalize,default<O2>' -internalize-public-api-list={public} {q(bc)} -o {q(bc)}" + inline
                  + f" && {llvm}clang -O2 -fPIC -c {q(bc)} -o {q(obj)} -Wno-unused-command-line-argument{ccflags} && {llvm}clang -shared {q(obj)} -o {q(out)}{libs} -lm{cflags}")
    elif cmd == "build":
        # AOT tier: default -O2 over program + runtime as one module. Experimental
        # lower tiers trade optimization time for execution speed of temporary builds.
        # With allocelide, clang optimizes it to bitcode, the late step inlines pys_new, the
        # allocator's fast path, into the remaining calls, and clang compiles that without
        # optimizing it again (the same code generation: a module without pys_new keeps the one step)
        if out == "":
            out = diagnostics.SRC[:-3] if diagnostics.SRC.endswith(".py") else diagnostics.SRC + ".exe"
        code = timed_sh("program.llvm_link", link)
        if code == 0 and newalloc:
            code = timed_sh("program.llvm_optimize", f"{llvm}clang -O{aotopt} -c -emit-llvm {q(bc)} -o {q(obc)} -Wno-unused-command-line-argument{ccflags}")
        if code == 0 and newalloc:
            code = timed_sh("program.late_inline", f"{llvm}opt -passes={LATE_PASSES} {LATE_INLINE} {q(obc)} -o {q(lbc)}")
        if code == 0:
            cc = f"{llvm}clang -O{aotopt} -c -Xclang -disable-llvm-passes {q(lbc)}" if newalloc else f"{llvm}clang -O{aotopt} -c {q(bc)}"
            code = timed_sh("program.codegen" if newalloc else "program.optimize_codegen", cc + f" -o {q(obj)} -Wno-unused-command-line-argument{ccflags}")
        if code == 0:
            code = timed_sh("program.link", f"{llvm}clang {q(obj)} -o {q(out)}{libs} -lm{cflags}")
    else:
        # Match the precompiled runtime's target before instcombine folds sizeof/GEP.
        # LLVM's default layout gives i64 only four-byte alignment; ORC later installs
        # the host layout, too late to repair an allocation size already folded to a
        # constant. Cache just the two target directives beside the keyed runtime.
        target = rtb[:-3] + ".target"
        layout = ""
        if trusted and os.path.exists(target):
            try:
                f = open(target, "r", encoding=RAW)
                layout = f.read()
                f.close()
            except OSError:
                pass  # (optional metadata: unreadable means derive it from the bitcode)
        if layout == "":
            code = sh(f"{tc[3]} -S -passes=verify {q(usebc)} -o {q(rsl)}")
            if code == 0:
                f = open(rsl, "r", encoding=RAW)
                layout = "\n".join([s for s in f.read().split("\n") if s.startswith("target ")]) + "\n"
                f.close()
                if pub:
                    tp = f"{target}.{os.getpid()}.{own}"
                    try:
                        f = open(tp, "w", encoding=RAW)
                        f.write(layout)
                        f.close()
                        sh(f"mv -f {q(tp)} {q(target)} 2> /dev/null")
                    except OSError:
                        pass  # (a read-only cache still supplies its runtime)
                    if os.path.exists(tp):
                        try:
                            os.remove(tp)
                        except OSError:
                            pass
        # What runs the program: Pystachy's JIT runner where it can be built (jit_launcher), else lli,
        # which with PYSTACHY_JIT_CODEGEN=0 links an object of llc's (below). PYSTACHY_TIMING names it
        # (program.jit_runner.lljit, or program.jit_runner.lli.REASON)
        lljit = ""
        if code == 0:
            looked = timing_start()
            chosen = jit_launcher(runner, home, cache, lli, paths[0], rj, memo, now, tmp, own, pcroot == "")
            lljit = chosen[0]
            timing_end("program.jit_runner." + ("lljit" if lljit != "" else "lli." + chosen[1]), looked)
        llcobj = codegen == "0" and lljit == ""
        jir = jit_alloc(ir)  # (with the allocator's fast path: JITFAST)
        if code == 0:
            f = open(ll, "w", encoding=RAW)
            # (the shared library's callbacks: RTSO; with llc, lli's main module holds them, below)
            f.write(layout + jir + (OBJHOOKS if useso != "" and not llcobj else ""))
            f.close()
        # JIT tier: discard unused internal functions before SSA cleanup and ORC's module-wide
        # code generation. The frontend still checks their bodies; external pys_obj_* dispatch
        # callbacks stay visible to the precompiled runtime (which this tier never inlines). A
        # program of up to JIT_INLINE lines of IR has its own functions inlined into their callers
        # first, bottom-up (cgscc), each then cleaned up as before
        clean = "function(mem2reg,instcombine<no-verify-fixpoint>,simplifycfg)"
        if ir.split("; pystachy source locations\n")[0].count("\n") <= jitinline:
            clean = f"cgscc(inline,{clean})"
        # Recursion accounting helpers belong to the program module, even when the
        # runtime is a separate library. Inline only those explicitly marked helpers
        # regardless of the user-function budget, including PYSTACHY_JIT_INLINE=0.
        passes = f"globaldce,always-inline,{clean}"
        if "@llvm.coro.id(" in ir:
            # generators are LLVM coroutines (docs/internals.md#generators), which lli cannot run
            # before LLVM's coroutine passes lower them: coro-early, then coro-split in the same
            # bottom-up walk as the inliner (so a generator is split before its callers inline its
            # ramp, and coro-elide may put a loop's generator frame in the loop's own frame), then
            # coro-cleanup. A module without them keeps the pipeline above
            split = clean.replace("simplifycfg)", "simplifycfg,coro-elide),coro-split") if clean.startswith("cgscc(") else f"cgscc({clean},coro-split)"
            passes = f"coro-early,globaldce,always-inline,{split},coro-cleanup,globaldce"
        # SSA promotion can leave unused feedback cycles (including numeric identity
        # generations). Remove those after inlining and coroutine lowering are complete;
        # instcombine alone does not eliminate cycles with no externally used result.
        late = "," + LATE_PASSES if jir != ir else ""
        # LLVM's -O0 PHI elimination (seen in 18, 20 and 23) lowers a landing pad's PHI by reusing
        # an identical PHI of the invoke's normal successor, whose copies follow the call: an except
        # clause then read values its loop never set or had since changed. Splitting critical edges
        # last gives such successors predecessors of their own, and the landing pad its own copies,
        # whichever program generates the code at -O0 (the JIT runner, or llc)
        split = ",function(break-crit-edges)" if codegen == "0" else ""
        fast = f"{llvm}opt -passes='{passes},function(early-cse,adce){late}{split}'" + (JITLATE if late != "" else "")
        if code == 0:
            # the cache's library may lie on a file system mounted noexec since it was made (or copied
            # there), from which lli could map nothing: the shell that runs opt first asks whether this
            # run may execute it (Linux's access(X_OK) fails on such a mount), and exits 3 if not, when
            # the program is written again without the callbacks' constructor, for lli to link the .o.
            # So with the JIT runner, which lies beside it: if this run may not execute it, opt's shell
            # exits 4, and lli runs the program, with llc's object for PYSTACHY_JIT_CODEGEN=0
            code = timed_sh("program.jit_optimize", (f"[ -x {q(useso)} ] || exit 3; " if useso != "" else "")
                            + (f"[ -x {q(lljit)} ] || exit 4; " if lljit != "" else "") + f"{fast} {q(ll)} -o {q(bc)}")
            while (code == 3 and useso != "") or (code == 4 and lljit != ""):
                if code == 3:
                    useso = ""
                else:
                    lljit = ""
                    llcobj = codegen == "0"
                    timing_end("program.jit_runner.lli.not-executable", timing_start())
                f = open(ll, "w", encoding=RAW)
                f.write(layout + jir + (OBJHOOKS if useso != "" and not llcobj else ""))
                f.close()
                code = timed_sh("program.jit_optimize", (f"[ -x {q(lljit)} ] || exit 4; " if lljit != "" else "") + f"{fast} {q(ll)} -o {q(bc)}")
        if code == 0:
            if pcroot != "":
                # The ordinary JIT cleanup above already ran. Disable further
                # LLVM IR passes: using the whole-program AOT pipeline here can
                # change floating-point results and allocation behavior.
                cachecode = sh(f"{{ {llvm}clang -O2 -Xclang -disable-llvm-passes -mllvm -profile-guided-section-prefix=false -fPIC -c {q(bc)} -o {q(obj)}"
                               + f" && {llvm}clang --ld-path=/usr/bin/ld {q(obj)} {q(useo)} -o {q(pcout)} -lm -ldl -Wl,-t > {q(pclink)}; }} 2> {q(pcerror)}")
                if cachecode == 0 and pub and cached_run.link_inputs(pclink, obj, useo):
                    # The first link discovers inputs; snapshot them before the
                    # final link, then require the same resolution and contents.
                    # Recording newly discovered CRT/archive files only after
                    # their consuming link could publish against newer bytes.
                    cachecode = sh(f"{llvm}clang --ld-path=/usr/bin/ld {q(obj)} {q(useo)} -o {q(pcout)} -lm -ldl -Wl,-t > {q(pclink2)} 2> {q(pcerror)}")
                    if cachecode == 0 and cached_run.same_link_inputs(pclink, pclink2) and cached_run.link_inputs(pclink2, obj, useo):
                        pcexe = program_cache.publish(pcroot, pccontext, pcout)
                    if pcexe != "":
                        for p in [ll, bc, obj, pcout, pclink, pclink2, pcerror, rcc, rll, rsl, rcb, rpl, rpb, lnk, part, parto, partso, hp, rso]:
                            if os.path.exists(p):
                                os.remove(p)
                        os.rmdir(tmp)
                        cached_run.trace("stored")
                        timing_end("driver.prepare_run", total)
                        cached_run.execute(pcexe, diagnostics.SRC, rest)
                cached_run.trace("bypass native artifact unavailable")
                program_cache.stop()
            if llcobj:
                # PYSTACHY_JIT_CODEGEN=0: llc's -O0 code generation, for the CPU lli's ORC compiles
                # for (the module's triple with LLVM's default CPU: neither tool is given -mcpu, and
                # no function names one), with lli's flag above, in position-independent code, which
                # ORC's JITLink links. ORC runs the constructors of IR modules alone, so lli's main
                # module holds the program's target and the shared library's callbacks, if any
                code = timed_sh("program.jit_codegen", f"{llvm}llc -O0 -filetype=obj -relocation-model=pic -profile-guided-section-prefix=false {q(bc)} -o {q(jobj)}")
                if code == 0:
                    f = open(jmain, "w", encoding=RAW)
                    f.write(layout + (OBJHOOKS_MAIN if useso != "" else ""))
                    f.close()
        if code == 0:
            # This process becomes the JIT runner or lli, with its inputs on allocated descriptors.
            # Keep those files open while unlinking temporary artifacts; inherited
            # descriptors belong to the caller and must never be replaced.
            # PYSTACHY_GC_STRESS_PROGRAM: the program's own collection interval, apart from the
            # compiler's (PYSTACHY_GC_STRESS), so that the tests can stress programs without stressing
            # their compilation
            for p in [ll, obj, pcout, pclink, pclink2, pcerror, rcc, rll, rsl, rcb, rpl, rpb, lnk, part, hp, rso, tmp + "/runtime.i", tmp + "/runtime-preprocess.err", tmp + "/pyembed.c"] + [g[3] for g in glue]:
                if os.path.exists(p):
                    os.remove(p)
            # Each standard stream the caller closed holds /dev/null until the program starts, so
            # that neither the inputs (always at least 3) nor lli's own files take it. Before any
            # of its code runs, the program's runtime closes these and the inputs and restores the
            # signal dispositions that LLVM's handlers replaced in lli (PYSTACHY_JIT_HANDOFF,
            # runtime.c's jit_handoff; the JIT runner replaces none): the program and its children
            # see the caller's descriptors and dispositions.
            reserved = []
            inputs = []
            pinned = []
            try:
                for i in range(3):
                    stream = open(os.devnull, "r+b")
                    if stream.fileno() >= 3:
                        stream.close()
                        break
                    reserved.append(stream)
                # the main module (the program's bitcode, or with llc the module beside its object),
                # the runtime, the embedding's object and llc's object
                for p in [jmain if llcobj else bc, useso if useso != "" else useo] + ([peo[1]] if embed else []) + ([jobj] if llcobj else []):
                    inputs.append(open(p, "rb"))
                # and the JIT runner, run from its descriptor: a run that publishes another runner
                # removes this one's file, which then still runs. Removed before (since opt's shell
                # found it), lli runs the same bitcode, at ORC's own level of code generation
                if lljit != "":
                    try:
                        pinned.append(open(lljit, "rb"))
                    except OSError:
                        lljit = ""
                        timing_end("program.jit_runner.lli.removed", timing_start())
                for stream in reserved + inputs + pinned:
                    os.set_inheritable(stream.fileno(), True)
                gsp = os.getenv("PYSTACHY_GC_STRESS_PROGRAM", "")
                env = f"PYSTACHY_GC_STRESS={q(gsp)} " if gsp != "" else ""
                handoff = str(ignored_signals()) + ";" + ",".join([str(stream.fileno()) for stream in reserved + inputs + pinned])
                env += f"PYSTACHY_JIT_HANDOFF={q(handoff)} "
                # Embedding also loads libpython and the pyembed machine code.
                pe = "".join([" -dlopen=" + q(x) for x in LIBS]) + (" -extra-object=/dev/fd/" + str(inputs[2].fileno()) if embed else "")
                rt = (" -dlopen=" if useso != "" else " -extra-object=") + "/dev/fd/" + str(inputs[1].fileno())
                prog = " -extra-object=/dev/fd/" + str(inputs[-1].fileno()) if llcobj else ""
                archive = ""
                if useso == "" and any([a.startswith("--rtlib=") or a.startswith("-rtlib=") for a in flags]):
                    # A shared runtime's native link includes the selected compiler builtins. When
                    # lli instead links the object (e.g. a noexec cache), it needs that archive too:
                    # compiler-rt supplies checked wide arithmetic that libgcc/UBSan do not export.
                    archive = f"jit_rtlib=$({tc[0]} -print-libgcc-file-name{ccflags}) || exit 1; "
                    archive += '[ -f "$jit_rtlib" ] || { echo "cannot find compiler runtime archive: $jit_rtlib" >&2; exit 1; }; '
                    rt += ' -extra-archive="$jit_rtlib"'
                # (the runner's -O: its level of code generation, which lli's ORC does not take)
                launch = f"/dev/fd/{pinned[0].fileno()} -O{codegen}" if lljit != "" else f"{llvm}lli"
                run = f"unset PYSTACHY_PROGRAM_CACHE_LOCK; {archive}{env}PYSTACHY_ARGV0={q(diagnostics.SRC)} exec {launch}{jitflags}{pe}{rt}{prog} /dev/fd/{inputs[0].fileno()} {' '.join([q(a) for a in rest])}"
                for p in [bc, jobj, jmain, parto, partso, peo[2]]:
                    if p != "" and os.path.exists(p):
                        os.remove(p)
                os.rmdir(tmp)
                timing_end("driver.prepare_run", total)
                os.execv("/bin/sh", ["sh", "-c", run])
            finally:
                for stream in reserved + inputs + pinned:
                    stream.close()
    for p in [ll, abc, bc, obj, jobj, jmain, obc, lbc, pcout, pclink, pclink2, pcerror, rcc, rll, rsl, rcb, rpl, rpb, lnk, part, parto, partso, hp, rso, tmp + "/runtime.i", tmp + "/runtime-preprocess.err", tmp + "/pyembed.c", tmp + "/pyext.c", peo[2]] + [g[3] for g in glue]:
        if os.path.exists(p):
            os.remove(p)
    os.rmdir(tmp)
    if code == 0 and msg == "" and retained != "":
        try:
            publish_retained_ir(retained, diagnostics.SRC, out, ir, own)
        except OSError:
            fail("cannot write --emit-ir output: " + retained, 0)
    timing_end("driver.total", total)
    if msg != "":
        fail(msg, 0)
    sys.exit(code)
