"""Guard benchmark evidence against corrupt results and missing rare inputs."""
import json
import unittest

import bench_json as bench

WARMUP = "JSON_WARMUP 3 2000000000\n"


class EvidenceTests(unittest.TestCase):
    def test_every_sample_is_checked_against_cpython(self):
        valid = WARMUP + "JSON_SAMPLE 0 100 200 200 1 2 3\nJSON_SAMPLE 1 100 200 200 4 5 6\n"
        result = bench.parse_output(valid, 2, [100, 200, 200])
        self.assertEqual(result["timings_s"]["process"], [2e-9, 5e-9])
        self.assertEqual(result["warmup"], {"rounds": 3, "seconds": 2.0})
        for field in ("100 201 200", "100 200 201", "99 200 200"):
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "checksum"):
                bench.parse_output(valid.replace("100 200 200", field, 1), 2, [100, 200, 200])

    def test_predecoded_samples_are_checked_against_cpython(self):
        valid = WARMUP + "JSON_PREDECODED 0 200 7 8\nJSON_PREDECODED 1 200 9 10\n"
        result = bench.parse_output(valid, 2, [100, 200, 200], "predecoded")
        self.assertEqual(result["timings_s"], {"process": [7e-9, 9e-9], "rebuild": [8e-9, 10e-9]})
        with self.assertRaisesRegex(ValueError, "checksum"):
            bench.parse_output(valid.replace("0 200 7", "0 201 7"), 2, [100, 200, 200], "predecoded")
        with self.assertRaisesRegex(ValueError, "reference"):
            bench.parse_output(valid, 2, None, "predecoded")

    def test_missing_extra_and_malformed_evidence_rejected(self):
        valid = WARMUP + "JSON_SAMPLE 0 100 200 200 1 2 3\n"
        for output in ("", valid + valid, valid.replace("0 100", "1 100"), valid.replace(WARMUP, ""),
                       valid.replace(WARMUP, "JSON_WARMUP 0 5\n"), valid.replace(" 1 2 3", " 1 -2 3"),
                       valid.replace(" 1 2 3", " 1 2"), valid.replace("JSON_SAMPLE", "JSON_PREDECODED")):
            with self.subTest(output=output), self.assertRaises(ValueError):
                bench.parse_output(output, 1)

    def test_skew_and_control_inputs_retain_rare_types(self):
        skewed = json.loads(bench.fixture(100, "skewed"))
        mixed = json.loads(bench.fixture(100, "mixed"))
        self.assertEqual(sum(type(row.get("amount")) is int for row in skewed), 92)
        self.assertEqual(sum(type(row.get("amount")) is int for row in mixed), 0)
        for rows in (skewed, mixed):
            self.assertEqual({type(row.get("amount")) for row in rows},
                             {float, type(None), str, bool, list, dict} | ({int} if rows is skewed else set()))
            self.assertTrue(any("amount" not in row for row in rows))
            self.assertTrue(all("雪" in row["details"]["name"] for row in rows))
        changing = json.loads(bench.fixture(200, "changing"))
        self.assertEqual(changing[:100], skewed)
        self.assertEqual(sum(type(row.get("amount")) is int for row in changing[100:]), 0)

    def test_text_variants_encode_comparable_values(self):
        utf8 = bench.fixture(100, "skewed")
        escaped = bench.fixture(100, "skewed", "escaped")
        ascii_text = bench.fixture(100, "skewed", "ascii")
        self.assertFalse(utf8.isascii())
        self.assertTrue(escaped.isascii() and ascii_text.isascii())
        self.assertEqual(json.loads(escaped), json.loads(utf8))
        # Same shapes and string lengths in characters, so the same processing checksum.
        lengths = [[len(row["details"]["name"])] + [len(tag) for tag in row["details"]["tags"]]
                   for row in json.loads(utf8)]
        self.assertEqual(lengths, [[len(row["details"]["name"])] + [len(tag) for tag in row["details"]["tags"]]
                                   for row in json.loads(ascii_text)])


if __name__ == "__main__":
    unittest.main()
