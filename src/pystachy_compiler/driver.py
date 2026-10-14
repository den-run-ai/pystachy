"""Driver component of the self-hosting Pystachy compiler."""
from __future__ import annotations
import os
import sys
import tempfile
import time
from src.pystachy_compiler import diagnostics
from src.pystachy_compiler.diagnostics import MAXNEST, RAW, fail
from src.pystachy_compiler.gen import Gen
from src.pystachy_compiler.lexer import Lexer
from src.pystachy_compiler.loader import Loader
from src.pystachy_compiler.parser import Parser
from src.pystachy_compiler.specs import JIT_INLINE, LINKDL, MODULES, OPTS
from src.pystachy_compiler.utils import optimizations


# Every hosted component contributes to runtime-cache identity and startup trust.
COMPILER_SOURCES: list[str] = [
    'src/__init__.py',
    'src/pystachy_compiler/__init__.py',
    'src/pystachy_compiler/analysis.py',
    'src/pystachy_compiler/builtins.py',
    'src/pystachy_compiler/calls.py',
    'src/pystachy_compiler/containers.py',
    'src/pystachy_compiler/conversions.py',
    'src/pystachy_compiler/declarations.py',
    'src/pystachy_compiler/diagnostics.py',
    'src/pystachy_compiler/driver.py',
    'src/pystachy_compiler/emission.py',
    'src/pystachy_compiler/exceptions.py',
    'src/pystachy_compiler/expressions.py',
    'src/pystachy_compiler/flow.py',
    'src/pystachy_compiler/functions.py',
    'src/pystachy_compiler/gen.py',
    'src/pystachy_compiler/ir.py',
    'src/pystachy_compiler/ircheck.py',
    'src/pystachy_compiler/lexer.py',
    'src/pystachy_compiler/loader.py',
    'src/pystachy_compiler/lowering.py',
    'src/pystachy_compiler/module.py',
    'src/pystachy_compiler/names.py',
    'src/pystachy_compiler/optimizations.py',
    'src/pystachy_compiler/parser.py',
    'src/pystachy_compiler/program.py',
    'src/pystachy_compiler/scope.py',
    'src/pystachy_compiler/specs.py',
    'src/pystachy_compiler/statements.py',
    'src/pystachy_compiler/syntax.py',
    'src/pystachy_compiler/templates.py',
    'src/pystachy_compiler/utils.py',
    'src/pystachy_compiler/variables.py',
]


def compile_program(path: str, src: str, dirs: list[str], ext: str) -> str:
    g = Gen()
    g.ext = ext
    ld = Loader(dirs)
    ld.ext = ext
    return g.program(ld.program(path, src))


def runtime_ir(path: str, src: str, cache: bool) -> str:
    # runtime.py (path, whose text, read as RAW, is src): the part of the runtime written in the
    # subset. Its pys_* functions are defined under their C names, with runtime.c's types, and
    # llvm-link joins them to runtime.c's code (runtime.c keeps a prototype of each). It imports only
    # builtin modules, and nothing runs its module code, so it holds only functions.
    g = Gen()
    g.rtmode = True
    g.rtcache = cache  # (the driver's: then PYSTACHY_IRFX prints the program's summaries only)
    MODULES["_rt"] = True
    ld = Loader([])
    ld.rtmode = True
    ir = g.program(ld.program(path, src))
    del MODULES["_rt"]
    return ir


def q(s: str) -> str:
    return "'" + s.replace("'", "'\\''") + "'"


def sh(cmd: str) -> int:
    st = os.system(cmd)
    return st >> 8 if st & 255 == 0 else 1


# the lines of /proc/cpuinfo that tell which CPU -march=native compiles for (x86-64's, AArch64's)
CPUID: list[str] = ["vendor_id", "cpu family", "model", "model name", "stepping", "flags", "CPU implementer", "CPU architecture",
                    "CPU variant", "CPU part", "CPU revision", "Features"]
