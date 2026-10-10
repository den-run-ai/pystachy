# Spike (B): JIT a Pystachy-generated .ll inside the running CPython process through the
# LLVM 18 C API (ORC LLJIT) loaded with ctypes -- no new dependency (system libLLVM-18).
# usage: python3 jit_inproc.py PROG.ll RUNTIME(.o|.so|.bc) [steps...]
#   steps: fib greet checked main boom gcstress
import ctypes
import os
import sys
import time

T0 = time.perf_counter()
marks: list[tuple[str, float]] = []


def mark(what: str) -> None:
    marks.append((what, time.perf_counter()))


prog, rt = sys.argv[1], sys.argv[2]
steps = sys.argv[3:] or ["fib", "greet", "checked", "main"]
L = ctypes.CDLL("/usr/lib/llvm-18/lib/libLLVM.so.1")
mark("dlopen libLLVM")
vp = ctypes.c_void_p
L.LLVMGetErrorMessage.restype = ctypes.c_char_p  # (leaks the message: fine for a spike)
L.LLVMGetErrorMessage.argtypes = [vp]


def check(err: int | None, what: str) -> None:
    if err:
        sys.exit(f"{what}: {L.LLVMGetErrorMessage(err).decode()}")


for f in ("LLVMInitializeX86TargetInfo", "LLVMInitializeX86Target", "LLVMInitializeX86TargetMC", "LLVMInitializeX86AsmPrinter"):
    getattr(L, f)()
for name, res, args in [
    ("LLVMOrcCreateLLJIT", vp, [ctypes.POINTER(vp), vp]),
    ("LLVMOrcLLJITGetMainJITDylib", vp, [vp]),
    ("LLVMOrcLLJITGetGlobalPrefix", ctypes.c_char, [vp]),
    ("LLVMOrcCreateDynamicLibrarySearchGeneratorForProcess", vp, [ctypes.POINTER(vp), ctypes.c_char, vp, vp]),
    ("LLVMOrcJITDylibAddGenerator", None, [vp, vp]),
    ("LLVMOrcCreateDynamicLibrarySearchGeneratorForPath", vp, [ctypes.POINTER(vp), ctypes.c_char_p, ctypes.c_char, vp, vp]),
    ("LLVMOrcCreateNewThreadSafeContext", vp, []),
    ("LLVMOrcThreadSafeContextGetContext", vp, [vp]),
    ("LLVMCreateMemoryBufferWithMemoryRangeCopy", vp, [ctypes.c_char_p, ctypes.c_size_t, ctypes.c_char_p]),
    ("LLVMParseIRInContext", ctypes.c_int, [vp, vp, ctypes.POINTER(vp), ctypes.POINTER(ctypes.c_char_p)]),
    ("LLVMParseBitcodeInContext2", ctypes.c_int, [vp, vp, ctypes.POINTER(vp)]),
    ("LLVMOrcCreateNewThreadSafeModule", vp, [vp, vp]),
    ("LLVMOrcLLJITAddLLVMIRModule", vp, [vp, vp, vp]),
    ("LLVMOrcLLJITAddObjectFile", vp, [vp, vp, vp]),
    ("LLVMOrcLLJITLookup", vp, [vp, ctypes.POINTER(ctypes.c_uint64), ctypes.c_char_p]),
    ("LLVMCreatePassBuilderOptions", vp, []),
    ("LLVMRunPasses", vp, [vp, ctypes.c_char_p, vp, vp]),
]:
    fn = getattr(L, name)
    fn.restype = res
    fn.argtypes = args
mark("target init + prototypes")

# the runtime needs libgcc_s's unwinder (_Unwind_ForcedUnwind), which python3.13 does not link
pass  # no libgcc_s
if rt.endswith(".so"):
    # runtime as a shared object: its symbols join the process's global scope (RTLD_GLOBAL), where
    # the process-symbols generator below finds them; its own references to the program's
    # pys_obj_eq/cmp/repr stay unbound (RTLD_LAZY), since ld.so cannot see JIT'd definitions
    ctypes.CDLL(os.path.abspath(rt), mode=os.RTLD_GLOBAL | os.RTLD_LAZY)
    mark("dlopen runtime.so")

jit = vp()
check(L.LLVMOrcCreateLLJIT(ctypes.byref(jit), None), "LLJIT")
jd = L.LLVMOrcLLJITGetMainJITDylib(jit)
gen = vp()
check(L.LLVMOrcCreateDynamicLibrarySearchGeneratorForProcess(ctypes.byref(gen), L.LLVMOrcLLJITGetGlobalPrefix(jit), None, None), "generator")
L.LLVMOrcJITDylibAddGenerator(jd, gen)
gen2 = vp()
check(L.LLVMOrcCreateDynamicLibrarySearchGeneratorForPath(ctypes.byref(gen2), b"libgcc_s.so.1", L.LLVMOrcLLJITGetGlobalPrefix(jit), None, None), "generator for libgcc_s")
L.LLVMOrcJITDylibAddGenerator(jd, gen2)
print("libgcc_s via ForPath generator (no RTLD_GLOBAL preload)")
mark("LLJIT created (+process symbols)")

tsc = L.LLVMOrcCreateNewThreadSafeContext()
ctx = L.LLVMOrcThreadSafeContextGetContext(tsc)


