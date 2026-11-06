"""Research build publication must preserve sources and existing artifacts."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
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

    def test_thinlto_requires_fixed_o2_and_default_inlining(self):
        for extra, accepted in (((), True), (("--opt", "0"), False), (("--opt", "1"), False),
                                 (("--inline-threshold", "0"), False), (("--inline-threshold", "75"), False)):
            with self.subTest(extra=extra), patch.object(sys, "argv", self.argv("--backend", "thinlto", *extra)), \
                    patch.object(pipeline, "run_pipeline", return_value=0) as run, \
                    contextlib.redirect_stderr(io.StringIO()):
                if accepted:
                    self.assertEqual(pipeline.main(), 0)
                    self.assertEqual(run.call_args.args[0].backend, "thinlto")
                else:
                    with self.assertRaises(SystemExit):
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


@unittest.skipUnless(os.getenv("PYSTACHY_TEST_LLVM"), "set PYSTACHY_TEST_LLVM for tiny ThinLTO pipeline checks")
class ThinLTOPipelineTests(unittest.TestCase):
    def test_overlap_backend_witnesses_and_publication(self):
        llvm = Path(os.environ["PYSTACHY_TEST_LLVM"]).resolve()
        with tempfile.TemporaryDirectory(prefix="pystachy-self-thinlto-") as directory:
            base = Path(directory)
            root = base / "source"
            root.mkdir()
            (root / "runtime.py").write_text("# frozen runtime fixture\n")
            (root / "runtime.c").write_text("/* frozen runtime fixture */\n")
            # This tiny producer/native stand-in exercises the real backend and
            # wrapper contracts. It is not a compiler performance measurement.
            (root / "pystachy.py").write_text('''import os, pathlib, shutil, sys, time
root = pathlib.Path(os.environ["PYSTACHY_HOME"])
mode = sys.argv[1]
out = pathlib.Path(sys.argv[sys.argv.index("-o") + 1])
if mode in ("ir", "build"):
    (root / (mode + ".started")).touch()
    peer = root / (("build" if mode == "ir" else "ir") + ".started")
    deadline = time.monotonic() + 2
    while not peer.exists():
        if time.monotonic() > deadline:
            raise RuntimeError("frontend/runtime overlap did not occur")
        time.sleep(.005)
if mode == "build":
    cache = pathlib.Path(os.environ["PYSTACHY_CACHE"])
    cache.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(root / "runtime-template.bc", cache / "runtime-py-fixture.bc")
    out.write_text("prepared tiny executable\\n")
else:
    out.write_bytes((root / ("runtime-template.ll" if mode == "rt" else "raw-template.ll")).read_bytes())
''')
            native = base / "standin.c"
            native.write_text('''#include <stdio.h>
#include <stdlib.h>
int main(int argc, char **argv) {
    if (argc != 5) return 2;
    char path[4096];
    snprintf(path, sizeof(path), "%s/%s", getenv("PYSTACHY_HOME"),
             argv[1][0] == 'r' ? "runtime-template.ll" : "raw-template.ll");
    FILE *in = fopen(path, "r"), *out = fopen(argv[4], "w");
    if (!in || !out) return 3;
    if (argv[1][0] == 'r' && getenv("STANDIN_BAD_RUNTIME")) fputs("wrong runtime\\n", out);
    else { int c; while ((c = fgetc(in)) != EOF) fputc(c, out); }
    fclose(in);
    return fclose(out);
}
''')
            subprocess.run([str(llvm / "clang"), "-O0", "-S", "-emit-llvm", str(native), "-o",
                            str(root / "raw-template.ll")], capture_output=True, check=True, timeout=15)
            (root / "runtime-template.ll").write_text('target triple = "x86_64-pc-linux-gnu"\n'
                                                       'define void @runtime_fixture() { ret void }\n')
            subprocess.run([str(llvm / "opt"), "-passes=verify", str(root / "runtime-template.ll"), "-o",
                            str(root / "runtime-template.bc")], capture_output=True, check=True, timeout=15)
            published, emitted = base / "published-compiler", base / "published.ll"
            for correct in (True, False):
                for mode in ("ir", "build"):
                    (root / f"{mode}.started").unlink(missing_ok=True)
                environment = {key: value for key, value in os.environ.items() if key != "STANDIN_BAD_RUNTIME"}
                if not correct:
                    environment["STANDIN_BAD_RUNTIME"] = "1"
                    emitted.write_bytes(b"previous sidecar must survive")
                    before = (published.read_bytes(), emitted.read_bytes())
                work, report_path = base / f"work-{correct}", base / f"report-{correct}.json"
                result = subprocess.run([sys.executable, str(BENCH / "self_pipeline.py"), "--hosted",
                                         "--root", str(root), "--llvm", str(llvm), "--work", str(work),
                                         "--report", str(report_path), "--backend", "thinlto", "--opt", "2",
                                         "--partitions", "2", "--jobs", "2", "--overlap",
                                         "--output", str(published), "--emit-ir", str(emitted)],
                                        env=environment, capture_output=True, text=True, timeout=30,
                                        start_new_session=True)
                self.assertEqual(result.returncode, 0 if correct else 1, result.stderr)
                report = json.loads(report_path.read_text())
                self.assertEqual(report["complete"], correct)
                self.assertEqual(report["backend_policy"], "thinlto")
                self.assertEqual(report["thinlto_job"]["prelink"], "summary")
                self.assertTrue(report["backend"]["complete"])
                self.assertIn("--inherited-group", report["stages"]["backend"]["command"])
                self.assertTrue(report["witnesses"]["ir"]["matches"])
                self.assertEqual(report["witnesses"]["rt"]["matches"], correct)
                self.assertIn("rt_reference", report["witnesses"])
                if correct:
                    self.assertEqual(published.read_bytes(), (work / "backend/compiler").read_bytes())
                    self.assertEqual(emitted.read_bytes(), (work / "raw.ll").read_bytes())
                else:
                    self.assertEqual((published.read_bytes(), emitted.read_bytes()), before)


if __name__ == "__main__":
    unittest.main()
