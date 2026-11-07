"""Research build publication must preserve sources and existing artifacts."""
import contextlib
from concurrent.futures import ThreadPoolExecutor
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import threading
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

    def test_ordinary_backend_rejects_partitions_before_work(self):
        with patch.object(sys, "argv", self.argv("--backend", "ordinary", "--partitions", "2")), \
                patch.object(pipeline, "run_pipeline") as run, contextlib.redirect_stderr(io.StringIO()), \
                self.assertRaises(SystemExit):
            pipeline.main()
        run.assert_not_called()

    def test_manifest_producer_and_publication_are_explicit_cli_options(self):
        argv = ["self_pipeline.py", "--compiler-manifest", "stage1.json", "--publish-manifest", "stage2.json",
                "--llvm", "llvm", "--work", "work", "--report", "report.json"]
        with patch.object(sys, "argv", argv), patch.object(pipeline, "run_pipeline", return_value=0) as run:
            self.assertEqual(pipeline.main(), 0)
            self.assertEqual(run.call_args.args[0].compiler_manifest, Path("stage1.json"))
            self.assertEqual(run.call_args.args[0].publish_manifest, Path("stage2.json"))
        with patch.object(sys, "argv", argv + ["--compiler", "compiler"]), \
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

    def test_manifest_cannot_alias_outputs_or_modify_existing_generations(self):
        self.args.publish_manifest = self.args.output
        with self.assertRaises(ValueError):
            self.validate()
        self.args.publish_manifest = self.root / "generation.json"
        self.args.output = self.root / "generation.json.generations" / "generation-abcdefgh" / "compiler"
        with self.assertRaisesRegex(ValueError, "immutable"):
            self.validate()


class ManifestPublicationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.pointer = self.root / "build.json"
        self.source_sha256 = "1" * 64

    def inputs(self, name):
        executable, raw = self.root / (name + ".exe"), self.root / (name + ".ll")
        executable.write_bytes(("executable " + name).encode())
        executable.chmod(0o755)
        raw.write_bytes(("retained IR " + name).encode())
        return executable, raw

    def publish(self, inputs, validation="local-witnesses"):
        compiler, raw_ir = inputs
        return pipeline.publish_generation(
            compiler, raw_ir, self.pointer, expected={"compiler": pipeline.sha(compiler), "raw_ir": pipeline.sha(raw_ir)},
            source_sha256=self.source_sha256, validation=validation)

    @staticmethod
    def contents(snapshot):
        return snapshot["compiler"].read_bytes(), snapshot["raw_ir"].read_bytes()

    def test_one_pointer_switches_both_artifacts_and_keeps_pinned_readers(self):
        old, new = self.inputs("old"), self.inputs("new")
        first = self.publish(old)
        original_copy = pipeline.shutil.copy2
        observations = []

        def copy(source, destination):
            result = original_copy(source, destination)
            observations.append(self.contents(pipeline.resolve_publication(self.pointer)))
            return result

        with patch.object(pipeline.shutil, "copy2", side_effect=copy):
            second = self.publish(new)
        self.assertEqual(observations, [(old[0].read_bytes(), old[1].read_bytes())] * 2)
        self.assertNotEqual(first["manifest"]["generation"], second["manifest"]["generation"])
        self.assertEqual(self.contents(pipeline.resolve_publication(self.pointer)), (new[0].read_bytes(), new[1].read_bytes()))
        self.assertEqual(self.contents(first), (old[0].read_bytes(), old[1].read_bytes()))
        # Legacy output replacement cannot mutate a copied generation.
        old[0].write_bytes(b"legacy output changed")
        self.assertNotEqual(first["compiler"].read_bytes(), old[0].read_bytes())

    def test_copy_or_pointer_failure_preserves_the_previous_generation(self):
        old, new = self.inputs("old"), self.inputs("new")
        snapshot = self.publish(old)
        pointer_before = self.pointer.read_bytes()
        with patch.object(pipeline.shutil, "copy2", side_effect=OSError("copy failed")), self.assertRaises(OSError):
            self.publish(new)
        self.assertEqual(self.pointer.read_bytes(), pointer_before)
        with patch.object(pipeline.os, "replace", side_effect=OSError("replace failed")), self.assertRaises(OSError):
            self.publish(new)
        self.assertEqual(self.pointer.read_bytes(), pointer_before)
        self.assertEqual(self.contents(pipeline.resolve_publication(self.pointer)), self.contents(snapshot))
        self.assertEqual(list(self.root.glob("build.json.*.pending")), [])

    def test_ambiguous_success_keeps_the_published_generation(self):
        self.publish(self.inputs("old"))
        new = self.inputs("new")
        replace = pipeline.os.replace

        def replace_then_interrupt(source, destination):
            replace(source, destination)
            raise KeyboardInterrupt

        with patch.object(pipeline.os, "replace", side_effect=replace_then_interrupt), self.assertRaises(KeyboardInterrupt):
            self.publish(new)
        self.assertEqual(self.contents(pipeline.resolve_publication(self.pointer)), (new[0].read_bytes(), new[1].read_bytes()))

    def test_copied_artifacts_must_match_the_prevalidated_hashes(self):
        self.publish(self.inputs("old"))
        before = self.pointer.read_bytes()
        compiler, raw_ir = self.inputs("new")
        expected = {"compiler": pipeline.sha(compiler), "raw_ir": pipeline.sha(raw_ir)}
        raw_ir.write_bytes(b"changed after witness validation")
        with self.assertRaisesRegex(ValueError, "changed before publication"):
            pipeline.publish_generation(compiler, raw_ir, self.pointer, expected=expected,
                                        source_sha256=self.source_sha256, validation="local-witnesses")
        self.assertEqual(self.pointer.read_bytes(), before)

    def test_concurrent_publishers_never_share_staging_or_mix_generations(self):
        inputs = (self.inputs("first"), self.inputs("second"))
        self.publish(self.inputs("old"))
        barrier = threading.Barrier(2)
        original_copy = pipeline.shutil.copy2

        def copy(source, destination):
            result = original_copy(source, destination)
            if source.suffix == ".ll":
                barrier.wait(timeout=5)
            return result

        with patch.object(pipeline.shutil, "copy2", side_effect=copy), ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(self.publish, pair) for pair in inputs]
            snapshots = [future.result(timeout=10) for future in futures]
        expected = [(pair[0].read_bytes(), pair[1].read_bytes()) for pair in inputs]
        self.assertEqual([self.contents(snapshot) for snapshot in snapshots], expected)
        self.assertIn(self.contents(pipeline.resolve_publication(self.pointer)), expected)
        self.assertNotEqual(snapshots[0]["compiler"].parent, snapshots[1]["compiler"].parent)

    def test_reader_rejects_traversal_schema_and_artifact_corruption(self):
        snapshot = self.publish(self.inputs("valid"))
        payload = self.pointer.read_bytes()
        for field, invalid in (("generation", "../outside"), ("generation", "/tmp/outside"),
                               ("version", True), ("complete", False), ("source_sha256", "wrong")):
            record = json.loads(payload)
            record[field] = invalid
            self.pointer.write_text(json.dumps(record))
            with self.subTest(field=field, invalid=invalid), self.assertRaises(ValueError):
                pipeline.resolve_publication(self.pointer)
        for invalid in ({"bytes": True}, {"path": "../../outside"}, {"sha256": "wrong"}):
            record = json.loads(payload)
            record["artifacts"]["raw_ir"].update(invalid)
            self.pointer.write_text(json.dumps(record))
            with self.subTest(artifact=invalid), self.assertRaises(ValueError):
                pipeline.resolve_publication(self.pointer)
        self.pointer.write_bytes(payload)
        raw_ir = snapshot["raw_ir"]
        raw_ir.chmod(0o644)
        raw_ir.write_bytes(b"x" * raw_ir.stat().st_size)
        with self.assertRaisesRegex(ValueError, "altered"):
            pipeline.resolve_publication(self.pointer)

    def test_reader_rejects_symlinks_at_each_publication_level(self):
        snapshot = self.publish(self.inputs("valid"))
        generation = snapshot["compiler"].parent
        for original in (self.pointer, generation.parent, generation, snapshot["compiler"], snapshot["raw_ir"]):
            moved = original.with_name(original.name + ".moved")
            original.rename(moved)
            original.symlink_to(moved, target_is_directory=moved.is_dir())
            try:
                with self.subTest(path=original.name), self.assertRaises(ValueError):
                    pipeline.resolve_publication(self.pointer)
            finally:
                original.unlink()
                moved.rename(original)

    def test_deferred_witnesses_remain_explicit(self):
        self.publish(self.inputs("stage1"), validation="caller-witnesses")
        self.assertEqual(pipeline.resolve_publication(self.pointer)["manifest"]["validation"], "caller-witnesses")
        with self.assertRaisesRegex(ValueError, "caller's IR witnesses"):
            pipeline.resolve_publication(self.pointer, require_witnesses=True)
        self.publish(self.inputs("checked"))
        self.assertEqual(pipeline.resolve_publication(self.pointer, require_witnesses=True)["manifest"]["validation"],
                         "local-witnesses")


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