def add_ir(path: str, passes: str) -> None:
    data = open(path, "rb").read()
    buf = L.LLVMCreateMemoryBufferWithMemoryRangeCopy(data, len(data), path.encode())
    mod = vp()
    if path.endswith(".bc"):
        if L.LLVMParseBitcodeInContext2(ctx, buf, ctypes.byref(mod)):
            sys.exit("bad bitcode")
    else:
        msg = ctypes.c_char_p()
        if L.LLVMParseIRInContext(ctx, buf, ctypes.byref(mod), ctypes.byref(msg)):  # (takes buf)
            sys.exit(f"parse: {msg.value.decode()}")
    if passes:
        opts = L.LLVMCreatePassBuilderOptions()
        check(L.LLVMRunPasses(mod, passes.encode(), None, opts), "passes")
    check(L.LLVMOrcLLJITAddLLVMIRModule(jit, jd, L.LLVMOrcCreateNewThreadSafeModule(mod, tsc)), "add module")


if rt.endswith(".o"):
    data = open(rt, "rb").read()
    buf = L.LLVMCreateMemoryBufferWithMemoryRangeCopy(data, len(data), rt.encode())
    check(L.LLVMOrcLLJITAddObjectFile(jit, jd, buf), "add runtime object")
    mark("runtime.o added")
elif rt.endswith(".bc"):
    add_ir(rt, "")
    mark("runtime.bc parsed + added")
# the driver's JIT pipeline: opt -passes='mem2reg,instcombine<no-verify-fixpoint>,simplifycfg'
add_ir(prog, "mem2reg,instcombine<no-verify-fixpoint>,simplifycfg")
mark("program parsed + cleanup passes + added")


def lookup(name: str) -> int:
    a = ctypes.c_uint64()
    check(L.LLVMOrcLLJITLookup(jit, ctypes.byref(a), name.encode()), f"lookup {name}")
    return a.value


fib = ctypes.CFUNCTYPE(ctypes.c_int64, ctypes.c_int64)(lookup("f.fib"))
mark("lookup f.fib (materializes: codegen)")


class Str(ctypes.Structure):
    _fields_ = [("len", ctypes.c_int64)]


def pystr(p: int) -> bytes:
    n = Str.from_address(p).len
    return ctypes.string_at(p + 8, n)


def stack_top() -> int:
    # the main thread's stack end: a stack bottom for the conservative scan that covers every
    # frame below it, CPython's included (no single @main frame exists in this process)
    for line in open("/proc/self/maps"):
        if line.rstrip().endswith("[stack]"):
            return int(line.split()[0].split("-")[1], 16)
    raise RuntimeError("no [stack]")


def flush_both(rtf) -> None:
    sys.stdout.flush()
    rtf()


rtflush = None
for s in steps:
    if s == "fib":
        print("fib(50) via ctypes =", fib(50))
        t = time.perf_counter()
        for i in range(100000):
            fib(20)
        print(f"100k ctypes calls of fib(20): {(time.perf_counter() - t) * 1000:.1f} ms")
    elif s == "init":
        init = ctypes.CFUNCTYPE(None, ctypes.c_int, vp, vp, vp, ctypes.c_int64)(lookup("pys_init"))
        rtflush = ctypes.CFUNCTYPE(None)(lookup("pys_flush"))
        eh_on = ctypes.CFUNCTYPE(None)(lookup("pys_eh_on"))
        init(0, None, stack_top() - 64, None, 0)  # (gc_init adds 16 bytes for a frame record); no argv; roots: none (the program has no pointer globals)
        eh_on()  # what @main does for a program with a try
        print("pys_init(stack bottom = [stack] end) + pys_eh_on done")
    elif s == "greet":
        greet = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_int64)(lookup("f.greet"))
        r = pystr(greet(1000))
        print("greet(1000) via ctypes: len", len(r), r[:20])
    elif s == "gcstress":
        # many collections while Python holds only the returned addresses (the conservative scan
        # sees Python's C stack, not its heap): earlier results die
        greet = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_int64)(lookup("f.greet"))
        keep = greet(50)
        before = pystr(keep)
        for i in range(400):
            greet(2000)
        after = pystr(keep)
        print("a Str held only by Python, after GCs:", "intact" if before == after else f"CLOBBERED {after[:30]!r}")
    elif s == "checked":
        checked = ctypes.CFUNCTYPE(ctypes.c_int64, ctypes.c_int64)(lookup("f.checked"))
        print("checked(100) (OverflowError caught inside JIT'd code) =", checked(100))
    elif s == "boom":
        boom = ctypes.CFUNCTYPE(ctypes.c_int64, ctypes.c_int64)(lookup("f.boom"))
        sys.stdout.flush()
        print("boom(1) =", boom(1))
        print("python continues")
    elif s == "main":
        main = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.c_char_p))(lookup("main"))
        argv = (ctypes.c_char_p * 2)(b"jitme.py", None)
        sys.stdout.flush()
        rc = main(1, argv)
        print("main() returned", rc)
    mark(s)

sys.stdout.flush()
prev = T0
out = []
for what, t in marks:
    out.append(f"{what}: {(t - prev) * 1000:.1f} ms")
    prev = t
print("TIMINGS | " + " | ".join(out) + f" | total {(marks[-1][1] - T0) * 1000:.1f} ms", file=sys.stderr)
