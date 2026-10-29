"""Guard benchmark evidence against corrupt results and missing rare inputs."""
import ast
import contextlib
import io
import json
import os
from pathlib import Path
import runpy
import sys
import tempfile
import unittest
from unittest import mock

import bench_json as bench

WARMUP = "JSON_WARMUP 3 2000000000\n"


class ObservedAny32Tests(unittest.TestCase):
    SOURCE = bench.ROOT / "bench/smoke/json_decode_any32.py"
    TYPED = bench.ROOT / "bench/smoke/json_decode.py"

    def run_control(self, case="numeric", loops=3):
        stdout, stderr = io.StringIO(), io.StringIO()
        with mock.patch.object(sys, "argv", [str(self.SOURCE), case, str(loops)]), \
                contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            namespace = runpy.run_path(str(self.SOURCE), run_name="__main__")
        return namespace, stdout.getvalue(), stderr.getvalue()

    def test_inputs_match_typed_control_and_independent_32_key_objects(self):
        def constants(path):
            result = {}
            for node in ast.parse(path.read_text()).body:
                if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                        and isinstance(node.targets[0], ast.Name) \
                        and node.targets[0].id in {"NUMERIC", "STRINGS", "MIXED"}:
                    result[node.targets[0].id] = ast.literal_eval(node.value)
            return result

        observed = constants(self.SOURCE)
        self.assertEqual(set(observed), {"NUMERIC", "STRINGS", "MIXED"})
        self.assertEqual(observed, constants(self.TYPED))
        values = [1000, 1001.25, "value-02", True, False, None,
                  [1006, "value-06"], {"inner": 1007}]
        expected = {
            "NUMERIC": {f"k{i}": 1000 + i for i in range(32)},
            "STRINGS": {f"k{i}": f"value-{i:02d}" for i in range(32)},
            "MIXED": {f"k{i}": values[i % 8] for i in range(32)},
        }
        for case, text in observed.items():
            with self.subTest(case=case):
                # repr checks order and distinguishes bool/int and int/float.
                self.assertEqual(repr(json.loads(text)), repr(expected[case]))

    def test_every_load_observes_any_result_and_prints_complete_oracle(self):
        original_loads = json.loads
        for case, per_load in (("numeric", 1063), ("strings", 40), ("mixed", 1039)):
            with self.subTest(case=case):
                observations = []

                class ObservedDict(dict):
                    def __init__(self, value, log):
                        super().__init__(value)
                        self.log = log

                    def __len__(self):
                        self.log.append("length")
                        return super().__len__()

                    def __getitem__(self, key):
                        self.log.append(key)
                        return super().__getitem__(key)

                def load(text, observations=observations):
                    return ObservedDict(original_loads(text), observations)

                with mock.patch.object(json, "loads", side_effect=load) as loads:
                    namespace, output, timing = self.run_control(case)
                self.assertEqual(loads.call_count, 3)
                self.assertEqual(observations, ["length", "k31"] * 3)
                expected = original_loads(namespace[case.upper()])
                self.assertEqual(output, f"json_decode_any32 {case} 3 {3 * per_load}\n{expected!r}\n")
                self.assertEqual(len(timing.splitlines()), 1)
                label, seconds = timing.split()
                self.assertEqual(label, "seconds")
                self.assertGreaterEqual(float(seconds), 0)

    def test_corrupt_intermediate_result_fails_even_with_correct_final_result(self):
        original_loads = json.loads
        for case in ("numeric", "strings", "mixed"):
            for corruption in ("field", "length"):
                with self.subTest(case=case, corruption=corruption):
                    calls = 0

                    def load(text, case=case, corruption=corruption):
                        nonlocal calls
                        calls += 1
                        result = original_loads(text)
                        if calls == 2:
                            if corruption == "length":
                                del result["k0"]
                            elif case == "numeric":
                                result["k31"] += 1
                            elif case == "strings":
                                result["k31"] += "x"
                            else:
                                result["k31"]["inner"] += 1
                        return result

                    with mock.patch.object(json, "loads", side_effect=load), \
                            self.assertRaises(AssertionError):
                        self.run_control(case)
                    self.assertEqual(calls, 3)

    def test_invalid_inputs_fail_before_decoding(self):
        for case, loops, message in (("numeric", 0, "positive"),
                                      ("numeric", -1, "positive"),
                                      ("unknown", 3, "case must"),
                                      ("numeric", "bad", "invalid literal")):
            with self.subTest(case=case, loops=loops), \
                    mock.patch.object(json, "loads") as loads, \
                    self.assertRaisesRegex(ValueError, message):
                self.run_control(case, loops)
            loads.assert_not_called()


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
        valid = WARMUP + "JSON_PREDECODED 0 200 50 99 7 8 6\nJSON_PREDECODED 1 200 50 99 9 10 5\n"
        result = bench.parse_output(valid, 2, [100, 200, 200], "predecoded", [50, 99])
        self.assertEqual(result["timings_s"], {"process": [7e-9, 9e-9], "rebuild": [8e-9, 10e-9],
                                               "encode": [6e-9, 5e-9]})
        with self.assertRaisesRegex(ValueError, "checksum"):
            bench.parse_output(valid.replace("0 200 50", "0 201 50"), 2, [100, 200, 200], "predecoded", [50, 99])
        for row in ("1 200 51 99", "1 200 50 98"):
            with self.subTest(row=row), self.assertRaisesRegex(ValueError, "encoded length and digest"):
                bench.parse_output(valid.replace("1 200 50 99", row), 2, [100, 200, 200], "predecoded", [50, 99])
        for expected, encoded in (([100, 200, 200], None), (None, [50, 99])):
            with self.subTest(expected=expected, encoded=encoded), self.assertRaisesRegex(ValueError, "reference"):
                bench.parse_output(valid, 2, expected, "predecoded", encoded)

    def test_encoding_digest_is_order_sensitive(self):
        # Same length, same decoded string lengths: only the digest tells these texts apart.
        text = '[{"a": "x\u00e9", "b": 1}]'
        self.assertEqual(bench.encoding(text)[0], len(json.dumps(json.loads(text))))
        for other in ('[{"b": 1, "a": "x\u00e9"}]', '[{"a": "\u00e9x", "b": 1}]'):
            self.assertEqual(len(json.dumps(json.loads(other))), bench.encoding(text)[0])
            self.assertNotEqual(bench.encoding(other)[1], bench.encoding(text)[1])

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

    def test_json_module_is_the_one_the_compiler_compiles(self):
        here = (bench.ROOT / "lib/json.py").resolve()
        self.assertEqual(bench.compiled_json_module({}, ["./pystachy"]), here)
        self.assertEqual(bench.compiled_json_module({}, ["python3.13", "-m", "pystachy"]), here)
        with tempfile.TemporaryDirectory() as tmp:
            other = Path(tmp).resolve()
            (other / "runtime.c").write_text("")
            (other / "lib").mkdir()
            (other / "lib/json.py").write_text("")
            elsewhere = (other / "lib/json.py").resolve()
            # another checkout's compiler reads its own lib/, unless PYSTACHY_HOME says otherwise
            self.assertEqual(bench.compiled_json_module({}, [str(other / "pystachy")]), elsewhere)
            self.assertEqual(bench.compiled_json_module({"PYSTACHY_HOME": str(bench.ROOT)},
                                                        [str(other / "pystachy")]), here)
            # PYSTACHY_PATH comes first; relative entries are relative to the compiler's cwd, ROOT
            relative = os.path.relpath(other / "lib", bench.ROOT)
            self.assertEqual(bench.compiled_json_module({"PYSTACHY_PATH": relative}, ["./pystachy"]), elsewhere)


if __name__ == "__main__":
    unittest.main()
