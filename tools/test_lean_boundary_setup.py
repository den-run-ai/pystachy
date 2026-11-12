"""Pinned Lean setup checks with local curl/tar substitutes and no network access."""

import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import setup_lean


class LeanSetupTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.cache = self.root / "cache"
        self.output = self.root / "fresh toolchain"
        self.source = self.root / "download"
        self.source.write_bytes(b"pinned release archive")
        self.digest = hashlib.sha256(self.source.read_bytes()).hexdigest()
        self.calls = self.root / "calls"
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.stub("curl", '''printf 'curl\n' >> "$SETUP_CALLS"
while [ "$#" -gt 0 ]; do
  if [ "$1" = --output ]; then shift; destination=$1; fi
  shift
done
cat "$ARCHIVE_SOURCE" > "$destination"
exit "${CURL_RESULT:-0}"
''')
        self.stub("tar", '''printf 'tar\n' >> "$SETUP_CALLS"
while [ "$#" -gt 0 ]; do
  if [ "$1" = -C ]; then shift; destination=$1; fi
  shift
done
if [ "${TAR_EMPTY:-0}" = 1 ]; then exit 0; fi
mkdir -p "$destination/lean-4.35.0-linux/bin"
for tool in lean lake; do
  printf '#!/bin/sh\nexit 0\n' > "$destination/lean-4.35.0-linux/bin/$tool"
  chmod +x "$destination/lean-4.35.0-linux/bin/$tool"
done
''')
        for target, value in (("SHA256", self.digest),):
            patched = patch.object(setup_lean, target, value)
            patched.start()
            self.addCleanup(patched.stop)
        for target, value in (("system", "Linux"), ("machine", "x86_64")):
            patched = patch.object(setup_lean.platform, target, return_value=value)
            patched.start()
            self.addCleanup(patched.stop)
        env = patch.dict(os.environ, PATH=str(self.bin) + os.pathsep + os.environ["PATH"],
                         SETUP_CALLS=str(self.calls), ARCHIVE_SOURCE=str(self.source))
        env.start()
        self.addCleanup(env.stop)

    def stub(self, name, script):
        path = self.bin / name
        path.write_text("#!/bin/sh\nset -eu\n" + script)
        path.chmod(0o755)

    def invoked(self):
        return self.calls.read_text().splitlines() if self.calls.exists() else []

    def archive(self):
        return self.cache / f"{self.digest}.tar.zst"

    def test_download_then_cache_hit_extracts_fresh_each_time(self):
        result = setup_lean.install(self.cache, self.output)
        self.assertEqual(result, self.output / "lean-4.35.0-linux/bin")
        self.assertEqual(self.archive().read_bytes(), self.source.read_bytes())
        self.assertEqual(self.invoked(), ["curl", "tar"])
        second = self.root / "second"
        setup_lean.install(self.cache, second)
        self.assertEqual(self.invoked(), ["curl", "tar", "tar"])
        self.assertTrue((second / "lean-4.35.0-linux/bin/lean").is_file())
        self.assertEqual(list(self.cache.iterdir()), [self.archive()])

    def test_restored_archive_is_rehashed_before_extraction(self):
        setup_lean.install(self.cache, self.output)
        self.archive().write_bytes(b"corrupted cache")
        setup_lean.install(self.cache, self.root / "next")
        self.assertEqual(self.invoked(), ["curl", "tar", "curl", "tar"])
        self.assertEqual(self.archive().read_bytes(), self.source.read_bytes())

    def test_download_mismatch_never_extracts_or_caches(self):
        self.source.write_bytes(b"wrong release")
        with self.assertRaisesRegex(ValueError, "SHA256"):
            setup_lean.install(self.cache, self.output)
        self.assertEqual(self.invoked(), ["curl"])
        self.assertEqual(list(self.cache.iterdir()), [])
        self.assertFalse(self.output.exists())

    def test_partial_download_is_removed_on_error(self):
        with patch.dict(os.environ, CURL_RESULT="23"), self.assertRaises(subprocess.CalledProcessError):
            setup_lean.install(self.cache, self.output)
        self.assertEqual(self.invoked(), ["curl"])
        self.assertEqual(list(self.cache.iterdir()), [])

    def test_cached_symlink_is_replaced_without_changing_target(self):
        self.cache.mkdir()
        self.archive().symlink_to(self.source)
        setup_lean.install(self.cache, self.output)
        self.assertFalse(self.archive().is_symlink())
        self.assertEqual(self.source.read_bytes(), b"pinned release archive")
        self.assertEqual(self.invoked(), ["curl", "tar"])

    def test_no_reuse_of_existing_extracted_binary(self):
        setup_lean.install(self.cache, self.output)
        with self.assertRaisesRegex(ValueError, "empty"):
            setup_lean.install(self.cache, self.output)
        self.assertEqual(self.invoked(), ["curl", "tar"])

    def test_symlink_output_is_rejected(self):
        target = self.root / "target"
        target.mkdir()
        self.output.symlink_to(target, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlink"):
            setup_lean.install(self.cache, self.output)
        self.assertEqual(self.invoked(), [])

    def test_extraction_must_provide_executables(self):
        with patch.dict(os.environ, TAR_EMPTY="1"), self.assertRaisesRegex(ValueError, "executables"):
            setup_lean.install(self.cache, self.output)

    def test_wrong_platform_fails_before_download_or_extraction(self):
        for system, machine in (("Linux", "aarch64"), ("Darwin", "x86_64")):
            with self.subTest(system=system, machine=machine), \
                    patch.object(setup_lean.platform, "system", return_value=system), \
                    patch.object(setup_lean.platform, "machine", return_value=machine), \
                    self.assertRaisesRegex(ValueError, "Linux x86_64"):
                setup_lean.install(self.cache, self.output)
        self.assertEqual(self.invoked(), [])


if __name__ == "__main__":
    unittest.main()
