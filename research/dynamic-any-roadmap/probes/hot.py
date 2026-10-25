# pystachy: dynamic-any
"""Hot paths through Any, each next to the same loop on typed values, for CPython and Pystachy.

Inputs are built before timing; each kernel's loop is timed with perf_counter_ns, so
start-up and JIT compilation are excluded. Prints: kernel checksum ns-per-operation.
dict_any's stored keys are the literals its lookups use; dict_any_rt's are built at run
time, as keys parsed from JSON are, so each hit compares two different strs.
usage: hot.py SCALE (runhot.py runs it interleaved; the README uses SCALE 4)
"""
import sys
import time
from typing import Any


class Base:
    def __init__(self, v: int) -> None:
        self.v = v

    def m(self, i: int) -> int:
        return self.v + i


class A(Base):
    def m(self, i: int) -> int:
        return self.v + i + 1


class B(Base):
    def m(self, i: int) -> int:
        return self.v + i + 2


class C(Base):
    def m(self, i: int) -> int:
        return self.v + i + 3


def attr_any(objs: list[Any], n: int) -> int:
    total = 0
    for _ in range(n):
        for o in objs:
            x = o.v
            if isinstance(x, int):
                total += x
    return total


def attr_typed(objs: list[Base], n: int) -> int:
    total = 0
    for _ in range(n):
        for o in objs:
            total += o.v
    return total


def call_any(objs: list[Any], n: int) -> int:
    total = 0
    for i in range(n):
        for o in objs:
            r = o.m(i)
            if isinstance(r, int):
                total += r
    return total


def call_typed(objs: list[Base], n: int) -> int:
    total = 0
    for i in range(n):
        for o in objs:
            total += o.m(i)
    return total


def dict_any(recs: list[Any], n: int) -> int:
    total = 0
    for _ in range(n):
        for r in recs:
            v = r["value"]
            if isinstance(v, int):
                total += v
            if r["type"] == "a":
                total += 1
    return total


def dict_any_rt(recs: list[Any], n: int) -> int:
    total = 0
    for _ in range(n):
        for r in recs:
            v = r["value"]
            if isinstance(v, int):
                total += v
            if r["type"] == "a":
                total += 1
    return total


def dict_typed(recs: list[dict[str, int]], n: int) -> int:
    total = 0
    for _ in range(n):
        for r in recs:
            total += r["value"]
            if r["type"] == 0:
                total += 1
    return total


def counter_any(words: list[Any], n: int) -> int:
    counts: dict[Any, Any] = {}
    for _ in range(n):
        for w in words:
            counts[w] = counts.get(w, 0) + 1
    total = 0
    for k in counts:
        v = counts[k]
        if isinstance(v, int):
            total += v * len(k)
    return total


def counter_typed(words: list[str], n: int) -> int:
    counts: dict[str, int] = {}
    for _ in range(n):
        for w in words:
            counts[w] = counts.get(w, 0) + 1
    total = 0
    for k in counts:
        total += counts[k] * len(k)
    return total


def float_any(xs: list[Any], n: int) -> int:
    acc: Any = 0.0
    for _ in range(n):
        for x in xs:
            acc = acc * 0.5 + x
    if isinstance(acc, float):
        return int(acc * 1000)
    return -1


def float_typed(xs: list[float], n: int) -> int:
    acc = 0.0
    for _ in range(n):
        for x in xs:
            acc = acc * 0.5 + x
    return int(acc * 1000)


def int_any(xs: list[Any], n: int) -> int:
    acc: Any = 0
    for _ in range(n):
        for x in xs:
            acc = acc + x
    if isinstance(acc, int):
        return acc
    return -1


def int_typed(xs: list[int], n: int) -> int:
    acc = 0
    for _ in range(n):
        for x in xs:
            acc = acc + x
    return acc


def split_any(texts: list[Any], n: int) -> int:
    total = 0
    for _ in range(n):
        for s in texts:
            total += len(s.split())
    return total


def split_typed(texts: list[str], n: int) -> int:
    total = 0
    for _ in range(n):
        for s in texts:
            total += len(s.split())
    return total


def report(name: str, checksum: int, ns: int, ops: int) -> None:
    print(f"{name} {checksum} {ns / ops:.2f}")


