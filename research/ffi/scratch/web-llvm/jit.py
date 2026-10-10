import ctypes as C, sys
if "--std" in sys.argv: C.CDLL("libstdc++.so.6", mode=C.RTLD_GLOBAL)
L = C.CDLL("/usr/lib/llvm-18/lib/libLLVM.so.18.1")
for n in ["X86TargetInfo","X86Target","X86TargetMC","X86AsmPrinter"]:
    getattr(L, "LLVMInitialize"+n)()
P = C.c_void_p
def chk(err):
    if err:
        L.LLVMGetErrorMessage.restype = C.c_char_p
        raise RuntimeError(L.LLVMGetErrorMessage(P(err)))
L.LLVMOrcCreateLLJIT.argtypes=[C.POINTER(P), P]; L.LLVMOrcCreateLLJIT.restype=P
L.LLVMOrcCreateNewThreadSafeContext.restype=P
L.LLVMOrcThreadSafeContextGetContext.argtypes=[P]; L.LLVMOrcThreadSafeContextGetContext.restype=P
L.LLVMCreateMemoryBufferWithMemoryRangeCopy.argtypes=[C.c_char_p, C.c_size_t, C.c_char_p]; L.LLVMCreateMemoryBufferWithMemoryRangeCopy.restype=P
L.LLVMParseIRInContext.argtypes=[P,P,C.POINTER(P),C.POINTER(C.c_char_p)]
L.LLVMOrcCreateNewThreadSafeModule.argtypes=[P,P]; L.LLVMOrcCreateNewThreadSafeModule.restype=P
L.LLVMOrcLLJITGetMainJITDylib.argtypes=[P]; L.LLVMOrcLLJITGetMainJITDylib.restype=P
L.LLVMOrcLLJITAddLLVMIRModule.argtypes=[P,P,P]; L.LLVMOrcLLJITAddLLVMIRModule.restype=P
L.LLVMOrcLLJITLookup.argtypes=[P,C.POINTER(C.c_uint64),C.c_char_p]; L.LLVMOrcLLJITLookup.restype=P
L.LLVMOrcLLJITGetGlobalPrefix.argtypes=[P]; L.LLVMOrcLLJITGetGlobalPrefix.restype=C.c_char
L.LLVMOrcCreateDynamicLibrarySearchGeneratorForProcess.argtypes=[C.POINTER(P), C.c_char, P, P]; L.LLVMOrcCreateDynamicLibrarySearchGeneratorForProcess.restype=P
L.LLVMOrcJITDylibAddGenerator.argtypes=[P,P]
J = P(); chk(L.LLVMOrcCreateLLJIT(C.byref(J), None))
tsc = L.LLVMOrcCreateNewThreadSafeContext(); ctx = L.LLVMOrcThreadSafeContextGetContext(tsc)
jd = L.LLVMOrcLLJITGetMainJITDylib(J)
if "--gen" in sys.argv:
    g = P(); chk(L.LLVMOrcCreateDynamicLibrarySearchGeneratorForProcess(C.byref(g), L.LLVMOrcLLJITGetGlobalPrefix(J), None, None)); L.LLVMOrcJITDylibAddGenerator(jd, g)
def add(path):
    src = open(path,"rb").read()
    buf = L.LLVMCreateMemoryBufferWithMemoryRangeCopy(src, len(src), b"m")
    mod = P(); msg = C.c_char_p()
    if L.LLVMParseIRInContext(ctx, buf, C.byref(mod), C.byref(msg)): raise RuntimeError(msg.value)
    chk(L.LLVMOrcLLJITAddLLVMIRModule(J, jd, L.LLVMOrcCreateNewThreadSafeModule(mod, tsc)))
def look(name):
    a = C.c_uint64(); chk(L.LLVMOrcLLJITLookup(J, C.byref(a), name)); return a.value
add("m.ll"); add("eh.ll")
addf = C.CFUNCTYPE(C.c_int64, C.c_int64, C.c_int64)(look(b"add"))
print("add:", addf(40, 2))
CB = C.CFUNCTYPE(C.c_int64, C.c_int64)
cb = CB(lambda x: x * 3)
tw = C.CFUNCTYPE(C.c_int64, CB, C.c_int64)(look(b"twice_via_py"))
print("python->jit->python callback:", tw(cb, 5))
try:
    mk = C.PYFUNCTYPE(C.py_object, C.c_int64)(look(b"mk"))
    print("jit calls C API PyLong_FromLongLong:", mk(1 << 40))
except Exception as e:
    print("mk lookup failed:", e)
cat = C.CFUNCTYPE(C.c_int, C.c_int)(look(b"catcher"))
print("C++ throw/catch inside in-process JIT:", cat(7), cat(0))
