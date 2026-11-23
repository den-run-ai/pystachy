"""tools/rtcheck.py finds seeded bugs in runtime.py's memory code.

Each mutant is one change to the list, str, set or dict code that a compiled runtime would
run without complaint: a write past a block, a stale slot that the collector would scan, a
read that breaks an alias rule, arithmetic that overflows unchecked, an identity that a
companion loses, a set whose table is no longer CPython's slot for slot, a dict whose
entries are no longer CPython's items. The heap model of
tools/rt_cpython/rt_heap.py must report every one of them at the size this test runs, and
nothing in the code as it is.
"""
import concurrent.futures
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROUNDS = "600"

# (what the fault is, the text of runtime.py that it replaces, the replacement)
SET_MUTANTS = [
    ("an insertion's probe looks at one slot less beside the first",
     '        free = -1\n        again = False\n        while not again:\n            probes = 9 if i + 9 <= mask else 0',
     '        free = -1\n        again = False\n        while not again:\n            probes = 8 if i + 9 <= mask else 0'),
    ("a lookup's probe looks at one slot less beside the first",
     '        perturb = h\n        again = False\n        while not again:\n            probes = 9 if i + 9 <= mask else 0',
     '        perturb = h\n        again = False\n        while not again:\n            probes = 8 if i + 9 <= mask else 0'),
    ("an insertion that fills 3/5 of the table does not rebuild it",
     '                        if fill * 5 >= mask * 3:\n                            set_resize(s, set_grown(s))\n                        return',
     '                        if fill * 5 >= mask * 4:\n                            set_resize(s, set_grown(s))\n                        return'),
    ("a discard leaves the element's hash",
     '    _rt.put(_rt.getp(s, "Set.keys"), j, 1)\n    _rt.put(hs, j, -1)\n    _rt.set(s, "Set.len", _rt.get(s, "Set.len") - 1)\n    return True',
     '    _rt.put(_rt.getp(s, "Set.keys"), j, 1)\n    _rt.set(s, "Set.len", _rt.get(s, "Set.len") - 1)\n    return True'),
    ("a rebuilt table is sized for twice its elements",
     '    return n * 2 if n > 50000 else n * 4',
     '    return n * 2'),
    ("a merge's copy of a table forgets its Mpz words",
     '            _rt.cpy(kb, _rt.getp(o, "Set.kb"), size * 8)\n            _rt.setp(s, "Set.kb", kb)\n',
     '            _rt.cpy(kb, _rt.getp(o, "Set.kb"), size * 8)\n'),
    ("a rebuild drops the Mpz of an element past 64 bits",
     '            if k <= -9223372036854775807 and _rt.word(kb, i) != 0:\n                set_big_put(s, e, _rt.ptr(_rt.word(kb, i)))\n',
     ''),
    ("the sentinel of an element past 64 bits ignores its hash",
     '    return -9223372036854775807 if h == -4 else -9223372036854775807 - 1',
     '    return -9223372036854775807 - 1'),
    ("an int's hash is -1",
     '    if v < 0:\n        h = -h\n    return -2 if h == -1 else h',
     '    if v < 0:\n        h = -h\n    return h'),
    ("a lookup goes on in the table that an __eq__ replaced",
     '                        eq = pys_rt_set_eq(s, j, x, k, 0)\n                        if eq < 0:\n                            again = True\n                            break\n                        if eq != 0:',
     '                        eq = pys_rt_set_eq(s, j, x, k, 0)\n                        if eq > 0:'),
    ("s & o walks the first set, not the smaller",
     '        t = a\n        a = b\n        b = t\n    i = 0\n    while i <= _rt.get(b, "Set.mask"):\n        k = _rt.word(_rt.getp(b, "Set.keys"), i)',
     '        pass\n    i = 0\n    while i <= _rt.get(b, "Set.mask"):\n        k = _rt.word(_rt.getp(b, "Set.keys"), i)'),
    ("an insertion does not reuse the dummy it passed",
     '                    if _rt.word(keys, j) != 0:\n                        free = j\n                    else:',
     '                    if _rt.word(keys, j) != 0:\n                        pass\n                    else:'),
    ("a difference keeps its dummies",
     '    if _rt.get(s, "Set.fill") - _rt.get(s, "Set.len") > _rt.lshr(_rt.get(s, "Set.mask"), 2):',
     '    if _rt.get(s, "Set.fill") - _rt.get(s, "Set.len") > _rt.get(s, "Set.mask"):'),
    ("list(s) gives an element past 64 bits its set's sentinel",
     '                _rt.put(items, n, -9223372036854775807 - 1)\n            n += 1',
     '                _rt.put(items, n, _rt.word(keys, i))\n            n += 1'),
    ("s ^= d adds a key it has just removed",
     '            if not set_discard(s, k, h):\n                set_add(s, k, h)\n        e += 1',
     '            set_discard(s, k, h)\n            set_add(s, k, h)\n        e += 1'),
    ("s.update(d) does not size the table for the dict's keys",
     '        set_resize(s, (_rt.get(s, "Set.len") + _rt.get(d, "Dict.len")) * 2)\n',
     '        pass\n'),
    ("the Mpz words of a table are one short",
     '        _rt.setp(s, "Set.kb", pys_alloc((_rt.get(s, "Set.mask") + 1) * 8))',
     '        _rt.setp(s, "Set.kb", pys_alloc(_rt.get(s, "Set.mask") * 8))'),
    ("a new table's last slot keeps hash 0",
     '    _rt.fill(hs, 255, size * 8)\n',
     '    _rt.fill(hs, 255, size * 8 - 8)\n'),
    ("a merge into a table with elements skips the last slot",
     '    while i <= _rt.get(o, "Set.mask"):  # (an __eq__ may change o: its table is read again)',
     '    while i < _rt.get(o, "Set.mask"):  # (an __eq__ may change o: its table is read again)'),
]
DICT_MUTANTS = [
    ("a deleted entry keeps its key",
     '    _rt.put(_rt.getp(d, "Dict.keys"), e, 0)\n    _rt.put(_rt.getp(d, "Dict.vals"), e, 0)\n    dict_val_clear(d, e)',
     '    _rt.put(_rt.getp(d, "Dict.vals"), e, 0)\n    dict_val_clear(d, e)'),
    ("a deleted entry's slot becomes empty, which ends the probes of the keys behind it",
     '    _rt.put_i32(idx, i, -1)\n    dict_hole(d, e)\n    return v',
     '    _rt.put_i32(idx, i, 0)\n    dict_hole(d, e)\n    return v'),
    ("a table is full one entry late",
     '    used = _rt.wrap_add(_rt.wrap_mul(_rt.get(d, "Dict.n") + _rt.get(d, "Dict.cut"), 3), 2)',
     '    used = _rt.wrap_mul(_rt.get(d, "Dict.n") + _rt.get(d, "Dict.cut"), 3)'),
    ("a str key is found only as itself",
     '            if x == k or same_str(x, k):\n                return i\n        p = _rt.lshr(p, 5)\n        i = dict_step(i, p, m)\n    return -1  # (not reached)\n\n\n@_rt.inline\n@_rt.unchecked\ndef pys_rt_dfind(',
     '            if x == k:\n                return i\n        p = _rt.lshr(p, 5)\n        i = dict_step(i, p, m)\n    return -1  # (not reached)\n\n\n@_rt.inline\n@_rt.unchecked\ndef pys_rt_dfind('),
    ("a copy shares the values' Mpz words",
     '        vb = pys_alloc(u * 8)\n        _rt.cpy(vb, _rt.getp(d, "Dict.vb"), n * 8)',
     '        vb = _rt.getp(d, "Dict.vb")'),
    ("a copy of a table leaves out its last hash",
     '    _rt.cpy(_rt.getp(r, "Dict.hs"), _rt.getp(d, "Dict.hs"), n * 8)',
     '    _rt.cpy(_rt.getp(r, "Dict.hs"), _rt.getp(d, "Dict.hs"), (n - 1) * 8)'),
    ("popitem takes the last entry, a hole or not",
     '    while not dict_live(d, e):  # (a class\'s key may hash to 0: see dict_live)\n        e -= 1\n',
     ''),
    ("a loop's step yields a hole",
     '    n = _rt.get(d, "Dict.n")\n    while e < n and not dict_live(d, e):\n        e += 1\n    if e >= n:\n        return -1\n    if count >= used:',
     '    n = _rt.get(d, "Dict.n")\n    if e >= n:\n        return -1\n    if count >= used:'),
    ("list(d) forgets the Mpz of a key or value past 64 bits",
     '                _rt.put(_rt.getp(l, "List.ids"), n + 1, _rt.word(b, e))',
     '                _rt.put(_rt.getp(l, "List.ids"), n + 1, 0)'),
    ("an insertion's idx slot names the entry before its own",
     '    _rt.put_i32(_rt.getp(d, "Dict.idx"), f, n + 1)',
     '    _rt.put_i32(_rt.getp(d, "Dict.idx"), f, n)'),
    ("a rebuild drops the last entry",
     '    n = 0\n    e = 0\n    while e < sn:\n        if dict_live(src, e):\n            h = _rt.word(sh, e)',
     '    n = 0\n    e = 0\n    while e < sn - 1:\n        if dict_live(src, e):\n            h = _rt.word(sh, e)'),
    ("a store over a value past 64 bits keeps its Mpz",
     '            _rt.put(_rt.getp(d, "Dict.vals"), e, v)\n            dict_val_clear(d, e)\n        return e\n    pys_rt_dadd(d, k, h, v, i)',
     '            _rt.put(_rt.getp(d, "Dict.vals"), e, v)\n        return e\n    pys_rt_dadd(d, k, h, v, i)'),
]
MUTANTS = [
    ("pop keeps the stale slot",
     '    _rt.set(l, "List.len", n)\n    _rt.put(_rt.getp(l, "List.a"), n, 0)\n    if _rt.get(l, "List.len") == 0:\n        pys_list_empty(l)\n    return v',
     '    _rt.set(l, "List.len", n)\n    if _rt.get(l, "List.len") == 0:\n        pys_list_empty(l)\n    return v'),
    ("pop moves the companion one entry short",
     '_rt.move(_rt.at(ids, i + 1), _rt.at(ids, i + 2), (_rt.get(l, "List.len") - i - 1) * 8)',
     '_rt.move(_rt.at(ids, i + 1), _rt.at(ids, i + 2), (_rt.get(l, "List.len") - i - 2) * 8)'),
    ("insert moves one item too many",
     '_rt.move(_rt.at(_rt.getp(l, "List.a"), i + 1), _rt.at(_rt.getp(l, "List.a"), i), (_rt.get(l, "List.len") - i) * 8)',
     '_rt.move(_rt.at(_rt.getp(l, "List.a"), i + 1), _rt.at(_rt.getp(l, "List.a"), i), (_rt.get(l, "List.len") - i + 1) * 8)'),
    ("reserve copies one companion entry short",
     '_rt.cpy(ids, _rt.getp(l, "List.ids"), (_rt.get(l, "List.len") + 1) * 8)',
     '_rt.cpy(ids, _rt.getp(l, "List.ids"), _rt.get(l, "List.len") * 8)'),
    ("reserve allocates a companion without its header word",
     'ids = pys_alloc((c + 1) * 8)\n        _rt.cpy(ids',
     'ids = pys_alloc(c * 8)\n        _rt.cpy(ids'),
    ("set does not mark its entry pending",
     '            _rt.put(_rt.getp(l, "List.ids"), 0, _rt.word(_rt.getp(l, "List.ids"), 0) | 4)\n',
     '            pass\n'),
    ("reverse leaves the companion",
     '        rev_words(_rt.at(_rt.getp(l, "List.ids"), 1), n)\n',
     '        pass\n'),
    ("del of a slice leaves its tail",
     '    _rt.fill(_rt.at(a, w), 0, k * 8)\n',
     ''),
    ("an inline list one item short",
     'l = pys_alloc(_rt.sizeof("List") + 32)',
     'l = pys_alloc(_rt.sizeof("List") + 24)'),
    ("str + str without its terminator",
     '    _rt.put_byte(d, len(a) + len(b), 0)\n',
     ''),
    ("str * n copies past the end",
     '            c = k if k < m - k else m - k\n            _rt.cpy(_rt.offset(d, k), d, c)',
     '            c = k\n            _rt.cpy(_rt.offset(d, k), d, c)'),
    ("a cached count across a seam",
     ' and _rt.byte_at(str_bytes(b), 0) & 192 != 128:\n        return chars1 + _rt.get(b, "Str.chars1") - 1',
     ':\n        return chars1 + _rt.get(b, "Str.chars1") - 1'),
    ("a field read as a word",
     'def pys_list_get(l: _rt.Ptr, i: int) -> int:\n    n = _rt.get(l, "List.len")',
     'def pys_list_get(l: _rt.Ptr, i: int) -> int:\n    n = _rt.word(l, 0)'),
    ("*= without its size check",
     '    if m > _rt.sdiv(576460752303423487, n):\n        raise MemoryError\n    if not _rt.null(_rt.getp(l, "List.ids")) and pys_rt_opt_in() != 0:\n        pys_list_identity(l, _rt.word(_rt.getp(l, "List.ids"), 0))\n    pys_list_reserve(l, m * n)',
     '    if not _rt.null(_rt.getp(l, "List.ids")) and pys_rt_opt_in() != 0:\n        pys_list_identity(l, _rt.word(_rt.getp(l, "List.ids"), 0))\n    pys_list_reserve(l, m * n)'),
    ("a slice shares items before their identities are made",
     '    if not _rt.null(_rt.getp(l, "List.ids")) and pys_rt_opt_in() != 0:\n        pys_list_identity(l, _rt.word(_rt.getp(l, "List.ids"), 0))\n    r = pys_list_make(hi - lo,',
     '    r = pys_list_make(hi - lo,'),
    ("extend copies one slot early",
     '_rt.cpy(_rt.at(_rt.getp(l, "List.a"), _rt.get(l, "List.len")), _rt.getp(m, "List.a"), n * 8)',
     '_rt.cpy(_rt.at(_rt.getp(l, "List.a"), _rt.get(l, "List.len") - 1), _rt.getp(m, "List.a"), n * 8)'),
    ("clear keeps the items",
     '    _rt.fill(_rt.getp(l, "List.a"), 0, n * 8)\n    if not _rt.null(_rt.getp(l, "List.ids")) and pys_rt_opt_in() != 0:\n        _rt.fill(_rt.at(_rt.getp(l, "List.ids"), 1), 0, n * 8)\n    _rt.set(l, "List.len", 0)',
     '    _rt.set(l, "List.len", 0)'),
    ("a search reads past the length",
     '        e = en if en < _rt.get(l, "List.len") else _rt.get(l, "List.len")\n',
     '        e = en\n'),
    ("remove deletes at an index that an __eq__ took away",
     '    if i < _rt.get(l, "List.len"):  # (an __eq__ that shrank the list past i: CPython deletes nothing)\n        pys_list_del(l, i)',
     '    pys_list_del(l, i)'),
    ("a search by slots of a list with a companion",
     '    if _rt.byte_at(str_bytes(d), 1) != 0 or not _rt.null(_rt.getp(l, "List.ids")):\n        return 0\n    c = _rt.byte_at(str_bytes(d), 0)',
     '    if _rt.byte_at(str_bytes(d), 1) != 0:\n        return 0\n    c = _rt.byte_at(str_bytes(d), 0)'),
    ("an inserted Mpz moves one entry short",
     '    _rt.move(_rt.at(ids, i + 2), _rt.at(ids, i + 1), (_rt.get(l, "List.len") - i) * 8)\n    _rt.put(ids, i + 1, box)\n    a = _rt.getp(l, "List.a")',
     '    _rt.move(_rt.at(ids, i + 2), _rt.at(ids, i + 1), (_rt.get(l, "List.len") - i - 1) * 8)\n    _rt.put(ids, i + 1, box)\n    a = _rt.getp(l, "List.a")'),
    ("a range's items multiply unchecked",
     '_rt.put(items, i, _rt.wrap_add(a, _rt.wrap_mul(i, s)))',
     '_rt.put(items, i, a + i * s)'),
    ("list(b) writes one item too many",
     '    while i < n:\n        _rt.put(items, i, _rt.byte_at(b, i))\n        i += 1',
     '    while i <= n:\n        _rt.put(items, i, _rt.byte_at(b, i if i < n else 0))\n        i += 1'),
    ("a slice assignment forgets the slots it frees",
     '    if m < k:\n        _rt.fill(_rt.at(a, n + m - k), 0, (k - m) * 8)\n    _rt.cpy(_rt.at(a, lo)',
     '    _rt.cpy(_rt.at(a, lo)'),
]


