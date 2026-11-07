"""Check the integrity and publication of managed LLVM installations."""

import hashlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import call, patch
from urllib.error import HTTPError, URLError

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

    def test_download_retries_transient_http_errors_and_timeouts(self):
        url = "https://example.invalid/llvm.tar"
        payload = b"LLVM archive"
        digest = hashlib.sha256(payload).hexdigest()
        errors = [HTTPError(url, code, "temporary failure", {}, None)
                  for code in (408, 429, 500, 502, 503, 504)]
        errors.extend((TimeoutError("timed out"), URLError(TimeoutError("timed out"))))
        for error in errors:
            with (self.subTest(error=error), tempfile.TemporaryDirectory() as directory,
                  patch.object(toolchain, "urlopen", side_effect=[error, io.BytesIO(payload)]) as fetch,
                  patch("time.sleep") as sleep):
                archive = Path(directory) / "archive"
                toolchain.download(url, digest, archive)
                self.assertEqual(archive.read_bytes(), payload)
                self.assertEqual(fetch.call_args_list, [call(url, timeout=60)] * 2)
                sleep.assert_called_once_with(1)

    def test_download_restarts_bytes_and_digest_after_a_read_timeout(self):
        class InterruptedResponse(io.BytesIO):
            def read(self, size=-1):
                if self.tell():
                    raise TimeoutError("read timed out")
                return super().read(size)

        partial = InterruptedResponse(b"partial content longer than the final archive")
        payload = b"LLVM archive"
        response = io.BytesIO(payload)
        with (tempfile.TemporaryDirectory() as directory,
              patch.object(toolchain, "urlopen", side_effect=[partial, response]) as fetch,
              patch("time.sleep") as sleep):
            archive = Path(directory) / "archive"
            archive.write_bytes(b"old content" * 10)
            toolchain.download("https://example.invalid/llvm.tar", hashlib.sha256(payload).hexdigest(), archive)
            self.assertEqual(archive.read_bytes(), payload)
            self.assertEqual(fetch.call_count, 2)
            self.assertTrue(partial.closed)
            self.assertTrue(response.closed)
            sleep.assert_called_once_with(1)

    def test_download_stops_after_three_transient_failures(self):
        url = "https://example.invalid/llvm.tar"
        errors = [HTTPError(url, 504, "Gateway Timeout", {}, io.BytesIO(b"unavailable"))
                  for _ in range(3)]
        with (tempfile.TemporaryDirectory() as directory,
              patch.object(toolchain, "urlopen", side_effect=errors) as fetch,
              patch("time.sleep") as sleep):
            with self.assertRaises(HTTPError) as raised:
                toolchain.download(url, "0" * 64, Path(directory) / "archive")
            self.assertIs(raised.exception, errors[-1])
            self.assertEqual(fetch.call_count, 3)
            self.assertEqual(sleep.call_args_list, [call(1), call(2)])
            self.assertTrue(all(error.closed for error in errors[:-1]))
            errors[-1].close()

    def test_download_does_not_retry_checksum_mismatches(self):
        with (tempfile.TemporaryDirectory() as directory,
              patch.object(toolchain, "urlopen", return_value=io.BytesIO(b"wrong archive")) as fetch,
              patch("time.sleep") as sleep):
            with self.assertRaisesRegex(ValueError, "checksum mismatch"):
                toolchain.download("https://example.invalid/llvm.tar", "0" * 64, Path(directory) / "archive")
            fetch.assert_called_once()
            sleep.assert_not_called()

    def test_download_does_not_retry_permanent_network_errors(self):
        url = "https://example.invalid/llvm.tar"
        errors = (HTTPError(url, 404, "Not Found", {}, None), URLError("certificate verify failed"))
        for error in errors:
            with (self.subTest(error=error), tempfile.TemporaryDirectory() as directory,
                  patch.object(toolchain, "urlopen", side_effect=error) as fetch,
                  patch("time.sleep") as sleep):
                with self.assertRaises(URLError) as raised:
                    toolchain.download(url, "0" * 64, Path(directory) / "archive")
                self.assertIs(raised.exception, error)
                fetch.assert_called_once()
                sleep.assert_not_called()

    def test_download_does_not_retry_local_write_errors(self):
        for error in (OSError("disk full"), TimeoutError("local write timed out")):
            with (self.subTest(error=error), tempfile.TemporaryDirectory() as directory,
                  patch.object(toolchain, "urlopen", return_value=io.BytesIO(b"LLVM archive")) as fetch,
                  patch.object(Path, "open") as open_archive,
                  patch("time.sleep") as sleep):
                open_archive.return_value.__enter__.return_value.write.side_effect = error
                with self.assertRaises(OSError) as raised:
                    toolchain.download("https://example.invalid/llvm.tar", "0" * 64, Path(directory) / "archive")
                self.assertIs(raised.exception, error)
                fetch.assert_called_once()
                sleep.assert_not_called()

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