@unittest.skipUnless(os.getenv("PYSTACHY_TEST_LLVM"), "set PYSTACHY_TEST_LLVM for tiny backend pipeline checks")
class ThinLTOPipelineTests(unittest.TestCase):
    def test_overlap_backend_witnesses_and_publication(self):
        self.check_backend("thinlto", 2)

    def test_ordinary_overlap_preserves_whole_module_witnesses_and_publication(self):
        self.check_backend("ordinary", 1)

    def test_ordinary_allocator_keeps_late_inline_order_and_threshold_scope(self):
        self.check_backend("ordinary", 1, allocator=True)

    def check_backend(self, backend, partitions, allocator=False):
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
#include <string.h>
#include <sys/stat.h>
int main(int argc, char **argv) {
    if (argc != 5) return 2;
    char path[4096];
    if (!strcmp(argv[1], "build")) {
        char target[4096];
        const char *cache = getenv("PYSTACHY_CACHE");
        mkdir(cache, 0700);
        snprintf(path, sizeof(path), "%s/runtime-template.bc", getenv("PYSTACHY_HOME"));
        snprintf(target, sizeof(target), "%s/runtime-py-fixture.bc", cache);
        FILE *in = fopen(path, "rb"), *out = fopen(target, "wb");
        if (!in || !out) return 5;
        int c; while ((c = fgetc(in)) != EOF) fputc(c, out);
        fclose(in);
        if (fclose(out)) return 6;
        out = fopen(argv[4], "w");
        if (!out) return 7;
        fputs("prepared tiny executable\\n", out);
        return fclose(out);
    }
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
            if allocator:
                native.write_text("extern void *pys_new(long);\n" + native.read_text().replace(
                    "    char path[4096];", "    volatile long *value = pys_new(8);\n"
                    "    *value = argc; if (*value != 5) return 4;\n    char path[4096];"))
            subprocess.run([str(llvm / "clang"), "-O0", "-S", "-emit-llvm", str(native), "-o",
                            str(root / "raw-template.ll")], capture_output=True, check=True, timeout=15)
            if allocator:
                raw = root / "raw-template.ll"
                # Use the actual Pystachy declaration spelling, not Clang's C-ABI
                # parameter attributes. The native witness really calls this allocator.
                raw.write_text(re.sub(r"^declare .*@pys_new\(.*$", "declare ptr @pys_new(i64)",
                                      raw.read_text(), flags=re.MULTILINE))
            (root / "runtime-template.ll").write_text('target triple = "x86_64-pc-linux-gnu"\n'
                                                       'define void @runtime_fixture() { ret void }\n')
            if allocator:
                runtime = root / "runtime-template.ll"
                runtime.write_text(runtime.read_text() + 'declare ptr @malloc(i64)\n'
                                   'define ptr @pys_new(i64 %n) noinline {\n'
                                   '  %p = call ptr @malloc(i64 %n)\n  ret ptr %p\n}\n')
            subprocess.run([str(llvm / "opt"), "-passes=verify", str(root / "runtime-template.ll"), "-o",
                            str(root / "runtime-template.bc")], capture_output=True, check=True, timeout=15)
            published, emitted, manifest = base / "published-compiler", base / "published.ll", base / "published.json"
            for correct in (True, False):
                for mode in ("ir", "build"):
                    (root / f"{mode}.started").unlink(missing_ok=True)
                environment = {key: value for key, value in os.environ.items() if key != "STANDIN_BAD_RUNTIME"}
                if not correct:
                    environment["STANDIN_BAD_RUNTIME"] = "1"
                    emitted.write_bytes(b"previous sidecar must survive")
                    before = (published.read_bytes(), emitted.read_bytes())
                    manifest_before = manifest.read_bytes()
                work, report_path = base / f"work-{correct}", base / f"report-{correct}.json"
                result = subprocess.run([sys.executable, str(BENCH / "self_pipeline.py"), "--hosted",
                                         "--root", str(root), "--llvm", str(llvm), "--work", str(work),
                                         "--report", str(report_path), "--backend", backend, "--opt", "2",
                                         "--partitions", str(partitions), "--jobs", "2", "--overlap",
                                         "--output", str(published), "--emit-ir", str(emitted), "--publish-manifest", str(manifest),
                                         *(["--inline-threshold", "75"] if allocator else [])],
                                        env=environment, capture_output=True, text=True, timeout=30,
                                        start_new_session=True)
                self.assertEqual(result.returncode, 0 if correct else 1, result.stderr)
                report = json.loads(report_path.read_text())
                self.assertEqual(report["complete"], correct)
                self.assertEqual(report["backend_policy"], backend)
                if backend == "thinlto":
                    self.assertEqual(report["thinlto_job"]["prelink"], "summary")
                    self.assertIn("--inherited-group", report["stages"]["backend"]["command"])
                else:
                    self.assertEqual(report["backend"]["allocator"], allocator)
                    self.assertEqual([row["name"] for row in report["backend"]["steps"]],
                                     ["optimize", "late_inline", "codegen", "link"] if allocator else ["optimize_codegen", "link"])
                    if allocator:
                        commands = [row["command"] for row in report["backend"]["steps"]]
                        self.assertIn("-inline-threshold=75", commands[0])
                        self.assertIn("-passes=forceattrs,always-inline", commands[1])
                        self.assertIn("-disable-llvm-passes", commands[2])
                        self.assertTrue(all("-inline-threshold=75" not in command for command in commands[1:]))
                self.assertTrue(report["backend"]["complete"])
                self.assertTrue(report["witnesses"]["ir"]["matches"])
                self.assertEqual(report["witnesses"]["rt"]["matches"], correct)
                self.assertIn("rt_reference", report["witnesses"])
                if correct:
                    self.assertEqual(published.read_bytes(), (work / "backend/compiler").read_bytes())
                    self.assertEqual(emitted.read_bytes(), (work / "raw.ll").read_bytes())
                    generation = pipeline.resolve_publication(manifest, require_witnesses=True)
                    self.assertEqual(generation["compiler"].read_bytes(), published.read_bytes())
                    self.assertEqual(generation["raw_ir"].read_bytes(), emitted.read_bytes())
                    self.assertEqual(report["publication"]["manifest_sha256"], generation["manifest_sha256"])
                else:
                    self.assertEqual((published.read_bytes(), emitted.read_bytes()), before)
                    self.assertEqual(manifest.read_bytes(), manifest_before)
                    self.assertEqual(pipeline.resolve_publication(manifest)["compiler"], generation["compiler"])
            # Exercise the manifest as a real next-stage compiler input. The
            # legacy IR sidecar above is deliberately stale and is not consumed.
            if backend == "ordinary" and not allocator:
                next_manifest, next_report = base / "next.json", base / "next-report.json"
                result = subprocess.run([sys.executable, str(BENCH / "self_pipeline.py"),
                                         "--compiler-manifest", str(manifest), "--publish-manifest", str(next_manifest),
                                         "--root", str(root), "--llvm", str(llvm), "--work", str(base / "next-work"),
                                         "--report", str(next_report), "--backend", "ordinary", "--jobs", "2", "--overlap"],
                                        env={key: value for key, value in os.environ.items() if key != "STANDIN_BAD_RUNTIME"},
                                        capture_output=True, text=True, timeout=30, start_new_session=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                report = json.loads(next_report.read_text())
                self.assertTrue(report["complete"])
                self.assertEqual(report["compiler"], [str(generation["compiler"])])
                self.assertEqual(report["producer_publication"]["manifest_sha256"], generation["manifest_sha256"])
                self.assertEqual(pipeline.resolve_publication(next_manifest)["raw_ir"].read_bytes(),
                                 generation["raw_ir"].read_bytes())


if __name__ == "__main__":
    unittest.main()
