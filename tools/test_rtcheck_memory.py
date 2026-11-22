"""tools/rtcheck.py finds seeded bugs in runtime.py's memory code.

Each mutant is one change to the list or str code that a compiled runtime would run without
complaint: a write past a block, a stale slot that the collector would scan, a read that
breaks an alias rule, arithmetic that overflows unchecked, an identity that a companion
loses. The heap model of tools/rt_cpython/rt_heap.py must report every one of them at the
size this test runs, and nothing in the code as it is.
"""
import concurrent.futures
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROUNDS = "1500"

# (what the fault is, the text of runtime.py that it replaces, the replacement)
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


def check(runtime):
    return subprocess.run([sys.executable, os.path.join(ROOT, "tools", "rtcheck.py"), ROUNDS, "1", "--runtime", runtime, "--only", "memory"],
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
                name, old, new = MUTANTS[j]
                self.assertEqual(source.count(old), 1, f"{name}: runtime.py no longer has the text this mutant replaces")
                path = os.path.join(tmp, f"runtime{j}.py")
                with open(path, "w", encoding="utf-8") as f:
                    f.write(source.replace(old, new))
                return name, check(path)

            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
                for name, r in pool.map(run, range(len(MUTANTS))):
                    with self.subTest(name):
                        self.assertNotEqual(r.returncode, 0, f"{name}: not found\n{r.stdout[-400:]}")


if __name__ == "__main__":
    unittest.main()
