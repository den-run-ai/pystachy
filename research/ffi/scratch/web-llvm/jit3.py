import ctypes as C, sys, resource
C.CDLL("libstdc++.so.6", mode=C.RTLD_GLOBAL)
exec(open(sys.argv[1]).read().split("add(\"m.ll\")")[0].split("\n",2)[2])
add("eh2.ll")
inner = C.CFUNCTYPE(None)(look(b"inner"))
outer = C.CFUNCTYPE(C.c_int, C.CFUNCTYPE(None))(look(b"outer"))
S = object()
def py_cb():
    y = S
    inner()
cbo = C.CFUNCTYPE(None)(py_cb)
r0 = sys.getrefcount(S); m0 = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
for i in range(int(sys.argv[2])): outer(cbo)
print("refcount(S) before", r0, "after", sys.getrefcount(S), "maxrss KiB", m0, "->", resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
