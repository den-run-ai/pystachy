"""In-process ORC LLJIT from CPython (LLVM 18 C API via ctypes): JIT the program's boundary IR,
resolve pys_* against the AOT-compiled runtime shared library. No headers needed."""
import ctypes as C
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
t_load = time.perf_counter()
L = C.CDLL("/usr/lib/llvm-18/lib/libLLVM.so.1")
t_load = time.perf_counter() - t_load
vp, cp = C.c_void_p, C.c_char_p


def fn(name, res, *args):
    f = getattr(L, name)
    f.restype = res
    f.argtypes = list(args)
    return f


def check(err):
    if err:
        msg = fn("LLVMGetErrorMessage", vp, vp)(err)
        raise RuntimeError(C.string_at(msg).decode())


for n in ["LLVMInitializeX86TargetInfo", "LLVMInitializeX86Target", "LLVMInitializeX86TargetMC", "LLVMInitializeX86AsmPrinter"]:
    fn(n, None)()

t0 = time.perf_counter()
jit = vp()
check(fn("LLVMOrcCreateLLJIT", vp, C.POINTER(vp), vp)(C.byref(jit), None))
jd = fn("LLVMOrcLLJITGetMainJITDylib", vp, vp)(jit)
prefix = fn("LLVMOrcLLJITGetGlobalPrefix", C.c_char, vp)(jit)
gen = vp()
check(fn("LLVMOrcCreateDynamicLibrarySearchGeneratorForPath", vp, C.POINTER(vp), cp, C.c_char, vp, vp)(
    C.byref(gen), os.path.join(HERE, "libpysrt.so").encode(), prefix, None, None))
fn("LLVMOrcJITDylibAddGenerator", None, vp, vp)(jd, gen)
gen2 = vp()
check(fn("LLVMOrcCreateDynamicLibrarySearchGeneratorForProcess", vp, C.POINTER(vp), C.c_char, vp, vp)(C.byref(gen2), prefix, None, None))
fn("LLVMOrcJITDylibAddGenerator", None, vp, vp)(jd, gen2)
tsc = fn("LLVMOrcCreateNewThreadSafeContext", vp)()
ctx = fn("LLVMOrcThreadSafeContextGetContext", vp, vp)(tsc)
buf, msg, mod = vp(), C.c_char_p(), vp()
assert not fn("LLVMCreateMemoryBufferWithContentsOfFile", C.c_int, cp, C.POINTER(vp), C.POINTER(C.c_char_p))(
    os.path.join(HERE, "prog_eh_fast.bc").encode(), C.byref(buf), C.byref(msg))
assert not fn("LLVMParseBitcodeInContext2", C.c_int, vp, vp, C.POINTER(vp))(ctx, buf, C.byref(mod))
tsm = fn("LLVMOrcCreateNewThreadSafeModule", vp, vp, vp)(mod, tsc)
check(fn("LLVMOrcLLJITAddLLVMIRModule", vp, vp, vp, vp)(jit, jd, tsm))
look = fn("LLVMOrcLLJITLookup", vp, vp, C.POINTER(C.c_uint64), cp)


def sym(name, cty):
    a = C.c_uint64()
    check(look(jit, C.byref(a), name.encode()))
    return cty(a.value)


I = C.c_int64
init = sym("pyx_init", C.CFUNCTYPE(None))
fib = sym("pyx_fib", C.CFUNCTYPE(I, I, C.POINTER(vp)))
chk = sym("pyx_check", C.CFUNCTYPE(I, I, C.POINTER(vp)))
t1 = time.perf_counter()
print(f"libLLVM dlopen {t_load * 1e3:.1f} ms; LLJIT create+add+materialize {(t1 - t0) * 1e3:.1f} ms")
init()
err = vp()
print("jit fib(25) =", fib(25, C.byref(err)), "err", err.value)
t0 = time.perf_counter()
fib(25, C.byref(err))
print(f"jit fib(25): {(time.perf_counter() - t0) * 1e3:.3f} ms")
rt = C.CDLL(os.path.join(HERE, "libpysrt.so"))
rt.pys_exc_str.restype = vp
rt.pys_exc_str.argtypes = [vp]
r = chk(-7, C.byref(err))
s = rt.pys_exc_str(err)
print("jit check(-7) ->", r, "caught Exc:", C.string_at(s + 8, I.from_address(s).value).decode())
print("jit check(4) ->", chk(4, C.byref(vp())))
import resource
print(f"max RSS {resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024:.0f} MiB")
