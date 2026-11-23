"""Differential fuzzing of runtime.py on CPython, against CPython's own str methods and math
(and the dict hash functions against the formulas runtime.c used, on unsigned 64-bit ints).

runtime.py is ordinary Python, so CPython runs it, with tools/rt_cpython/_rt.py standing in for
the compiler's primitives: each pys_* function is called directly and compared with what CPython
computes, on random inputs, with no compilation. Strs are ASCII here (where Pystachy behaves exactly
as CPython) plus UTF-8 text for character classification, case, the width methods and replace("", x); a
Pystachy str is given as its bytes, one character per byte. 64-bit overflow is not tested here
(CPython's ints grow): the differential tests compile the same code and check it.

The format functions get runtime.c's pys_fmt_float (float digits by snprintf, or by Ryu as repr's
without a type or precision) from CPython's own float formatting, which it reproduces.

The memory code (lists, strs, sets and dicts in runtime.c's layouts, and the walks of a value
by its descriptor: repr, == and ordering) runs on a model of the heap that checks each access,
tools/rt_cpython/rt_heap.py, against CPython's own list, str, set, dict, repr and comparisons.

usage: python3 tools/rtcheck.py [N] [SEED] [--runtime FILE] [--only memory|lists|sets|dicts|walks] [--stop]
(N rounds of cases, default 5000; FILE in place of runtime.py; the memory code's checks alone, or
a part of them; --stop: end at the first failure)
"""
import itertools
import math
import os
import posixpath
import random
import re
import struct
import sys
import unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(ROOT, "tools", "rt_cpython"), ROOT]
import _rt  # noqa: E402
import rt_heap  # noqa: E402
from src.pystachy_compiler.specs import RTRECORDS  # noqa: E402

# runtime.py's machine memory runs on a model that checks each access (rt_heap.py), with what
# it calls in runtime.c beside it; its @_rt.unchecked functions check their arithmetic
ARGS = sys.argv[1:]
STOP = "--stop" in ARGS  # end at the first failure: for a run that only asks whether there is one
if STOP:
    ARGS.remove("--stop")
RUNTIME = os.path.join(ROOT, "runtime.py")
ONLY = ""
for flag in ("--runtime", "--only"):
    if flag in ARGS:
        at = ARGS.index(flag)
        if at + 1 == len(ARGS):
            sys.exit(f"rtcheck: {flag} needs a value")
        if flag == "--runtime":
            RUNTIME = ARGS[at + 1]
        else:
            ONLY = ARGS[at + 1]
        del ARGS[at : at + 2]
if ONLY not in ("", "memory", "lists", "sets", "dicts", "walks"):
    sys.exit("rtcheck: --only takes memory, or lists, sets, dicts or walks for a part of it")
HEAP = rt_heap.Heap(RTRECORDS)
_rt.use(rt_heap.primitives(HEAP))
rt = rt_heap.load(RUNTIME)
C = rt_heap.CSide(HEAP)
C.install(rt)
from unicode_classification_tables import case_flags, case_ignorable, case_map, check as check_unicode_table, flags as unicode_flags  # noqa: E402

rt.pys_unicode_flags = unicode_flags
rt.pys_unicode_case_flags = case_flags
rt.pys_unicode_case_map = case_map
rt.pys_unicode_case_ignorable = case_ignorable

N = int(ARGS[0]) if len(ARGS) > 0 else 5000
R = random.Random(int(ARGS[1]) if len(ARGS) > 1 else 1)
ASCII = "ab AB-+0\t\n\r\x0b\x0c\x1c\x1f_.,lL"
WIDE = "aé€𝄞 "
MAXI = (1 << 63) - 1
fails = 0
cases = 0


def b(s):
    # the Pystachy str of a CPython str: its UTF-8 bytes, one character per byte
    return s.encode("utf-8").decode("latin-1")


def u(s):
    return s.encode("latin-1").decode("utf-8")


def text(alpha=ASCII, n=12):
    if alpha is ASCII and R.randrange(3) == 0:
        alpha = "ab"  # repetitive text: overlapping matches
    return "".join(R.choice(alpha) for _ in range(R.randrange(n + 1)))


def outcome(f, *a):
    HEAP.steps = 0
    try:
        return ("ok", f(*a))
    except rt_heap.Runaway as e:
        # (nothing after it would end either)
        print(f"FAIL {getattr(f, '__name__', 'an operation')}: {e}")
        sys.exit(1)
    except Exception as e:  # the runtime raises CPython's exception types and messages
        return (type(e).__name__, str(e))


def ref(f):
    # CPython's outcome, with the text of its result or message as a Pystachy str
    r = outcome(f)
    return (r[0], b(r[1]) if isinstance(r[1], str) else r[1])


def stop():
    if STOP:
        print(f"{cases} cases, a failure: stopped at the first")
        sys.exit(1)


def same(name, got, want, args):
    global fails, cases
    cases += 1
    if got != want:
        fails += 1
        if fails <= 20:
            print(f"FAIL {name}{args!r}: runtime.py {got!r}, CPython {want!r}")
        stop()


def idx():
    return R.choice([0, 1, 2, -1, -3, 5, 40, -40, MAXI, -MAXI - 1])


class Item:
    """An item of the CPython list that a heap list is compared with: its word, and its identity
    (the object's own), which a list with a companion must keep as CPython's list keeps it.
    An int has no identity before a list with a companion holds it: what a list without one
    gives to another are other items of the same values (fresh)."""
    def __init__(self, value, big=0):
        self.value = value
        self.big = big  # (the address of its Mpz where the word is -2**63 for an int past 64 bits)


def fresh(items):
    return [Item(x.value, x.big) for x in items]


class HeapList:
    def __init__(self, ptr, ref, atomic):
        self.ptr = ptr
        self.ref = ref
        self.atomic = atomic


def list_fault(l, mode, boxes):
    # "" if heap list l is CPython's l.ref and its storage is what runtime.c's List promises
    a = HEAP.of(l.ptr)
    n, cap, items, ids = C.w(a), C.w(a + 8), C.w(a + 16), C.w(a + 24)
    if n != len(l.ref):
        return f"len {n}, CPython's {len(l.ref)}"
    if not n <= cap:
        return f"len {n} past cap {cap}"
    have = HEAP.words(items, n)
    if have != [x.value for x in l.ref]:
        return f"items {have}, CPython's {[x.value for x in l.ref]}"
    if cap == 0:
        if items not in ((C.empty_atomic,) if l.atomic else (C.empty_list, C.empty_inline)):
            return "an emptied list's sentinel is not one of its kind"
    elif items == a + 32:
        if cap != 4 or l.atomic or HEAP.block_of(a).size != 65:
            return "inline items in a list that has none"
    else:
        b = HEAP.block_of(items)
        if b is None or b.base != items or b.size < cap * 8 + 1 or b.kind != ("atomic" if l.atomic else "scan"):
            return f"the item array is not an array of {cap} {'atomic' if l.atomic else 'scanned'} items"
    if cap and any(HEAP.words(items + 8 * n, cap - n)):
        return "a slot past the length is not zero"  # (the collector scans the whole array)
    if ids == 0:
        return "a big item without a companion" if any(x.big for x in l.ref) else ""
    if mode == "plain":
        return "a companion in a program that does not opt in"
    kind = C.w(ids)
    if ids in C.empty_ids.values():
        return "" if cap == 0 and ids == C.empty_identity(kind) else "a companion's sentinel that is not the list's"
    b = HEAP.block_of(ids)
    if b is None or b.base != ids or b.size < (cap + 1) * 8 + 1:
        return f"the companion is not an array of {cap} + 1 words"
    entries = HEAP.words(ids + 8, cap)
    if any(entries[n:]):
        return "a companion's entry past the length is not zero"
    for i in range(n):
        x = l.ref[i]
        if kind & 3 == 3:
            if entries[i] != x.big:
                return f"item {i}'s Mpz is {entries[i]:#x}, not {x.big:#x}"
        elif entries[i] != 0:
            # an identity that was observed: the box is the item's, as the object is CPython's
            if boxes.setdefault(entries[i], x) is not x:
                return f"item {i} has the box of another item"
            if getattr(x, "box", entries[i]) != entries[i]:
                return f"item {i} lost its box"
            x.box = entries[i]
            want = ("big", x.big) if x.big else x.value
            if C.boxes[entries[i]] != want:
                return f"item {i}'s box holds {C.boxes[entries[i]]}, not {want}"
        elif not kind & 4:
            return f"item {i} has no box in a companion that marks none pending"
    return ""


