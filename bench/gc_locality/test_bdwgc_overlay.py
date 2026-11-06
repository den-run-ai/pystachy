"""Overlay filesystem isolation checks; no compiler or BDWGC dependency needed."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent


class OverlayPathTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.work = Path(temporary.name).resolve()
        self.source = self.work / "source"
        self.source.mkdir()
        self.runtime = (HERE.parents[1] / "runtime.c").read_bytes()
        (self.source / "runtime.c").write_bytes(self.runtime)
        self.include = self.work / "include"
        (self.include / "gc").mkdir(parents=True)
        # The generator hashes these inputs; it does not compile or link them.
        for name in ("gc.h", "gc_mark.h"):
            (self.include / "gc" / name).write_text("/* fixture header */\n")
        self.library = self.work / "libgc.a"
        self.library.write_bytes(b"fixture library")

    def invoke(self, output):
        return subprocess.run(
            [sys.executable, "-I", str(HERE / "bdwgc_overlay.py"),
             "--source", str(self.source), "--output", str(output),
             "--include", str(self.include), "--library", str(self.library)],
            capture_output=True, text=True, timeout=30)

    def test_output_inside_source_is_rejected_through_symlink_ancestor(self):
        alias = self.work / "source-alias"
        alias.symlink_to(self.source, target_is_directory=True)
        for parent in (self.source, alias):
            with self.subTest(parent=parent):
                result = self.invoke(parent / "overlay")
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn("place --output outside the source tree", result.stderr)
                self.assertEqual(list(self.source.iterdir()), [self.source / "runtime.c"])
                self.assertEqual((self.source / "runtime.c").read_bytes(), self.runtime)

    def test_external_symlink_ancestor_uses_canonical_output(self):
        destination = self.work / "destination"
        destination.mkdir()
        alias = self.work / "destination-alias"
        alias.symlink_to(destination, target_is_directory=True)
        result = self.invoke(alias / "overlay")
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest = json.loads(result.stdout)
        output = destination / "overlay"
        self.assertEqual(manifest["overlay"], str(output))
        self.assertEqual(manifest["environment"]["PYSTACHY_HOME"], str(output))
        self.assertEqual(json.loads((output / "bdwgc-manifest.json").read_text()), manifest)
        self.assertEqual(list(self.source.iterdir()), [self.source / "runtime.c"])
        self.assertEqual((self.source / "runtime.c").read_bytes(), self.runtime)

    def test_existing_output_and_dangling_link_are_not_reused(self):
        existing = self.work / "existing"
        existing.mkdir()
        sentinel = existing / "keep"
        sentinel.write_text("unchanged")
        missing = self.work / "missing"
        dangling = self.work / "dangling"
        dangling.symlink_to(missing, target_is_directory=True)
        for output in (existing, dangling):
            with self.subTest(output=output):
                result = self.invoke(output)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn("--output must not exist", result.stderr)
                self.assertEqual(sentinel.read_text(), "unchanged")
                self.assertFalse(missing.exists())


if __name__ == "__main__":
    unittest.main()
