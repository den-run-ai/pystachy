"""Guard benchmark evidence against corrupt results and missing rare inputs."""
import json
import unittest

import bench_json as bench


class EvidenceTests(unittest.TestCase):
    def test_every_sample_is_checked_against_cpython(self):
        valid = "JSON_SAMPLE 0 100 200 200 1 2 3\nJSON_SAMPLE 1 100 200 200 4 5 6\n"
        result = bench.parse_output(valid, 2, [100, 200, 200])
        self.assertEqual(result["timings_s"]["process"], [2e-9, 5e-9])
        for field in ("100 201 200", "100 200 201", "99 200 200"):
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "checksum"):
                bench.parse_output(valid.replace("100 200 200", field, 1), 2, [100, 200, 200])

    def test_missing_extra_and_malformed_evidence_rejected(self):
        valid = "JSON_SAMPLE 0 100 200 200 1 2 3\n"
        for output in ("", valid + valid, valid.replace("0 100", "1 100"),
                       valid.replace(" 1 2 3", " 1 -2 3"), valid.replace(" 1 2 3", " 1 2")):
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


if __name__ == "__main__":
    unittest.main()
