"""ThinLTO resolution controls; optional LLVM 18 import/link execution proof.

Default tests need no LLVM. Set PYSTACHY_TEST_LLVM to the matching bin directory
to prove cross-partition importing, native behavior and worker-count parity.
"""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / "bench/compiler_host"
sys.path.insert(0, str(BENCH))
SPEC = importlib.util.spec_from_file_location("partition_import", BENCH / "partition_import.py")
imports = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(imports)


def table(rows, triple="x86_64-pc-linux-gnu"):
    return imports.parse_symtab(f"version: 3\nproducer: 18.1.3\ntarget triple: {triple}\n"
                                f"source filename: probe\ndependent libraries:\n{rows}\n")


def resolutions(*rows):
    args, counts = imports.symbol_resolutions([(f"part-{i}.bc", table(row)) for i, row in enumerate(rows)])
    return {tuple(value.split(",")[:2]): value.split(",")[2] for value in args[1::2]}, counts


class ResolutionTests(unittest.TestCase):
    def test_cross_partition_hidden_calls_and_library_references(self):
        actual, counts = resolutions("D------X main\nHU-----X helper\nDU-----X puts", "H------X helper")
        self.assertEqual(actual, {("part-0.bc", "main"): "plx", ("part-0.bc", "helper"): "l",
                                  ("part-0.bc", "puts"): "", ("part-1.bc", "helper"): "pl"})
        self.assertEqual(counts["hidden_definitions"], 1)
        self.assertEqual(counts["visible_definitions"], 1)
        self.assertEqual(counts["external_symbols"], 1)

    def test_linkonce_constant_in_one_comdat_is_supported(self):
        actual, counts = resolutions("D------X main\nD--W-O-- table\n         comdat any table")
        self.assertEqual(actual["part-0.bc", "table"], "plx")
        self.assertEqual(counts["weak_definitions"], 1)

    def test_weak_definitions_follow_input_order_and_strong_prevails(self):
        weak = "D--W-O-- value"
        actual, _ = resolutions(f"D------X main\n{weak}", weak)
        self.assertEqual(actual["part-0.bc", "value"], "plx")
        self.assertEqual(actual["part-1.bc", "value"], "lx")
        actual, _ = resolutions(f"D------X main\n{weak}", "D------- value")
        self.assertEqual(actual["part-0.bc", "value"], "lx")
        self.assertEqual(actual["part-1.bc", "value"], "plx")

    def test_ambiguous_or_unsupported_resolutions_fail(self):
        cases = [
            ("D------X main\nD------- value", "D------- value"),
            ("D------X main\nD--W-O-- value\n         comdat any group",
             "D--W-O-- value\n         comdat any group"),
            ("D------X main\nD--W-O-- value\n         comdat largest group",),
            ("D------X main\nHU-----X missing",),
            ("D------X main\nD------X main",),
            ("D------X main\nD-C----- common",),
            ("D------X main\nD---I--X alias",),
            ("D------X main\nD-----T- tls",),
            ("D------- value",),
        ]
        for rows in cases:
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                resolutions(*rows)

    def test_actual_allocator_symbol_needs_the_late_inline_contract(self):
        for flags in ("DU-----X", "D------X"):
            with self.subTest(flags=flags), self.assertRaisesRegex(ValueError, "allocator contract"):
                resolutions(f"D------X main\n{flags} pys_new")
        actual, _ = resolutions("D------X main\nD------X mentions_pys_new")
        self.assertIn(("part-0.bc", "mentions_pys_new"), actual)

    def test_unknown_symbol_table_formats_fail(self):
        for rows in ("D------- bad,name", "D------- bad name", "D----Q-- value", "unrecognized record",
                     "         comdat any orphan"):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                table(rows)
        for triple in ("aarch64-unknown-linux-gnu", "x86_64-apple-darwin", "x86_64-pc-windows-msvc"):
            with self.subTest(triple=triple), self.assertRaisesRegex(ValueError, "GNU/Linux"):
                table("D------X main", triple)
        for replacement in ("producer: 19.1.0", 'dependent libraries: "opaque"'):
            with self.subTest(replacement=replacement), self.assertRaises(ValueError):
                imports.parse_symtab("version: 3\nproducer: 18.1.3\ntarget triple: x86_64-pc-linux-gnu\n"
                                     f"source filename: probe\ndependent libraries:\n{replacement}\n")


class InputTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)

    def test_llvm_text_inside_strings_does_not_trigger_assembly_gate(self):
        path = self.directory / "input.ll"
        path.write_text('@s = constant [32 x i8] c"asm @pys_new( ; module asm\\00"\n'
                        '@asm = internal global i32 0\n'
                        'define i32 @main() {\n  ret i32 0\n}\n')
        self.assertEqual(imports.inspect_ir(path, reject_assembly=True)["function_definitions"], 1)
        for line in ('module asm "hidden: ret"', '%r = call i32 asm "", "=r"()'):
            path.write_text(line + "\n")
            with self.subTest(line=line), self.assertRaisesRegex(ValueError, "assembly"):
                imports.inspect_ir(path, reject_assembly=True)

    def test_response_file_preserves_literal_arguments(self):
        argv = ["-r", "file with 'quote.bc,symbol$part,plx", "$(literal)", r"back\slash", "double\"quote"]
        path = self.directory / "response"
        imports.write_response(path, argv)
        self.assertEqual(shlex.split(path.read_text()), argv)

    def test_prelink_preserves_owned_linkonce_definitions_without_changing_text(self):
        source, destination = self.directory / "input.ll", self.directory / "prepared.ll"
        text = ('@factor = linkonce_odr constant i32 3\n'
                '@"x = linkonce" = linkonce global i32 4\n'
                'define linkonce_odr i32 @helper() {\n  ret i32 5\n}\n'
                '@text = private constant [18 x i8] c"linkonce_odr\\00"\n')
        source.write_text(text)
        self.assertEqual(imports.preserve_linkonce(source, destination), 3)
        self.assertEqual(source.read_text(), text)
        self.assertEqual(destination.read_text(),
                         text.replace('= linkonce_odr constant', '= weak_odr constant')
                             .replace('= linkonce global', '= weak global')
                             .replace('define linkonce_odr', 'define weak_odr'))
        self.assertEqual(imports.inspect_ir(source)["linkonce_definitions"], 3)

    def test_outputs_cannot_overwrite_inputs_or_existing_artifacts(self):
        snapshot, root = self.directory / "snapshot", self.directory / "source"
        snapshot.mkdir()
        root.mkdir()
        for name in imports.INPUTS:
            (snapshot / name).write_bytes(b"input must survive")
        work, report = self.directory / "work", self.directory / "report.json"
        imports.validate_paths(snapshot, root, work, report)
        for output in (snapshot / "linked.bc", root / "new.json", work / "report.json"):
            with self.subTest(report=output), self.assertRaises(ValueError):
                imports.validate_paths(snapshot, root, work, output)
        report.write_text("previous report")
        with self.assertRaisesRegex(ValueError, "destination must be new"):
            imports.validate_paths(snapshot, root, work, report)
        self.assertEqual(report.read_text(), "previous report")
        with self.assertRaises(ValueError):
            imports.validate_paths(snapshot, root, root / "build", self.directory / "other.json")
        self.assertEqual((snapshot / "linked.bc").read_bytes(), b"input must survive")

    def test_worker_and_timeout_bounds(self):
        imports.validate_settings(4, 4, "summary", 600)
        imports.validate_settings(2, 1, "o2", .5)
        for settings in ((0, 1, "summary", 1), (1, 9, "summary", 1),
                         (9, 1, "summary", 1), (1, 1, "unknown", 1),
                         (1, 1, "summary", 0), (1, 1, "summary", float("inf")),
                         (1, 1, "summary", float("nan"))):
            with self.subTest(settings=settings), self.assertRaises(ValueError):
                imports.validate_settings(*settings)