# the files that runtime.c includes from beside it, each DIR/NAME (ryu/: Ryu's d2s, a float's shortest
# digits, ryu/README.md): the runtime is built from their bytes too
RTPARTS: list[str] = ["ryu/d2s.c", "ryu/ryu.h", "ryu/common.h", "ryu/digit_table.h", "ryu/d2s_intrinsics.h",
                      "ryu/d2s_small_table.h"]


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


def main() -> None:
    # the parser and the code generator recurse for each level of nesting (at most MAXNEST), a
    # dozen calls deep each: more than CPython's default limit of 1,000 calls when it runs this file
    sys.setrecursionlimit(MAXNEST * 40)
    argv = sys.argv
    if len(argv) == 2 and (argv[1] == "--version" or argv[1] == "-V"):
        print(compiler_version(compiler_home()))
        return
    if len(argv) < 3 or (argv[1] != "run" and argv[1] != "build" and argv[1] != "ext" and argv[1] != "ir" and argv[1] != "check" and argv[1] != "rt"):
        print("usage: pystachy run FILE.py [ARGS...]   JIT-compile and run (LLVM ORC via lli)", file=sys.stderr)
        print("       pystachy build FILE.py [-o EXE]  compile ahead of time to a native executable", file=sys.stderr)
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
    if cmd == "check":
        f = open(diagnostics.SRC, "r", encoding=RAW)
        Parser(Lexer(f.read(), 1).file()).module()
        f.close()
        return
    if cmd == "rt":
        f = open(diagnostics.SRC, "r", encoding=RAW)
        ir = runtime_ir(diagnostics.SRC, f.read(), False)
        f.close()
        if len(argv) == 5 and argv[3] == "-o":
            f = open(argv[4], "w", encoding=RAW)
            f.write(ir)
            f.close()
        else:
            print(ir, end="")
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
    for d in dirs[:-1]:
        if os.path.exists(d + "/ffi.py") or os.path.exists(d + "/ffi/__init__.py"):
            del MODULES["ffi"]  # (the program's own ffi module comes first, as under CPython: Pystachy's is not imported then)
            break
    f = open(diagnostics.SRC, "r", encoding=RAW)
    ext = diagnostics.SRC[diagnostics.SRC.rfind("/") + 1 : -3] if cmd == "ext" and diagnostics.SRC.endswith(".py") else ""
    ir = compile_program(diagnostics.SRC, f.read(), dirs, ext)
    f.close()
    out = ""
    abi = "abi3"  # pystachy ext: abi3 (CPython 3.12+, GIL builds) or abi3t (3.15+, GIL and free-threaded)
    rest: list[str] = []
    i = 3
    while i < len(argv):
        if argv[i] == "-o" and i + 1 < len(argv) and cmd != "run":
            out = argv[i + 1]
            i += 2
        elif argv[i] == "--abi" and i + 1 < len(argv) and cmd == "ext" and (argv[i + 1] == "abi3" or argv[i + 1] == "abi3t"):
            abi = argv[i + 1]
            i += 2
        else:
            rest.append(argv[i])
            i += 1
    if cmd == "ir":
        if out == "":
            print(ir, end="")
        else:
            f = open(out, "w", encoding=RAW)
            f.write(ir)
            f.close()
        return
    rtc = home + "/runtime.c"
    rtpy = home + "/runtime.py"
    if not os.path.exists(rtc) or not os.path.exists(rtpy):
        fail("cannot find runtime.c and runtime.py next to the compiler; set PYSTACHY_HOME to the directory that holds them", 0)
    # PYSTACHY_CFLAGS: extra clang flags (e.g. -fsanitize=undefined) for the runtime and the AOT link.
    # The runtime is compiled with them and then -fexceptions (so they cannot drop it): a raise unwinds
    # through runtime functions to compiled code's landing pads, which -O2 would turn back into calls
    # if clang marked them nounwind. runtime.py goes through the optimizations on the IR as programs
    # do, so the ones PYSTACHY_OPT turns off count too: the cached runtime's key (below) has both
    flags = os.getenv("PYSTACHY_CFLAGS", "").split()
    on = optimizations()
    off = [o for o in OPTS if o not in on]
    keyed = flags + ["-fexceptions"]
    if len(off) > 0:
        keyed = keyed + ["PYSTACHY_OPT=-" + ",-".join(off)]
    cflags = "".join([" " + q(a) for a in flags])
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
    ask = [t for t in tools if llvm == ""]
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
        if byname:
            comp = got[len(ask) - 1]
    now = time.time()
    lines = [os.path.realpath(comp) if comp != "" else "", " ".join(keyed)]
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
    key = fnv("\n".join(lines + times + [rc[1], rp[1], rm[1]] + component_hashes + [x[1] for x in rs]))
    rtb = f"{cache}/runtime-py-{lin}-{key}.bc"
    rtir = ""
    if not trusted or not os.path.exists(rtb):
        # the bytes of runtime.c, of the files it includes and of runtime.py, read once: the runtime is
        # built from them, and named by their hash, so that an edit while it is built names another
        # runtime, which a later run builds
        rc = hashed(rtc, memo, now, True)
        rs = [hashed(home + "/" + p, memo, now, True) for p in RTPARTS]
        rp = hashed(rtpy, memo, now, True)
        key = fnv("\n".join(lines + times + [rc[1], rp[1], rm[1]] + component_hashes + [x[1] for x in rs]))
        rtb = f"{cache}/runtime-py-{lin}-{key}.bc"
        if (not trusted or not os.path.exists(rtb)) and rc[1] != "" and rp[1] != "" and "" not in [x[1] for x in rs]:
            # (an error in runtime.py exits: the private directory is made again after it)
            os.rmdir(tmp)
            src = diagnostics.SRC
            diagnostics.SRC = rtpy
            rtir = runtime_ir(rtpy, rp[0].replace("\r\n", "\n").replace("\r", "\n"), True)
            diagnostics.SRC = src
            tmp = tempfile.mkdtemp()
    ll = tmp + "/prog.ll"
    bc = tmp + "/prog.bc"
    obj = tmp + "/prog.o"
    rcc = tmp + "/runtime.c"
    rll = tmp + "/runtime.ll"
    rsl = tmp + "/runtime-s.ll"
    rcb = tmp + "/runtime-c.bc"
    rpl = tmp + "/rtpy.ll"
    lnk = tmp + "/runtime-l.bc"
    rto = rtb[:-3] + ".o"  # the runtime as machine code, for the JIT tier
    # the runtime's bitcode and machine code are written to names of this process's own in the
    # cache's directory, then renamed over the cache once complete (in one file system, so that the
    # rename is atomic). The process ID alone is no such name: processes in separate PID namespaces
    # share it (each container's first process is 1), so tmp's random name is in it too
    own = tmp[tmp.rfind("/") + 1 :]
    part = f"{rtb}.{os.getpid()}.{own}"
    parto = f"{rto}.{os.getpid()}.{own}"
    f = open(ll, "w", encoding=RAW)
    f.write(ir)
    f.close()
    tc = [q(paths[i]) if paths[i] != "" else tools[i] for i in range(len(tools))]
    msg = ""
    code = 0
    usebc = rtb  # the runtime this run links: the cache's, or the one it builds (part, parto)
    useo = rto
    if rtir != "":
        f = open(rpl, "w", encoding=RAW)
        f.write(rtir)
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
        code = sh(f"{tc[0]} -O2 -S -emit-llvm -x c {q(rcc)} -o {q(rll)}{cflags} -fexceptions && {strip} {q(rll)} > {q(rsl)} && {tc[1]} {q(rsl)} -o {q(rcb)} && {tc[2]} {q(rpl)} {q(rcb)} -o {q(lnk)} && {tc[3]} -O2 {q(lnk)} -o {q(part)}")
        for p in RTPARTS:
            os.remove(tmp + "/" + p)
        for d in sub:
            os.rmdir(tmp + "/" + d)
        usebc = part
    elif not trusted or not os.path.exists(rtb):
        code = 1  # (runtime.c, a file it includes or runtime.py cannot be read)
    if code == 0 and cmd == "run" and (rtir != "" or not os.path.exists(rto)):
        # (from the bitcode, so runtime.py's part is in it; sanitizer flags instrumented runtime.c already.
        # -x ir: clang would take a name not ending in .bc, as part's, for a linker input, and do nothing)
        code = sh(f"{tc[0]} -O2 -fPIC -c -x ir {q(usebc)} -o {q(parto)} -Wno-unused-command-line-argument{ccflags}")
        useo = parto
    # pystachy ext links two more C files, compiled as runtime.c is and cached beside it by the same
    # rules: pyembed.c (CPython in the process, hosting an extension module: its stdio hooks) and
    # pyext.c for the ABI. Each is named by the fnv() of the runtime's key, its tag and its bytes,
    # runtime-py-<L>-<G>.<tag>.bc, and built under a name of its own (not part, which may hold this
    # run's runtime): [tag, cached name, the name this run links, partial name]
    glue: list[list[str]] = []
    if code == 0 and cmd == "ext":
        for g in [["pyembed", "pyembed.c", ""], [f"pyext-{abi}", "pyext.c", " -DPYX_ABI3T" if abi == "abi3t" else ""]]:
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
            code = sh(f"{tc[0]} -O2 -fPIC -S -emit-llvm -x c - -o {q(rll)}{cflags} -fexceptions{g[2]} < {q(tmp + '/' + g[1])} && {strip} {q(rll)} > {q(rsl)} && {tc[1]} {q(rsl)} -o {q(gp)}")
            if code != 0:
                break
    # what this run built is published if the tools' times had settled and they and the compiler are
    # as they were (else it uses it alone), with the hashes learnt
    mvs: list[str] = []
    pub = code == 0 and trusted and len([t for t in times if not settled(t, now)]) == 0 and [stat3(p) for p in paths] == times and stat3(comp) == cst and [stat3(p) for p in sources] == sourceborn
    if pub and (usebc == part or useo == parto):
        if usebc == part:
            mvs.append(f"mv -f {q(part)} {q(rtb)}")
        if useo == parto:
            mvs.append(f"mv -f {q(parto)} {q(rto)}")
        old = f"{q(cache)}/runtime-py-{lin}-{'?' * 16}"
        mvs.append(f"for f in {old}.bc {old}.o; do case $f in {q(rtb)} | {q(rto)}) ;; *) rm -f \"$f\" ;; esac; done")
    for g in glue:
        if pub and g[3] != "":
            old = f"{q(cache)}/runtime-py-{lin}-{'?' * 16}.{g[0]}.bc"
            mvs.append(f"mv -f {q(g[3])} {q(g[1])}; for f in {old}; do [ \"$f\" = {q(g[1])} ] || rm -f \"$f\"; done")
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
        for g in glue:
            if g[2] == g[3] and not os.path.exists(g[3]):
                g[2] = g[1]
    llvm = q(llvm) if llvm != "" else ""  # shell prefix: preserve spaces and literal metacharacters
    link = f"{llvm}llvm-link --only-needed {q(ll)} {q(usebc)} -o {q(bc)}"
    libs = " -ldl" if len(LINKDL) > 0 or cmd == "ext" else ""  # (dlopen, dlsym: @ffi.extern, pyembed.c)
    if code != 0:
        msg = "cannot build the runtime (install LLVM 18 on Linux or LLVM 20 on macOS; see PYSTACHY_LLVM, PYSTACHY_CFLAGS)"
    elif cmd == "ext":
        # a CPython extension module: program, pyext.c, pyembed.c and runtime as one module, of which
        # only PyInit_<name> stays visible (the C files' bitcode is cached as the runtime's is: glue)
        entry = "PyModExport_" if abi == "abi3t" else "PyInit_"
        if out == "":
            out = diagnostics.SRC[:-3] + "." + abi + ".so"
        code = sh(f"{llvm}llvm-link {q(ll)} {q(glue[1][2])} {q(glue[0][2])} -o {q(lnk)} && {llvm}llvm-link --only-needed {q(lnk)} {q(usebc)} -o {q(bc)}"
                  + f" && {llvm}opt -passes='internalize,default<O2>' -internalize-public-api-list={entry}{ext} {q(bc)} -o {q(bc)}"
                  + f" && {llvm}clang -O2 -fPIC -c {q(bc)} -o {q(obj)} -Wno-unused-command-line-argument{ccflags} && {llvm}clang -shared {q(obj)} -o {q(out)}{libs} -lm{cflags}")
    elif cmd == "build":
        # AOT tier: full -O2 over program + runtime as one module (whole-program optimization)
        if out == "":
            out = diagnostics.SRC[:-3] if diagnostics.SRC.endswith(".py") else diagnostics.SRC + ".exe"
        code = sh(f"{link} && {llvm}clang -O2 -c {q(bc)} -o {q(obj)} -Wno-unused-command-line-argument{ccflags} && {llvm}clang {q(obj)} -o {q(out)}{libs} -lm{cflags}")
    else:
        # JIT tier: discard unused internal functions before SSA cleanup and ORC's module-wide
        # code generation. The frontend still checks their bodies; external pys_obj_* dispatch
        # callbacks stay visible to the precompiled runtime (which this tier never inlines). A
        # program of up to JIT_INLINE lines of IR has its own functions inlined into their callers
        # first, bottom-up (cgscc), each then cleaned up as before
        lim = os.getenv("PYSTACHY_JIT_INLINE", str(JIT_INLINE))
        if not lim.isdigit():
            fail(f"PYSTACHY_JIT_INLINE: {lim} is no number of lines (0 turns the JIT's inliner off)", 0)
        clean = "function(mem2reg,instcombine<no-verify-fixpoint>,simplifycfg)"
        if ir.count("\n") <= int(lim):
            clean = f"cgscc(inline,{clean})"
        fast = f"{llvm}opt -passes='globaldce,{clean}'"
        code = sh(f"{fast} {q(ll)} -o {q(bc)}")
        if code == 0:
            # then this process becomes lli, through a shell that opens the bitcode and the runtime's
            # machine code for it (the cache's, or this run's own) and removes the files: the program's
            # end is pystachy run's own, a signal that kills it too.
            # PYSTACHY_GC_STRESS_PROGRAM: the program's own collection interval, apart from the
            # compiler's (PYSTACHY_GC_STRESS), so that the tests can stress programs without stressing
            # their compilation
            for p in [ll, obj, rcc, rll, rsl, rcb, rpl, lnk, part, hp]:
                if os.path.exists(p):
                    os.remove(p)
            gsp = os.getenv("PYSTACHY_GC_STRESS_PROGRAM", "")
            env = f"PYSTACHY_GC_STRESS={q(gsp)} " if gsp != "" else ""
            run = f"{env}PYSTACHY_ARGV0={q(diagnostics.SRC)} exec {llvm}lli -extra-object=/dev/fd/8 /dev/fd/9 {' '.join([q(a) for a in rest])}"
            os.execv("/bin/sh", ["sh", "-c", f"exec 9< {q(bc)} 8< {q(useo)} && rm -f {q(bc)} {q(parto)} && rmdir {q(tmp)} && {run}"])
    for p in [ll, bc, obj, rcc, rll, rsl, rcb, rpl, lnk, part, parto, hp, tmp + "/pyembed.c", tmp + "/pyext.c"] + [g[3] for g in glue]:
        if os.path.exists(p):
            os.remove(p)
    os.rmdir(tmp)
    if msg != "":
        fail(msg, 0)
    sys.exit(code)