def fuzz_lists():
    # runtime.py's lists against CPython's, an operation at a time: the result or the error,
    # then the list's storage. With a companion, each item's identity too
    global fails, cases
    none = -(1 << 63)
    for mode, atomic in [("plain", False), ("plain", True), ("identity", True), ("big", True)]:
        for _ in range(max(1, N // 25)):
            HEAP.reset()
            C.setup()
            C.opt = int(mode != "plain")
            boxes = {}
            lists = []

            def item():
                return Item(R.choice([0, 0, 1, 2, 3, 7, -1, none, MAXI, R.randrange(-99, 99)]))

            def new(ref):
                n = R.choice([0, 0, 1, 4, 5, len(ref)])
                l = HeapList(rt.pys_list_new_atomic(n) if atomic else rt.pys_list_new(n), [], atomic)
                for x in ref:
                    rt.pys_list_append(l.ptr, x.value)
                    l.ref.append(x)
                lists.append(l)
                return l

            def bound():
                return R.choice([none, none, 0, 1, 2, 3, -1, -2, 5, 9, -9, MAXI, -MAXI])

            def sl(lo, hi, st=None):
                return slice(None if lo == none else lo, None if hi == none else hi, st)

            for _ in range(3):
                new([item() for _ in range(R.choice([0, 1, 3, 4, 5, 9]))])
            for _ in range(60):
                l = R.choice(lists)
                m = R.choice(lists)
                i = R.choice([0, 1, 2, -1, -2, 4, 5, 9, -9, MAXI, none, R.randrange(len(l.ref) + 1), R.randrange(len(l.ref) + 1)])
                lo, hi = bound(), bound()
                st = R.choice([1, 1, 1, 2, -1, -2, 3, 0, none, MAXI, -MAXI])
                k = R.choice([-1, 0, 1, 2, 3, 5, MAXI])
                x = item()
                made = None
                # do the items that this operation copies keep their identities? (a companion holds them)
                kept = C.w(HEAP.of(l.ptr) + 24) != 0
                both = kept or C.w(HEAP.of(m.ptr) + 24) != 0

                def give(items, keep):
                    return list(items) if keep else fresh(items)
                # (with a companion, more of what makes one and of what leaves an entry pending)
                op = R.choice(("append get set pop del insert extend slice copy clear slice_step set_slice del_slice add imul mul reverse "
                               "reserve from_const" + (" observe observe observe plant plant plant set set forget" if mode != "plain" else "")).split())
                if op == "append":
                    got, want = outcome(rt.pys_list_append, l.ptr, x.value), outcome(l.ref.append, x)
                elif op == "get":
                    got, want = outcome(rt.pys_list_get, l.ptr, i), outcome(lambda: l.ref[i].value)
                elif op == "set":
                    def store():
                        l.ref[i] = x
                    got, want = outcome(rt.pys_list_set, l.ptr, i, x.value), outcome(store)
                elif op == "pop":
                    got, want = outcome(rt.pys_list_pop, l.ptr, i), outcome(lambda: l.ref.pop(i).value)
                elif op == "del":
                    def delete():
                        del l.ref[i]
                    got, want = outcome(rt.pys_list_del, l.ptr, i), outcome(delete)
                elif op == "insert":
                    got, want = outcome(rt.pys_list_insert, l.ptr, i, x.value), outcome(l.ref.insert, i, x)
                elif op == "extend":
                    got, want = outcome(rt.pys_list_extend, l.ptr, m.ptr), outcome(l.ref.extend, give(m.ref, both))
                elif op in ("slice", "copy", "slice_step", "add", "mul"):
                    if op == "slice":
                        got, want = outcome(rt.pys_list_slice, l.ptr, lo, hi), outcome(lambda: give(l.ref[sl(lo, hi)], kept))
                    elif op == "copy":
                        got, want = outcome(rt.pys_list_copy, l.ptr), outcome(lambda: give(l.ref, kept))
                    elif op == "slice_step":
                        got, want = outcome(rt.pys_list_slice_step, l.ptr, lo, hi, st), outcome(lambda: give(l.ref[sl(lo, hi, st)], kept))
                    elif op == "add":
                        got, want = outcome(rt.pys_list_add, l.ptr, m.ptr), outcome(lambda: give(l.ref, both) + give(m.ref, both))
                    else:
                        got, want = outcome(rt.pys_list_mul, l.ptr, k), outcome(lambda: l.ref * k if kept or k > 9 or not l.ref else [y for _ in range(k) for y in fresh(l.ref)])
                    if got[0] == "ok" and want[0] == "ok":
                        made = HeapList(got[1], want[1], atomic)
                        got = want = ("ok", None)
                elif op == "clear":
                    got, want = outcome(rt.pys_list_clear, l.ptr), outcome(l.ref.clear)
                elif op == "set_slice":
                    def assign():
                        l.ref[sl(lo, hi, st)] = give(m.ref, both)
                    got, want = outcome(rt.pys_list_set_slice, l.ptr, lo, hi, st, m.ptr), outcome(assign)
                elif op == "del_slice":
                    def remove():
                        del l.ref[sl(lo, hi, st)]
                    got, want = outcome(rt.pys_list_del_slice, l.ptr, lo, hi, st), outcome(remove)
                elif op == "imul":
                    def repeat():
                        if kept or k <= 1 or k > 9:
                            l.ref *= k
                        else:
                            l.ref.extend([y for _ in range(k - 1) for y in fresh(l.ref)])
                    got, want = outcome(rt.pys_list_imul, l.ptr, k), outcome(repeat)
                elif op == "reverse":
                    got, want = outcome(rt.pys_list_reverse, l.ptr), outcome(l.ref.reverse)
                elif op == "reserve":
                    got, want = outcome(rt.pys_list_reserve, l.ptr, R.choice([0, 1, 4, 5, 9, 40])), ("ok", None)
                elif op == "from_const":
                    if not atomic:
                        continue
                    ref = [item() for _ in range(R.choice([0, 1, 5, 9]))]
                    values = HEAP.static([x.value for x in ref], "const")
                    made = HeapList(rt.pys_list_from_const(HEAP.P(values), len(ref)), ref, True)
                    got = want = ("ok", None)
                elif op == "observe":
                    # compiled code asks for a list's identities before it reads one
                    if mode != "identity":
                        continue
                    got, want = outcome(C.pys_list_identity, l.ptr, 1), ("ok", None)
                elif op == "plant":
                    # an int past 64 bits (its Mpz's address here): stored, appended or inserted
                    if mode != "big":
                        continue
                    x = Item(none, HEAP.new(16, "atomic", "mpz"))
                    how = R.randrange(4)
                    if how == 0:
                        def store_big():
                            l.ref[i] = x
                        got, want = outcome(rt.pys_list_set_big, l.ptr, i, HEAP.P(x.big)), outcome(store_big)
                    elif how == 1:
                        got, want = outcome(rt.pys_list_append_big, l.ptr, HEAP.P(x.big)), outcome(l.ref.append, x)
                    elif how == 2:
                        got, want = outcome(rt.pys_list_insert_big, l.ptr, i, HEAP.P(x.big)), outcome(l.ref.insert, i, x)
                    else:
                        j = R.randrange(-len(l.ref), len(l.ref)) if l.ref else 0
                        if not l.ref:
                            continue
                        got, want = outcome(lambda: rt.pys_list_big_at(l.ptr, j).addr), outcome(lambda: l.ref[j].big)
                else:
                    # the CPython FFI twin's copy back: every item of a list with identities is a new object
                    if mode != "identity":
                        continue
                    got, want = outcome(rt.pys_list_forget_identity, l.ptr), ("ok", None)
                    if C.w(HEAP.of(l.ptr) + 24) != 0:
                        l.ref[:] = fresh(l.ref)
                if made is not None:
                    lists.append(made)
                if got == want:
                    bad = next((f"{w.ref and ''}{e}" for w in lists for e in [list_fault(w, mode, boxes)] if e), "")
                    got = ("ok", None) if not bad else ("storage", bad)
                    want = ("ok", None)
                same(f"list-{mode}-{op}", got, want, (len(l.ref), len(m.ref), i, lo, hi, st, k))
                if got != want:
                    break
                if len(lists) > 6:
                    del lists[R.randrange(len(lists))]


def fuzz_list_search():
    # x in l, l.index, l.count and l.remove against CPython's, and list(range(...)) and list(b):
    # ints and bools by their slots, strs by pys_str_eq, and other items through the comparison
    # that may run an __eq__, which here removes the list's last item at a time of its choosing
    none = -(1 << 63)
    for _ in range(N):
        HEAP.reset()
        C.setup()
        how = R.choice(["i", "b", "s", "x", "companion"])
        C.opt = int(how == "companion")
        d = HEAP.as_str(HEAP.new_str({"companion": b"i", "x": b"O000"}.get(how, how.encode()), 2))
        if how == "s":
            pool = [None, "", "a", "b", "ab", "abc"]
            values = [R.choice(pool) for _ in range(R.randrange(9))]
            x = R.choice(pool)
            words = [0 if v is None else HEAP.new_str(v.encode(), 0) for v in values]
            xw = 0 if x is None else HEAP.new_str(x.encode(), 0)
            l = rt.pys_list_new(len(words))
        else:
            values = [R.randrange(2) if how == "b" else R.choice([0, 1, 2, 3, -1, none, MAXI]) for _ in range(R.randrange(9))]
            x = xw = R.choice([0, 1, 2, 3, -1, none, MAXI, 9])
            words = values
            if how == "x":
                # (objects of a class of the program's, here of these ints, whose __eq__ the heap
                # side runs through runtime.c's pys_obj_eq)
                words = [C.new_obj(v) for v in values]
                xw = C.new_obj(x)
            l = (rt.pys_list_new if how == "x" else rt.pys_list_new_atomic)(len(words))
        for w in words:
            rt.pys_list_append(l, w)
        if how == "companion":
            C.pys_list_identity(l, 1)
        ref = list(values)
        st, en = R.choice([0, 0, 1, -1, -3, 5, -9, MAXI]), R.choice([MAXI, MAXI, 0, 2, -1, -4, 9])
        # the comparison that removes the last item, in both lists: the k-th one made
        # (often the one that finds x: the index it gives is then past the end)
        first = values.index(x) + 1 if x in values else 0
        count = [0, R.choice([0, 0, 1, 2, 3, first, first])]
        heap_count = [0]

        class E:
            def __init__(self, v):
                self.v = v

            def __eq__(self, o):
                count[0] += 1
                if count[0] == count[1] and ref:
                    ref.pop()
                return self.v == o.v

        def on_eq():
            heap_count[0] += 1
            if heap_count[0] == count[1] and C.w(HEAP.of(l)):
                rt.pys_list_pop(l, -1)

        generic = how == "x"
        if generic:
            ref[:] = [E(v) for v in values]
            C.on_eq = on_eq
        q = E(x) if generic else x
        op = R.choice(["find", "index", "count", "remove", "index_as"])
        if op == "find":
            got, want = outcome(rt.pys_list_find, l, xw, d), outcome(lambda: next((i for i in range(len(values)) if i < len(ref) and ref[i] == q), -1))
        elif op == "index":
            got, want = outcome(rt.pys_list_index, l, xw, d, st, en), outcome(ref.index, q, st, en)
        elif op == "index_as":
            ok = R.randrange(2)
            got, want = outcome(rt.pys_list_index_as, l, xw, d, st, en, ok, xw, d), outcome(ref.index, q, st, en) if ok else ("ValueError", "")
        elif op == "count":
            got, want = outcome(rt.pys_list_count, l, xw, d), outcome(ref.count, q)
        else:
            got, want = outcome(rt.pys_list_remove, l, xw, d), outcome(ref.remove, q)
        if got[0] == want[0] == "ValueError" and op != "remove":
            want = got  # (the text of x in the message is repr's, which is runtime.c's still)
        if got == want:
            a = HEAP.of(l)
            have = HEAP.words(C.w(a + 16), C.w(a))
            left = [w.v if generic else w for w in ref]
            if generic:
                have = [C.objs[w] for w in have]
            if how == "s":
                have = [None if w == 0 else C.text(w) for w in have]
            if have != left:
                got = ("storage", f"items {have}, CPython's {left}")
        same(f"list-{op}-{how}", got, want, (values, x, st, en, count[1]))
        # list(range(a, b, s)) and list(b)
        a, b, step = R.choice([0, 1, -3, 7, MAXI - 2, none]), R.choice([0, 5, -9, 12, MAXI, none + 3]), R.choice([1, 1, 2, -1, -3, 0, MAXI, none])
        want = outcome(lambda: list(range(a, b, step)) if len(range(a, b, step)) < 1000 else 1 / 0)
        if want[0] != "ZeroDivisionError":
            got = outcome(rt.pys_range_list, a, b, step)
            if got[0] == "ok":
                p = HEAP.of(got[1])
                block = HEAP.block_of(C.w(p + 16))
                got = ("ok", HEAP.words(C.w(p + 16), C.w(p))) if C.w(p + 8) == 0 or block.kind == "atomic" else ("storage", "a scanned array")
            same("range-list", got, want, (a, b, step))
        data = bytes(R.randrange(256) for _ in range(R.randrange(40)))
        got = outcome(rt.pys_bytes_list, HEAP.as_str(HEAP.new_str(data, 0)))
        if got[0] == "ok":
            p = HEAP.of(got[1])
            got = ("ok", HEAP.words(C.w(p + 16), C.w(p)))
        same("bytes-list", got, ("ok", list(data)), (data,))


class Key:
    """An element whose hash and equality are the program's: hv picks its probes (equal hashes
    collide) and == compares v. hook, where one is set, runs at each comparison: an __eq__
    that changes a set while a lookup of it is under way."""
    hook = None

    def __init__(self, hv, v):
        self.hv, self.v = hv, v

    def __hash__(self):
        return self.hv

    def __eq__(self, other):
        if Key.hook is not None:
            Key.hook()
        return self.v == other.v

    def __repr__(self):
        return f"Key({self.hv}, {self.v})"


class HeapSet:
    def __init__(self, ptr, ref, exact):
        self.ptr = ptr
        self.ref = ref
        self.exact = exact  # its table is CPython's, slot for slot: the elements come in its order


def set_table(s, mode):
    # (heap set s's elements in the order of their slots, as CPython values; what its storage
    # breaks of runtime.c's Set, or "")
    none = -(1 << 63)
    a = HEAP.of(s.ptr)
    n, kind, fill, mask, keys, hs, kb = C.w(a), C.w(a + 8), C.w(a + 16), C.w(a + 24), C.w(a + 40), C.w(a + 48), C.w(a + 56)
    size = mask + 1
    if size < 8 or size & mask:
        return [], f"a table of {size} slots"
    ints = mode in ("int", "big")
    for name, at, want in (("keys", keys, "atomic" if ints and size > 8 else "scan"), ("hs", hs, "atomic"), ("kb", kb, "scan")):
        if name == "kb" and at == 0:
            continue
        b = HEAP.block_of(at)
        if b is None or b.base != at or b.size < size * 8 + 1 or b.kind != want:
            return [], f"{name} is not an array of {size} {want} words"
    if kb and mode != "big":
        return [], "Mpz words in a set that holds no int past 64 bits"
    out = []
    dummies = 0
    for j in range(size):
        h, k = C.w(hs + 8 * j), C.w(keys + 8 * j)
        m = C.w(kb + 8 * j) if kb else 0
        if h == -1:
            if k not in (0, 1) or m:
                return [], f"slot {j} holds no element, and key {k} or an Mpz"
            dummies += k
            continue
        if m:
            v = C.mpz[m]
            if k != (none + 1 if h == -4 else none):
                return [], f"slot {j} has an Mpz and not its sentinel"
        else:
            v = C.element(k, kind)
        want = rt.str_key_hash(k) if mode == "str" else hash(v)
        if h != want:
            return [], f"slot {j} keeps hash {h} of an element whose hash is {want}"
        out.append(v)
    if len(out) != n or fill != n + dummies:
        return out, f"len {n} and fill {fill} of {len(out)} elements and {dummies} dummies"
    if fill * 5 >= mask * 3:
        return out, f"{fill} of {size} slots are used: a table that insertions would have rebuilt"
    return out, ""


def set_dict(mode, keys, ktag):
    # a Dict of runtime.c's with these keys in order (None: a hole), as much of one as the sets
    # read; ktag: its keys are hashed by CPython's hash, which its table keeps
    none = -(1 << 63)
    n = max(len(keys), 1)
    d = HEAP.new(96, "scan", "dict")
    ka = HEAP.new(8 * n, "scan" if mode == "str" else "atomic", "dict keys")
    ha = HEAP.new(8 * n, "atomic", "dict hs")
    kb = 0
    kind = 1 if mode == "str" else 0
    if ktag:
        kind = 3 if mode == "str" else HEAP.new_str(b"!i", 0) | 2
    live = 0
    for e, k in enumerate(keys):
        if k is None:
            C.put(ha + 8 * e, -1 if ktag else 0)
            continue
        live += 1
        if mode == "str":
            w = HEAP.new_str(k.encode(), 0)
            h = rt.str_key_hash(w)
        elif none <= k <= MAXI:
            w = k
            h = hash(k) if ktag else rt.pys_hash_int(k) or 1
        else:
            w = none
            if not kb:
                kb = HEAP.new(8 * n, "scan", "dict kb")
            C.put(kb + 8 * e, C.new_mpz(k))
            h = hash(k) if ktag else rt.pys_hash_int(hash(k)) or 1
        C.put(ka + 8 * e, w)
        C.put(ha + 8 * e, h)
    for at, v in ((0, live), (8, kind), (16, len(keys)), (24, 8), (32, ka), (48, ha), (88, kb)):
        C.put(d + at, v)
    C.dicts[d] = {k for k in keys if k is not None}
    return HEAP.P(d)


def fuzz_sets():
    # runtime.py's sets against CPython's, an operation at a time: the result or the error, then
    # the table. Of ints, of ints past 64 bits and of objects with a __hash__ of their own, the
    # table is CPython's slot for slot, since the hashes are: the elements come in CPython's
    # order. A str's hash is not CPython's, so a set of strs is compared as a set. An __eq__
    # that changes a set during a lookup has no CPython to compare with here (the suite's
    # programs do that): the storage must stay sound
    global fails, cases
    none = -(1 << 63)
    prime = (1 << 61) - 1
    # (each round goes through every mode, so that a fault of any mode shows in the first rounds)
    for round in range(max(1, N // 25)):
        for mode in ("int", "str", "obj", "big"):
            HEAP.reset()
            C.setup()
            C.opt = int(mode == "big")
            Key.hook = None
            kind = {"int": 0, "big": 0, "str": 1}.get(mode) if mode != "obj" else HEAP.new_str(b"P000", 0)
            sets = []
            if mode == "obj":
                pool = [Key(hv, v) for hv in (0, 0, 1, 8, 16, 17, -2, 1 << 40) for v in range(4)]
                for x in pool:
                    x.addr = C.new_obj(x)
            elif mode == "str":
                pool = ["", "a", "b", "ab", "ba", "abc"] + [chr(97 + i % 26) * (1 + i // 26) for i in range(60)]
            else:
                pool = [0, 1, 2, 3, -1, -2, 7, 8, 9, 15, 16, 24, 32, prime - 1, prime, prime + 1, MAXI, none, none + 1, -prime, -prime - 4] + list(range(40, 100))
                if mode == "big":
                    pool += [1 << 63, -(1 << 63) - 1, 1 << 64, (1 << 70) + 3, 4 - (1 << 64), 8 * prime + 12, -(1 << 63) - 4, prime << 3]
            grow = R.randrange(4) == 0  # (some rounds fill their tables past the small ones)

            def elem():
                return R.choice(pool) if grow or mode == "obj" else R.choice(pool[: 12 + R.randrange(12)])

            def word(x):
                # element x as the runtime takes it: its word, and its Mpz where it is past 64 bits
                if mode == "str":
                    return HEAP.new_str(x.encode(), 0), _rt.nil()
                if mode == "obj":
                    return x.addr, _rt.nil()
                if none <= x <= MAXI:
                    return x, _rt.nil()
                return 0, HEAP.P(C.new_mpz(x))

            def call(name, s, x):
                # s.add(x), x in s, s.discard(x), s.remove(x)
                w, m = word(x)
                if mode == "big":
                    return outcome(getattr(rt, "pys_set_big_" + name), s.ptr, w, m)
                return outcome(getattr(rt, "pys_set_" + name), s.ptr, w)

            def new(ref, exact=True):
                s = HeapSet(rt.pys_set_new(kind), set(), exact and mode != "str")
                for x in ref:
                    call("add", s, x)
                    s.ref.add(x)
                sets.append(s)
                return s

            def heap_list(xs):
                l = rt.pys_list_new(len(xs)) if mode in ("str", "obj") else rt.pys_list_new_atomic(len(xs))
                for x in xs:
                    w, m = word(x)
                    if m.addr:
                        rt.pys_list_append_big(l, m)
                    else:
                        rt.pys_list_append(l, w)
                return l

            def values(l):
                # the elements of heap list l, as CPython values
                a = HEAP.of(l)
                out = []
                for i, w in enumerate(HEAP.words(C.w(a + 16), C.w(a))):
                    m = rt.pys_rt_lbig(l, i).addr
                    out.append(C.mpz[m] if m else C.element(w, kind))
                return out

            def sound(s, after):
                # is heap set s CPython's s.ref, in its order where its table is CPython's?
                global fails, cases
                have, fault = set_table(s, mode)
                cases += 1
                if fault == "" and (have != list(s.ref) if s.exact else len(have) != len(s.ref) or set(have) != s.ref):
                    fault = f"elements {have[:12]}, CPython's {list(s.ref)[:12]}"
                if fault != "":
                    fails += 1
                    stop()
                    if fails <= 20:
                        print(f"FAIL set after {after} ({mode}): {fault}")
                return fault == ""

            if mode == "int" and round == 0:
                # a probe's ten adjacent slots: 193 starts at slot 1 of 32, where 1 to 9 are, and
                # takes the tenth, before 11's; one slot less, and its next probe is slot 12
                s = new(list(range(1, 10)) + [11, 193])
                same("set-has-run", call("has", s, 193), ("ok", 1), ())
                if not sound(s, "a run of nine"):
                    return
            if mode == "big" and round == 0:
                # an element past 64 bits whose hash is -2**63's (-4): its slot holds the other
                # sentinel, and a list of the set's elements holds -2**63 for it all the same
                s = new([4 - (1 << 64), 7])
                same("set-list-sentinel", outcome(lambda: values(rt.pys_set_list(s.ptr))), ("ok", set_table(s, mode)[0]), ())
            for _ in range(3):
                new([elem() for _ in range(R.choice([0, 1, 3, 5, 9, 30]))])
            for _ in range(60):
                a = R.choice(sets)
                b = R.choice(sets)
                x = elem()
                xs = [elem() for _ in range(R.choice([0, 1, 2, 5, 12, 40]))]
                made = None
                hooked = False
                if mode == "obj" and R.randrange(3) == 0:
                    # the program's __eq__, at one of the next comparisons: it changes a or b
                    count = [R.randrange(1, 4)]
                    victim = R.choice([a, b])
                    change = R.choice(["add", "discard", "clear", "grow"])
                    extra = [elem() for _ in range(12)]

                    def hook():
                        nonlocal hooked
                        count[0] -= 1
                        if count[0] == 0:
                            Key.hook = None
                            hooked = True
                            if change == "clear":
                                rt.pys_set_clear(victim.ptr)
                            elif change == "grow":
                                for e in extra:
                                    rt.pys_set_add(victim.ptr, e.addr)
                            else:
                                getattr(rt, "pys_set_" + change)(victim.ptr, extra[0].addr)
                    Key.hook = hook
                op = R.choice(("add add add has has discard remove pop clear copy update update_list or and and_list iand isub isub_list sub "
                               "sub_list xor xor_list ixor ixor_list cmp le_list ge_list isdisjoint isdisjoint_list iterate list union "
                               "slot_del" + (" update_dict sub_dict xor_dict ixor_dict" if mode != "obj" else "")).split())
                dkeys = []
                for k in [R.choice([None, elem()]) for _ in range(R.choice([0, 1, 3, 8, 30]))] if op.endswith("_dict") else []:
                    dkeys.append(k if k is None or k not in dkeys else None)  # (a dict has each key once)
                dref = dict.fromkeys(k for k in dkeys if k is not None)
                d = set_dict(mode, dkeys, R.randrange(2) == 1) if op.endswith("_dict") else None
                both = a.exact and b.exact
                if op in ("add", "discard", "remove"):
                    got, want = call(op, a, x), outcome(getattr(a.ref, op), x)
                elif op == "has":
                    got, want = call("has", a, x), ("ok", int(x in a.ref))
                elif op == "pop":
                    def pop():
                        # (a set of ints past 64 bits: pys_set_big_pop, whose result is a promoting int's two words)
                        if mode != "big":
                            return C.element(rt.pys_set_pop(a.ptr), kind)
                        k, m = rt.pys_set_big_pop(a.ptr)
                        return C.mpz[m.addr] if m.addr else k
                    got = outcome(pop)
                    if a.exact or got[0] != "ok":
                        want = outcome(a.ref.pop)
                    else:
                        want = ("ok", got[1]) if got[1] in a.ref else ("missing", None)
                        a.ref.discard(got[1])
                elif op == "clear":
                    got, want = outcome(rt.pys_set_clear, a.ptr), outcome(a.ref.clear)
                elif op == "copy":
                    made = HeapSet(rt.pys_set_copy(a.ptr), a.ref.copy(), a.exact)
                    got = want = ("ok", None)
                elif op == "update":
                    got, want = outcome(rt.pys_set_update, a.ptr, b.ptr), outcome(a.ref.update, b.ref)
                    a.exact = both
                elif op == "update_list":
                    got, want = outcome(rt.pys_set_update_list, a.ptr, heap_list(xs)), outcome(a.ref.update, xs)
                elif op == "update_dict":
                    got, want = outcome(rt.pys_set_update_dict, a.ptr, d), outcome(a.ref.update, dref)
                elif op == "union":
                    r = rt.pys_set_copy(a.ptr)
                    rt.pys_set_union_more(r, a.ptr, b.ptr)
                    made = HeapSet(r, a.ref.union(b.ref), both)
                    got = want = ("ok", None)
                elif op in ("or", "and", "sub", "xor"):
                    f = {"or": set.__or__, "and": set.__and__, "sub": set.__sub__, "xor": set.__xor__}[op]
                    made = HeapSet(getattr(rt, "pys_set_" + op)(a.ptr, b.ptr), f(a.ref, b.ref), both)
                    got = want = ("ok", None)
                elif op in ("and_list", "sub_list", "xor_list"):
                    f = {"and_list": a.ref.intersection, "sub_list": a.ref.difference, "xor_list": a.ref.symmetric_difference}[op]
                    made = HeapSet(getattr(rt, "pys_set_" + op)(a.ptr, heap_list(xs)), f(xs), a.exact)
                    got = want = ("ok", None)
                elif op in ("sub_dict", "xor_dict"):
                    f = a.ref.difference if op == "sub_dict" else a.ref.symmetric_difference
                    made = HeapSet(getattr(rt, "pys_set_" + op)(a.ptr, d), f(dref), a.exact)
                    got = want = ("ok", None)
                elif op == "iand":
                    def iand():
                        a.ref &= b.ref
                    got, want = outcome(lambda: rt.pys_set_assign(a.ptr, rt.pys_set_and(a.ptr, b.ptr))), outcome(iand)
                    a.exact = both
                elif op == "isub":
                    def isub():
                        a.ref -= b.ref
                    got, want = outcome(rt.pys_set_isub, a.ptr, b.ptr), outcome(isub)
                    a.exact = both
                elif op == "ixor":
                    def ixor():
                        a.ref ^= b.ref
                    got, want = outcome(rt.pys_set_ixor, a.ptr, b.ptr), outcome(ixor)
                    a.exact = both
                elif op in ("isub_list", "ixor_list"):
                    f = a.ref.difference_update if op == "isub_list" else a.ref.symmetric_difference_update
                    got, want = outcome(getattr(rt, "pys_set_" + op), a.ptr, heap_list(xs)), outcome(f, xs)
                elif op == "ixor_dict":
                    got, want = outcome(rt.pys_set_ixor_dict, a.ptr, d), outcome(a.ref.symmetric_difference_update, dref)
                elif op == "cmp":
                    k = R.randrange(6)
                    f = [set.__lt__, set.__le__, set.__gt__, set.__ge__, set.__eq__, set.__ne__][k]
                    got, want = outcome(rt.pys_set_cmp, a.ptr, b.ptr, k), ("ok", int(f(a.ref, b.ref)))
                elif op in ("le_list", "ge_list", "isdisjoint_list"):
                    f = {"le_list": a.ref.issubset, "ge_list": a.ref.issuperset, "isdisjoint_list": a.ref.isdisjoint}[op]
                    got, want = outcome(getattr(rt, "pys_set_" + op), a.ptr, heap_list(xs)), ("ok", int(f(xs)))
                elif op == "isdisjoint":
                    got, want = outcome(rt.pys_set_isdisjoint, a.ptr, b.ptr), ("ok", int(a.ref.isdisjoint(b.ref)))
                elif op == "iterate":
                    # a for loop's calls, and one that finds the set another size
                    def loop():
                        out = []
                        used = C.w(HEAP.of(a.ptr))
                        j = rt.pys_set_next(a.ptr, 0, used)
                        while j >= 0:
                            m = rt.pys_set_big_key(a.ptr, j).addr
                            out.append(C.mpz[m] if m else C.element(rt.pys_set_key(a.ptr, j), kind))
                            j = rt.pys_set_next(a.ptr, j + 1, used)
                        return out
                    got, want = outcome(loop), ("ok", set_table(a, mode)[0])
                    same("set-next-changed", outcome(rt.pys_set_next, a.ptr, 0, len(a.ref) + 1), ("RuntimeError", "Set changed size during iteration"), (mode,))
                elif op == "list":
                    got, want = outcome(lambda: values(rt.pys_set_list(a.ptr))), ("ok", set_table(a, mode)[0])
                else:
                    live = [j for j in range(C.w(HEAP.of(a.ptr) + 24) + 1) if C.w(C.w(HEAP.of(a.ptr) + 48) + 8 * j) != -1]
                    if not live:
                        continue
                    j = R.choice(live)
                    m = rt.pys_rt_sbig(a.ptr, j).addr
                    gone = C.mpz[m] if m else C.element(C.w(C.w(HEAP.of(a.ptr) + 40) + 8 * j), kind)
                    got, want = outcome(rt.pys_set_slot_del, a.ptr, j), outcome(a.ref.remove, gone)
                Key.hook = None
                if made is not None:
                    sets.append(made)
                if hooked:
                    # no CPython outcome to compare with: no fault, and the tables stay sound
                    cases += 1
                    if got[0] not in ("ok", "KeyError"):
                        fails += 1
                        stop()
                        print(f"FAIL set {op} ({mode}), with an __eq__ that changes a set: {got}")
                    for s in sets:
                        s.ref = set(set_table(s, mode)[0])
                        s.exact = False
                    got = want
                same(f"set-{op}", got, want, (mode, x if op in ("add", "has", "discard", "remove") else len(xs)))
                for s in (a, b, made):
                    if s is not None and not sound(s, op):
                        return


class HeapDict:
    def __init__(self, ptr, ref):
        self.ptr = ptr
        self.ref = ref


def dict_table(d, mode):
    # (heap dict d's items in the order of its entries, as CPython values; what its storage
    # breaks of runtime.c's Dict, or "")
    none = -(1 << 63)
    a = HEAP.of(d.ptr)
    count, kind, n, size, keys, vals, hs, idx, cut, vatomic, vb, kb = [C.w(a + 8 * j) for j in range(12)]
    if size == 0:
        return [], "a dict without a table that has entries or arrays" if any((count, n, cut, keys, vals, hs, idx, vb, kb)) else ""
    if size < 8 or size & (size - 1):
        return [], f"a table of size {size}"
    u = size * 2 // 3
    slots = size if kind & 2 else size * 2
    ints = mode in ("int", "big")
    for name, at, room, want in (("keys", keys, u * 8, "atomic" if ints else "scan"), ("vals", vals, u * 8, "atomic" if vatomic else "scan"),
                                 ("hs", hs, u * 8, "atomic"), ("idx", idx, slots * 4, "atomic"), ("vb", vb, u * 8, "scan"), ("kb", kb, u * 8, "scan")):
        if name in ("vb", "kb") and at == 0:
            continue
        b = HEAP.block_of(at)
        if b is None or b.base != at or b.size < room + 1 or b.kind != want:
            return [], f"{name} is not an array of {room} {want} bytes"
    if (vb or kb) and mode != "big":
        return [], "Mpz words in a dict that holds no int past 64 bits"
    if n + cut > u:
        return [], f"{n} entries and {cut} cut off in a table of {u}"
    where = {}
    for i in range(slots):
        e = C.i32(idx + 4 * i)
        if e < -1 or e > n or e - 1 in where:
            return [], f"idx slot {i} holds {e}: past the {n} entries, or an entry that another slot has"
        if e > 0:
            where[e - 1] = i
    out = []
    for e in range(u):
        k, v, h = C.w(keys + 8 * e), C.w(vals + 8 * e), C.w(hs + 8 * e)
        km = C.w(kb + 8 * e) if kb else 0
        vm = C.w(vb + 8 * e) if vb else 0
        if e >= n or (h == -1 if kind & 2 else h == 0 and k == 0):
            # a hole, or past the last entry (where popitem leaves its hole's hash): nothing the
            # collector would keep, and no idx slot
            if k or v or km or vm or (e >= n and h not in (0, -1 if kind & 2 else 0)) or e in where:
                return [], f"entry {e}, a hole or past the last, is not empty"
            continue
        if e not in where:
            return [], f"entry {e} is in no idx slot"
        if km and k != none or vm and v != none:
            return [], f"entry {e} has an Mpz and not its sentinel"
        key = C.mpz[km] if km else C.element(k, kind)
        want = rt.str_key_hash(k) if mode in ("str", "str!") else hash(key) if kind & 2 else rt.int_key_hash(hash(key) if km else k)
        if h != want:
            return [], f"entry {e} keeps hash {h} of a key whose hash is {want}"
        i, p, steps = h & (slots - 1), h & ((1 << 64) - 1), 0
        while C.i32(idx + 4 * i) != e + 1:
            if C.i32(idx + 4 * i) == 0 or steps > slots * 70:
                return [], f"entry {e} is not on the probes of its hash"
            p >>= 5
            i = (i * 5 + p + 1) & (slots - 1)
            steps += 1
        out.append((key, C.mpz[vm] if vm else v))
    if len(out) != count:
        return out, f"len {count} of {len(out)} live entries"
    return out, ""


def fuzz_dicts():
    # runtime.py's dicts against CPython's, an operation at a time: the result or the error, then
    # the table, whose entries are CPython's items in CPython's order. Int keys, str keys in
    # both hash schemes, objects with a __hash__ of their own (whose probes are runtime.c's, here
    # its twin) and ints past 64 bits as keys and values. An __eq__ that changes a dict during a
    # lookup has no CPython to compare with here: the storage must stay sound
    global fails, cases
    none = -(1 << 63)
    for round in range(max(1, N // 25)):
        for mode in ("int", "str", "str!", "obj", "big"):
            HEAP.reset()
            C.setup()
            C.opt = int(mode == "big")
            Key.hook = None
            kind = {"int": 0, "big": 0, "str": 1, "str!": 3}.get(mode) if mode != "obj" else HEAP.new_str(b"H000", 0)
            dicts = []
            if mode == "obj":
                pool = [Key(hv, v) for hv in (0, 0, 1, 8, 16, 17, -2, 1 << 40) for v in range(4)]
                for x in pool:
                    x.addr = C.new_obj(x)
            elif mode in ("str", "str!"):
                pool = ["", "a", "b", "ab", "ba", "abc"] + [chr(97 + i % 26) * (1 + i // 26) for i in range(60)]
            else:
                pool = [0, 1, 2, 3, -1, -2, 7, 8, 9, 15, 16, 24, 32, MAXI, none, none + 1] + list(range(40, 100))
                if mode == "big":
                    pool += [1 << 63, -(1 << 63) - 1, 1 << 64, (1 << 70) + 3, 4 - (1 << 64)]
            grow = R.randrange(4) == 0  # (some rounds fill their tables past the small ones)

            def a_key():
                return R.choice(pool) if grow or mode == "obj" else R.choice(pool[: 10 + R.randrange(10)])

            def a_value():
                if mode == "big" and R.randrange(4) == 0:
                    return R.choice([1 << 63, -(1 << 64), (1 << 80) + 1])
                return R.choice([0, 1, -1, 7, none, MAXI, R.randrange(1000)])

            def word(x):
                # key x as the runtime takes it: its word, and its Mpz where it is past 64 bits
                if mode in ("str", "str!"):
                    return HEAP.new_str(x.encode(), 0), _rt.nil()
                if mode == "obj":
                    return x.addr, _rt.nil()
                if none <= x <= MAXI:
                    return x, _rt.nil()
                return 0, HEAP.P(C.new_mpz(x))

            def vword(v):
                return (v, _rt.nil()) if none <= v <= MAXI else (0, HEAP.P(C.new_mpz(v)))

            def entry(d, x):
                # the entry of key x, or -1: what compiled code calls for a key that may be past 64 bits
                w, m = word(x)
                return rt.pys_dict_big_find(d.ptr, w, m) if mode == "big" else rt.pys_dict_find(d.ptr, w)

            def value(d, e):
                m = rt.pys_dict_big_val(d.ptr, e).addr
                return C.mpz[m] if m else rt.pys_dict_val(d.ptr, e)

            def key_at(d, e):
                m = rt.pys_dict_big_key(d.ptr, e).addr
                return C.mpz[m] if m else C.element(rt.pys_dict_key(d.ptr, e), kind)

            def store(d, x, v):
                w, m = word(x)
                vw, vm = vword(v)
                if mode != "big":
                    rt.pys_dict_set(d.ptr, w, vw)
                elif m.addr:
                    rt.pys_dict_entry_set_big(d.ptr, rt.pys_dict_big_put(d.ptr, w, m), vw, vm)
                else:
                    rt.pys_dict_set_big(d.ptr, w, vw, vm)

            def new(items, atomic):
                d = HeapDict((rt.pys_dict_new_atomic if atomic else rt.pys_dict_new)(kind, R.choice([0, 0, 3, 6, 9, 40])), {})
                for x, v in items:
                    store(d, x, v)
                    d.ref[x] = v
                dicts.append(d)
                return d

            def sound(d, after):
                global fails, cases
                have, fault = dict_table(d, mode)
                cases += 1
                if fault == "" and have != list(d.ref.items()):
                    fault = f"items {have[:8]}, CPython's {list(d.ref.items())[:8]}"
                if fault != "":
                    fails += 1
                    stop()
                    if fails <= 20:
                        print(f"FAIL dict after {after} ({mode}): {fault}")
                return fault == ""

            def heap_list(xs):
                l = rt.pys_list_new(len(xs)) if mode in ("str", "str!", "obj") else rt.pys_list_new_atomic(len(xs))
                for x in xs:
                    w, m = word(x)
                    if m.addr:
                        rt.pys_list_append_big(l, m)
                    else:
                        rt.pys_list_append(l, w)
                return l

            def values(l, k):
                # the items of heap list l as CPython values: keys of this kind, or (k == 0) ints
                a = HEAP.of(l)
                out = []
                for i, w in enumerate(HEAP.words(C.w(a + 16), C.w(a))):
                    m = rt.pys_rt_lbig(l, i).addr
                    out.append(C.mpz[m] if m else C.element(w, k))
                return out

            atomic = R.randrange(2) == 1
            for _ in range(3):
                new([(a_key(), a_value()) for _ in range(R.choice([0, 1, 3, 5, 9, 30]))], atomic)
            for _ in range(60):
                d = R.choice(dicts)
                o = R.choice(dicts)
                x = a_key()
                v = a_value()
                w, m = word(x)
                made = None
                hooked = False
                if mode == "obj" and R.randrange(3) == 0:
                    # the program's __eq__, at one of the next comparisons: it changes d or o
                    count = [R.randrange(1, 4)]
                    victim = R.choice([d, o])
                    change = R.choice(["set", "pop_default", "clear", "grow"])
                    extra = [a_key() for _ in range(12)]

                    def hook():
                        nonlocal hooked
                        count[0] -= 1
                        if count[0] == 0:
                            Key.hook = None
                            hooked = True
                            if change == "clear":
                                rt.pys_dict_clear(victim.ptr)
                            elif change == "grow":
                                for e in extra:
                                    rt.pys_dict_set(victim.ptr, e.addr, 5)
                            else:
                                getattr(rt, "pys_dict_" + change)(victim.ptr, extra[0].addr, 6)
                    Key.hook = hook
                op = R.choice(("set set set get getitem has pop pop_default del setdefault popitem clear copy from update fromkeys fromkeys_dict "
                               "keys values items iterate reversed eq_find entry_del" + (" update_pairs getbox popbox entry" if mode != "big" else " narrow")).split())
                if op == "set":
                    got, want = outcome(store, d, x, v), outcome(d.ref.__setitem__, x, v)
                elif op == "get":
                    def get():
                        e = entry(d, x)
                        return -5 if e < 0 else value(d, e)
                    got, want = outcome(get) if mode == "big" else outcome(rt.pys_dict_get, d.ptr, w, -5), ("ok", d.ref.get(x, -5))
                elif op == "getitem":
                    if mode == "big":
                        got = outcome(lambda: value(d, rt.pys_dict_big_entry(d.ptr, w, m)))
                    else:
                        got = outcome(rt.pys_dict_getitem, d.ptr, w)
                    want = outcome(d.ref.__getitem__, x)
                elif op == "has":
                    got, want = outcome(lambda: int(entry(d, x) >= 0)) if mode == "big" else outcome(rt.pys_dict_has, d.ptr, w), ("ok", int(x in d.ref))
                elif op in ("pop", "pop_default"):
                    def big_pop():
                        # pys_dict_bkey_big_pop: by a promoting int key, a promoting int's two words (the default's)
                        lo, b = rt.pys_dict_bkey_big_pop(d.ptr, w, m, int(op == "pop_default"), -7, _rt.nil())
                        return C.mpz[b.addr] if b.addr else lo
                    if mode == "big":
                        got = outcome(big_pop)
                    elif op == "pop":
                        got = outcome(rt.pys_dict_pop, d.ptr, w)
                    else:
                        got = outcome(rt.pys_dict_pop_default, d.ptr, w, -7)
                    want = outcome(d.ref.pop, x) if op == "pop" else ("ok", d.ref.pop(x, -7))
                elif op == "del":
                    def delete():
                        del d.ref[x]
                    def take():
                        rt.pys_dict_del(d.ptr, w)
                    got = outcome(rt.pys_dict_big_del, d.ptr, w, m) if mode == "big" else outcome(take)
                    want = outcome(delete)
                elif op == "setdefault":
                    def big_setdefault():
                        # pys_dict_bkey_big_setdefault: the value there, or the default stored, as a promoting int
                        vw, vm = vword(v)
                        lo, b = rt.pys_dict_bkey_big_setdefault(d.ptr, w, m, vw, vm)
                        return C.mpz[b.addr] if b.addr else lo
                    got = outcome(big_setdefault) if mode == "big" else outcome(rt.pys_dict_setdefault, d.ptr, w, v)
                    want = outcome(d.ref.setdefault, x, v)
                elif op == "popitem":
                    def popitem():
                        t = (rt.pys_dict_big_popitem if mode == "big" else rt.pys_dict_popitem)(d.ptr)
                        k0, v0 = _rt.word(t, 0), _rt.word(t, 1)
                        big = mode == "big" and none in (k0, v0)
                        km = _rt.word(t, 2) if big else 0
                        vm = _rt.word(t, 3) if big else 0
                        return (C.mpz[km] if km else C.element(k0, kind), C.mpz[vm] if vm else v0)
                    got, want = outcome(popitem), outcome(d.ref.popitem)
                    if got[0] == want[0] == "KeyError":
                        got = want  # (the message is CPython's: 'popitem(): dictionary is empty')
                elif op == "clear":
                    got, want = outcome(rt.pys_dict_clear, d.ptr), outcome(d.ref.clear)
                elif op in ("copy", "from"):
                    # (an __eq__ that changes d while its keys are inserted: RuntimeError, as CPython's)
                    got, want = outcome(getattr(rt, "pys_dict_" + op), d.ptr), ("ok", None)
                    if got[0] == "ok":
                        made = HeapDict(got[1], dict(d.ref))
                        got = want
                elif op == "update":
                    got, want = outcome(rt.pys_dict_update, d.ptr, o.ptr), outcome(d.ref.update, o.ref)
                elif op == "update_pairs":
                    pairs = [(a_key(), a_value()) for _ in range(R.choice([0, 1, 4, 12]))]
                    l = rt.pys_list_new(len(pairs))
                    for pk, pv in pairs:
                        t = HEAP.new(16, "scan", "tuple")
                        C.put(t, word(pk)[0])
                        C.put(t + 8, pv)
                        rt.pys_list_append(l, t)
                    got, want = outcome(rt.pys_dict_update_pairs, d.ptr, l), outcome(d.ref.update, pairs)
                elif op == "fromkeys":
                    xs = [a_key() for _ in range(R.choice([0, 1, 4, 12, 40]))]
                    got, want = outcome(rt.pys_dict_fromkeys, kind, heap_list(xs), 3), ("ok", None)
                    if got[0] == "ok":
                        made = HeapDict(got[1], dict.fromkeys(xs, 3))
                        got = want
                elif op == "fromkeys_dict":
                    got, want = outcome(rt.pys_dict_fromkeys_dict, d.ptr, 4), ("ok", None)
                    if got[0] == "ok":
                        made = HeapDict(got[1], dict.fromkeys(d.ref, 4))
                        got = want
                elif op in ("keys", "values"):
                    got = outcome(lambda: values(getattr(rt, "pys_dict_" + op)(d.ptr), kind if op == "keys" else 0))
                    want = ("ok", list(d.ref) if op == "keys" else list(d.ref.values()))
                elif op == "items":
                    def items():
                        l = (rt.pys_dict_big_items if mode == "big" else rt.pys_dict_items)(d.ptr)
                        out = []
                        for t in HEAP.words(C.w(HEAP.of(l) + 16), C.w(HEAP.of(l))):
                            k0, v0 = C.w(t), C.w(t + 8)
                            big = mode == "big" and none in (k0, v0)
                            km = C.w(t + 16) if big else 0
                            vm = C.w(t + 24) if big else 0
                            out.append((C.mpz[km] if km else C.element(k0, kind), C.mpz[vm] if vm else v0))
                        return out
                    got, want = outcome(items), ("ok", list(d.ref.items()))
                elif op in ("iterate", "reversed"):
                    # a for loop's calls, and one that finds the dict another size
                    def loop():
                        out = []
                        used = C.w(HEAP.of(d.ptr))
                        step = 1 if op == "iterate" else -1
                        walk = rt.pys_dict_next if op == "iterate" else rt.pys_dict_prev
                        e = walk(d.ptr, 0 if op == "iterate" else rt.pys_dict_end(d.ptr) - 1, used, 0)
                        while e >= 0:
                            out.append((key_at(d, e), value(d, e)))
                            e = walk(d.ptr, e + step, used, len(out))
                        return out
                    got, want = outcome(loop), ("ok", list(d.ref.items()) if op == "iterate" else list(reversed(d.ref.items())))
                    same("dict-next-changed", outcome(rt.pys_dict_next, d.ptr, 0, len(d.ref) + 1, 0), ("RuntimeError", "dictionary changed size during iteration"), (mode,))
                elif op == "eq_find":
                    # each of o's entries looked up in d by the hash o keeps: d == o's steps
                    def eq_find():
                        out = []
                        e = rt.pys_dict_eq_next(o.ptr, 0)
                        while e >= 0:
                            f = rt.pys_dict_eq_find(d.ptr, o.ptr, e)
                            out.append(None if f < 0 else value(d, f))
                            e = rt.pys_dict_eq_next(o.ptr, e + 1)
                        return out
                    got, want = outcome(eq_find), ("ok", [d.ref.get(k0) for k0 in o.ref])
                elif op == "entry_del":
                    def entry_del():
                        e = entry(d, x)
                        if e >= 0:
                            rt.pys_dict_entry_del(d.ptr, e)
                        return e >= 0
                    had = x in d.ref
                    d.ref.pop(x, None)
                    got, want = outcome(entry_del), ("ok", had)
                elif op == "narrow":
                    got = outcome(rt.pys_dict_narrow, d.ptr)
                    want = ("OverflowError", "Python int too large to convert to C long") if any(not none <= y <= MAXI for y in d.ref.values()) else ("ok", None)
                elif op in ("getbox", "popbox"):
                    def boxed():
                        b = getattr(rt, "pys_dict_" + op)(d.ptr, w, 0)
                        return -9 if b == 0 else C.boxes[b]
                    got, want = outcome(boxed), ("ok", d.ref.get(x, -9) if op == "getbox" else d.ref.pop(x, -9))
                else:
                    def set_entry():
                        e = rt.pys_dict_entry(d.ptr, w)
                        rt.pys_dict_entry_set(d.ptr, e, v)
                    def set_ref():
                        d.ref[x]
                        d.ref[x] = v
                    got, want = outcome(set_entry), outcome(set_ref)
                Key.hook = None
                if made is not None:
                    dicts.append(made)
                if hooked:
                    # no CPython outcome to compare with: no fault, and the tables stay sound
                    cases += 1
                    if got[0] not in ("ok", "KeyError", "RuntimeError"):
                        fails += 1
                        stop()
                        print(f"FAIL dict {op} ({mode}), with an __eq__ that changes a dict: {got}")
                    for s in dicts:
                        s.ref = dict(dict_table(s, mode)[0])
                    got = want
                same(f"dict-{op}", got, want, (mode, x if mode != "obj" else repr(x)))
                for s in (d, o, made):
                    if s is not None and not sound(s, op):
                        return


class Obj:
    # an object of a class of the program's: its __eq__, ordering and __repr__ are the program's
    # (pys_obj_*), here those of its value
    def __init__(self, v):
        self.v = v

    def __eq__(self, o):
        return self.v == o.v if isinstance(o, Obj) else NotImplemented

    def __lt__(self, o):
        return self.v < o.v

    def __le__(self, o):
        return self.v <= o.v

    def __gt__(self, o):
        return self.v > o.v

    def __ge__(self, o):
        return self.v >= o.v

    def __repr__(self):
        return f"Obj({self.v})"

    __hash__ = None


WALK_STRS = ["", "a", "ab", "it's", 'say "hi"', "both ' and \"", "tab\there", "nl\n\r", "\\", "\x00\x1f\x7f", "\xe9", "\u20acuro",
             "\U0001d11e", "\u200b", "\U000e0001", "\u0378", "\xa0", "\u2028", "ab\u0300c", "\ud7ff\ue000"]
WALK_FLOATS = [0.0, -0.0, 1.5, -2.5, 1e300, 1e-310, 1 / 3, 3.0, 2.0 ** 63, float("inf"), float("-inf"), 1e16, 12345.678]
BIG_J = [0, 5, -1, -(1 << 63), (1 << 63) - 1, 1 << 64, -(1 << 70), 10 ** 30, -(10 ** 25)]
KIND = {"i": int, "b": bool, "f": float, "s": str, "y": bytes, "L": list, "D": dict, "S": set, "F": frozenset, "T": tuple, "V": tuple}


def wtype(depth, numeric=False):
    # a random type, as a tuple of its letter and parts (numeric: only what CPython orders by
    # value with an int and a float in a union: ints, floats, and sequences of them)
    if numeric:
        r = R.randrange(7 if depth > 0 else 3)
        if r < 3:
            return (("i",), ("f",), ("b",))[r]
        if r == 3:
            return ("L", wtype(depth - 1, True))
        if r == 4:
            return ("T", [wtype(depth - 1, True) if R.randrange(4) else ("J",) for _ in range(R.randrange(4))])
        if r == 5:
            return ("U", [(3, ("i",)), (8, ("f",))]) if R.randrange(2) else ("V", wtype(depth - 1, True))
        inner = wtype(depth - 1, True)
        return inner if inner[0] == "?" else ("?", inner)
    r = R.randrange(14 if depth > 0 else 6)
    if r < 6:
        return (("i",), ("b",), ("f",), ("s",), ("O",), ("y",))[r]
    if r == 6:
        return ("L", wtype(depth - 1))
    if r == 7:
        return ("D", R.choice([("i",), ("s",)]), wtype(depth - 1))
    if r == 8:
        return (R.choice("SF"), ("i",))
    if r == 9:
        return ("T", [wtype(depth - 1) if R.randrange(4) else ("J",) for _ in range(R.randrange(4))])
    if r == 10:
        return ("V", wtype(depth - 1))
    if r == 11:
        inner = wtype(depth - 1)
        return inner if inner[0] == "?" else ("?", inner)
    if r == 12:
        # a union: members of distinct Python types (no bool beside int), each of a program-wide tag
        # (and no object compared by its __eq__: the compiler gives a union's classes P, by identity)
        inner = wtype(depth - 1)
        pool = [("i",), ("f",), ("s",), ("L", inner if not has(inner, "OSF") else ("s",)), ("T", [("i",), ("s",)]), ("D", ("s",), ("i",))]
        ms = R.sample(pool, R.randrange(2, 4))
        tags = R.sample(range(1, 30), len(ms))
        return ("U", list(zip(tags, ms)))
    return ("L", ("i",))


def wdesc(t):
    k = t[0]
    if k == "O":
        return "O000"
    if k in "LVSF?":
        return k + wdesc(t[1])
    if k == "D":
        return "D" + wdesc(t[1]) + wdesc(t[2])
    if k == "T":
        return "T" + str(len(t[1])) + "".join(wdesc(x) for x in t[1])
    if k == "U":
        # (a member that ends in an object's id ends at a '.')
        return "U" + str(len(t[1])) + ":" + "".join(f"{tag}:{wdesc(m)}" + ("." if re.search(r"[OPH][0-9]{3,}$", wdesc(m)) else "") for tag, m in t[1])
    return k


def wvalue(t, depth=0):
    # a CPython value of type t
    k = t[0]
    if k == "i":
        return R.choice([0, 1, -1, 7, 255, MAXI, -MAXI - 1, R.randrange(-1000, 1000)])
    if k == "b":
        return R.choice([False, True])
    if k == "f":
        return R.choice(WALK_FLOATS)
    if k == "s":
        return R.choice(WALK_STRS) if R.randrange(3) else text()
    if k == "y":
        return bytes(R.randrange(256) for _ in range(R.randrange(6)))
    if k == "J":
        return R.choice(BIG_J)
    if k == "O":
        return Obj(R.randrange(4))
    if k == "L":
        return [wvalue(t[1], depth + 1) for _ in range(R.randrange(4))]
    if k == "D":
        return {wvalue(t[1]): wvalue(t[2], depth + 1) for _ in range(R.randrange(4))}
    if k in "SF":
        xs = [R.randrange(-5, 40) for _ in range(R.randrange(12))]
        return ("set" if k == "S" else "frozenset", xs)  # (the insertion order: the table's order is CPython's)
    if k == "T":
        return tuple(wvalue(x, depth + 1) for x in t[1])
    if k == "V":
        return tuple(wvalue(t[1], depth + 1) for _ in range(R.randrange(4)))
    if k == "?":
        return None if R.randrange(3) == 0 else wvalue(t[1], depth)
    return wvalue(R.choice(t[1])[1], depth)


def wpy(v):
    # the CPython value of a generated one: a set made in its insertion order
    if isinstance(v, tuple) and len(v) == 2 and type(v[0]) is str and v[0] in ("set", "frozenset") and isinstance(v[1], list):
        return set(v[1]) if v[0] == "set" else frozenset(v[1])
    if isinstance(v, list):
        return [wpy(x) for x in v]
    if isinstance(v, tuple):
        return tuple(wpy(x) for x in v)
    if isinstance(v, dict):
        return {k: wpy(x) for k, x in v.items()}
    return v


def fbits(x):
    return struct.unpack("<q", struct.pack("<d", x))[0]


def wlay(t, v):
    # the word of value v of type t in runtime.c's layouts, on the heap
    k = t[0]
    if k in "ib":
        return int(v)
    if k == "f":
        return fbits(v)
    if k == "s":
        return HEAP.new_str(v.encode("utf-8"), 0)
    if k == "y":
        return HEAP.new_str(v, 0)
    if k == "O":
        return C.new_obj(v)
    if k == "L":
        atomic = t[1][0] in "ibf"
        l = (rt.pys_list_new_atomic if atomic else rt.pys_list_new)(len(v))
        for x in v:
            rt.pys_list_append(l, wlay(t[1], x))
        return HEAP.of(l)
    if k == "D":
        d = (rt.pys_dict_new_atomic if t[2][0] in "ibf" else rt.pys_dict_new)(0 if t[1][0] == "i" else 1, 0)
        for key, x in v.items():
            rt.pys_dict_set(d, wlay(t[1], key), wlay(t[2], x))
        return HEAP.of(d)
    if k in "SF":
        s = rt.pys_set_new(0)
        for x in v[1]:
            rt.pys_set_add(s, x)
        return HEAP.of(s)
    if k == "T":
        n = len(t[1])
        big = any(x[0] == "J" for x in t[1])
        a = HEAP.new(8 * (2 * n if big else n), "scan", "tuple")
        for i, (x, item) in enumerate(zip(t[1], v)):
            if x[0] == "J":
                fit = -(1 << 63) < item < (1 << 63)
                C.put(a + 8 * i, item if fit else -(1 << 63))
                C.put(a + 8 * (n + i), 0 if fit or item == -(1 << 63) else C.new_mpz(item))
            else:
                C.put(a + 8 * i, wlay(x, item))
            if big and x[0] != "J":
                C.put(a + 8 * (n + i), 0)
        return a
    if k == "V":
        a = HEAP.new(16 + 8 * len(v), "scan", "vtuple")
        C.put(a, len(v))
        C.put(a + 8, 0)
        for i, item in enumerate(v):
            C.put(a + 16 + 8 * i, wlay(t[1], item))
        return a
    if k == "?":
        if v is None:
            return 0
        if t[1][0] in "ibf":
            a = HEAP.new(16, "atomic", "box")
            C.put(a, wlay(t[1], v))
            C.put(a + 8, 0)
            return a
        return wlay(t[1], v)
    if v is None:
        return 0
    for tag, m in t[1]:
        if type(wpy(v)) is KIND[m[0]] or (m[0] == "f" and type(v) is float):
            a = HEAP.new(16, "scan", "union")
            C.put(a, tag)
            C.put(a + 8, wlay(m, v))
            return a
    raise AssertionError(f"no member of {wdesc(t)} holds {v!r}")


def walt(t):
    # another type whose values include t's, for == of two descriptors (eq.pair)
    k = t[0]
    r = R.randrange(3)
    if k == "i":
        return (("i",), ("?", ("i",)), ("U", [(4, ("i",)), (9, ("s",))]))[r]
    if k == "b":
        return (("b",), ("?", ("b",)), ("U", [(4, ("b",)), (9, ("s",))]))[r]
    if k == "f":
        return (("f",), ("?", ("f",)), ("U", [(5, ("i",)), (6, ("f",))]))[r]
    if k == "s":
        return (("s",), ("?", ("s",)), ("U", [(7, ("s",)), (2, ("f",))]))[r]
    if k == "L":
        return ("L", walt(t[1]))
    if k == "D":
        return ("D", t[1], walt(t[2]))
    if k == "T":
        same_items = len(t[1]) > 0 and all(x == t[1][0] and x[0] != "J" for x in t[1])
        return ("V", walt(t[1][0])) if same_items and r == 0 else ("T", [walt(x) if x[0] != "J" else x for x in t[1]])
    if k == "V":
        return ("V", walt(t[1]))
    if k == "?":
        inner = walt(t[1])
        return inner if inner[0] == "?" else ("?", inner)
    return t


def has(t, letters):
    if t[0] in letters:
        return True
    parts = t[1:] if t[0] != "U" and t[0] != "T" else [m for _, m in t[1]] if t[0] == "U" else t[1]
    return any(isinstance(x, tuple) and has(x, letters) for x in parts)


def only(t, letters):
    if t[0] not in letters:
        return False
    parts = t[1:] if t[0] != "U" and t[0] != "T" else [m for _, m in t[1]] if t[0] == "U" else t[1]
    return all(only(x, letters) for x in parts if isinstance(x, tuple))


def wout(f, *a):
    # outcome's, with a str in the heap as its text
    r = outcome(f, *a)
    return (r[0], r[1].text()) if r[0] == "ok" and isinstance(r[1], rt_heap.Str) else r


def fuzz_walks():
    # repr(), == and < <= > >= of values that a descriptor describes (runtime.py's walks), against
    # CPython's: values of a random type laid out in runtime.c's layouts, and == of two
    # descriptors of the same values (eq.pair). Ints past 64 bits are promoting ints, items of a
    # tuple; objects are a class's of the program, whose __eq__, ordering and __repr__ it defines
    for _ in range(N):
        HEAP.reset()
        C.setup()
        C.opt = 1
        t = wtype(R.randrange(4))
        d = wdesc(t)
        ds = HEAP.as_str(HEAP.new_str(d.encode(), 0))
        v = wvalue(t)
        w = wlay(t, v)
        p = wpy(v)
        same("walk-repr", wout(rt.pys_repr, w, ds), ref(lambda: repr(p)), (d, p))
        same("walk-repr-marks", sorted(C.busy), [], (d, p))  # (each repr under way is ended)
        # ==, and the orderings where every float is a number (a NaN's identity, which CPython keeps
        # in a container, an unboxed float has not)
        v2 = wvalue(t) if R.randrange(2) else v
        w2 = w if v2 is v and R.randrange(2) else wlay(t, v2)
        p2 = p if w2 == w else wpy(v2)
        if not has(t, "y"):
            same("walk-eq", outcome(rt.pys_eq, w, w2, ds), ref(lambda: int(p == p2)), (d, p, p2))
        tn = wtype(R.randrange(3), True)
        dn = HEAP.as_str(HEAP.new_str(wdesc(tn).encode(), 0))
        a, b2 = wvalue(tn), wvalue(tn)
        pa, pb = wpy(a), wpy(b2)
        wa, wb = wlay(tn, a), wlay(tn, b2)
        op = R.randrange(4)
        cmp = (lambda x, y: x < y, lambda x, y: x <= y, lambda x, y: x > y, lambda x, y: x >= y)[op]
        same("walk-order", outcome(rt.pys_cmpop, wa, wb, dn, op), ref(lambda: int(cmp(pa, pb))), (wdesc(tn), pa, pb, op))
        if not has(t, "OySF"):
            # == of two descriptors: the same type's values, laid out as another type that holds them
            t2 = walt(t)
            d2 = HEAP.as_str(HEAP.new_str(wdesc(t2).encode(), 0))
            w3 = wlay(t2, v2)
            same("walk-eq-pair", outcome(rt.pys_eq_pair, w, w3, ds, d2), ref(lambda: int(p == p2)), (d, wdesc(t2), p, p2))
        if has(t, "O") and only(t, "OLTV"):
            # the orderings of objects: theirs, the program's
            same("walk-order-obj", outcome(rt.pys_cmpop, w, w2, ds, op), ref(lambda: int(cmp(p, p2))), (d, p, p2, op))
    # deterministic: a recursive alias's 512 edges (list[R], descriptor LR1:), then the 513th, which
    # RecursionError ends (CPython's own limit is the interpreter's); an int past CPython's 4300
    # digits; a list being printed again through its own item
    was = sys.getrecursionlimit()
    sys.setrecursionlimit(max(was, 20000))  # (runtime.py's walks recurse here as compiled)
    for depth, want in [(512, None), (513, "RecursionError")]:
        HEAP.reset()
        C.setup()
        ds = HEAP.as_str(HEAP.new_str(b"LR1:", 0))
        chains = []
        for _ in range(2):
            inner = rt.pys_list_new(0)
            for _ in range(depth):
                outer = rt.pys_list_new(1)
                rt.pys_list_append(outer, HEAP.of(inner))
                inner = outer
            chains.append(HEAP.of(inner))
        p = []
        for _ in range(depth):
            p = [p]
        got = wout(rt.pys_repr, chains[0], ds)
        same("walk-deep-repr", got[0], want or "ok", (depth,))
        if want is None:
            same("walk-deep-repr-text", got[1], b(repr(p)), (depth,))
        same("walk-deep-eq", outcome(rt.pys_eq_pair, chains[0], chains[1], ds, ds)[0], want or "ok", (depth,))
    sys.setrecursionlimit(was)
    HEAP.reset()
    C.setup()
    C.opt = 1
    t = ("T", [("J",), ("i",)])
    ds = HEAP.as_str(HEAP.new_str(b"T2Ji", 0))
    for v in [(10 ** 4299, 1), (10 ** 4300, 2)]:
        same("walk-digits", wout(rt.pys_repr, wlay(t, v), ds), ref(lambda: repr(v)), (len(str(v[0])) if v[0] < 10 ** 4300 else 4301,))
    l = rt.pys_list_new(1)
    ds = HEAP.as_str(HEAP.new_str(b"LO000", 0))
    rt.pys_list_append(l, C.new_obj(Obj(1)))
    same("walk-busy", wout(rt.pys_repr, HEAP.of(l), ds), ("ok", "[Obj(1)]"), ())
    C.busy.add(HEAP.of(l))
    same("walk-busy", wout(rt.pys_repr, HEAP.of(l), ds), ("ok", "[...]"), ())


def u8count(data):
    # the code points of a str's bytes as runtime.c's u8char reads them: a sequence that chr()
    # writes, else a byte
    n = i = 0
    while i < len(data):
        c = data[i]
        k = 1 if c > 0xF4 else 4 if c >= 0xF0 else 3 if c >= 0xE0 else 2 if c >= 0xC2 else 1
        if k > 1 and k <= len(data) - i and all(x & 0xC0 == 0x80 for x in data[i + 1 : i + k]):
            v = c & (0x7F >> k)
            for x in data[i + 1 : i + k]:
                v = v << 6 | (x & 0x3F)
            if not (v < (0x80 if k == 2 else 0x800 if k == 3 else 0x10000) or v > 0x10FFFF):
                i += k
                n += 1
                continue
        i += 1
        n += 1
    return n


def fuzz_str_memory():
    # str + str, the joined parts of an f-string and str * n in the heap: the bytes, the NUL
    # after them, the length, and a cached count of code points that is the str's or unset
    pieces = [b"", b"a", b"ab", b"\xc3\xa9", b"\xe2\x82\xac", b"\xe2\x82", b"\xac", b"\x82\xac", b"\xf0\x9d\x84\x9e", b"\xff", b"x" * 40]

    def heap_str():
        data = b"".join(R.choice(pieces) for _ in range(R.randrange(4)))
        return HEAP.as_str(HEAP.new_str(data, R.choice([0, u8count(data) + 1]))), data

    def result(f, *a):
        r = outcome(f, *a)
        if r[0] != "ok":
            return r
        addr = HEAP.of(r[1])
        n = C.w(addr)
        data = HEAP.read(addr + 24, n + 1)
        if data[n] != 0:
            return ("storage", "no NUL after the bytes")
        if C.w(addr + 8) != 0:
            return ("storage", "a dict hash in a new str")
        if C.w(addr + 16) not in (0, u8count(data[:n]) + 1):
            return ("storage", f"cached count {C.w(addr + 16) - 1} of a str of {u8count(data[:n])} code points")
        return ("ok", data[:n])

    for _ in range(N):
        HEAP.reset()
        C.setup()
        parts = [heap_str() for _ in range(8)]
        a, b = parts[0], parts[1]
        same("str-add", result(rt.pys_str_add, a[0], b[0]), ("ok", a[1] + b[1]), (a[1], b[1]))
        n = R.randrange(9)
        same("str-cat", result(rt.pys_str_cat, n, *[x[0] for x in parts]), ("ok", b"".join(x[1] for x in parts[:n])), (n, [x[1] for x in parts]))
        k = R.choice([-1, 0, 1, 2, 3, 7, MAXI])
        want = outcome(lambda: (a[1].decode("latin-1") * k).encode("latin-1"))
        same("str-mul", result(rt.pys_str_mul, a[0], k), want, (a[1], k))


def check_model():
    # the model itself: each kind of fault that it exists to find is one it raises
    h = rt_heap.Heap(RTRECORDS)
    m = rt_heap.primitives(h)
    c = rt_heap.CSide(h)
    l = c.pys_alloc(31)
    arr = c.pys_alloc_atomic(16)
    raw = c.pys_rt_raw(8)
    m["set"](l, "List.len", 2)
    m["put"](arr, 0, 5)

    def unchecked_sum():
        return rt.span_lo(-MAXI, -MAXI)  # (-MAXI + -MAXI in an @_rt.unchecked function)

    for name, f in [
        ("a read past a block", lambda: m["word"](arr, 3)),
        ("a write past a block", lambda: m["put"](arr, 3, 1)),
        ("a read before a block", lambda: m["word"](arr, -1)),
        ("a read of what nothing wrote", lambda: m["word"](raw, 0)),
        ("a word read as a field", lambda: m["get"](arr, "List.len")),
        ("a field read as a word", lambda: m["word"](l, 0)),
        ("a word field read as an address", lambda: m["getp"](l, "List.len")),
        ("overlapping copy", lambda: m["cpy"](m["offset"](arr, 4), arr, 8)),
        ("a copy of a size below zero", lambda: m["cpy"](arr, l, -8)),
        ("a store that does not fit", lambda: m["put"](arr, 0, 1 << 63)),
        ("a write that changes a sentinel", lambda: m["put"](c.pys_rt_empty_list(), 0, 1)),
        ("unchecked overflow", unchecked_sum),
    ]:
        same("model: " + name, outcome(f)[0], "Fault", ())
    # and what is no fault: one past the end as an address, a copy of nothing anywhere, bytes
    # read of a word, a word read after a block operation wrote it
    for name, f in [
        ("one past the end", lambda: m["at"](arr, 3)),
        ("a copy of nothing", lambda: m["cpy"](m["nil"](), m["nil"](), 0)),
        ("a byte of a word", lambda: m["byte_at"](arr, 0)),
        ("a field after a fill", lambda: (m["fill"](l, 0, 32), m["word"](l, 0))),
        ("the slack byte", lambda: m["byte_at"](arr, 16)),
        ("a sentinel's own bits stored again", lambda: m["put"](c.pys_rt_empty_identity(1), 0, 1)),
    ]:
        same("model: " + name, outcome(f)[0], "ok", ())


def fuzz_str():
    for _ in range(N):
        s = text()
        n = text(n=3)
        st, en = idx(), idx()
        for name, mine, ref in [
            ("find", rt.pys_str_find, lambda: s.find(n, st, en)),
            ("rfind", rt.pys_str_rfind, lambda: s.rfind(n, st, en)),
            ("index", rt.pys_str_index, lambda: s.index(n, st, en)),
            ("rindex", rt.pys_str_rindex, lambda: s.rindex(n, st, en)),
            ("count", rt.pys_str_count, lambda: s.count(n, st, en)),
            ("startswith", rt.pys_str_startswith, lambda: int(s.startswith(n, st, en))),
            ("endswith", rt.pys_str_endswith, lambda: int(s.endswith(n, st, en))),
        ]:
            same(name, outcome(mine, s, n, st, en), outcome(ref), (s, n, st, en))
        same("contains", outcome(rt.pys_str_contains, s, n), outcome(lambda: int(n in s)), (s, n))
        r = text(n=3)
        same("replace", outcome(rt.pys_str_replace, s, n, r), outcome(s.replace, n, r), (s, n, r))
        cs = R.choice([None, text(n=3)])
        for name, mine, ref in [("strip", rt.pys_str_strip, s.strip), ("lstrip", rt.pys_str_lstrip, s.lstrip), ("rstrip", rt.pys_str_rstrip, s.rstrip)]:
            same(name, outcome(mine, s, cs), outcome(ref, cs), (s, cs))
        for name in "isdigit isalpha isalnum isspace isupper islower isascii isdecimal isnumeric istitle".split():
            same(name, outcome(getattr(rt, "pys_str_" + name), s), outcome(lambda: int(getattr(s, name)())), (s,))
        for name in "upper lower swapcase capitalize title casefold".split():
            same(name, outcome(getattr(rt, "pys_str_" + name), s), outcome(getattr(s, name)), (s,))
        sep = R.choice([None, None, text(n=2)])
        m = R.choice([-1, -1, 0, 1, 2, 5])
        same("split", outcome(rt.pys_str_split, s, sep, m), outcome(s.split, sep, m), (s, sep, m))
        same("rsplit", outcome(rt.pys_str_rsplit, s, sep, m), outcome(s.rsplit, sep, m), (s, sep, m))
        keep = R.randrange(2)
        same("splitlines", outcome(rt.pys_str_splitlines, s, keep), outcome(s.splitlines, bool(keep)), (s, keep))
        same("partition", outcome(rt.pys_str_partition, s, n), outcome(s.partition, n), (s, n))
        same("rpartition", outcome(rt.pys_str_rpartition, s, n), outcome(s.rpartition, n), (s, n))
        same("removeprefix", outcome(rt.pys_str_removeprefix, s, n), outcome(s.removeprefix, n), (s, n))
        same("removesuffix", outcome(rt.pys_str_removesuffix, s, n), outcome(s.removesuffix, n), (s, n))
        ts = R.choice([-1, 0, 1, 4, 8, -2**31, -2**31 - 1, 2**31, 2**62])
        same("expandtabs", outcome(rt.pys_str_expandtabs, s, ts), outcome(s.expandtabs, ts), (s, ts))
        parts = [text(n=4) for _ in range(R.randrange(4))]
        same("join", outcome(rt.pys_str_join, n, parts), outcome(n.join, parts), (n, parts))
        # widths count characters: compare on UTF-8 text through its bytes
        w = text(WIDE, 6)
        width = R.randrange(-2, 12)
        fill = R.choice([None, R.choice(WIDE), "ab"])
        for name in "ljust rjust center".split():
            ref = outcome(getattr(w, name), width, fill if fill is not None else " ")
            if ref[0] == "ok":
                ref = ("ok", b(ref[1]))
            same(name, outcome(getattr(rt, "pys_str_" + name), b(w), width, b(fill) if fill is not None else None), ref, (w, width, fill))
        z = R.choice(["", "+", "-"]) + text("12é", 4)
        same("zfill", outcome(rt.pys_str_zfill, b(z), width), ("ok", b(z.zfill(width))), (z, width))
        # and replace("", x) puts x between characters
        x = text(WIDE, 2)
        k = R.choice([-1, 0, 1, 2, 5, 9])
        same("replace", outcome(rt.pys_str_replace, b(w), "", b(x)), ("ok", b(w.replace("", x))), (w, x))
        same("replace_count", outcome(rt.pys_str_replace_count, b(w), "", b(x), k), ("ok", b(w.replace("", x, k))), (w, x, k))


BYTES = b"ab AB-+0\t\n\r\x0b\x0c\x1c\x85_.,lL\x80\xa0\xc3\xa9\xe2\x82\xac\xed\xa0\xf0\xff"


def bt(s):
    # the Pystachy str of a bytes: a character per byte
    return s.decode("latin-1")


def bref(f):
    # CPython's outcome, its bytes (and those in a list or tuple) as Pystachy strs, a str as the
    # UTF-8 a Pystachy str holds (surrogates too), a bool as an int
    r = outcome(f)
    v = r[1]
    if isinstance(v, bytes):
        v = bt(v)
    elif isinstance(v, (list, tuple)) and all(isinstance(x, bytes) for x in v):
        v = type(v)(bt(x) for x in v)
    elif isinstance(v, str) and r[0] == "ok":
        v = v.encode("utf-8", "surrogatepass").decode("latin-1")
    elif isinstance(v, bool):
        v = int(v)
    return (r[0], v)


def data(n=12):
    alpha = b"ab" if R.randrange(3) == 0 else BYTES
    return bytes(R.choice(alpha) for _ in range(R.randrange(n + 1)))


def fuzz_unicode_classification():
    # Exercise runtime.py's UTF-8 traversal separately from its C lookup. The table check
    # regenerates every code point; unicode_audit.py also compares native lookup results.
    check_unicode_table()
    pool = "aZ09é界न\u0301\u0345²½Ⅳ四٩१२𝟘\U0001e4f0\U0002ebf0😀\ud800\udfff\x00"
    for _ in range(N):
        s = text(pool) if R.randrange(2) else "".join(chr(R.randrange(0x110000)) for _ in range(R.randrange(8)))
        raw = s.encode("utf-8", "surrogatepass").decode("latin-1")
        for name in "isalpha isalnum isdecimal isdigit isnumeric".split():
            same(name, outcome(getattr(rt, "pys_str_" + name), raw), outcome(getattr(s, name)), (s,))


CASE_METHODS = "upper lower swapcase capitalize title casefold".split()
CASE_TESTS = "isupper islower istitle".split()


def fuzz_unicode_case():
    # str's case methods on text that is not ASCII: runtime.py's traversal, its Final_Sigma
    # context and its sizes, with CPython's own mappings standing in for runtime.c's lookups
    # (the table check above compares those with every code point; unicode_audit.py the native
    # ones). Characters whose mappings are longer or shorter than they are, in characters and
    # in bytes; cased, titlecase and case-ignorable ones around sigmas; and any code point
    pool = ("aZ0 '.:\u00ad\u0301\u02b0\u2019\u00e9\u00c9\u00df\u1e9e\u0149\u01c4\u01c5\u01c6\u0130\u0131\u017f"
            "\ufb01\ufb03\u0390\u1f88\u1fb3\u2126\u212a\u023a\u2c65\u13a0\uab70\u10d0\u1c90\U00010400\U00010428"
            "\u754c\U0001f600\ud800\udfff\x00")
    sigmas = "\u03a3\u03c3\u03c2aA '.\u0301\u02b0\u01c51\u754c"
    for _ in range(N):
        k = R.randrange(3)
        s = text(pool) if k == 0 else text(sigmas, 8) if k == 1 else "".join(chr(R.randrange(0x110000)) for _ in range(R.randrange(8)))
        raw = s.encode("utf-8", "surrogatepass").decode("latin-1")
        for name in CASE_METHODS:
            same(name, outcome(getattr(rt, "pys_str_" + name), raw),
                 ("ok", getattr(s, name)().encode("utf-8", "surrogatepass").decode("latin-1")), (s,))
        for name in CASE_TESTS:
            same(name, outcome(getattr(rt, "pys_str_" + name), raw), outcome(getattr(s, name)), (s,))
    # bytes that begin no character are kept and are no letters, as the lone surrogates are
    # that CPython's surrogateescape reads them as
    for _ in range(N):
        r = b"".join(R.choice(PIECES + CASE_PIECES) for _ in range(R.randrange(9)))
        s = r.decode("latin-1")
        c = esc(r)
        for name in CASE_METHODS:
            same(name, outcome(getattr(rt, "pys_str_" + name), s), ref_raw(getattr(c, name)), (r,))
        for name in CASE_TESTS:
            same(name, outcome(getattr(rt, "pys_str_" + name), s), outcome(getattr(c, name)), (r,))


def fuzz_bytes():
    # runtime.py's bytes operations against CPython's bytes methods and codecs
    for _ in range(N):
        s = data()
        n = data(3)
        st, en = idx(), idx()
        for name in "find rfind index rindex count startswith endswith".split():
            same("bytes." + name, outcome(getattr(rt, "pys_bytes_" + name), bt(s), bt(n), st, en), bref(lambda: getattr(s, name)(n, st, en)), (s, n, st, en))
        same("bytes.contains", outcome(rt.pys_bytes_contains, bt(s), bt(n)), bref(lambda: n in s), (s, n))
        x = R.choice([0, 97, 255, 256, -1, R.randrange(256)])
        same("bytes.has", outcome(rt.pys_bytes_has, bt(s), x), bref(lambda: x in s), (s, x))
        r = data(3)
        same("bytes.replace", outcome(rt.pys_bytes_replace, bt(s), bt(n), bt(r)), bref(lambda: s.replace(n, r)), (s, n, r))
        k = R.choice([-1, 0, 1, 2])
        same("bytes.replace_count", outcome(rt.pys_bytes_replace_count, bt(s), bt(n), bt(r), k), bref(lambda: s.replace(n, r, k)), (s, n, r, k))
        cs = R.choice([None, data(3)])
        for name in "strip lstrip rstrip".split():
            same("bytes." + name, outcome(getattr(rt, "pys_bytes_" + name), bt(s), None if cs is None else bt(cs)), bref(lambda: getattr(s, name)(cs)), (s, cs))
        for name in "isdigit isalpha isalnum isspace isupper islower isascii upper lower swapcase capitalize hex".split():
            same("bytes." + name, outcome(getattr(rt, "pys_bytes_" + name), bt(s)), bref(getattr(s, name)), (s,))
        sep = R.choice([None, None, data(2)])
        m = R.choice([-1, -1, 0, 1, 2, 5])
        same("bytes.split", outcome(rt.pys_bytes_split, bt(s), None if sep is None else bt(sep), m), bref(lambda: s.split(sep, m)), (s, sep, m))
        same("bytes.rsplit", outcome(rt.pys_bytes_rsplit, bt(s), None if sep is None else bt(sep), m), bref(lambda: s.rsplit(sep, m)), (s, sep, m))
        keep = R.randrange(2)
        same("bytes.splitlines", outcome(rt.pys_bytes_splitlines, bt(s), keep), bref(lambda: s.splitlines(bool(keep))), (s, keep))
        for name in "partition rpartition removeprefix removesuffix".split():
            same("bytes." + name, outcome(getattr(rt, "pys_bytes_" + name), bt(s), bt(n)), bref(lambda: getattr(s, name)(n)), (s, n))
        parts = [data(4) for _ in range(R.randrange(4))]
        same("bytes.join", outcome(rt.pys_bytes_join, bt(n), [bt(p) for p in parts]), bref(lambda: n.join(parts)), (n, parts))
        width = R.randrange(-2, 16)
        fill = R.choice([None, data(1) or b"*", b"ab"])
        for name in "ljust rjust center".split():
            same("bytes." + name, outcome(getattr(rt, "pys_bytes_" + name), bt(s), width, None if fill is None else bt(fill)),
                 bref(lambda: getattr(s, name)(width) if fill is None else getattr(s, name)(width, fill)), (s, width, fill))
        z = R.choice([b"", b"+", b"-"]) + s
        same("bytes.zfill", outcome(rt.pys_bytes_zfill, bt(z), width), bref(lambda: z.zfill(width)), (z, width))
        h = "".join(R.choice("0123456789abcdefABCDEF  \tgx") for _ in range(R.randrange(9)))
        same("bytes.fromhex", outcome(rt.pys_bytes_fromhex, h), bref(lambda: bytes.fromhex(h)), (h,))
        xs = [R.choice([0, 65, 255, 256, -1, R.randrange(256)]) for _ in range(R.randrange(4))]
        same("bytes.from_list", outcome(rt.pys_bytes_from_list, xs), bref(lambda: bytes(xs)), (xs,))
        c = R.choice([-1, 0, 3])
        same("bytes.zeros", outcome(rt.pys_bytes_zeros, c), bref(lambda: bytes(c)), (c,))
        frm = data(4)
        to = bytes(R.choice(BYTES) for _ in range(len(frm) if R.randrange(6) else R.randrange(5)))
        same("bytes.maketrans", outcome(rt.pys_bytes_maketrans, bt(frm), bt(to)), bref(lambda: bytes.maketrans(frm, to)), (frm, to))
        tab = R.choice([None, bytes.maketrans(frm, to) if len(frm) == len(to) else bytes(range(256)),
                        bytes(R.randrange(256) for _ in range(256)), data(3)])
        dl = R.choice([None, b"", data(3)])
        same("bytes.translate", outcome(rt.pys_bytes_translate, bt(s), None if tab is None else bt(tab), None if dl is None else bt(dl)),
             bref(lambda: s.translate(tab) if dl is None else s.translate(tab, dl)), (s, tab, dl))
        hs = R.choice([None, ":", "-", "", "::", "é", "€", b":", b"\xff", b"\x00", b"", b"ab"])
        per = R.choice([1, 2, 3, -1, -2, -3, 0, 7, 2147483647, -2147483648, 2147483648, -2147483649])
        same("bytes.hex_sep", outcome(rt.pys_bytes_hex_sep, bt(s), None if hs is None else bt(hs) if isinstance(hs, bytes) else b(hs),
                                      1 if isinstance(hs, str) else 0, per),
             bref(lambda: s.hex(bytes_per_sep=per) if hs is None else s.hex(hs, per)), (s, hs, per))
        enc = R.choice(["utf-8", "UTF8", "latin-1", "iso-8859-1", "ascii", "us-ascii", "nope"])
        errs = R.choice(["strict", "replace", "ignore", "backslashreplace", "surrogateescape", "surrogatepass", "xmlcharrefreplace", "nope"])
        same("bytes.decode", outcome(rt.pys_bytes_decode, bt(s), enc, errs), bref(lambda: s.decode(enc, errs)), (s, enc, errs))
        t = "".join(R.choice("aé€\U0001d11e \udc80\udcff\ud800") for _ in range(R.randrange(6)))
        same("str.encode", outcome(rt.pys_str_encode, t.encode("utf-8", "surrogatepass").decode("latin-1"), enc, errs), bref(lambda: t.encode(enc, errs)), (t, enc, errs))


def num():
    k = R.randrange(4)
    if k == 0:
        return R.randrange(-30, 31)
    if k == 1:
        return R.randrange(-(1 << 20), 1 << 20)
    return R.randrange(-(1 << 62), 1 << 62)


def fits(r):
    return r[0] != "ok" or -MAXI - 1 <= r[1] <= MAXI


def fuzz_math():
    for _ in range(N):
        a, c = num(), num()
        q = R.randrange(3037000500 >> R.randrange(32))  # up to the root of 2**63: squares, where the float root can fall short
        for name, mine, ref, args in [
            ("gcd", rt.pys_m_gcd, math.gcd, (a, c)),
            ("lcm", rt.pys_m_lcm, math.lcm, (a, c)),
            ("isqrt", rt.pys_m_isqrt, math.isqrt, (a,)),
            ("isqrt", rt.pys_m_isqrt, math.isqrt, (q * q + R.choice([-1, 0, 1]),)),
            ("factorial", rt.pys_m_factorial, math.factorial, (R.randrange(-2, 21),)),
            ("comb", rt.pys_m_comb, math.comb, (R.randrange(-2, 70), R.randrange(-2, 40))),
            ("perm", rt.pys_m_perm, math.perm, (R.randrange(-2, 30), R.randrange(-2, 15))),
        ]:
            want = outcome(ref, *args)
            if fits(want):  # beyond 64 bits the compiled code raises OverflowError (the differential tests check it)
                same(name, outcome(mine, *args), want, args)
        xs = [real() for _ in range(R.randrange(12))]
        if R.randrange(3) == 0:  # cancellation: the items negated, some halved or one ulp off
            xs += [-x * R.choice([1.0, 0.5, 1.0000000000000002]) for x in xs]
            R.shuffle(xs)
        same("fsum", bits(outcome(rt.pys_m_fsum, xs)), bits(outcome(math.fsum, xs)), (xs,))
        start = real()
        same("sum-float", bits(outcome(rt.pys_sum_float, xs, start)), bits(outcome(sum, xs, start)), (xs, start))
        same("sum-int-start", bits(outcome(rt.pys_sum_float_int, xs, a)),
             bits(outcome(lambda: float(sum(xs, a)))), (xs, a))
        ns = [R.choice([0, 0, 0, 1, -1, a, c, num()]) for _ in range(R.randrange(9))]
        same("any", outcome(rt.pys_any, ns), ("ok", int(any(ns))), (ns,))
        same("all", outcome(rt.pys_all, ns), ("ok", int(all(ns))), (ns,))
        same("sum-ints-float", bits(outcome(rt.pys_sum_int_float, ns, start)), bits(outcome(sum, ns, start)), (ns, start))
        for name, mine, ref in [("degrees", rt.pys_m_degrees, math.degrees), ("radians", rt.pys_m_radians, math.radians)]:
            same(name, bits(outcome(mine, start)), bits(outcome(ref, start)), (start,))
        other, rel, ab = real(), real(), real()
        same("isclose", outcome(rt.pys_m_isclose, start, other, rel, ab),
             outcome(lambda: int(math.isclose(start, other, rel_tol=rel, abs_tol=ab))), (start, other, rel, ab))
        same("prod", bits(outcome(rt.pys_m_prod_float, xs, 1.5)), bits(outcome(lambda: math.prod(xs, start=1.5))), (xs,))
        ns = [R.randrange(-1000, 1001) for _ in range(R.randrange(7))]
        st = R.choice([1, -1, a])
        want = outcome(lambda: math.prod(ns, start=st))
        if fits(want):
            same("prod", outcome(rt.pys_m_prod_int, ns, st), want, (ns, st))


def wide():
    # an int for pow() and round(): the ends of the 64-bit range, small ones, anything between
    k = R.randrange(6)
    if k == 0:
        return R.choice([0, 1, -1, 2, -2, MAXI, -MAXI - 1, MAXI - 1, -MAXI, 1 << 62, -(1 << 62), 10**18, -(10**18),
                         5 * 10**18, -5 * 10**18, 5 * 10**18 + 1, -5 * 10**18 - 1])
    if k == 1:
        return R.randrange(-100, 101)
    if k == 2:
        return R.randrange(-MAXI - 1, MAXI + 1)
    return R.randrange(-(1 << R.randrange(1, 64)), 1 << R.randrange(1, 64))


def coords(n):
    # coordinates for hypot and dist: around one exponent, among the subnormals, or anything
    k = R.randrange(6)
    if k == 0:
        e = R.randrange(-1074, 1021)
        return [math.ldexp(R.random() - 0.5, e + R.randrange(-3, 4)) for _ in range(n)]
    if k == 1:
        return [math.ldexp(R.random() - 0.5, R.randrange(-1074, -1015)) for _ in range(n)]
    return [real() for _ in range(n)]


def fuzz_numeric():
    # hypot, dist and fma by their bits; pow(a, b, m), round(x, n) and the int sum where CPython's
    # result is a 64-bit int (past it the compiled code raises OverflowError)
    for _ in range(N):
        x, y, z = real(), real(), real()
        same("hypot", bits(outcome(rt.pys_m_hypot, x, y)), bits(outcome(math.hypot, x, y)), (x, y))
        n = R.randrange(9)
        p = coords(n)
        q = coords(n if R.randrange(10) else R.randrange(9))
        same("hypot-list", bits(outcome(rt.pys_m_hypot_list, p)), bits(outcome(math.hypot, *p)), (p,))
        same("dist", bits(outcome(rt.pys_m_dist, p, q)), bits(outcome(math.dist, p, q)), (p, q))
        if hasattr(math, "fma"):  # (Python 3.13)
            same("fma", bits(outcome(rt.pys_m_fma, x, y, z)), bits(outcome(math.fma, x, y, z)), (x, y, z))
        a, e, m = wide(), wide(), wide()
        same("idiv", bits(outcome(rt.pys_idiv, a, m)), bits(outcome(lambda: a / m)), (a, m))
        want = outcome(lambda: a // m)
        if not fits(want):  # MIN // -1 overflows, but MIN % -1 is zero.
            want = ("OverflowError", "integer result does not fit in 64 bits")
        same("floordiv", outcome(rt.pys_floordiv, a, m), want, (a, m))
        same("mod", outcome(rt.pys_mod, a, m), outcome(lambda: a % m), (a, m))
        same("bit_length", outcome(rt.pys_int_bit_length, a), outcome(int.bit_length, a), (a,))
        same("bit_count", outcome(rt.pys_int_bit_count, a), outcome(int.bit_count, a), (a,))
        if R.randrange(3) == 0:
            e = R.randrange(-5, 6)
        same("powmod", outcome(rt.pys_powmod, a, e, m), outcome(pow, a, e, m), (a, e, m))
        places = R.randrange(-22, 3)
        want = outcome(round, a, places)
        if fits(want):
            same("round-int", outcome(rt.pys_round_int, a, places), want, (a, places))
        ns = [wide() for _ in range(R.randrange(6))]
        if all(-MAXI - 1 <= t <= MAXI for t in itertools.accumulate(ns, initial=e)):
            same("sum-int", outcome(rt.pys_sum_int, ns, e), outcome(sum, ns, e), (ns, e))


def real():
    # a float for fsum and prod: specials, small ints (exact sums, ties), anything in range
    k = R.randrange(8)
    if k == 0:
        return R.choice([0.0, -0.0, 5e-324, 2.2250738585072014e-308, 1.7976931348623157e308, -1.7976931348623157e308,
                         1e16, 1.0, math.inf, -math.inf, math.nan])
    if k == 1:
        return float(R.randrange(-1000, 1001))
    if k == 2:
        return math.ldexp(R.random() - 0.5, R.randrange(-1074, 1025))
    return (R.random() - 0.5) * 2.0 ** R.randrange(-60, 60)


def bits(r):
    # a float outcome by its bits, so that a nan or a zero's sign compares
    return (r[0], r[1].hex()) if r[0] == "ok" else r


M64 = (1 << 64) - 1


def fnv(s):
    # the dict hash of runtime.c before it moved: FNV-1a, then h ^ h >> 29, over unsigned 64 bits
    h = 1469598103934665603
    for c in s.encode("latin-1"):
        h = ((h ^ c) * 1099511628211) & M64
    return h ^ h >> 29


def mix(k):
    h = k & M64
    h = ((h ^ h >> 30) * 0xBF58476D1CE4E5B9) & M64
    return h ^ h >> 31


def conv_float():
    # a float for the conversions to an int: every bit pattern, halves, and the ends of the ranges
    # where a float is whole (2**52, 2**53) and where an int has 64 bits (2**63)
    k = R.randrange(7)
    if k == 0:
        return struct.unpack("<d", struct.pack("<Q", R.getrandbits(64)))[0]
    if k == 1:
        return R.choice([0.0, -0.0, 0.5, -0.5, 1.5, 2.5, -1.5, -2.5, 0.49999999999999994, -0.49999999999999994, math.inf, -math.inf, math.nan,
                         2.0**52, 2.0**52 + 1, 2.0**53, -(2.0**53), 2.0**63, -(2.0**63), 2.0**63 - 1024, -(2.0**63) - 2048, 2.0**64, 5e-324])
    if k == 2:
        return (R.randrange(-(10**6), 10**6) + 0.5) * R.choice([1.0, 2.0 ** R.randrange(12)])
    if k == 3:
        return float(R.getrandbits(R.randrange(1, 66))) * R.choice([1, -1])
    if k == 4:
        return math.ldexp(R.random() + 0.5, R.randrange(48, 66)) * R.choice([1, -1])
    if k == 5:
        return float(R.randrange(-(1 << 54), 1 << 54)) + R.choice([0.0, 0.25, 0.5, 0.75])
    return R.uniform(-1000.0, 1000.0)


def fuzz_float_int():
    # int(x), round(x), math.floor, math.ceil and math.trunc of a float, whose result past 64
    # bits is OverflowError here; x / y; and the exact order of an int and a float
    past = ("OverflowError", "float too large for a 64-bit int")
    for _ in range(N):
        x = conv_float()
        for name, f, g in (("f2i", rt.pys_f2i, int), ("round", rt.pys_round, round), ("floor", rt.pys_floor, math.floor),
                           ("ceil", rt.pys_ceil, math.ceil), ("trunc", rt.pys_m_trunc, math.trunc)):
            want = outcome(g, x)
            if not fits(want):
                want = past
            same(name, outcome(f, x), want, (x,))
        y = conv_float()
        same("fdiv", bits(outcome(rt.pys_fdiv, x, y)), bits(outcome(lambda: x / y)), (x, y))
        i = wide() if R.randrange(3) else int(x) + R.randrange(-2, 3) if math.isfinite(x) and abs(x) < 2.0**63 else wide()
        i = max(-MAXI - 1, min(MAXI, i))
        same("cmp_if", rt.pys_cmp_if(i, x), 2 if x != x else -1 if i < x else 1 if i > x else 0, (i, x))
        same("isfinite", rt.pys_m_isfinite(x), int(math.isfinite(x)), (x,))
        same("isinf", rt.pys_m_isinf(x), int(math.isinf(x)), (x,))
        same("isnan", rt.pys_m_isnan(x), int(math.isnan(x)), (x,))
        same("copysign", rt.pys_m_copysign(x, y).hex(), math.copysign(x, y).hex(), (x, y))


def check_shifts():
    for n in [-MAXI - 1, -1, *range(66), MAXI]:
        operands = {0, 1, -1, MAXI, -MAXI - 1}
        if 0 <= n < 64:
            lo, hi = (-MAXI - 1) >> n, MAXI >> n
            operands.update((lo - 1, lo, lo + 1, hi - 1, hi, hi + 1))
        for a in operands:
            if -MAXI - 1 <= a <= MAXI:
                # Beyond 63 bits only zero fits; cap the reference shift to avoid a giant int.
                want = outcome(lambda: a << min(n, 64))
                if not fits(want):
                    want = ("OverflowError", "integer result does not fit in 64 bits")
                same("shl", outcome(rt.pys_shl, a, n), want, (a, n))
                same("shr", outcome(rt.pys_shr, a, n), outcome(lambda: a >> n), (a, n))


def fuzz_hash():
    for _ in range(N):
        k = R.choice([num(), R.randrange(-(1 << 63), 1 << 63)])
        same("hash_int", rt.pys_hash_int(k) & M64, mix(k), (k,))
        s = b(text(WIDE + ASCII, 10))
        same("hash_str", rt.pys_hash_str(s) & M64, fnv(s), (s,))


def fmt_float(m, ty, prec, alt):
    # runtime.c's pys_fmt_float (snprintf, or Ryu) writes what CPython's float formatting writes for |x|
    return format(m, ("#" if alt else "") + (f".{prec}" if prec >= 0 else "") + (chr(ty) if ty else ""))


rt.pys_fmt_float = fmt_float


def text_len(s):
    # runtime.c's pys_text_len, which ulen calls: the characters as u8char (uchar) reads them
    n, i, k = len(s), 0, 0
    while i < n:
        i += 1 if ord(s[i]) < 128 else rt.uchar(s, i, n) & 7
        k += 1
    return k


rt.pys_text_len = text_len


def spec():
    # a random format spec, mostly well-formed
    parts = []
    if R.randrange(3) == 0:
        parts.append(R.choice(["", "*", "0", "é", "€", " "]) + R.choice("<>=^"))
    for opts, k in [("+- ", 4), ("z", 6), ("#", 4), ("0", 4)]:
        if R.randrange(k) == 0:
            parts.append(R.choice(opts))
    if R.randrange(2) == 0:
        parts.append(str(R.choice([0, 1, 5, 12, 30])))
    if R.randrange(5) == 0:
        parts.append(R.choice(",_"))
    if R.randrange(3) == 0:
        parts.append("." + str(R.choice([0, 1, 3, 10, 17])))
    if R.randrange(2) == 0:
        parts.append(R.choice("bcdoxXneEfFgGs%a"))
    elif R.randrange(8) == 0:
        parts.append(R.choice(["\x00", " ", "\t", "é", "𝄞", "\x7f"]))  # types CPython escapes or rejects
    s = "".join(parts)
    if R.randrange(40) == 0:
        s = s + R.choice(["x", "1", ".", ",,", "_,", "a" * 600 + "x", "<\x005"])  # malformed, long, NUL inside
    return s


def fuzz_format():
    for _ in range(N):
        sp = spec()
        v = R.choice([0, 1, -1, 7, -42, 255, 1000000, R.randrange(-(1 << 63), 1 << 63), 0x10FFFF + 1])
        for name, mine, cpy in [
            ("format_int", lambda: rt.pys_format_int(v, 0, b(sp)), lambda: format(v, sp)),
            ("format_bool", lambda: rt.pys_format_int(int(v != 0), 1, b(sp)), lambda: format(v != 0, sp)),
        ]:
            if name == "format_bool" and sp == "":
                continue  # format(True, "") is str(True), decided before pys_format_int
            same(name, outcome(mine), ref(cpy), (v, sp))
        x = R.choice([0.0, -0.0, 1.5, -2.5, 1e16, 1.0e-5, 123456.789, -0.0004, float("inf"), float("nan"), R.uniform(-1e6, 1e6)])
        same("format_float", outcome(rt.pys_format_float, x, b(sp)), ref(lambda: format(x, sp)), (x, sp))
        t = text(WIDE, 6)
        same("format_str", outcome(rt.pys_format_str, b(t), b(sp)), ref(lambda: format(t, sp)), (t, sp))


def fuzz_search():
    # long needles in repetitive text, where search() gives up its candidate checks for memmem;
    # first a needle right after each number of failed candidates, around the cutover
    for pre in range(40):
        h = "a" * pre + "a" * 10 + "b" + "ab" * 3
        n = "a" * 10 + "b"
        same("find", outcome(rt.pys_str_find, h, n, 0, len(h)), outcome(h.find, n), (h, n))
        same("count", outcome(rt.pys_str_count, h, n, 0, len(h)), outcome(h.count, n), (h, n))
    for _ in range(N // 10):
        unit = "".join(R.choice("ab") for _ in range(R.randrange(1, 4)))
        h = unit * R.randrange(1, 120) + text("ab", 6)
        n = R.choice([h[R.randrange(len(h)) :][: R.randrange(1, 40)], "a" * R.randrange(5, 30) + "b", text("ab", 20)])
        st, en = R.choice([0, 0, 3, -50]), R.choice([len(h), len(h), len(h) - 2, 200])
        for name, mine, ref in [
            ("find", rt.pys_str_find, lambda: h.find(n, st, en)),
            ("rfind", rt.pys_str_rfind, lambda: h.rfind(n, st, en)),
            ("count", rt.pys_str_count, lambda: h.count(n, st, en)),
        ]:
            same(name, outcome(mine, h, n, st, en), outcome(ref), (h, n, st, en))
        same("split", outcome(rt.pys_str_split, h, n, -1), outcome(h.split, n), (h, n))
        same("replace", outcome(rt.pys_str_replace, h, n, "X"), outcome(h.replace, n, "X"), (h, n))
    # HTML-like text: a candidate at each "<", most of them failing, between many occurrences, so
    # count, replace and split go on with memmem once the failures turn out dense
    tags = ["<span>", "</span>", "<b>", "</b>", "<br>", "x", "yz", " "]
    for _ in range(N // 10):
        h = "".join(R.choice(tags) for _ in range(R.randrange(1, 80)))
        n = R.choice(["</span>", "</b>", "<", "</", "span>", "<b>x", "</span><", "<i>"])
        st, en = R.choice([0, 0, 5, -30]), R.choice([len(h), len(h), len(h) - 3, 100])
        for name, mine, ref in [
            ("find", rt.pys_str_find, lambda: h.find(n, st, en)),
            ("count", rt.pys_str_count, lambda: h.count(n, st, en)),
        ]:
            same(name, outcome(mine, h, n, st, en), outcome(ref), (h, n, st, en))
        m = R.choice([-1, -1, 3])
        same("split", outcome(rt.pys_str_split, h, n, m), outcome(h.split, n, m), (h, n, m))
        same("replace", outcome(rt.pys_str_replace, h, n, "X"), outcome(h.replace, n, "X"), (h, n))
    # dense failing candidates first, so memmem takes over at once for a stretch of d bytes
    # (reach()): an occurrence at each place around its end, alone or d bytes after another, at
    # the end of the text or not
    for n in ["</p>", "</span>", "</"]:
        d = rt.reach(0, 0, len(n))  # (so the cases follow its formula)
        for head in ["<x" * 3, "<" * 40]:
            for p in range(d - 40, d + 10):
                for h in [head + "y" * p + n, head + "y" * 5 + n + "y" * p + n + "<y" * 3, head + "y" * p + n + "y" * 9 + n]:
                    same("find", outcome(rt.pys_str_find, h, n, 0, len(h)), outcome(h.find, n), (h, n))
                    same("count", outcome(rt.pys_str_count, h, n, 0, len(h)), outcome(h.count, n), (h, n))
                    same("split", outcome(rt.pys_str_split, h, n, -1), outcome(h.split, n), (h, n))
                    same("replace", outcome(rt.pys_str_replace, h, n, "X"), outcome(h.replace, n, "X"), (h, n))
    # longer text: runs of dense failing candidates and of sparse ones, so memmem's stretches (300
    # bytes and more) end at random places, often around an occurrence, and the candidates are
    # counted again; runs of a byte and single ones, for count's two ways with one byte
    for _ in range(N // 40):
        n = R.choice(["</p>", "</", "<p>x", "</table-of-contents>", "<", "y"])
        parts = []
        for _ in range(R.randrange(1, 6)):
            parts.append(R.choice(["<x", "<p", "<", "</", "y"]) * R.randrange(60))
            parts.append(R.choice(["y", "z", "yz<"]) * R.randrange(400))
            parts.append(R.choice([n, n, n[:-1], "<"]))
        h = "".join(parts)
        st, en = R.choice([0, 0, R.randrange(300)]), R.choice([len(h), len(h), R.randrange(len(h) + 1)])
        for name, mine, ref in [
            ("find", rt.pys_str_find, lambda: h.find(n, st, en)),
            ("count", rt.pys_str_count, lambda: h.count(n, st, en)),
        ]:
            same(name, outcome(mine, h, n, st, en), outcome(ref), (h, n, st, en))
        same("contains", outcome(rt.pys_str_contains, h, n), outcome(lambda: int(n in h)), (h, n))
        m = R.choice([-1, -1, 5])
        same("split", outcome(rt.pys_str_split, h, n, m), outcome(h.split, n, m), (h, n, m))
        same("replace", outcome(rt.pys_str_replace, h, n, "X"), outcome(h.replace, n, "X"), (h, n))


def fuzz_replace():
    # replace past the 65,536 occurrences replaced() lists before it weighs them: dense ones
    # counted and copied as they are found, sparse ones listed on, and texts that change between
    # the two, with a count that stops before, at or after each place the way changes
    def check(h, n, r, k):
        h, n, r = b(h), b(n), b(r)
        same("replace", outcome(rt.pys_str_replace_count, h, n, r, k), outcome(h.replace, n, r, k), (len(h), n, r, k))

    cap = 65536
    for g in [0, 1, 15, 16, 17]:  # an occurrence every g + 1 bytes: dense up to 16
        for i, k in enumerate([-1, cap - 1, cap, cap + 1, 2 * cap + 3]):
            check(("*" + "y" * g) * (cap + 40) + "end", "*", ["", "_", ";;", "é", "XYZ"][(i + g) % 5], k)
    check("*" * cap, "*", "_", -1)  # exactly the listed ones, none left to count
    check("*" * (cap + 2), "*", "_", cap + 1)  # one more left than count lets go
    for n, unit in [("ab", "aba"), ("</p>", "</p><"), ("aab", "aaab")]:  # failed candidates
        for k in [-1, cap + 5]:
            check(unit * (cap + 40), n, "_", k)
    check("a," * (cap + 7), ",", ";", -1)
    # dense, but failed candidates costlier than the bytes they pass, so the rest is listed (DNA's
    # "CA" in ACG, and a run of the needle's first byte after a dense prefix), and cheap ones
    for k, n in [(3, "CA"), (4, "GA"), (2, "CAC")]:
        dna = "".join(R.choice("ACGT"[:k]) for _ in range(1100000))
        for c in [-1, cap + 1, R.randrange(cap, dna.count(n) + 2)]:
            check(dna, n, R.choice(["", "#", "<n>"]), c)
    for n in ["ab", "a" * 15 + "b", "é" * 3 + "è"]:
        for c in [-1, cap + 1, 70000, 70001]:
            check(n * 70000 + n[0] * 30000 + n, n, "_", c)
    for n, unit in [("aa", "a"), ("aaa", "a"), ("abab", "ab")]:  # needles that overlap themselves
        for c in [-1, cap + 1]:
            check(unit * (3 * cap * len(n) + 7), n, "-", c)
    for c in [-1, cap + 1, 140000]:
        check("ab" * 70000 + ("a" * 40 + "ab") * 300 + "ab" * 100000, "ab", "Z", c)
        check(("ab" + "y" * 13 + "ab" + "y" * 12 + "a") * 40000, "ab", "", c)
    for n, r in [("ab", "X"), ("é", ""), ("</p>", "\n"), ("aa", "b"), ("𝄞", "→")]:
        for k in [-1, cap + 1]:
            check((n + "y") * (cap + 40) + n[:-1], n, r, k)
    for _ in range(max(2, N // 2500)):
        n = R.choice(["*", ",", "ab", "\r\n", "é", "𝄞", "</p>", "aa"])
        r = R.choice(["", "_", ";;", "XYZ", "é", "\n", n])
        parts = []
        while len(parts) < 3 or R.randrange(3):
            gap = R.choice(["", "y", "é", "yz" * R.randrange(8), "y" * R.randrange(17, 80), "a", "a" * R.randrange(40)])
            parts.append((n + gap) * R.randrange(1, 70000))
        h = "".join(parts)
        k = R.choice([-1, -1, cap - 1, cap, cap + 1, 3 * cap, R.randrange(h.count(n) + 2)])
        check(h, n, r, k)


# Pieces of raw text: ASCII, whole UTF-8 characters, and bytes that begin no character as
# runtime.c's u8char reads them (a lone continuation, an overlong lead, a cut sequence, an
# overlong form, one above U+10FFFF), which Pystachy reads unchecked from files and stdin. CPython
# decodes such bytes with surrogateescape to one lone surrogate each, as its stdin does in UTF-8
# mode. No encoded surrogate (ED A0..BF): Pystachy reads those as one character, CPython as three
PIECES = [b"a", b"Z", b" ", b"\t", b"0", "é".encode(), "€".encode(), "𝄞".encode(), b"\x80", b"\xbf", b"\xc1\xbf",
          b"\xc0\xaf", b"\xe2\x82", b"\xf0\x9f\x98", b"\xe0\x80\xaf", b"\xf4\x90\x80\x80", b"\xf5", b"\xff", "\ud7ff".encode()]


CASE_PIECES = [x.encode() for x in "\u03a3 \u03c3 \u00df \u00e9 \u00c9 \u01c5 \u0130 \ufb03 \u0301 A b '".split(" ")] + [b" "]


def raw(n=8):
    return b"".join(R.choice(PIECES) for _ in range(R.randrange(n + 1)))


def esc(r):
    # CPython's str of raw bytes r
    return r.decode("utf-8", "surrogateescape")


def ref_raw(f):
    # CPython's outcome, with the text of its result or message as the bytes it writes. A byte
    # that begins no character is its own code point in Pystachy (ord() of it), U+DC00 + it in
    # CPython: an unknown presentation type's message shows that code point
    r = outcome(f)
    if not isinstance(r[1], str):
        return r
    return (r[0], re.sub(r"code '\\xdc([89a-f][0-9a-f])'", r"code '\\x\1'", r[1]).encode("utf-8", "surrogateescape").decode("latin-1"))


def fuzz_malformed():
    # widths, precision, fill characters, zfill, expandtabs and presentation types count
    # characters as len() does (#29)
    for _ in range(N):
        r = raw()
        s = r.decode("latin-1")
        c = esc(r)
        width = R.randrange(-2, 12)
        f = R.choice([None, b"*", "é".encode(), b"\x80", b"\xc1", b"\xe2\x82", b"ab"])
        for name in "ljust rjust center".split():
            same(name, outcome(getattr(rt, "pys_str_" + name), s, width, f.decode("latin-1") if f is not None else None),
                 ref_raw(lambda: getattr(c, name)(width, esc(f) if f is not None else " ")), (r, width, f))
        same("zfill", outcome(rt.pys_str_zfill, s, width), ref_raw(lambda: c.zfill(width)), (r, width))
        ts = R.choice([0, 1, 4, 8])
        same("expandtabs", outcome(rt.pys_str_expandtabs, s, ts), ref_raw(lambda: c.expandtabs(ts)), (r, ts))
        sp = spec()
        same("format_str", outcome(rt.pys_format_str, s, b(sp)), ref_raw(lambda: format(c, sp)), (r, sp))
        rs = raw(3)  # a spec of raw bytes: a fill, a type, or neither
        same("format_int", outcome(lambda: rt.pys_format_int(5, 0, rs.decode("latin-1"))), ref_raw(lambda: format(5, esc(rs))), (rs,))
        same("format_str", outcome(rt.pys_format_str, s, rs.decode("latin-1")), ref_raw(lambda: format(c, esc(rs))), (r, rs))


def ascii_raw(r):
    # Independently decode one UTF-8 character through CPython's codec, accepting encoded
    # surrogates. Where no character starts, runtime.c's u8char treats the byte as its code
    # point. ascii() transforms repr's non-ASCII only: quotes, controls and backslashes stay.
    out = []
    i = 0
    while i < len(r):
        c = chr(r[i])
        n = 1
        if r[i] >= 128:
            for k in (2, 3, 4):
                try:
                    decoded = r[i : i + k].decode("utf-8", "surrogatepass")
                except UnicodeDecodeError:
                    continue
                if len(decoded) == 1:
                    c, n = decoded, k
                    break
        out.append(c.encode("ascii", "backslashreplace").decode("ascii"))
        i += n
    return "".join(out)


def fuzz_ascii():
    # Raw repr bytes include every escape width, valid surrogate sequences, overlong and
    # truncated sequences, invalid continuations, NULs, and runs with no escaping required.
    boundaries = [0x7F, 0x80, 0xFF, 0x100, 0x7FF, 0x800, 0xD7FF, 0xD800, 0xDBFF,
                  0xDC00, 0xDCFF, 0xDFFF, 0xE000, 0xFFFF, 0x10000, 0x10FFFF]
    pieces = PIECES + [b"", b"'\"\\\x00\n", b"ascii" * 32]
    for cp in boundaries:
        char = chr(cp).encode("utf-8", "surrogatepass")
        pieces.extend([char, char[:-1], char[:1] + b"x" + char[2:]])
    edges = pieces + [bytes([c]) for c in range(256)] + [bytes(range(256))]
    for r in edges:
        same("ascii-raw", outcome(rt.pys_ascii, bt(r)), ("ok", ascii_raw(r)), (r,))
    for _ in range(N):
        for r in [b"".join(R.choice(pieces) for _ in range(R.randrange(9))),
                  bytes(R.randrange(256) for _ in range(R.randrange(25)))]:
            same("ascii-raw", outcome(rt.pys_ascii, bt(r)), ("ok", ascii_raw(r)), (r,))


def fuzz_path():
    # os.path's string functions against posixpath's, which os.path is on POSIX: paths of
    # slashes, dots, names and "~", also of non-ASCII characters. abspath() and relpath() take
    # the working directory from CPython here, as they take runtime.c's when compiled
    rt.pys_getcwd = lambda: b(os.getcwd())
    parts = ["/", "/", ".", ".", "..", "a", "b.c", "é", "€", "𝄞", "~", " ", "//", "x.y.z", ".h"]

    def path():
        return "".join(R.choice(parts) for _ in range(R.randrange(9)))

    def strs(v):
        # a CPython result as runtime.py gives it: strs as Pystachy strs, a bool as an int
        return tuple(b(x) for x in v) if isinstance(v, tuple) else b(v) if isinstance(v, str) else int(v)

    def want(f, *a):
        r = outcome(f, *a)
        return (r[0], strs(r[1])) if r[0] == "ok" else r

    for _ in range(N):
        p, q = path(), path()
        for name in "basename dirname split splitext isabs normpath abspath".split():
            same("path." + name, outcome(getattr(rt, "pys_path_" + name), b(p)), want(getattr(posixpath, name), p), (p,))
        same("path.relpath", outcome(rt.pys_path_relpath, b(p), b(q)), want(posixpath.relpath, p, q), (p, q))
        same("path.join", outcome(rt.pys_path_join, b(p), b(q)), want(posixpath.join, p, q), (p, q))
        m = [path() for _ in range(R.randrange(4))] + [p + q for _ in range(R.randrange(2))]
        same("path.commonprefix", outcome(rt.pys_path_commonprefix, [b(x) for x in m]), want(posixpath.commonprefix, m), (m,))


def fuzz_int_text():
    # str(int) against CPython's, and int(str, base) against CPython's where its result fits in
    # 64 bits: past them runtime.py raises OverflowError, once the str is found to be an int.
    # The two steps that runtime.c keeps are CPython's here: the ASCII form of a str with other
    # characters (a space for each Unicode space, a decimal digit's ASCII digit, and "?" for
    # another character, where the text ends) and the ValueError, with 200 characters of the repr
    def num_ascii(s):
        out = ""
        for ch in u(s):
            d = unicodedata.decimal(ch, -1)
            out += ch if ord(ch) < 128 else " " if ch.isspace() else str(d) if d >= 0 else "?"
            if out[-1] == "?" and ch != "?":
                break
        return out

    def badlit(s, base):
        raise ValueError(b("invalid literal for int() with base %d: %.200s" % (base, repr(u(s)))))

    rt.pys_num_ascii = num_ascii
    rt.pys_int_badlit = badlit

    def want(s, base):
        r = outcome(int, u(s), base)
        if r[0] == "ok" and not fits(r):
            return ("OverflowError", "int() result does not fit in 64 bits")
        return (r[0], b(r[1])) if isinstance(r[1], str) else r

    def spell(v, base):
        n, out = abs(v), ""
        while n or not out:
            out = "0123456789abcdefghijklmnopqrstuvwxyz"[n % base] + out
            n //= base
        return ("-" if v < 0 else "") + out

    edge = [0, MAXI, MAXI - 1, -MAXI, -MAXI - 1, MAXI // 10, MAXI // 10 + 1]
    for k in range(64):
        edge += [10**k, 10**k - 1, 10**k + 1, -(10**k), 1 - 10**k, 1 << k, (1 << k) - 1, -(1 << k), -(1 << k) - 1]
    edge = [v for v in edge if -MAXI - 1 <= v <= MAXI]
    for v in edge + [R.randrange(-(10 ** R.randrange(1, 20)), 10 ** R.randrange(1, 20)) for _ in range(4 * N)]:
        if -MAXI - 1 <= v <= MAXI:
            same("str-int", outcome(rt.pys_str_int, v), ("ok", str(v)), (v,))
    # the values around the 64-bit limits in every base: where the last digit that fits is found
    for base in range(2, 37):
        pre = {2: "0b", 8: "0o", 16: "0x"}.get(base, "")
        for v in [MAXI, MAXI + 1, MAXI + 2, MAXI - 1, -MAXI - 1, -MAXI - 2, -MAXI, MAXI * base, MAXI * base + base - 1, (MAXI + 1) * base,
                  (MAXI + 1) // base, (MAXI + 1) // base * base, 0, 1, base - 1, base, 1 << 64, (1 << 64) - 1, -(1 << 64)]:
            d = spell(abs(v), base)
            forms = [spell(v, base), spell(v, base).upper(), "+" + d, " " + spell(v, base) + "\n", "00000" + d]
            if pre:
                forms += [pre + d, "-" + pre + d, pre.upper() + "_" + d, pre + "__" + d, pre, pre + "_"]
            for t in forms:
                for given in [base, 0, 10, 36]:
                    same("int-str", outcome(rt.pys_int_str, t, given), want(t, given), (t, given))
    # the syntax: signs, prefixes, single underscores, whitespace, a NUL, and other characters
    alphas = ["0123456789 _+-xXoObBaAfFzZ\t\n\x0b\x0c\r\x1c\x00.e", "0123456789_ ", "01_ -+xob",
              "0123456789 _+-\u0660\u0669\u00a0\u2003\u00e9\uff11\U0001d7ce\U0001d7d9"]
    for i in range(8 * N):
        t = b("".join(R.choice(alphas[i % 4]) for _ in range(R.randrange(9 if i % 3 else 24))))
        base = R.choice([10, 10, 10, 0, 0, 2, 8, 16, 36, 1, -1, 37, 3, 11, 35, R.randrange(-3, 40)])
        same("int-str", outcome(rt.pys_int_str, t, base), want(t, base), (t, base))
    # CPython's limit of 4300 digits: it counts digits alone, in a base that is no power of two,
    # after the syntax is checked, but before a NUL ends the text
    z = "0" * 4300
    for t, base in [(z[1:] + "7", 10), (z + "7", 10), (z + "1", 16), ("0x" + z + "1", 0), ("0b" + z, 0), (z + "0", 32), ("-" + z[1:] + "_9", 10),
                    (" " + z[1:] + "1 ", 10), (z + "7", 3), (z + "7x", 10), (z + "7\x00", 10), (z + "7 \x00", 10), (z + "7 \x00 ", 10), (z + "_", 10),
                    ("1" * 4301, 10), ("1" * 4300, 10), ("1" * 4301, 2), ("0_" * 4301 + "0", 10), (z + "0", 0), (z + "1", 0), (z[1:] + "1", 0),
                    (z + "\u0660", 8), ("9" * 30, 10), ("-" + "9" * 30, 10), ("0" + "9" * 30, 0), ("x" * 300, 10), ("\u00e9" * 300, 10), ("'" * 300, 10),
                    ("12\x00", 10), ("12\x0034", 10), ("\x00", 10), ("", 10), ("_1", 10), ("1_", 10), ("1__2", 10), ("1_2", 10), ("0_7", 0), ("0_0", 0),
                    ("00", 0), ("0", 0), ("-0", 0), ("+0_0", 0), ("0x_f", 0), ("0x_f", 16), ("0_x_f", 16), ("0x", 16), ("0x", 36), ("0b2", 0), ("0b1", 36)]:
        same("int-str", outcome(rt.pys_int_str, b(t), base), want(b(t), base), (t[:30], len(t), base))


if ONLY in ("", "memory", "lists"):
    fuzz_lists()
    fuzz_list_search()
    fuzz_str_memory()
    check_model()
if ONLY in ("", "memory", "sets"):
    fuzz_sets()
if ONLY in ("", "memory", "dicts"):
    fuzz_dicts()
if ONLY in ("", "memory", "walks"):
    fuzz_walks()
if ONLY != "":
    print(f"{cases} cases, {fails} failed")
    sys.exit(1 if fails else 0)
fuzz_str()
fuzz_path()
fuzz_int_text()
fuzz_unicode_classification()
fuzz_unicode_case()
fuzz_replace()
fuzz_bytes()
fuzz_search()
fuzz_math()
fuzz_numeric()
fuzz_hash()
check_shifts()
fuzz_float_int()
fuzz_format()
fuzz_malformed()
fuzz_ascii()
print(f"{cases} cases, {fails} failed")
sys.exit(1 if fails else 0)