@unittest.skipUnless(os.getenv("PYSTACHY_TEST_LLVM"), "set PYSTACHY_TEST_LLVM for LLVM 18 importing checks")
class RealLLVMTests(unittest.TestCase):
    def test_public_harness_requires_both_frozen_witnesses(self):
        llvm = Path(os.environ["PYSTACHY_TEST_LLVM"]).resolve()
        with tempfile.TemporaryDirectory(prefix="pystachy-import-witness-") as directory:
            base = Path(directory)
            snapshot, source = base / "snapshot", base / "source"
            snapshot.mkdir()
            source.mkdir()
            for filename in ("pystachy.py", "runtime.py", "runtime.c"):
                (source / filename).write_text("frozen test source\n")
            # A tiny stand-in exercises publication and the real process tree;
            # it is not evidence of Pystachy compiler correctness/performance.
            standin = base / "standin.c"
            standin.write_text('''#include <stdio.h>
int main(int argc, char **argv) {
    if (argc != 5) return 2;
    FILE *out = fopen(argv[4], "w");
    if (!out) return 3;
    fputs(argv[1][0] == 'r' ? "runtime\\n" : "compiler\\n", out);
    return fclose(out);
}
''')
            subprocess.run([str(llvm / "clang"), "-O0", "-c", "-emit-llvm", str(standin),
                            "-o", str(snapshot / "linked.bc")], capture_output=True, check=True, timeout=15)
            (snapshot / "seed-rt.ll").write_text("runtime\n")
            for correct in (True, False):
                (snapshot / "raw.ll").write_text("compiler\n" if correct else "mismatched witness\n")
                report_path = base / f"report-{correct}.json"
                result = subprocess.run([sys.executable, str(BENCH / "partition_import.py"),
                                         "--snapshot", str(snapshot), "--source-root", str(source),
                                         "--llvm", str(llvm), "--work", str(base / f"work-{correct}"),
                                         "--report", str(report_path), "--partitions", "2", "--jobs", "2",
                                         "--execution-samples", "1", "--timeout", "15"],
                                        capture_output=True, text=True, timeout=30, start_new_session=True)
                self.assertEqual(result.returncode, 0 if correct else 1, result.stderr)
                report = json.loads(report_path.read_text())
                self.assertEqual(report["complete"], correct)
                self.assertEqual(report["witnesses"]["ir"]["matches"], correct)
                if correct:
                    self.assertTrue(report["witnesses"]["rt"]["matches"])
                    self.assertEqual(len(report["execution"]), 1)
                    self.assertTrue(report["execution"][0]["matches"])
                    self.assertEqual(report["settings"]["jobs"], 2)
                else:
                    self.assertEqual(report["error"], "ir compiler witness mismatch")
                    self.assertEqual(report["execution"], [])

    def test_importing_native_result_and_worker_count_parity(self):
        llvm = Path(os.environ["PYSTACHY_TEST_LLVM"]).resolve()
        with tempfile.TemporaryDirectory(prefix="pystachy import '") as directory:
            root = Path(directory)
            source, bitcode = root / "input.ll", root / "input.bc"
            source.write_text('''target triple = "x86_64-pc-linux-gnu"
@value = internal global i32 7
@factor = linkonce_odr constant i32 3
@compiler_text = private constant [10 x i8] c"@pys_new(\\00"
define internal i32 @multiply(i32 %x) {
entry:
  %factor = load i32, ptr @factor
  %result = mul i32 %x, %factor
  ret i32 %result
}
define i32 @main() {
entry:
  %x = load i32, ptr @value
  %result = call i32 @multiply(i32 %x)
  ret i32 %result
}
''')
            subprocess.run([str(llvm / "opt"), "-passes=verify", str(source), "-o", str(bitcode)],
                           capture_output=True, check=True, timeout=15)
            binaries = []
            for prelink, jobs in (("summary", 1), ("summary", 2), ("o2", 2)):
                work = root / f"job-{prelink}-{jobs}"
                work.mkdir()
                job_path = work / "job.json"
                imports.atomic_json(job_path, {"version": 1, "llvm": str(llvm), "tools": imports.tool_identity(llvm),
                                               "input": str(bitcode), "input_sha256": imports.sha(bitcode),
                                               "partitions": 2, "jobs": jobs, "prelink": prelink, "timeout": 15})
                result = subprocess.run([sys.executable, str(BENCH / "partition_import.py"),
                                         "--backend-job", str(job_path)], capture_output=True, text=True,
                                        timeout=30, start_new_session=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                report = json.loads((work / "build.json").read_text())
                self.assertTrue(report["complete"])
                self.assertGreater(report["resolution_counts"]["weak_definitions"], 0)
                if prelink == "o2":
                    self.assertEqual(sum(report["linkonce_promoted"]), 1)
                native = subprocess.run([str(work / "compiler")], timeout=5)
                self.assertEqual(native.returncode, 21)
                imported = 0
                for path in work.glob("thin.o.*.3.import.bc"):
                    output = path.with_suffix(".ll")
                    subprocess.run([str(llvm / "llvm-dis"), str(path), "-o", str(output)],
                                   capture_output=True, check=True, timeout=15)
                    imported += imports.inspect_ir(output)["available_externally_definitions"]
                if prelink == "summary":
                    self.assertGreater(imported, 0)
                    binaries.append(imports.sha(work / "compiler"))
            self.assertEqual(binaries[0], binaries[1])


if __name__ == "__main__":
    unittest.main()
