"""wasm/check_corpus.py: the Wasm modes' differences from CPython against wasm/known_differences.txt."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from wasm import check_corpus as C


class CheckCorpus(unittest.TestCase):
    def test_entries_cover_both_modes_unless_named(self):
        k = C.known("# comment\n\nalpha errno\nbeta #1695 wasm\n")
        self.assertEqual(k, {("alpha", "wasm"): "errno", ("alpha", "wasm-tir"): "errno", ("beta", "wasm"): "#1695"})

    def test_malformed_entries_are_rejected(self):
        for text, why in [("alpha", "expected NAME"), ("alpha errno jit", "expected NAME"),
                          ("alpha typo", "unknown reason"), ("alpha errno\nalpha gc wasm", "listed twice")]:
            with self.assertRaisesRegex(ValueError, why):
                C.known(text)

    def test_unexpected_and_now_matching(self):
        report = "FAIL alpha (wasm)\n1c1\n< x\n---\n> y\nFAIL gamma (wasm-tir)\nselected 3 cases\n1 passed, 2 failed\n"
        expected = C.known("alpha errno\nbeta gc\ndelta gc\n")
        unexpected, fixed = C.compare(expected, C.failures(report), {"alpha", "beta", "gamma"}, ["wasm", "wasm-tir"])
        self.assertEqual(unexpected, [("gamma", "wasm-tir")])
        # (delta was not run: its entry stays)
        self.assertEqual(fixed, [("alpha", "wasm-tir"), ("beta", "wasm"), ("beta", "wasm-tir")])

    def test_list_names_corpus_programs(self):
        expected = C.known(Path(C.KNOWN).read_text(encoding="utf-8"))
        corpus = {Path(p).stem for p in C.corpus()}
        self.assertEqual(sorted({name for name, _ in expected} - corpus), [])

    def test_shards_partition_the_programs(self):
        shards = [C.shard(f"{i}/6") for i in range(6)]
        self.assertEqual(sorted(p for s in shards for p in s), C.corpus())
        self.assertTrue(all(shards))


if __name__ == "__main__":
    unittest.main()
