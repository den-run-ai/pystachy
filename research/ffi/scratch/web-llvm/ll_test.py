import sys, ctypes as C
import llvmlite.binding as llvm
use_jl = "--jitlink" in sys.argv
if "--gcc" in sys.argv: C.CDLL("libgcc_s.so.1", mode=C.RTLD_GLOBAL)
llvm.initialize_native_target(); llvm.initialize_native_asmprinter()
tm = llvm.Target.from_default_triple().create_target_machine(reloc="pic", codemodel="small")
jit = llvm.create_lljit_compiler(tm, use_jit_link=use_jl)
ir = open(sys.argv[1]).read()
b = llvm.JITLibraryBuilder().add_ir(ir).add_object_file(sys.argv[2]).add_current_process()
b.export_symbol("pyx_init").export_symbol("pyx_f")
rt = b.link(jit, "pys")
init = C.CFUNCTYPE(C.c_int)(rt["pyx_init"]); f = C.CFUNCTYPE(C.c_int, C.c_int64, C.POINTER(C.c_int64))(rt["pyx_f"])
init(); out = C.c_int64()
for x in (21, 1 << 62, 5):
    st = f(x, C.byref(out)); print("llvmlite", "jitlink" if use_jl else "rtdyld", x, "status", st, "value", out.value if st == 0 else None)
