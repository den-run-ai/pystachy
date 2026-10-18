"""The offline parity tool must reject missing and numerically wrong results."""

import ast
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


SPEC = importlib.util.spec_from_file_location("check_nanogpt", Path(__file__).with_name("check_nanogpt.py"))
BENCH = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BENCH)


class ParityContractTests(unittest.TestCase):
    def test_every_value_order_type_and_shape_are_compared(self):
        expected = {"shape": [1, 2], "values": [1.0, 2.0], "loss": 0.0}
        result = BENCH.compare(expected, expected)
        self.assertEqual(result["numeric_values"], 3)
        for actual in (
            {"shape": [2, 1], "values": [1.0, 2.0], "loss": 0.0},
            {"shape": [1, 2], "values": [2.0, 1.0], "loss": 0.0},
            {"shape": [1, 2], "values": [True, 2.0], "loss": 0.0},
            {"shape": [1, 2], "values": [1.0, float("nan")], "loss": 0.0},
            {"shape": [1, 2], "values": [1.0, 2.0], "loss": float("inf")},
            {"shape": [1, 2], "values": [1.0], "loss": 0.0},
            {"shape": [1, 2], "values": [1.0, 2.0]},
        ):
            with self.subTest(actual=actual), self.assertRaises(ValueError):
                BENCH.compare(expected, actual)

    def test_parser_requires_complete_unique_records(self):
        lines = [
            "NANOGPT_LOAD_TIME 0.01",
            "NANOGPT_FULL ([1, 1, 2], [0.25, -0.25], 0.47)",
            "NANOGPT_FULL_TIME [0.001]",
            "NANOGPT_LAST ([1, 1, 2], [0.25, -0.25])",
            "NANOGPT_LAST_TIME [0.002]",
            "NANOGPT_EDGE (True,)",
        ]
        valid = "\n".join(lines)
        checks, timings = BENCH.parse_output(valid, 1, 0)
        self.assertEqual(checks["full"]["logits"], [0.25, -0.25])
        self.assertEqual(timings["full_time"], [0.001])
        for invalid in (
            "\n".join(lines[1:]),
            valid + "\n" + lines[1],
            valid.replace("[0.001]", "[]"),
            valid.replace("[0.001]", "[-1.0]"),
            valid.replace("[0.001]", "[True]"),
            valid + "\nNANOGPT_UNKNOWN []",
        ):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                BENCH.parse_output(invalid, 1, 0)
        with self.assertRaises(ValueError):
            BENCH.parse_output(valid, 1, 1)

    def test_runner_has_no_torch_or_numpy_dependency(self):
        for backend in ("scalar", "blas"):
            for steps in (0, 2):
                source = BENCH.runner_source(backend, steps)
                tree = ast.parse(source)
                imports = [node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
                self.assertNotIn("torch", imports)
                self.assertNotIn("numpy", imports)
                self.assertEqual("training" in imports, steps > 0)
                self.assertIn("ndarray" if backend == "scalar" else "ndarray_blas", imports)

    def test_export_preserves_names_shapes_and_float64_values(self):
        class Tensor:
            shape = (1, 2)

            def detach(self):
                return self

            def reshape(self, _):
                return self

            def tolist(self):
                return [1.0000000000000002, -0.125]

        class Config:
            n_layer, n_head, n_embd, block_size, vocab_size, bias = 1, 1, 2, 4, 5, True

        class Model:
            config = Config()

            def named_parameters(self):
                return [("transformer.wte.weight", Tensor())]

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "weights.txt"
            BENCH.write_weights(Model(), path)
            self.assertEqual(path.read_text(), "PYSTACHY_NANOGPT_V1\n1 1 2 4 5 1\n1\ntransformer.wte.weight 2 1 2\n1.0000000000000002 -0.125\n")

    def test_blas_override_is_exact_and_quoted(self):
        original = '@extern("libblas.so.3", "cblas_dgemm")\ndef gemm(): pass\n'
        result = BENCH.blas_overlay(original, "/tmp/my'blas.so", "scipy_cblas_dgemm")
        tree = ast.parse(result)
        args = tree.body[0].decorator_list[0].args
        self.assertEqual(ast.literal_eval(args[0]), "/tmp/my'blas.so")
        self.assertEqual(ast.literal_eval(args[1]), "scipy_cblas_dgemm")
        for source, symbol in (("", "cblas_dgemm"), (original * 2, "cblas_dgemm"), (original, "bad-symbol")):
            with self.subTest(source=source, symbol=symbol), self.assertRaises(ValueError):
                BENCH.blas_overlay(source, "libblas.so.3", symbol)

    def test_fixture_or_reference_changes_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            weight, inputs, reference = [directory / f"case.{suffix}" for suffix in ("weights", "input", "json")]
            weight.write_text("weight values")
            inputs.write_text("input values")
            reference.write_text(json.dumps({"weight_sha256": BENCH.digest(weight), "input_sha256": BENCH.digest(inputs)}))
            entry = {"name": "case", "reference_sha256": BENCH.digest(reference)}
            BENCH.load_reference(directory, entry)
            for path in (weight, inputs, reference):
                original = path.read_bytes()
                path.write_bytes(original + b"changed")
                with self.subTest(path=path), self.assertRaises(ValueError):
                    BENCH.load_reference(directory, entry)
                path.write_bytes(original)
            with self.assertRaisesRegex(ValueError, "pinned source hash"):
                BENCH.export_reference(weight, directory, [], 0, 1, 0)


    def test_requested_case_inventory_and_configuration_are_required(self):
        manifest = {"cases": [{"name": case["name"]} for case in BENCH.CASES]}
        BENCH.validate_cases(manifest, BENCH.CASES)
        for actual in (manifest["cases"][:-1], manifest["cases"] * 2, list(reversed(manifest["cases"]))):
            with self.subTest(actual=actual), self.assertRaises(ValueError):
                BENCH.validate_cases({"cases": actual}, BENCH.CASES)
        with self.assertRaises(ValueError):
            BENCH.validate_cases(manifest, BENCH.CASES + [BENCH.BENCHMARK])
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            reference = directory / "case.json"
            reference.write_text(json.dumps({"case": {"name": "wrong"}}))
            entry = {"name": "case", "reference_sha256": BENCH.digest(reference)}
            with self.assertRaisesRegex(ValueError, "configuration"):
                BENCH.load_reference(directory, entry, BENCH.CASES[0])


if __name__ == "__main__":
    unittest.main()
