"""A reused bootstrap must never hide a failed build or cross source/toolchain/run identities."""
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

import check_bootstrap_tier as tier
import verification_bootstrap as bundle


class BootstrapBundleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / "checkout"
        self.root.mkdir()
        (self.root / "src").mkdir()
        for name in ("pystachy.py", "runtime.c", "runtime.py", "src/compiler.py", "test-input.txt"):
            (self.root / name).write_text("source\n")
        subprocess.run(["git", "init", "-q", str(self.root)], check=True, capture_output=True)
        self.git("add", ".")
        self.git("-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                 "commit", "-qm", "fixture")
        toolchain = self.base / "llvm"
        toolchain.mkdir()
        for tool in bundle.TOOLS:
            path = toolchain / tool
            path.write_text(f"#!/bin/sh\nprintf '%s\\n' '{tool} test version 18'\n")
            path.chmod(0o755)
        patch = mock.patch.dict(os.environ, {"PYSTACHY_LLVM": str(toolchain), "GITHUB_RUN_ID": "1234"})
        patch.start()
        self.addCleanup(patch.stop)
        self.current = bundle.identity(self.root)
        self.work = self.root / "build/verify"
        self.work.mkdir(parents=True)
        for prefix in ("stage", "rt"):
            for index in (1, 2, 3):
                (self.work / f"{prefix}{index}.ll").write_text(prefix + " IR\n")
        (self.work / "pystachy2").write_bytes(b"fixture native compiler\n")
        (self.work / "pystachy2").chmod(0o755)
        (self.work / "bootstrap.log").write_text("both fixed points passed\n")
        (self.work / "home").mkdir()
        (self.work / "home/runtime.cache").write_text("must not be exported")
        sources = {name: {"lines": 1, "sha256": bundle.digest(b"source\n")}
                   for name in ("pystachy.py", "runtime.c", "runtime.py", "src/compiler.py")}
        sources.update(suite_checks=10, mode_checks=6)
        self.report = {
            "project": "Pystachy", "group": "bootstrap", "result": "pass",
            "summary": {"steps": 1, "passed": 1, "failed": 0, "seconds": 120.5},
            "git": {"commit": self.current["commit"], "dirty": False}, "sources": sources,
            "platform": {"machine": self.current["machine"]},
            "toolchain": {"python": "Python " + self.current["python_version"],
                          "clang": self.current["tools"]["clang"], "llvm": self.current["tools"]["opt"]},
            "steps": [{"name": "bootstrap", "result": "pass", "seconds": 120.0,
                       "ir_identical": True, "ir_sha256": bundle.digest(b"stage IR\n"), "ir_lines": 1,
                       "native_compiler_bytes": len(b"fixture native compiler\n"),
                       "cpython_self_compile_seconds": 40.0, "native_self_compile_seconds": 3.0,
                       "log": "build/verify/bootstrap.log"}]}
        self.write_report(self.report)
        self.directory = self.base / "bundle"

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.root, check=True, capture_output=True)

    def write_report(self, report):
        (self.root / "build/verification.json").write_text(json.dumps(report))

    def export(self):
        result = bundle.export_bundle(self.directory, self.root)
        shutil.rmtree(self.work)
        return result

    def rewrite_bundle_report(self, mutate):
        path = self.directory / "verification.json"
        report = json.loads(path.read_text())
        mutate(report)
        path.write_text(json.dumps(report))
        manifest_path = self.directory / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["sha256"]["verification.json"] = bundle.digest(path.read_bytes())
        manifest_path.write_text(json.dumps(manifest))

    def assert_rejected_without_restore(self, error, regex):
        with self.assertRaisesRegex(error, regex):
            bundle.restore_bundle(self.directory, self.root)
        self.assertFalse((self.work / "pystachy2").exists())

    def test_round_trip_has_proof_timings_and_no_runtime_cache(self):
        bundle_id = self.export()
        producer = json.loads((self.root / "build/verification.json").read_text())["steps"][0]
        fields = bundle.restore_bundle(self.directory, self.root)
        self.assertEqual(fields["bootstrap_bundle_id"], bundle_id)
        self.assertEqual(producer["bootstrap_bundle_id"], bundle_id)
        self.assertFalse(producer["bootstrap_reused"])
        self.assertTrue(fields["bootstrap_reused"])
        self.assertTrue(fields["runtime_ir_identical"])
        self.assertEqual(fields["producer_seconds"], 120)
        self.assertEqual(fields["native_self_compile_seconds"], 3)
        self.assertEqual(json.loads((self.work / "bootstrap-reuse.json").read_text()), fields)
        self.assertNotIn("seconds", fields)
        self.assertEqual((self.work / "pystachy2").stat().st_mode & 0o777, 0o755)
        self.assertFalse((self.work / "home").exists())
        self.assertEqual(set(p.name for p in self.directory.iterdir()),
                         {*bundle.PAYLOAD, "verification.json", "manifest.json"})

    def test_relocated_checkout_and_failed_job_rerun_are_allowed(self):
        self.export()
        moved = self.base / "another-path"
        shutil.move(self.root, moved)
        with mock.patch.dict(os.environ, {"GITHUB_RUN_ATTEMPT": "2"}):
            fields = bundle.restore_bundle(self.directory, moved)
        self.assertTrue(fields["bootstrap_reused"])

    def test_tracked_noncompiler_source_change_is_rejected(self):
        self.export()
        (self.root / "test-input.txt").write_text("edited\n")
        self.assert_rejected_without_restore(ValueError, "identity differs")

    def test_same_size_same_timestamp_source_change_is_rejected(self):
        self.export()
        path = self.root / "test-input.txt"
        metadata = path.stat()
        path.write_text("change\n")
        os.utime(path, ns=(metadata.st_atime_ns, metadata.st_mtime_ns))
        self.assert_rejected_without_restore(ValueError, "identity differs")

    def test_tracked_symlinks_dangling_links_and_loops_are_bound_without_following(self):
        for name, target in (("link", "runtime.c"), ("dangling", "absent"),
                             ("loop1", "loop2"), ("loop2", "loop1")):
            (self.root / name).symlink_to(target)
        self.git("add", "link", "dangling", "loop1", "loop2")
        self.export()
        bundle.restore_bundle(self.directory, self.root)
        shutil.rmtree(self.work)
        (self.root / "dangling").unlink()
        (self.root / "dangling").symlink_to("another-absent-file")
        self.assert_rejected_without_restore(ValueError, "identity differs")

    def test_tracked_executable_bit_changes_identity(self):
        self.export()
        (self.root / "test-input.txt").chmod(0o755)
        self.assert_rejected_without_restore(ValueError, "identity differs")

    def test_commit_change_is_rejected_even_when_sources_match(self):
        self.export()
        self.git("-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                 "commit", "--allow-empty", "-qm", "different commit")
        self.assert_rejected_without_restore(ValueError, "identity differs")

    def test_other_workflow_run_is_rejected(self):
        self.export()
        with mock.patch.dict(os.environ, {"GITHUB_RUN_ID": "5678"}):
            self.assert_rejected_without_restore(ValueError, "identity differs")

    def test_toolchain_change_is_rejected(self):
        self.export()
        (self.base / "llvm/lli").write_text("#!/bin/sh\necho changed-version\n")
        self.assert_rejected_without_restore(ValueError, "identity differs")

    def test_platform_and_python_identity_changes_are_rejected(self):
        self.export()
        for key in ("machine", "libc", "os", "python", "python_implementation"):
            changed = copy.deepcopy(self.current)
            changed[key] = "different"
            with self.subTest(key=key), mock.patch.object(bundle, "identity", return_value=changed):
                self.assert_rejected_without_restore(ValueError, "identity differs")

    def test_missing_or_corrupt_payload_never_restores_compiler(self):
        self.export()
        for name in (*bundle.PAYLOAD, "verification.json"):
            path = self.directory / name
            original = path.read_bytes()
            with self.subTest(file=name, failure="missing"):
                path.unlink()
                self.assert_rejected_without_restore(OSError, name)
            with self.subTest(file=name, failure="corrupt"):
                path.write_bytes(original + b"corrupt")
                self.assert_rejected_without_restore(ValueError, "digest differs")
            path.write_bytes(original)

    def test_payload_symlink_and_traversal_name_are_rejected(self):
        self.export()
        path = self.directory / "pystachy2"
        contents = path.read_bytes()
        elsewhere = self.base / "elsewhere"
        elsewhere.write_bytes(contents)
        path.unlink()
        path.symlink_to(elsewhere)
        self.assert_rejected_without_restore(ValueError, "not a regular file")
        path.unlink()
        path.write_bytes(contents)
        manifest_path = self.directory / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["sha256"]["../elsewhere"] = bundle.digest(contents)
        manifest_path.write_text(json.dumps(manifest))
        self.assert_rejected_without_restore(ValueError, "unexpected bootstrap payload filenames")

    def test_failed_incomplete_or_reused_producer_cannot_be_exported(self):
        mutations = (
            lambda r: r.update(result="fail"),
            lambda r: r.update(group="native-0"),
            lambda r: r["summary"].update(passed=0),
            lambda r: r["steps"][0].update(result="fail"),
            lambda r: r["steps"][0].update(ir_identical=False),
            lambda r: r["steps"][0].update(bootstrap_reused=True),
            lambda r: r["steps"].append(copy.deepcopy(r["steps"][0])),
            lambda r: r["git"].update(commit="b" * 40),
            lambda r: r["toolchain"].update(clang="wrong"),
            lambda r: r["sources"]["runtime.c"].update(sha256="b" * 64),
        )
        for index, mutate in enumerate(mutations):
            report = copy.deepcopy(self.report)
            mutate(report)
            self.write_report(report)
            with self.subTest(case=index), self.assertRaises(ValueError):
                bundle.export_bundle(self.directory, self.root)
            self.assertFalse(self.directory.exists())

    def test_both_actual_fixed_points_are_required_at_export(self):
        for name in ("stage2.ll", "stage3.ll", "rt2.ll", "rt3.ll"):
            path = self.work / name
            original = path.read_bytes()
            path.write_bytes(b"bad IR\n")
            with self.subTest(file=name), self.assertRaisesRegex(ValueError, "fixed point differs"):
                bundle.export_bundle(self.directory, self.root)
            self.assertFalse(self.directory.exists())
            path.write_bytes(original)

    def test_report_cannot_claim_different_payload_evidence(self):
        self.export()
        original_report = (self.directory / "verification.json").read_bytes()
        original_manifest = (self.directory / "manifest.json").read_bytes()
        for key, value in (("ir_sha256", "d" * 64), ("ir_lines", 500),
                           ("runtime_ir_identical", False), ("runtime_ir_sha256", "d" * 64),
                           ("native_compiler_bytes", 500)):
            self.rewrite_bundle_report(lambda r, key=key, value=value: r["steps"][0].update({key: value}))
            with self.subTest(field=key):
                self.assert_rejected_without_restore(ValueError, "differs from producer evidence")
            (self.directory / "verification.json").write_bytes(original_report)
            (self.directory / "manifest.json").write_bytes(original_manifest)

    def test_failed_report_rejected_even_if_manifest_hash_matches(self):
        self.export()
        self.rewrite_bundle_report(lambda r: r.update(result="fail"))
        self.assert_rejected_without_restore(ValueError, "verification did not pass")

    def test_duplicate_json_keys_are_rejected(self):
        self.export()
        path = self.directory / "manifest.json"
        path.write_bytes(b'{"schema":1,' + path.read_bytes()[1:])
        self.assert_rejected_without_restore(ValueError, "duplicate JSON key")

    def test_existing_destination_executable_unchanged_on_rejection(self):
        self.export()
        self.work.mkdir()
        path = self.work / "pystachy2"
        path.write_bytes(b"old executable")
        (self.directory / "bootstrap.log").write_text("corrupted")
        with self.assertRaisesRegex(ValueError, "digest differs"):
            bundle.restore_bundle(self.directory, self.root)
        self.assertEqual(path.read_bytes(), b"old executable")

    def test_destination_symlink_is_rejected(self):
        self.export()
        elsewhere = self.base / "destination"
        elsewhere.mkdir()
        self.work.symlink_to(elsewhere, target_is_directory=True)
        self.assert_rejected_without_restore(ValueError, "destination must not be a symlink")
        self.assertEqual(list(elsewhere.iterdir()), [])

    def tier_outputs(self, root, env, log):
        # Only the expensive Make invocation is replaced. Bundle validation still
        # uses a real Git checkout, source hashes and the fixture LLVM executables.
        for prefix in ("stage", "rt"):
            for index in (1, 2, 3):
                (root / f"build/{prefix}{index}.ll").write_text(prefix + " IR\n")
        for name in ("pystachy", "build/pystachy2"):
            (root / name).write_bytes(b"candidate native compiler\n")
        log.write("fixture Make completed\n")

    def run_tier(self, action=None):
        with mock.patch.object(tier, "make_bootstrap", side_effect=action or self.tier_outputs):
            return tier.qualify(self.directory, self.root)

    def test_tier_qualification_preserves_standard_bundle_and_records_scope(self):
        bundle_id = bundle.export_bundle(self.directory, self.root)
        standard = {path: path.read_bytes() for parent in (self.directory, self.work)
                    for path in parent.rglob("*") if path.is_file()}
        standard[self.root / "build/verification.json"] = (self.root / "build/verification.json").read_bytes()
        inherited = {"PYSTACHY_AOT_OPT": "0", "PYSTACHY_CFLAGS": "-O0", "PYSTACHY_OPT": "-all",
                     "MAKEFLAGS": "n", "MAKEFILES": "/missing/makefile"}

        def build(root, env, log):
            self.assertEqual(env["PYSTACHY_HOME"], str(root))
            self.assertEqual(env["PYSTACHY_LLVM"], os.environ["PYSTACHY_LLVM"])
            self.assertEqual(env["PYSTACHY_JOBS"], "2")
            self.assertTrue(Path(env["PYSTACHY_CACHE"]).is_dir())
            self.assertEqual(Path(env["PYSTACHY_CACHE"]).parent, root / "build/bootstrap-tier")
            for key in inherited:
                self.assertNotIn(key, env)
            self.tier_outputs(root, env, log)

        with mock.patch.dict(os.environ, inherited):
            report = self.run_tier(build)
        self.assertEqual(report["result"], "pass")
        self.assertEqual(report["identity"], self.current)
        self.assertEqual(report["standard_bootstrap_bundle_id"], bundle_id)
        self.assertEqual(report["temporary_aot_opt"], "1")
        self.assertEqual(report["final_aot_opt"], "2")
        self.assertEqual(len(report["witnesses"]), 6)
        self.assertFalse(report["final_compiler_bytes_identical"])
        self.assertEqual(report["performance_conclusion"], "inconclusive")
        self.assertEqual(json.loads((self.root / "build/bootstrap-tier/report.json").read_bytes()), report)
        for path, data in standard.items():
            self.assertEqual(path.read_bytes(), data, path)
        self.assertFalse((self.work / "bootstrap-reuse.json").exists())

    def test_tier_qualification_rejects_stale_identity_before_make(self):
        bundle.export_bundle(self.directory, self.root)
        (self.root / "test-input.txt").write_text("edited\n")
        with mock.patch.object(tier, "make_bootstrap") as build:
            with self.assertRaisesRegex(ValueError, "identity differs"):
                tier.qualify(self.directory, self.root)
            build.assert_not_called()
        self.assertEqual(json.loads((self.root / "build/bootstrap-tier/report.json").read_bytes())["result"], "fail")

    def test_tier_qualification_requires_all_witnesses_and_the_installed_final(self):
        bundle.export_bundle(self.directory, self.root)
        paths = [f"build/{prefix}{index}.ll" for prefix in ("stage", "rt") for index in (1, 2, 3)]
        for name in (*paths, "pystachy"):
            def build(root, env, log, name=name):
                self.tier_outputs(root, env, log)
                (root / name).write_bytes(b"wrong result\n")
            with self.subTest(file=name), self.assertRaisesRegex(ValueError, "differs"):
                self.run_tier(build)

    def test_tier_qualification_build_failure_cannot_reuse_previous_success(self):
        bundle.export_bundle(self.directory, self.root)
        self.run_tier()
        with mock.patch.object(tier, "make_bootstrap", side_effect=subprocess.CalledProcessError(9, ["make"])):
            with self.assertRaises(subprocess.CalledProcessError):
                tier.qualify(self.directory, self.root)
        report = json.loads((self.root / "build/bootstrap-tier/report.json").read_bytes())
        self.assertEqual(report["result"], "fail")
        self.assertIn("exit status 9", report["error"])

    def test_tier_qualification_rechecks_source_bundle_and_producer_report(self):
        bundle.export_bundle(self.directory, self.root)
        original = {path: path.read_bytes() for path in self.directory.iterdir()}
        original.update({self.root / "runtime.c": b"source\n",
                         self.root / "build/verification.json": (self.root / "build/verification.json").read_bytes()})
        for change, error in (("source", "identity differs"), ("bundle", "bundle changed"),
                              ("report", "verification report changed")):
            def build(root, env, log, change=change):
                self.tier_outputs(root, env, log)
                if change == "source":
                    (root / "runtime.c").write_text("edited\n")
                elif change == "bundle":
                    self.rewrite_bundle_report(lambda report: report["steps"][0].update(seconds=121))
                else:
                    (root / "build/verification.json").write_text("changed report\n")
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, error):
                self.run_tier(build)
            for path, data in original.items():
                path.write_bytes(data)


if __name__ == "__main__":
    unittest.main()
