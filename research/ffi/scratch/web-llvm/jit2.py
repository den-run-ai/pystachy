import ctypes as C, sys
C.CDLL("libstdc++.so.6", mode=C.RTLD_GLOBAL)
exec(open(sys.argv[1]).read().split("add(\"m.ll\")")[0].split("\n",2)[2])
add("eh2.ll")
inner = C.CFUNCTYPE(None)(look(b"inner"))
outer = C.CFUNCTYPE(C.c_int, C.CFUNCTYPE(None))(look(b"outer"))
def py_cb():
    x = [1, 2, 3]
    inner()          # C++ exception unwinds through ctypes/libffi + ceval frames
    print("never")
cbo = C.CFUNCTYPE(None)(py_cb)
print("outer returned", outer(cbo))
import gc; gc.collect()
def deep(n): return 0 if n == 0 else 1 + deep(n - 1)
print("after: deep", deep(500))
import traceback; traceback.print_stack(limit=3)
def show():
    f = sys._getframe(); names = []
    while f: names.append(f.f_code.co_name); f = f.f_back
    print("frames seen from a new call:", names)
show()
import threading
t = threading.Thread(target=lambda: print("thread ran")); t.start(); t.join()
print("refcount-ish: sys.getrefcount(None)", sys.getrefcount(None) > 0)
