# An extension module that CPython calls from deeper in its thread's native stack than the import
# was (#1015). A worker thread with a 1 MiB stack imports recdeep near the top of its stack, then
# calls it from a C callback below 4 KiB frames (tests/ffi/ffitest.c's ffi_deep), placed by the
# stack bounds that glibc reports, which runtime.c's floor uses too. Each call from Python computes
# again, from its own frame, the depth that the stack holds (pys_enter), where the import's would
# let about a hundred levels run unchecked: a call made below the floor raises the stack's
# RecursionError at its first counted entry; an unbounded recursion entered just above the floor
# raises it at the floor, before a limit of 2000; a call that recdeep makes back into Python, and
# which calls recdeep again from below the floor, raises alike, and recdeep's own recursion after
# it returns completes. CPython's twin has no native floor, its Python frames being on the heap:
# there the same calls complete or reach the limit (a low one: freeing a long traceback takes C
# stack in CPython 3.13). Each run checks what its own runtime must do; both print the same lines.
import ctypes
import threading

KIB = 1024
lib = ctypes.CDLL("libpystachy-ffitest.so")   # (tests/ffi/run.sh puts it on LD_LIBRARY_PATH)
CALLBACK = ctypes.CFUNCTYPE(ctypes.c_long, ctypes.c_long, ctypes.c_long)
lib.ffi_deep.argtypes = [ctypes.c_long, CALLBACK]
lib.ffi_deep.restype = ctypes.c_long
results: list[str] = []
failures: list[str] = []


def bounds() -> tuple[int, int]:
    # this thread's stack, as glibc's pthread_getattr_np reports it (runtime.c's stack_floor asks too)
    libc = ctypes.CDLL(None)
    libc.pthread_self.restype = ctypes.c_ulong
    libc.pthread_getattr_np.argtypes = [ctypes.c_ulong, ctypes.c_void_p]
    libc.pthread_attr_getstack.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_size_t)]
    libc.pthread_attr_destroy.argtypes = [ctypes.c_void_p]
    attr = ctypes.create_string_buffer(256)
    if libc.pthread_getattr_np(libc.pthread_self(), attr) != 0:
        raise OSError("pthread_getattr_np failed")
    addr, size = ctypes.c_void_p(), ctypes.c_size_t()
    if libc.pthread_attr_getstack(attr, ctypes.byref(addr), ctypes.byref(size)) != 0:
        raise OSError("pthread_attr_getstack failed")
    libc.pthread_attr_destroy(attr)
    return addr.value or 0, size.value


def at(target: int, action) -> str:
    # action() in a C callback whose deepest C frame lies just below target, an address of this
    # thread's stack (one ffi_deep frame is measured first)
    marks: list[int] = []
    probe = CALLBACK(lambda n, here: marks.append(here) or 0)
    lib.ffi_deep(0, probe)
    lib.ffi_deep(1, probe)
    step = marks[0] - marks[1]
    out: list[str] = []
    call = CALLBACK(lambda n, here: out.append(action()) or 0)
    lib.ffi_deep(max(0, (marks[0] - target + step - 1) // step), call)
    return out[0] if out else "no result"


def check(what: str, got: str, native: str, twin: str) -> None:
    expected = native if NATIVE[0] else twin
    if got != expected:
        failures.append(f"{what}: {got}, expected {expected}")
    results.append(f"{what}: {'as its runtime must' if got == expected else got}")


NATIVE = [False]
FLOOR = [0]


def raised(error: RecursionError) -> str:
    return "the stack's" if "native stack" in str(error) else "the limit's"


def first_entry() -> str:
    import recdeep
    try:
        recdeep.depth(1)
    except RecursionError as error:
        return raised(error)
    return "completed"


def unbounded() -> str:
    import recdeep
    original = recdeep.get_limit()
    recdeep.set_limit(2000)
    try:
        recdeep.climb()
    except RecursionError as error:
        return raised(error)
    finally:
        recdeep.set_limit(original)
    return "completed"


def reenter(n: int) -> int:
    # (called back by recdeep.through: recdeep's frames are active above this one)
    check("re-entered below the floor", at(FLOOR[0] - 48 * KIB, first_entry), "the stack's", "completed")
    return n + 1


def run() -> None:
    import recdeep
    NATIVE[0] = recdeep.__file__.endswith(".so")
    lo, size = bounds()
    FLOOR[0] = lo + min(256 * KIB, size // 8)   # (runtime.c's: an eighth of a stack below 2 MiB)
    results.append(f"shallow {recdeep.depth(10)}")
    check("below the floor", at(FLOOR[0] - 48 * KIB, first_entry), "the stack's", "completed")
    check("unbounded, entered above the floor", at(FLOOR[0] + 64 * KIB, unbounded), "the stack's", "the limit's")
    results.append(f"through {recdeep.through('reenter', 0)}")
    results.append(f"recovered {recdeep.depth(400)} {recdeep.get_limit()}")


threading.stack_size(1024 * KIB)
worker = threading.Thread(target=run)
worker.start()
worker.join()
print("\n".join(results))
assert not failures, failures
