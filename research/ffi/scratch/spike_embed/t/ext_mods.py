import time


def py_init() -> int: ...
def py_import(name: str) -> int: ...
def py_getattr(o: int, name: str) -> int: ...
def py_call1(f: int, a: int) -> int: ...
def py_from_str(s: str) -> int: ...
def py_as_str(o: int) -> str: ...
def py_repr(o: int) -> str: ...
def py_finalize() -> int: ...


def main() -> None:
    t0 = time.perf_counter()
    py_init()
    t1 = time.perf_counter()
    j = py_import("_json")
    print(py_repr(j))
    dec = py_import("decimal")
    D = py_getattr(dec, "Decimal")
    x = py_call1(D, py_from_str("1.10"))
    print("Decimal:", py_repr(x), "C impl:", py_repr(py_getattr(dec, "__file__")).endswith("decimal.py'"), py_repr(py_import("_decimal")))
    t2 = time.perf_counter()
    py_finalize()
    t3 = time.perf_counter()
    print("init ms", round((t1 - t0) * 1000, 2), "imports ms", round((t2 - t1) * 1000, 2), "finalize ms", round((t3 - t2) * 1000, 2))


main()