def main() -> None:
    scale = int(sys.argv[1])
    objs_t: list[Base] = [A(1), B(2), C(3), Base(4)]
    objs_a: list[Any] = [A(1), B(2), C(3), Base(4)]
    recs_a: list[Any] = []
    recs_t: list[dict[str, int]] = []
    for i in range(16):
        d: dict[Any, Any] = {"type": "a" if i % 3 == 0 else "b", "value": i * 1000, "name": "r" + str(i)}
        recs_a.append(d)
        recs_t.append({"type": 0 if i % 3 == 0 else 1, "value": i * 1000, "name": i})
    recs_rt: list[Any] = []
    for i in range(16):
        kt = "".join(["ty", "pe"])
        kv = "".join(["val", "ue"])
        kn = "".join(["na", "me"])
        e: dict[Any, Any] = {}
        e[kt] = "".join(["a" if i % 3 == 0 else "b"])
        e[kv] = i * 1000
        e[kn] = "r" + str(i)
        recs_rt.append(e)
    words_t: list[str] = []
    words_a: list[Any] = []
    for i in range(64):
        w = "word" + str(i % 40)
        words_t.append(w)
        words_a.append(w)
    xs_ft: list[float] = []
    xs_fa: list[Any] = []
    xs_it: list[int] = []
    xs_ia: list[Any] = []
    for i in range(64):
        xs_ft.append(i * 0.25)
        xs_fa.append(i * 0.25)
        xs_it.append(i * 1001)
        xs_ia.append(i * 1001)
    texts_t: list[str] = []
    texts_a: list[Any] = []
    for i in range(16):
        s = "alpha beta " * (i % 5 + 1) + "end"
        texts_t.append(s)
        texts_a.append(s)

    n = 50000 * scale
    t0 = time.perf_counter_ns()
    c = attr_any(objs_a, n)
    report("attr_any", c, time.perf_counter_ns() - t0, n * 4)
    t0 = time.perf_counter_ns()
    c = attr_typed(objs_t, n)
    report("attr_typed", c, time.perf_counter_ns() - t0, n * 4)
    t0 = time.perf_counter_ns()
    c = call_any(objs_a, n)
    report("call_any", c, time.perf_counter_ns() - t0, n * 4)
    t0 = time.perf_counter_ns()
    c = call_typed(objs_t, n)
    report("call_typed", c, time.perf_counter_ns() - t0, n * 4)
    n = 10000 * scale
    t0 = time.perf_counter_ns()
    c = dict_any(recs_a, n)
    report("dict_any", c, time.perf_counter_ns() - t0, n * 16)
    t0 = time.perf_counter_ns()
    c = dict_any_rt(recs_rt, n)
    report("dict_any_rt", c, time.perf_counter_ns() - t0, n * 16)
    t0 = time.perf_counter_ns()
    c = dict_typed(recs_t, n)
    report("dict_typed", c, time.perf_counter_ns() - t0, n * 16)
    n = 3000 * scale
    t0 = time.perf_counter_ns()
    c = counter_any(words_a, n)
    report("counter_any", c, time.perf_counter_ns() - t0, n * 64)
    t0 = time.perf_counter_ns()
    c = counter_typed(words_t, n)
    report("counter_typed", c, time.perf_counter_ns() - t0, n * 64)
    t0 = time.perf_counter_ns()
    c = float_any(xs_fa, n)
    report("float_any", c, time.perf_counter_ns() - t0, n * 64)
    t0 = time.perf_counter_ns()
    c = float_typed(xs_ft, n)
    report("float_typed", c, time.perf_counter_ns() - t0, n * 64)
    t0 = time.perf_counter_ns()
    c = int_any(xs_ia, n)
    report("int_any", c, time.perf_counter_ns() - t0, n * 64)
    t0 = time.perf_counter_ns()
    c = int_typed(xs_it, n)
    report("int_typed", c, time.perf_counter_ns() - t0, n * 64)
    n = 10000 * scale
    t0 = time.perf_counter_ns()
    c = split_any(texts_a, n)
    report("split_any", c, time.perf_counter_ns() - t0, n * 16)
    t0 = time.perf_counter_ns()
    c = split_typed(texts_t, n)
    report("split_typed", c, time.perf_counter_ns() - t0, n * 16)


main()
