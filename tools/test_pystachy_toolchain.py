"""Check the integrity and publication of managed LLVM installations."""

import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pystachy_toolchain as toolchain


class ManagedToolchainTests(unittest.TestCase):
    def test_download_checks_the_pinned_digest(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = root / "source"
            fixture.write_bytes(b"LLVM archive")
            archive = root / "archive"
            digest = hashlib.sha256(fixture.read_bytes()).hexdigest()
            toolchain.download(fixture.as_uri(), digest, archive)
            self.assertEqual(archive.read_bytes(), fixture.read_bytes())
            with self.assertRaisesRegex(ValueError, "checksum mismatch"):
                toolchain.download(fixture.as_uri(), "0" * 64, archive)

    def test_partial_install_is_not_published_and_retry_is_cached(self):
        def partial_install(staging, payload, arch):
            payload.mkdir()
            raise ValueError("incomplete archive")

        def complete_install(staging, payload, arch):
            bin_dir = payload / "usr/lib/llvm-18/bin"
            bin_dir.mkdir(parents=True)
            for name in toolchain.TOOLS:
                path = bin_dir / name
                path.touch(mode=0o700)
            header = bin_dir.parent / "lib/clang/18/include/stddef.h"
            header.parent.mkdir(parents=True)
            header.touch()
            return bin_dir

        ubuntu = {"ID": "ubuntu", "VERSION_ID": "24.04"}
        with (tempfile.TemporaryDirectory() as directory,
              patch.dict(toolchain.os.environ, {"PYSTACHY_LLVM_CACHE": directory}),
              patch.object(toolchain.sys, "platform", "linux"),
              patch.object(toolchain.platform, "machine", return_value="x86_64"),
              patch.object(toolchain.platform, "freedesktop_os_release", return_value=ubuntu),
              patch.object(toolchain, "unpack_ubuntu", side_effect=partial_install) as unpack,
              patch.object(toolchain.subprocess, "check_output", return_value="LLVM version 18.1.3")):
            cache = Path(directory)
            with self.assertRaisesRegex(ValueError, "incomplete archive"):
                toolchain.ensure_toolchain()
            self.assertFalse(any(cache.glob("*/bin")))
            unpack.side_effect = complete_install
            bin_dir = toolchain.ensure_toolchain()
            self.assertEqual(toolchain.ensure_toolchain(), bin_dir)
            self.assertEqual(unpack.call_count, 2)
            self.assertTrue(all((bin_dir / name).is_file() for name in toolchain.TOOLS))


if __name__ == "__main__":
    unittest.main()