def check(runtime, part="memory"):
    # (--stop: a seeded bug's run ends at its first failure)
    return subprocess.run([sys.executable, os.path.join(ROOT, "tools", "rtcheck.py"), ROUNDS, "1", "--runtime", runtime, "--only", part, "--stop"],
                          capture_output=True, text=True, cwd=ROOT)


class Memory(unittest.TestCase):
    def test_the_code_as_it_is_passes(self):
        r = check(os.path.join(ROOT, "runtime.py"))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertRegex(r.stdout, r"\d+ cases, 0 failed")

    def test_each_seeded_bug_is_found(self):
        with open(os.path.join(ROOT, "runtime.py"), encoding="utf-8") as f:
            source = f.read()
        with tempfile.TemporaryDirectory() as tmp:
            def run(j):
                # (each against the part of the fuzz that is about its code)
                name, old, new = (MUTANTS + SET_MUTANTS + DICT_MUTANTS)[j]
                self.assertEqual(source.count(old), 1, f"{name}: runtime.py no longer has the text this mutant replaces")
                path = os.path.join(tmp, f"runtime{j}.py")
                with open(path, "w", encoding="utf-8") as f:
                    f.write(source.replace(old, new))
                return name, check(path, "lists" if j < len(MUTANTS) else "sets" if j < len(MUTANTS) + len(SET_MUTANTS) else "dicts")

            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
                for name, r in pool.map(run, range(len(MUTANTS) + len(SET_MUTANTS) + len(DICT_MUTANTS))):
                    with self.subTest(name):
                        self.assertNotEqual(r.returncode, 0, f"{name}: not found\n{r.stdout[-400:]}")


if __name__ == "__main__":
    unittest.main()
