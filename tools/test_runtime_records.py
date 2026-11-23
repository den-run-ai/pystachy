"""specs.RTRECORDS: runtime.c's records, the one layout table that lowering and wasm/tir_wasm.py read."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
from src.pystachy_compiler import specs as S  # noqa: E402
from check_runtime import record_errors  # noqa: E402


class RuntimeRecords(unittest.TestCase):
    def test_offsets_follow_each_targets_pointer_size(self):
        # (runtime.c's _Static_asserts: List under LP64 and under WASI)
        self.assertEqual([S.rt_record_offset("List", f, 8) for f in ["len", "cap", "a", "ids", ""]], [0, 8, 16, 24, 32])
        self.assertEqual([S.rt_record_offset("List", f, 4) for f in ["len", "cap", "a", "ids", ""]], [0, 8, 16, 20, 24])
        self.assertEqual([S.rt_record_offset("ReflRec", f.rstrip("*"), 4) for f in S.RTRECORDS["ReflRec"].split()],
                         [0, 4, 8, 16, 24, 32, 40, 48])
        self.assertEqual(S.rt_record_offset("ReflRec", "", 4), 56)
        self.assertEqual(S.rt_record_offset("VTuple", "", 4), S.rt_record_offset("VTuple", "", 8))
        self.assertEqual(S.rt_record_offset("Dyn", "", 4), 16)
        self.assertEqual(S.rt_record_offset("List", "nope", 8), -1)

    def test_lowering_reads_its_types_from_the_table(self):
        self.assertEqual(S.STR_HEADER_SIZE, 24)
        self.assertEqual(S.CLASSREC_LL, "{ptr, ptr, ptr, i64, i64, ptr, i64, ptr}")
        self.assertEqual(S.DYNTYPE_LL, "{i64, ptr, ptr, i64, ptr, i64, ptr, ptr, ptr}")
        self.assertEqual((S.LIST_ITEMS, S.LIST_ITEMS_LL), (2, "{i64, i64, ptr}"))
        self.assertEqual(S.BIGLL, "{i64, ptr}")
        self.assertEqual(S.rt_record_values("ReflRec", ["@a", "@b", "@c", "@d"], ["1", "2", "3"]),
                         "ptr @a, ptr @b, ptr @c, i64 1, i64 2, ptr @d, i64 3, ptr null")

    def test_check_names_a_record_that_runtime_c_lays_out_otherwise(self):
        ll = "%struct.List = type { i64, i64, ptr, ptr }\n%struct.Str = type { i64, i64, i64, [0 x i8] }\n"
        self.assertEqual(record_errors(ll, {"List": "len cap a* ids*", "Str": "len dict_hash chars1"}), [])
        self.assertEqual(record_errors(ll, {"List": "len cap ids* a"}),
                         ["RTRECORDS: List is {i64, i64, ptr, i64} to the compiler, {i64, i64, ptr, ptr} in runtime.c"])
        self.assertEqual(record_errors(ll, {"Set": "len"}), ["RTRECORDS: runtime.c has no struct Set"])


if __name__ == "__main__":
    unittest.main()
