# Spike: a Pystachy program that calls CPython through C shims (pyshim.c).
# Each `def py_*(...) -> T: ...` stub is replaced, after `pystachy ir`, by a call to the C
# function of the same name (postprocess.py), since the extern mechanism is runtime-mode only.
import sys


def py_init() -> int: ...
def py_finalize() -> int: ...
def py_import(name: str) -> int: ...
def py_getattr(o: int, name: str) -> int: ...
def py_call0(f: int) -> int: ...
def py_call1(f: int, a: int) -> int: ...
def py_call2(f: int, a: int, b: int) -> int: ...
def py_from_float(x: float) -> int: ...
def py_as_float(o: int) -> float: ...
def py_from_int(x: int) -> int: ...
def py_as_int(o: int) -> int: ...
def py_from_str(s: str) -> int: ...
def py_as_str(o: int) -> str: ...
def py_repr(o: int) -> str: ...
def py_list_new() -> int: ...
def py_list_append(lst: int, x: int) -> None: ...
def py_decref(o: int) -> None: ...
def py_incref(o: int) -> None: ...
def py_refcnt(o: int) -> int: ...
def py_run(code: str) -> int: ...
def py_blocks() -> int: ...
def py_make_cb(fnaddr: int) -> int: ...
def py_set_error(kind: str, msg: str) -> None: ...
def py_capsule(p: int) -> int: ...
def py_capsule_ptr(c: int) -> int: ...
def addr_cb_square() -> int: ...
def addr_of_list(xs: list[int]) -> int: ...
def list_at_addr(p: int) -> list[int]: ...


class PyObj:
    # a Pystachy object owning a CPython reference; no __del__ ever runs, so it leaks
    def __init__(self, h: int) -> None:
        self.h = h


def square(x: int) -> int:
    if x == 3:
        raise ValueError("pystachy refuses 3")
    return x * x


def cb_square(x: int) -> int:
    # the trampoline's body: no Pystachy exception may unwind into CPython's frames
    try:
        return square(x)
    except ValueError as e:
        py_set_error("ValueError", str(e))
        return 0


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    print("py_init:", py_init())
    math = py_import("math")
    sqrt = py_getattr(math, "sqrt")
    two = py_from_float(2.0)
    r = py_call1(sqrt, two)
    print("math.sqrt(2.0) =", py_as_float(r))
    py_decref(r)
    py_decref(two)

    json = py_import("json")
    dumps = py_getattr(json, "dumps")
    lst = py_list_new()
    py_list_append(lst, py_from_int(1))
    py_list_append(lst, py_from_str("héllo"))
    py_list_append(lst, py_from_float(2.5))
    s = py_call1(dumps, lst)
    print("json.dumps =", py_as_str(s))
    py_decref(s)

    # a Python exception surfaces as a Pystachy exception
    try:
        py_call1(sqrt, py_from_float(-1.0))
    except ValueError as e:
        print("caught ValueError:", e)

    # Python calls back into Pystachy (map over a compiled function)
    builtins = py_import("builtins")
    cb = py_make_cb(addr_cb_square())
    rng = py_call1(py_getattr(builtins, "range"), py_from_int(3))
    m = py_call2(py_getattr(builtins, "map"), cb, rng)
    out = py_call1(py_getattr(builtins, "list"), m)
    print("list(map(square, range(3))) =", py_repr(out))
    rng4 = py_call1(py_getattr(builtins, "range"), py_from_int(4))
    m4 = py_call2(py_getattr(builtins, "map"), cb, rng4)
    try:
        py_call1(py_getattr(builtins, "list"), m4)
    except ValueError as e:
        print("round trip ValueError:", e)

    # handles held in Pystachy objects, many collections later (PYSTACHY_GC_STRESS)
    objs: list[PyObj] = []
    for i in range(2000):
        objs.append(PyObj(py_from_str("item" + str(i))))
    junk: list[str] = []
    for i in range(20000):
        junk.append(str(i) * 3)
    total = 0
    for o in objs:
        total += len(py_as_str(o.h))
    print("handles still valid after GC churn: total len", total, "refcnt[0]", py_refcnt(objs[0].h))

    # leak: wrappers that die without Py_DecRef
    b0 = py_blocks()
    for i in range(50000):
        w = PyObj(py_from_str("leak" + str(i)))
    b1 = py_blocks()
    for i in range(50000):
        w = PyObj(py_from_str("leak" + str(i)))
        py_decref(w.h)
    b2 = py_blocks()
    print("CPython blocks: +", b1 - b0, "without decref, +", b2 - b1, "with explicit decref")

    # reverse: a Pystachy list held only by CPython (a capsule)
    if mode == "capsule":
        keep = py_list_new()
        xs: list[int] = [11, 22, 33]
        cap = py_capsule(addr_of_list(xs))
        py_list_append(keep, cap)
        xs = [0]
        for i in range(200000):
            junk.append(str(i))
        back = list_at_addr(py_capsule_ptr(cap))
        print("list via capsule after collections:", back)

    # Python and Pystachy writing to the same stdout
    print("pystachy line 1")
    py_run("print('python line')")
    print("pystachy line 2")
    print("Py_FinalizeEx:", py_finalize())


main()
