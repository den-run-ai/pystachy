"""Research build publication must preserve sources and existing artifacts."""
import contextlib
import importlib.util
import io
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch


BENCH = Path(__file__).resolve().parents[1] / "bench/compiler_host"
sys.path.insert(0, str(BENCH))
SPEC = importlib.util.spec_from_file_location("self_build_pipeline", BENCH / "self_pipeline.py")
pipeline = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pipeline)


class InliningPolicyTests(unittest.TestCase):
    def argv(self, *extra):
        return ["self_pipeline.py", "--hosted", "--llvm", "llvm", "--work", "work", "--report", "report.json", *extra]

    def test_default_and_explicit_policy_reach_the_pipeline(self):
        for extra, expected in (((), None), (("--inline-threshold", "0"), 0), (("--inline-threshold", "75"), 75)):
            with self.subTest(extra=extra), patch.object(sys, "argv", self.argv(*extra)), \
                 patch.object(pipeline, "run_pipeline", return_value=0) as run:
                self.assertEqual(pipeline.main(), 0)
                self.assertEqual(run.call_args.args[0].inline_threshold, expected)

    def test_invalid_policy_rejects_before_the_pipeline(self):
        for value in ("-1", "10001", "invalid"):
            with self.subTest(value=value), patch.object(sys, "argv", self.argv("--inline-threshold", value)), \
                 patch.object(pipeline, "run_pipeline") as run, contextlib.redirect_stderr(io.StringIO()), \
                 self.assertRaises(SystemExit):
                pipeline.main()
            run.assert_not_called()


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "pystachy.py"
        self.source.write_text("source must survive\n")
        self.work = self.root / "private"
        self.args = SimpleNamespace(output=self.root / "compiler", emit_ir=self.root / "raw.ll",
                                    report=self.root / "report.json")

    def validate(self):
        pipeline.validate_outputs(self.args, self.root, self.work, [str(self.source)])

    def test_sources_hardlinks_symlinks_and_other_outputs_are_protected(self):
        for alias in (self.source, self.root / "symlink", self.root / "hardlink"):
            if alias.name == "symlink":
                alias.symlink_to(self.source)
            elif alias.name == "hardlink":
                alias.hardlink_to(self.source)
            self.args.output = alias
            with self.subTest(alias=alias), self.assertRaises(ValueError):
                self.validate()
        self.args.output = self.args.emit_ir
        with self.assertRaises(ValueError):
            self.validate()
        self.args.output = self.work / "raw.ll"
        with self.assertRaises(ValueError):
            self.validate()
        self.assertEqual(self.source.read_text(), "source must survive\n")

    def test_failed_publication_preserves_previous_output_and_unrelated_staging(self):
        self.validate()
        destination = self.args.output
        destination.write_text("previous\n")
        unrelated = destination.with_name(destination.name + ".pending")
        unrelated.write_text("another invocation\n")
        with patch.object(pipeline.shutil, "copy2", side_effect=OSError("injected copy failure")):
            with self.assertRaises(OSError):
                pipeline.publish(self.source, destination)
        self.assertEqual(destination.read_text(), "previous\n")
        self.assertEqual(unrelated.read_text(), "another invocation\n")
        self.assertEqual(list(self.root.glob("compiler.*.pending")), [])
        pipeline.publish(self.source, destination)
        self.assertEqual(destination.read_bytes(), self.source.read_bytes())
        self.assertEqual(unrelated.read_text(), "another invocation\n")


class RuntimeSelectionTests(unittest.TestCase):
    def test_each_producer_uses_its_own_new_artifact_and_ambiguity_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory)
            first = cache / "runtime-py-first.bc"
            second = cache / "runtime-py-second.bc"
            first.write_bytes(b"first producer")
            before = {first: pipeline.sha(first)}
            self.assertEqual(pipeline.prepared_runtime(cache, before, "cache hit"), first)
            with self.assertRaises(RuntimeError):
                pipeline.prepared_runtime(cache, before, "pystachy-timing\truntime.frontend\t1\n")
            second.write_bytes(b"second producer")
            self.assertEqual(pipeline.prepared_runtime(cache, before, ""), second)
            with self.assertRaises(RuntimeError):
                pipeline.prepared_runtime(cache, {}, "")
            with self.assertRaises(RuntimeError):
                pipeline.prepared_runtime(cache, {p: pipeline.sha(p) for p in (first, second)}, "cache hit")


if __name__ == "__main__":
    unittest.main()
