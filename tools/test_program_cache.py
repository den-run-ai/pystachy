"""Complete-program cache invalidation, integrity and publication checks."""
import multiprocessing
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.pystachy_compiler import program_cache as pc


def writer(cache, source, executable, context, results):
    pc.start()
    with open(source, encoding="latin-1") as stream:
        pc.track_source(source, stream.read())
    results.put(pc.publish(cache, context, executable))


@unittest.skipUnless(sys.platform == "linux", "the initial native cache supports Linux")
class ProgramCacheTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.cache = self.root / "cache"
        self.source = self.root / "main.py"
        self.source.write_text("print(42)\n")
        self.executable = self.root / "native"
        self.executable.write_bytes(b"\x7fELF\x00\xff\x80\r\nprototype\n")
        self.executable.chmod(0o700)
        self.context = "compiler/runtime/toolchain/options/import-path identity"
        pc.STATIC_MEMO.clear()
        pc.MEMO_ROOT[0] = ""
        pc.start()
        self.addCleanup(pc.stop)

    def remember(self, path=None):
        path = self.source if path is None else path
        with path.open(encoding="latin-1") as stream:
            pc.track_source(str(path), stream.read())

    def publish(self):
        self.remember()
        result = pc.publish(str(self.cache), self.context, str(self.executable))
        self.assertTrue(result)
        return Path(result)

    def lookup(self):
        return pc.lookup(str(self.cache), self.context)

    def index(self):
        return self.cache / "program-v2" / (pc.fnv(self.context) + ".manifest")

    def test_unchanged_program_reuses_exact_executable(self):
        target = self.publish()
        self.assertEqual(self.lookup(), str(target))
        self.assertEqual(target.read_bytes(), self.executable.read_bytes())
        self.assertEqual(target.stat().st_mode & 0o777, 0o700)
        self.assertEqual(target.parent.stat().st_mode & 0o777, 0o700)
        self.assertEqual(list(target.parent.glob("stage-*")), [])

    def test_hit_skips_optional_hash_memo_but_miss_loads_it(self):
        target = self.publish()
        with patch.object(pc, "_load_memo") as load:
            self.assertEqual(self.lookup(), str(target))
            load.assert_not_called()
            self.source.write_text("print(43)\n")
            self.assertEqual(self.lookup(), "")
            load.assert_called_once_with(str(self.cache / "program-v2"))

    def test_disabled_tracking_has_no_hash_or_realpath_work(self):
        pc.stop()
        with patch.object(pc, "fnv", side_effect=AssertionError("hash")), \
                patch.object(pc.os.path, "realpath", side_effect=AssertionError("realpath")):
            self.assertTrue(pc.tracked_exists(str(self.source)))
            self.assertFalse(pc.tracked_exists(str(self.source) + ".missing"))
            pc.track_source(str(self.source), "ignored")
            pc.track_static(str(self.source))
        self.assertEqual(pc.SOURCES, {})
        self.assertEqual(pc.PROBES, {})
        self.assertEqual(pc.STATICS, {})

    def test_source_same_size_and_preserved_mtime_misses(self):
        self.publish()
        before = self.source.stat()
        self.source.write_text("print(43)\n")
        os.utime(self.source, ns=(before.st_atime_ns, before.st_mtime_ns))
        self.assertEqual(self.source.stat().st_size, before.st_size)
        self.assertEqual(self.source.stat().st_mtime_ns, before.st_mtime_ns)
        self.assertEqual(self.lookup(), "")

    def test_deleted_or_changed_import_misses(self):
        imported = self.root / "dependency.py"
        imported.write_text("value = 1\n")
        self.remember(imported)
        self.publish()
        imported.write_text("value = 2\n")
        self.assertEqual(self.lookup(), "")
        imported.write_text("value = 1\n")
        self.assertTrue(self.lookup())
        imported.unlink()
        self.assertEqual(self.lookup(), "")

    def test_new_previously_missing_module_or_package_misses(self):
        for candidate in (self.root / "earlier.py", self.root / "pkg" / "__init__.py"):
            with self.subTest(candidate=candidate):
                pc.start()
                self.assertFalse(pc.tracked_exists(str(candidate)))
                self.publish()
                candidate.parent.mkdir(exist_ok=True)
                candidate.write_text("")
                self.assertEqual(self.lookup(), "")

    def test_existing_probe_removed_misses(self):
        candidate = self.root / "package"
        candidate.mkdir()
        self.assertTrue(pc.tracked_exists(str(candidate)))
        self.publish()
        candidate.rmdir()
        self.assertEqual(self.lookup(), "")

    def test_probe_kinds_follow_symlinks_as_cpython_import_does(self):
        # Only a directory, also through a symbolic link, is a namespace portion (#1166).
        directory = self.root / "portion"
        directory.mkdir()
        plain = self.root / "plainname"
        plain.write_text("not a module\n")
        fifo = self.root / "fifo"
        os.mkfifo(fifo)
        linked_directory = self.root / "linked-portion"
        linked_directory.symlink_to(directory, target_is_directory=True)
        linked_file = self.root / "linked-plainname"
        linked_file.symlink_to(plain)
        dangling = self.root / "dangling"
        dangling.symlink_to(self.root / "nowhere")
        kinds = {directory: "d", linked_directory: "d", plain: "f", linked_file: "f",
                 fifo: "o", dangling: "0", self.root / "missing": "0"}
        for path, kind in kinds.items():
            with self.subTest(path=path.name):
                self.assertEqual(pc.tracked_kind(str(path)), kind)
                self.assertEqual(pc.tracked_isdir(str(path)), kind == "d")
                self.assertEqual(pc.tracked_exists(str(path)), kind != "0")
        self.assertTrue(pc.VALID[0])
        self.assertEqual(pc._unpack(pc.PROBES[str(linked_directory)]), ["d", str(directory.resolve())])
        target = self.publish()
        self.assertEqual(self.lookup(), str(target))

    def test_candidate_changing_kind_misses(self):
        # A file, a directory or nothing at one candidate path (with one resolved path)
        # can each resolve an import differently: every flip misses, and restoring hits.
        candidate = self.root / "plainname"

        def make(kind):
            if candidate.is_dir():
                candidate.rmdir()
            elif candidate.exists():
                candidate.unlink()
            if kind == "file":
                candidate.write_text("not a module\n")
            elif kind == "directory":
                candidate.mkdir()

        for before, after in (("file", "directory"), ("directory", "file"), ("missing", "file"),
                              ("missing", "directory"), ("file", "missing"), ("directory", "missing")):
            with self.subTest(before=before, after=after):
                make(before)
                pc.start()
                self.assertEqual(pc.tracked_isdir(str(candidate)), before == "directory")
                target = self.publish()
                self.assertEqual(self.lookup(), str(target))
                make(after)
                self.assertEqual(self.lookup(), "")
                make(before)
                self.assertEqual(self.lookup(), str(target))

    def test_symlink_directory_retarget_misses_even_for_identical_text(self):
        first = self.root / "first"
        second = self.root / "second"
        first.mkdir()
        second.mkdir()
        for directory in (first, second):
            (directory / "part.py").write_text("value = 1\n")
        alias = self.root / "alias"
        alias.symlink_to(first, target_is_directory=True)
        self.remember(alias / "part.py")
        self.assertFalse(pc.tracked_exists(str(alias / "absent.py")))
        self.publish()
        alias.unlink()
        alias.symlink_to(second, target_is_directory=True)
        self.assertEqual(self.lookup(), "")

    def test_negative_probe_realpath_changes_when_symlink_retargets(self):
        first = self.root / "first"
        second = self.root / "second"
        first.mkdir()
        second.mkdir()
        alias = self.root / "alias"
        alias.symlink_to(first, target_is_directory=True)
        self.assertFalse(pc.tracked_exists(str(alias / "missing.py")))
        self.publish()
        alias.unlink()
        alias.symlink_to(second, target_is_directory=True)
        self.assertEqual(self.lookup(), "")

    def test_actual_read_snapshot_is_checked_before_publication(self):
        before = self.source.read_text()
        self.source.write_text("print(43)\n")
        pc.track_source(str(self.source), before)
        self.assertEqual(pc.publish(str(self.cache), self.context, str(self.executable)), "")
        self.assertFalse(self.index().exists())

    def test_inference_retries_preserve_conflicting_source_snapshots(self):
        self.remember()
        pc.track_source(str(self.source), "print(43)\n")
        self.remember()
        self.assertEqual(pc.publish(str(self.cache), self.context, str(self.executable)), "")

    def test_inference_retries_preserve_conflicting_probe_snapshots(self):
        probe = self.root / "missing.py"
        self.assertFalse(pc.tracked_exists(str(probe)))
        probe.write_text("")
        self.assertTrue(pc.tracked_exists(str(probe)))
        probe.unlink()
        self.assertFalse(pc.tracked_exists(str(probe)))
        self.remember()
        self.assertEqual(pc.publish(str(self.cache), self.context, str(self.executable)), "")

    def test_stop_retains_dependencies_but_start_resets_them(self):
        self.remember()
        pc.stop()
        self.assertTrue(pc.publish(str(self.cache), self.context, str(self.executable)))
        pc.start()
        self.assertEqual(pc.publish(str(self.cache), self.context, str(self.executable)), "")

    def test_universal_newlines_match_exact_consumed_source(self):
        self.source.write_bytes(b"value = 1\r\nprint(value)\r")
        self.publish()
        self.assertTrue(self.lookup())

    def test_path_and_identity_serialization_preserves_special_characters(self):
        directory = self.root / "space tab\tnewline\ncr\rquote'backslash\\omega\u03a9"
        directory.mkdir()
        self.source = directory / "main.py"
        self.source.write_text("print(42)\n")
        self.cache = directory / "cache with spaces"
        self.context += "\n\t\\\r'\u03a9"
        self.assertFalse(pc.tracked_exists(str(directory / "missing\nfile.py")))
        target = self.publish()
        self.assertEqual(self.lookup(), str(target))

    def test_context_collision_cannot_reuse_another_identity(self):
        self.publish()
        self.assertEqual(pc.lookup(str(self.cache), self.context + "changed"), "")
        # Even if an index is copied into another context's slot, its exact context
        # must match; a hash alone does not authorize a hit.
        other = self.context + "other"
        (self.index().parent / (pc.fnv(other) + ".manifest")).write_bytes(self.index().read_bytes())
        self.assertEqual(pc.lookup(str(self.cache), other), "")

    def test_binary_checksum_rejects_same_size_preserved_mtime_damage(self):
        target = self.publish()
        before = target.stat()
        data = target.read_bytes()
        target.write_bytes(bytes([data[0] ^ 1]) + data[1:])
        os.utime(target, ns=(before.st_atime_ns, before.st_mtime_ns))
        self.assertEqual(self.lookup(), "")

    def test_missing_empty_or_nonexecutable_binary_misses(self):
        target = self.publish()
        target.chmod(0o600)
        self.assertEqual(self.lookup(), "")
        target.write_bytes(b"")
        target.chmod(0o700)
        self.assertEqual(self.lookup(), "")
        target.unlink()
        self.assertEqual(self.lookup(), "")

    def test_corrupt_truncated_and_oversized_manifest_miss(self):
        self.publish()
        original = self.index().read_bytes()
        for damaged in (b"", original[:-1], original[:20], b"x" + original[1:], original + b"x", b"\xff"):
            with self.subTest(damaged=damaged[:20]):
                self.index().write_bytes(damaged)
                self.assertEqual(self.lookup(), "")
        self.index().write_bytes(original)
        with patch.object(pc, "MAX_MANIFEST", len(original) - 1):
            self.assertEqual(self.lookup(), "")

    def test_malformed_lengths_and_artifact_paths_cannot_escape_entry(self):
        self.publish()
        for payload in ("999999999999:x", "-1:x", "1", "x:y", "4:abc", "\u00b2:ab"):
            with self.subTest(payload=payload):
                text = pc.MAGIC + pc.fnv(payload) + "\n" + payload
                self.index().write_text(text)
                self.assertEqual(self.lookup(), "")
        for artifact in ("../native", "../../0123456789abcdef", "/tmp/native", "0" * 15, "G" * 16):
            with self.subTest(artifact=artifact):
                payload = pc._pack(pc._records(self.context, artifact))
                self.index().write_text(pc.MAGIC + pc.fnv(payload) + "\n" + payload)
                self.assertEqual(self.lookup(), "")

    def test_no_source_or_unknown_duplicate_records_miss(self):
        self.publish()
        fields = pc._records(self.context, pc._file_hash(str(self.executable)))
        for changed in (fields[:2], fields + fields[2:5], fields[:2] + ["unknown", "x", "y"]):
            with self.subTest(changed=changed):
                payload = pc._pack(changed)
                self.index().write_text(pc.MAGIC + pc.fnv(payload) + "\n" + payload)
                self.assertEqual(self.lookup(), "")

    def test_symlink_cache_directory_manifest_and_binary_bypass(self):
        target = self.publish()
        index = self.index()
        saved = self.root / "saved-manifest"
        index.rename(saved)
        index.symlink_to(saved)
        self.assertEqual(self.lookup(), "")
        index.unlink()
        saved.rename(index)
        saved_binary = self.root / "saved-native"
        target.rename(saved_binary)
        target.symlink_to(saved_binary)
        self.assertEqual(self.lookup(), "")
        target.unlink()
        saved_binary.rename(target)
        actual = self.root / "actual-cache"
        self.cache.rename(actual)
        self.cache.symlink_to(actual, target_is_directory=True)
        self.assertEqual(self.lookup(), "")
        self.assertEqual(pc.publish(str(self.cache), self.context, str(self.executable)), "")

    def test_unsafe_private_directory_is_not_repaired(self):
        self.publish()
        private = self.cache / "program-v2"
        private.chmod(0o755)
        self.assertEqual(self.lookup(), "")
        self.assertEqual(pc.publish(str(self.cache), self.context, str(self.executable)), "")
        self.assertEqual(private.stat().st_mode & 0o777, 0o755)
        private.chmod(0o700)
        self.cache.chmod(0o777)
        self.assertEqual(self.lookup(), "")
        self.assertEqual(pc.publish(str(self.cache), self.context, str(self.executable)), "")

    def test_symlink_inside_cache_path_and_private_subdirectory_bypass(self):
        self.publish()
        alias = self.root / "alias"
        alias.symlink_to(self.root, target_is_directory=True)
        self.assertEqual(pc.lookup(str(alias / "cache"), self.context), "")
        private = self.cache / "program-v2"
        saved = self.root / "saved-program-v2"
        private.rename(saved)
        private.symlink_to(saved, target_is_directory=True)
        self.assertEqual(self.lookup(), "")
        self.assertEqual(pc.publish(str(self.cache), self.context, str(self.executable)), "")

    def test_io_failure_falls_open_and_cleans_own_stage(self):
        self.remember()
        with patch.object(pc.os, "replace", side_effect=PermissionError("read-only cache")):
            self.assertEqual(pc.publish(str(self.cache), self.context, str(self.executable)), "")
        self.assertEqual(self.lookup(), "")
        self.assertEqual(list((self.cache / "program-v2").glob("stage-*")), [])
        self.assertFalse(self.index().exists())
        with patch.object(pc.os, "mkdir", side_effect=PermissionError("read-only cache")):
            self.assertEqual(pc.publish(str(self.cache), self.context, str(self.executable)), "")

    def test_source_change_while_copying_prevents_publication(self):
        self.remember()
        original_hash = pc._file_hash

        def changed_during_copy(path):
            digest = original_hash(path)
            self.source.write_text("print(43)\n")
            return digest

        with patch.object(pc, "_file_hash", side_effect=changed_during_copy):
            self.assertEqual(pc.publish(str(self.cache), self.context, str(self.executable)), "")
        self.assertFalse(self.index().exists())

    def test_reader_observes_old_complete_entry_until_manifest_replacement(self):
        old = self.publish()
        self.executable.write_bytes(b"\x7fELFsecond-complete-binary")
        replace = pc.os.replace
        observations = []

        def observed_replace(source, destination):
            if str(destination).endswith(".manifest"):
                observations.append(self.lookup())
                replace(source, destination)
                observations.append(self.lookup())
            else:
                replace(source, destination)

        with patch.object(pc.os, "replace", side_effect=observed_replace):
            new = pc.publish(str(self.cache), self.context, str(self.executable))
        self.assertTrue(new)
        self.assertNotEqual(str(old), new)
        self.assertEqual(observations, [str(old), new])

    def test_concurrent_publishers_leave_one_complete_reusable_entry(self):
        mp = multiprocessing.get_context("fork")
        results = mp.Queue()
        processes = []
        for i in range(3):
            executable = self.root / f"native-{i}"
            executable.write_bytes(self.executable.read_bytes() + str(i).encode())
            executable.chmod(0o700)
            process = mp.Process(target=writer, args=(str(self.cache), str(self.source),
                                 str(executable), self.context, results))
            processes.append(process)
            process.start()
        completed = [results.get(timeout=10) for _ in processes]
        for process in processes:
            process.join(timeout=10)
            self.assertEqual(process.exitcode, 0)
        self.assertTrue(all(completed))
        self.assertIn(self.lookup(), completed)
        self.assertEqual(list((self.cache / "program-v2").glob("stage-*")), [])

    def test_static_dependencies_invalidate_on_content_or_realpath_change(self):
        static = self.root / "library.so"
        static.write_bytes(b"first native library")
        before = static.stat()
        pc.track_static(str(static))
        self.publish()
        self.assertTrue(self.lookup())
        static.write_bytes(b"other native library")
        os.utime(static, ns=(before.st_atime_ns, before.st_mtime_ns))
        self.assertEqual(self.lookup(), "")

    def test_static_realpath_aliases_hash_only_once_when_settled(self):
        static = self.root / "library.so"
        static.write_bytes(b"native library")
        alias = self.root / "alias.so"
        alias.symlink_to(static)
        future = time.time() + 10
        with patch.object(pc.time, "time", return_value=future), \
                patch.object(pc, "_file_hash", wraps=pc._file_hash) as hashed:
            pc.track_static(str(static))
            pc.track_static(str(alias))
            pc.track_static(str(static))
        self.assertEqual(hashed.call_count, 1)
        self.assertEqual(len(pc.STATICS), 2)
        self.publish()
        self.assertTrue(self.lookup())

    def test_unsettled_static_capture_keeps_content_check_after_time_passes(self):
        static = self.root / "library.so"
        static.write_bytes(b"first native library")
        pc.track_static(str(static))
        self.publish()
        recorded = pc._stat3(str(static))
        real_stat = pc._stat3
        static.write_bytes(b"other native library")
        # Simulate a coarse timestamp bucket containing two different versions.
        # Aging that bucket later must not turn a racy capture into a trusted memo.
        with patch.object(pc.time, "time", return_value=time.time() + 10), \
                patch.object(pc, "_stat3", side_effect=lambda path: recorded if path == str(static) else real_stat(path)):
            self.assertEqual(self.lookup(), "")

    def test_duplicate_static_capture_crossing_settle_threshold_can_publish(self):
        static = self.root / "compiler"
        static.write_bytes(b"unchanged native compiler")
        path = str(static)
        changed = max(float(value) for value in pc._stat3(path).split()[1:])
        with patch.object(pc.time, "time", return_value=changed):
            pc.track_static(path)
        recorded = pc.STATICS[path]
        self.assertEqual(pc._unpack(recorded)[3], "0")
        # tool_inputs records the fresh compiler before and after hashing its
        # libraries. Elapsed time alone must not invalidate the original read.
        with patch.object(pc.time, "time", return_value=changed + 3):
            pc.track_static(path)
        self.assertTrue(pc.VALID[0])
        self.assertEqual(pc.STATICS[path], recorded)
        target = self.publish()
        self.assertEqual(self.lookup(), str(target))

    def test_duplicate_static_capture_still_rejects_changed_inputs(self):
        static = self.root / "compiler"
        path = str(static)
        real_stat = pc._stat3
        for change in ("content within a coarse timestamp", "metadata"):
            with self.subTest(change=change):
                pc.start()
                pc.STATIC_MEMO.clear()
                static.write_bytes(b"first native compiler")
                stamp = real_stat(path)
                changed = max(float(value) for value in stamp.split()[1:])
                with patch.object(pc.time, "time", return_value=changed):
                    pc.track_static(path)
                if change == "metadata":
                    os.utime(static, (changed + 1, changed + 1))
                else:
                    static.write_bytes(b"other native compiler")
                def observed(item, recorded=stamp, mutation=change):
                    return recorded if item == path and mutation != "metadata" else real_stat(item)

                with patch.object(pc.time, "time", return_value=changed + 3), \
                        patch.object(pc, "_stat3", side_effect=observed):
                    pc.track_static(path)
                self.assertFalse(pc.VALID[0])
                self.remember()
                self.assertEqual(pc.publish(str(self.cache), self.context, str(self.executable)), "")

    def test_persistent_static_memo_avoids_rehash_for_another_program(self):
        static = self.root / "library.so"
        static.write_bytes(b"shared toolchain library")
        with patch.object(pc.time, "time", return_value=time.time() + 10):
            pc.track_static(str(static))
        self.publish()
        pc.STATIC_MEMO.clear()
        pc.MEMO_ROOT[0] = ""
        pc.start()
        self.assertEqual(pc.lookup(str(self.cache), self.context + "another source"), "")
        with patch.object(pc, "_file_hash", side_effect=AssertionError("already hashed")):
            pc.track_static(str(static))
        self.assertTrue(pc.VALID[0])
        self.assertIn(str(static), pc.STATICS)

    def test_corrupt_persistent_static_memo_rehashes_instead_of_poisoning_entry(self):
        static = self.root / "library.so"
        static.write_bytes(b"shared toolchain library")
        with patch.object(pc.time, "time", return_value=time.time() + 10):
            pc.track_static(str(static))
        self.publish()
        (self.cache / "program-v2" / "static-hashes").write_bytes(b"partial metadata")
        pc.STATIC_MEMO.clear()
        pc.MEMO_ROOT[0] = ""
        pc.start()
        self.assertEqual(pc.lookup(str(self.cache), self.context + "another source"), "")
        with patch.object(pc, "_file_hash", wraps=pc._file_hash) as hashed:
            pc.track_static(str(static))
        self.assertEqual(hashed.call_count, 1)
        self.assertTrue(pc.VALID[0])
        self.assertTrue(self.lookup())

    def test_changed_persistent_static_memo_dependency_is_rehashed(self):
        static = self.root / "library.so"
        static.write_bytes(b"first native library")
        with patch.object(pc.time, "time", return_value=time.time() + 10):
            pc.track_static(str(static))
        self.publish()
        before = static.stat()
        static.write_bytes(b"other native library")
        os.utime(static, ns=(before.st_atime_ns, before.st_mtime_ns))
        pc.STATIC_MEMO.clear()
        pc.MEMO_ROOT[0] = ""
        pc.start()
        self.assertEqual(pc.lookup(str(self.cache), self.context + "another source"), "")
        with patch.object(pc, "_file_hash", wraps=pc._file_hash) as hashed:
            pc.track_static(str(static))
        self.assertEqual(hashed.call_count, 1)
        self.assertTrue(pc.VALID[0])
        self.assertEqual(self.lookup(), "")

    def test_streamed_binary_hash_matches_raw_bytes_across_chunk_boundaries(self):
        data = bytes(range(256)) * 600
        self.executable.write_bytes(data)
        self.assertEqual(pc._file_hash(str(self.executable)), pc.fnv(data.decode("latin-1")))


if __name__ == "__main__":
    unittest.main()
