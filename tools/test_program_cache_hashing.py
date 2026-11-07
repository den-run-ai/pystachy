"""Fast static-input hashing keeps content validation and conservative fallback."""
import hashlib
import os
from pathlib import Path
import shlex
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.pystachy_compiler import program_cache as pc


@unittest.skipUnless(sys.platform == "linux", "the native cache supports Linux")
class ProgramCacheHashingTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.input = self.root / "library.so"
        self.data = bytes(range(256)) * 4096
        self.input.write_bytes(self.data)
        pc.STATIC_MEMO.clear()
        pc.MEMO_ROOT[0] = ""
        pc.start()
        self.addCleanup(pc.stop)

    def expected(self, data=None):
        return "sha256:" + hashlib.sha256(self.data if data is None else data).hexdigest()

    def require_helper(self):
        if not Path("/usr/bin/sha256sum").is_file():
            self.skipTest("fast hashing uses /usr/bin/sha256sum when available")

    def test_large_static_input_uses_exact_byte_sha256(self):
        self.require_helper()
        with patch.object(pc, "_file_hash", side_effect=AssertionError("large FNV loop")):
            pc.track_static(str(self.input))
        snapshot = pc._unpack(pc.STATICS[str(self.input)])
        self.assertEqual(snapshot[2], self.expected())
        self.assertTrue(pc.VALID[0])

    def test_small_static_input_retains_in_process_fnv(self):
        data = b"small native object\x00\r\n\xff"
        self.input.write_bytes(data)
        with patch.object(pc, "_sha256", side_effect=AssertionError("small helper process")):
            pc.track_static(str(self.input))
        snapshot = pc._unpack(pc.STATICS[str(self.input)])
        self.assertEqual(snapshot[2], pc.fnv(data.decode("latin-1")))
        self.assertTrue(pc.VALID[0])

    def test_missing_helper_falls_back_to_existing_content_hash(self):
        with patch.object(pc, "_sh", return_value=False), \
                patch.object(pc, "_file_hash", wraps=pc._file_hash) as fallback:
            pc.track_static(str(self.input))
        self.assertEqual(fallback.call_count, 1)
        self.assertTrue(pc.VALID[0])
        snapshot = pc._unpack(pc.STATICS[str(self.input)])
        self.assertEqual(snapshot[2], pc.fnv(self.data.decode("latin-1")))

    def test_invalid_helper_output_is_never_accepted(self):
        for output in ("", "0" * 64 + "  -", "X" * 64 + "  -\n", "0" * 65 + "  -\n",
                       "0" * 64 + "  other\n", "0" * 64 + "  -\nextra"):
            with self.subTest(output=output):
                def write_output(command, captured=output):
                    Path(shlex.split(command)[-1]).write_text(captured)
                    return True
                with patch.object(pc, "_sh", side_effect=write_output):
                    self.assertEqual(pc._sha256(str(self.input)), "")

    def test_helper_output_directory_is_private_and_always_removed(self):
        self.require_helper()
        mkdtemp = tempfile.mkdtemp
        directories = []

        def capture_directory():
            path = mkdtemp(dir=self.root)
            directories.append(Path(path))
            self.assertEqual(Path(path).stat().st_mode & 0o777, 0o700)
            return path

        with patch.object(pc.tempfile, "mkdtemp", side_effect=capture_directory):
            self.assertEqual(pc._sha256(str(self.input)), self.expected())
            with patch.object(pc, "_sh", return_value=False):
                self.assertEqual(pc._sha256(str(self.input)), "")
        self.assertEqual(len(directories), 2)
        self.assertTrue(all(not path.exists() for path in directories))

    def test_quoted_newline_and_shell_metacharacters_in_filename(self):
        self.require_helper()
        unusual = self.root / "quote'\n$(touch escaped) `touch injected` -file"
        unusual.write_bytes(self.data)
        self.assertEqual(pc._sha256(str(unusual)), self.expected())
        self.assertFalse((self.root / "escaped").exists())
        self.assertFalse((self.root / "injected").exists())
        self.assertFalse(Path("escaped").exists())
        self.assertFalse(Path("injected").exists())

    def test_missing_fifo_and_oversized_inputs_are_rejected_before_helper(self):
        fifo = self.root / "fifo"
        os.mkfifo(fifo)
        with patch.object(pc, "_sh", side_effect=AssertionError("invalid hash input")):
            self.assertEqual(pc._sha256(str(self.root / "absent")), "")
            self.assertEqual(pc._sha256(str(fifo)), "")
            with patch.object(pc.os.path, "getsize", return_value=pc.MAX_BINARY + 1):
                self.assertEqual(pc._sha256(str(self.input)), "")
            self.assertEqual(pc._sha256("nul\0path"), "")

    def test_unsettled_sha_capture_rechecks_content_after_timestamp_ages(self):
        self.require_helper()
        pc.track_static(str(self.input))
        snapshot = pc.STATICS[str(self.input)]
        fields = pc._unpack(snapshot)
        self.assertEqual(fields[3], "0")
        self.input.write_bytes(b"X" + self.data[1:])
        with patch.object(pc, "_stat3", return_value=fields[1]), \
                patch.object(pc.time, "time", return_value=time.time() + 10):
            self.assertFalse(pc._static_matches(str(self.input), snapshot))

    def test_unsettled_sha_cannot_be_validated_when_helper_is_missing(self):
        self.require_helper()
        pc.track_static(str(self.input))
        snapshot = pc.STATICS[str(self.input)]
        with patch.object(pc, "_sh", return_value=False):
            self.assertFalse(pc._static_matches(str(self.input), snapshot))

    def test_fnv_snapshot_keeps_its_algorithm_when_helper_becomes_available(self):
        self.input.write_bytes(b"legacy static bytes")
        pc.track_static(str(self.input))
        snapshot = pc.STATICS[str(self.input)]
        with patch.object(pc, "_sha256", side_effect=AssertionError("hash format changed")):
            self.assertTrue(pc._static_matches(str(self.input), snapshot))

    def test_stat_change_during_fast_hash_disables_capture(self):
        self.require_helper()
        sha256 = pc._sha256

        def change_during_hash(path):
            digest = sha256(path)
            self.input.write_bytes(self.data + b"changed")
            return digest

        with patch.object(pc, "_sha256", side_effect=change_during_hash):
            pc.track_static(str(self.input))
        self.assertFalse(pc.VALID[0])
        self.assertNotIn(str(self.input), pc.STATICS)

    def test_settled_sha_aliases_use_one_hash(self):
        self.require_helper()
        alias = self.root / "alias.so"
        alias.symlink_to(self.input)
        with patch.object(pc.time, "time", return_value=time.time() + 10), \
                patch.object(pc, "_sha256", wraps=pc._sha256) as hashed:
            pc.track_static(str(self.input))
            pc.track_static(str(alias))
        self.assertEqual(hashed.call_count, 1)
        self.assertEqual(len(pc.STATICS), 2)

    def test_memo_accepts_tagged_sha_and_rejects_invalid_digests(self):
        real = str(self.input)
        fields = []
        valid = self.expected()
        for index, digest in enumerate((valid, "sha256:" + "x" * 64, "0" * 64, "sha256:" + "0" * 63)):
            path = real + str(index)
            fields.extend([path, pc._pack([path, pc._stat3(real), digest, "1"])])
        payload = pc._pack(fields)
        (self.root / "static-hashes").write_text(pc.MEMO_MAGIC + pc.fnv(payload) + "\n" + payload)
        pc._load_memo(str(self.root))
        self.assertEqual(list(pc.STATIC_MEMO), [real + "0"])

    def test_settled_snapshot_rejects_invalid_digest(self):
        snapshot = pc._pack([str(self.input), pc._stat3(str(self.input)), "sha256:invalid", "1"])
        self.assertFalse(pc._static_matches(str(self.input), snapshot))

    def test_persistent_sha_memo_reuses_digest_without_another_helper(self):
        self.require_helper()
        with patch.object(pc.time, "time", return_value=time.time() + 10):
            pc.track_static(str(self.input))
        expected = pc.STATIC_MEMO.copy()
        stage = self.root / "stage"
        stage.mkdir()
        pc._save_memo(str(self.root), str(stage))
        pc.STATIC_MEMO.clear()
        pc.start()
        pc._load_memo(str(self.root))
        self.assertEqual(pc.STATIC_MEMO, expected)
        with patch.object(pc, "_sha256", side_effect=AssertionError("persistent input rehashed")):
            pc.track_static(str(self.input))
        self.assertTrue(pc.VALID[0])


if __name__ == "__main__":
    unittest.main()
