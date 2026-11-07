#!/usr/bin/env python3
"""Native cache retention and lock-lifetime regressions, independent of LLVM."""
from __future__ import annotations

from contextlib import contextmanager
import fcntl
import multiprocessing
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.pystachy_compiler import program_cache as pc


@contextmanager
def bucket_lock(cache: Path, context: str):
    path = pc.lock_path(str(cache), context)
    if not path:
        raise AssertionError("no safe cache lock")
    saved = -1
    try:
        saved = os.dup(9)
    except OSError:
        pass
    fd = os.open(path, os.O_RDWR)
    if fd != 9:
        os.dup2(fd, 9)
        os.close(fd)
    fcntl.flock(9, fcntl.LOCK_EX | fcntl.LOCK_NB)
    try:
        yield path
    finally:
        fcntl.flock(9, fcntl.LOCK_UN)
        os.close(9)
        if saved >= 0:
            os.dup2(saved, 9)
            os.close(saved)


def concurrent_publish(cache: str, context: str, source: str, executable: str, gate):
    with bucket_lock(Path(cache), context):
        pc.start()
        pc.track_source(source, Path(source).read_text())
        gate.wait(10)
        pc.publish(cache, context, executable)


class ProgramCacheLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.cache = self.base / "cache"
        self.source = self.base / "source.py"
        self.source.write_text("print(42)\n")
        self.executable = self.base / "program"
        self.executable.write_bytes(b"\x7fELF" + b"native program" * 32)
        self.executable.chmod(0o700)
        self.contexts = []
        buckets = set()
        for i in range(1000):
            context = "lifecycle-context-" + str(i)
            bucket = pc.fnv(context)[:2]
            if bucket not in buckets:
                self.contexts.append(context)
                buckets.add(bucket)
                if len(self.contexts) == 12:
                    break
        self.assertEqual(len(self.contexts), 12)
        pc.MEMO_ROOT[0] = ""
        pc.STATIC_MEMO.clear()
        pc.start()

    def tearDown(self):
        pc.stop()
        self.temp.cleanup()

    @property
    def root(self):
        return self.cache / "program-v2"

    def manifest(self, context):
        return self.root / (pc.fnv(context) + ".manifest")

    def publish(self, context):
        with bucket_lock(self.cache, context):
            pc.start()
            pc.track_source(str(self.source), self.source.read_text())
            return pc.publish(str(self.cache), context, str(self.executable))

    def lookup(self, context):
        with bucket_lock(self.cache, context):
            return pc.lookup(str(self.cache), context)

    def stage(self, context, suffix="interrupted"):
        stage = self.root / ("stage-" + pc.fnv(context) + "-" + suffix)
        stage.mkdir()
        for name in ("program", "manifest", "memo"):
            (stage / name).write_bytes(b"partial")
        return stage

    @contextmanager
    def external_lock(self, context):
        path = pc.lock_path(str(self.cache), context)
        script = "import fcntl,sys; f=open(sys.argv[1],'r+'); fcntl.flock(f,fcntl.LOCK_EX); print('ready',flush=True); sys.stdin.read()"
        child = subprocess.Popen([sys.executable, "-c", script, path], stdin=subprocess.PIPE,
                                 stdout=subprocess.PIPE, text=True)
        self.assertEqual(child.stdout.readline(), "ready\n")
        try:
            yield child
        finally:
            child.communicate(timeout=10)
            self.assertEqual(child.returncode, 0)

    def test_locks_are_stable_and_bucket_count_is_bounded(self):
        paths = {pc.lock_path(str(self.cache), "context " + str(i)) for i in range(600)}
        self.assertLessEqual(len(paths), 256)
        self.assertNotIn("", paths)
        context = self.contexts[0]
        path = Path(pc.lock_path(str(self.cache), context))
        inode = path.stat().st_ino
        self.publish(context)
        self.lookup(context)
        self.assertEqual(path.stat().st_ino, inode)

    def test_descriptor_identity_matches_only_held_bucket(self):
        first, other = self.contexts[:2]
        self.assertFalse(pc.lock_held(str(self.cache), first))
        with bucket_lock(self.cache, first):
            self.assertTrue(pc.lock_held(str(self.cache), first))
            self.assertFalse(pc.lock_held(str(self.cache), other))
        self.assertFalse(pc.lock_held(str(self.cache), first))

    def test_symlink_lock_does_not_truncate_target(self):
        context = self.contexts[0]
        path = Path(pc.lock_path(str(self.cache), context))
        path.unlink()
        outside = self.base / "outside"
        outside.write_text("preserve me")
        path.symlink_to(outside)
        self.assertEqual(pc.lock_path(str(self.cache), context), "")
        self.assertEqual(outside.read_text(), "preserve me")

    def test_entry_limit_evicts_least_recently_used_after_hit(self):
        first, second, third = self.contexts[:3]
        with patch.object(pc, "MAX_CACHE_ENTRIES", 2):
            self.assertTrue(self.publish(first))
            self.assertTrue(self.publish(second))
            os.utime(self.manifest(first), (1, 1))
            os.utime(self.manifest(second), (2, 2))
            self.assertTrue(self.lookup(first))
            self.assertTrue(self.publish(third))
        self.assertTrue(self.lookup(first))
        self.assertEqual(self.lookup(second), "")
        self.assertTrue(self.lookup(third))
        self.assertEqual(len(list(self.root.glob("*.manifest"))), 2)

    def test_byte_limit_includes_manifest_and_executable(self):
        first, second = self.contexts[:2]
        self.assertTrue(self.publish(first))
        one = sum(p.stat().st_size for p in self.root.iterdir() if pc._entry_key(p.name))
        with patch.object(pc, "MAX_CACHE_BYTES", one + 20):
            self.assertTrue(self.publish(second))
        total = sum(p.stat().st_size for p in self.root.iterdir() if pc._entry_key(p.name))
        self.assertLessEqual(total, one + 20)
        self.assertEqual(self.lookup(first), "")
        self.assertTrue(self.lookup(second))

    def test_oversized_artifact_declines_without_copying_stage(self):
        with patch.object(pc, "MAX_CACHE_BYTES", 1):
            self.assertEqual(self.publish(self.contexts[0]), "")
        self.assertEqual(list(self.root.glob("*.exe")), [])
        self.assertEqual(list(self.root.glob("stage-*")), [])

    def test_active_entry_is_retained_and_new_entry_declines(self):
        first, second = self.contexts[:2]
        old = self.publish(first)
        with self.external_lock(first), patch.object(pc, "MAX_CACHE_ENTRIES", 1):
            self.assertEqual(self.publish(second), "")
            self.assertTrue(Path(old).is_file())
        self.assertEqual(self.lookup(first), old)
        self.assertEqual(self.lookup(second), "")

    def test_identical_binary_contents_are_owned_by_each_context(self):
        first, second, third = self.contexts[:3]
        a = self.publish(first)
        b = self.publish(second)
        self.assertNotEqual(a, b)
        self.assertEqual(Path(a).read_bytes(), Path(b).read_bytes())
        os.utime(self.manifest(first), (1, 1))
        os.utime(self.manifest(second), (2, 2))
        with patch.object(pc, "MAX_CACHE_ENTRIES", 2):
            self.assertTrue(self.publish(third))
        self.assertFalse(Path(a).exists())
        self.assertEqual(self.lookup(second), b)

    def test_interrupted_stage_is_cleaned_on_next_bucket_lookup(self):
        context = self.contexts[0]
        pc.lock_path(str(self.cache), context)
        stage = self.stage(context)
        self.assertEqual(self.lookup(context), "")
        self.assertFalse(stage.exists())

    def test_killed_owner_releases_lock_and_its_stage_is_recovered(self):
        context = self.contexts[0]
        path = pc.lock_path(str(self.cache), context)
        stage = self.stage(context)
        script = "import fcntl,sys; f=open(sys.argv[1],'r+'); fcntl.flock(f,fcntl.LOCK_EX); print('ready',flush=True); sys.stdin.read()"
        child = subprocess.Popen([sys.executable, "-c", script, path], stdin=subprocess.PIPE,
                                 stdout=subprocess.PIPE, text=True)
        self.assertEqual(child.stdout.readline(), "ready\n")
        child.kill()
        child.communicate(timeout=10)
        with bucket_lock(self.cache, context):
            pc.cleanup(str(self.cache), context)
        self.assertFalse(stage.exists())
        self.assertTrue(Path(path).is_file())

    def test_failed_manifest_publications_do_not_accumulate_orphan_binaries(self):
        replace = pc.os.replace

        def fail_manifest(source, target):
            if target.endswith(".manifest"):
                raise OSError("manifest rename failed")
            replace(source, target)

        with patch.object(pc, "MAX_CACHE_BYTES", 1024), patch.object(pc, "MAX_CACHE_ENTRIES", 2), \
                patch.object(pc.os, "replace", side_effect=fail_manifest):
            for context in self.contexts[:4]:
                self.assertEqual(self.publish(context), "")
        self.assertEqual(list(self.root.glob("*.exe")), [])
        self.assertEqual(list(self.root.glob("*.manifest")), [])
        self.assertEqual(list(self.root.glob("stage-*")), [])

    def failed_replacement_keeps_previous_entry(self, change_binary):
        context = self.contexts[0]
        previous = self.publish(context)
        manifest = self.manifest(context).read_bytes()
        binary = Path(previous).read_bytes()
        if change_binary:
            self.executable.write_bytes(b"different executable contents")
        replace = pc.os.replace

        def fail_manifest(source, target):
            if target.endswith(".manifest"):
                raise OSError("manifest rename failed")
            replace(source, target)

        with patch.object(pc.os, "replace", side_effect=fail_manifest):
            self.assertEqual(self.publish(context), "")
        self.assertEqual(self.manifest(context).read_bytes(), manifest)
        self.assertEqual(Path(previous).read_bytes(), binary)
        self.assertEqual(self.lookup(context), previous)
        self.assertEqual(list(self.root.glob("*.exe")), [Path(previous)])
        self.assertEqual(list(self.root.glob("stage-*")), [])

    def test_failed_new_digest_replacement_preserves_previous_entry(self):
        self.failed_replacement_keeps_previous_entry(True)

    def test_failed_same_digest_replacement_preserves_previous_entry(self):
        self.failed_replacement_keeps_previous_entry(False)

    def test_failed_post_publication_census_removes_new_entry(self):
        context = self.contexts[0]
        with patch.object(pc, "_prune", side_effect=OSError("unreadable census")):
            self.assertEqual(self.publish(context), "")
        self.assertFalse(self.manifest(context).exists())
        self.assertEqual(list(self.root.glob("*.exe")), [])

    def test_active_other_stage_is_skipped_then_reclaimed(self):
        first, second, third = self.contexts[:3]
        pc.lock_path(str(self.cache), first)
        stage = self.stage(first)
        with self.external_lock(first):
            self.assertTrue(self.publish(second))
            self.assertTrue((stage / "program").exists())
        self.assertTrue(self.publish(third))
        self.assertFalse(stage.exists())

    def test_stage_symlink_never_removes_outside_files(self):
        first, second = self.contexts[:2]
        pc.lock_path(str(self.cache), first)
        outside = self.base / "outside"
        outside.mkdir()
        (outside / "program").write_text("sentinel")
        stage = self.root / ("stage-" + pc.fnv(first) + "-symlink")
        stage.symlink_to(outside, target_is_directory=True)
        self.assertTrue(self.publish(second))
        self.assertEqual((outside / "program").read_text(), "sentinel")
        self.assertTrue(stage.is_symlink())

    def test_corrupt_manifest_does_not_retain_unreferenced_executables(self):
        context = self.contexts[0]
        original = self.publish(context)
        self.manifest(context).write_bytes(b"partial manifest")
        orphan = self.root / (pc.fnv(context) + "-0123456789abcdef.exe")
        orphan.write_bytes(b"partial executable")
        self.assertEqual(self.lookup(context), "")
        self.assertFalse(Path(original).exists())
        self.assertFalse(orphan.exists())

    def test_open_executable_remains_readable_after_eviction(self):
        first, second = self.contexts[:2]
        old = self.publish(first)
        with bucket_lock(self.cache, first):
            self.assertEqual(pc.lookup(str(self.cache), first), old)
            fd = os.open(old, os.O_RDONLY)
        try:
            with patch.object(pc, "MAX_CACHE_ENTRIES", 1):
                self.assertTrue(self.publish(second))
            self.assertFalse(Path(old).exists())
            self.assertEqual(os.read(fd, 4096), self.executable.read_bytes())
        finally:
            os.close(fd)

    def test_concurrent_publication_finishes_with_bounded_entries(self):
        contexts = self.contexts[:8]
        ctx = multiprocessing.get_context("fork")
        gate = ctx.Barrier(len(contexts))
        with patch.object(pc, "MAX_CACHE_ENTRIES", 2):
            children = [ctx.Process(target=concurrent_publish, args=(str(self.cache), context,
                        str(self.source), str(self.executable), gate)) for context in contexts]
            for child in children:
                child.start()
            for child in children:
                child.join(20)
                self.assertEqual(child.exitcode, 0)
        self.assertLessEqual(len(list(self.root.glob("*.manifest"))), 2)
        self.assertLessEqual(len(list(self.root.glob("*.exe"))), 2)
        self.assertEqual(list(self.root.glob("stage-*")), [])


if __name__ == "__main__":
    unittest.main()
