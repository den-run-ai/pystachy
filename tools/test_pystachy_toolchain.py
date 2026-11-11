"""Check the integrity and publication of managed LLVM installations."""

import hashlib
import io
from pathlib import Path
import ssl
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
            with self.assertRaises(URLError) as raised:
                toolchain.download(url, "0" * 64, Path(directory) / "archive")
            self.assertIs(raised.exception.__cause__, errors[-1])
            self.assertIn(url, str(raised.exception))
            self.assertIn("504", str(raised.exception))
            self.assertEqual(fetch.call_count, 3)
            self.assertEqual(sleep.call_args_list, [call(1), call(2)])
            self.assertTrue(all(error.closed for error in errors))

    def test_download_uses_mirror_without_increasing_retry_budget(self):
        url = "https://snapshot.invalid/package.deb"
        mirror = "https://archive.invalid/package.deb"
        payload = b"LLVM archive"
        digest = hashlib.sha256(payload).hexdigest()
        for middle in (io.BytesIO(payload), HTTPError(mirror, 503, "unavailable", {}, None),
                       HTTPError(mirror, 404, "pruned", {}, None)):
            outcomes = [HTTPError(url, 503, "unavailable", {}, None), middle, io.BytesIO(payload)]
            with (self.subTest(middle=middle), tempfile.TemporaryDirectory() as directory,
                  patch.object(toolchain, "urlopen", side_effect=outcomes) as fetch,
                  patch("time.sleep") as sleep):
                archive = Path(directory) / "archive"
                toolchain.download(url, digest, archive, fallback_url=mirror)
                self.assertEqual(archive.read_bytes(), payload)
                calls = [call(url, timeout=60), call(mirror, timeout=60)]
                if isinstance(middle, HTTPError):
                    calls.append(call(url, timeout=60))
                self.assertEqual(fetch.call_args_list, calls)
                self.assertEqual(sleep.call_count, len(calls) - 1)

    def test_download_mirror_failures_report_final_endpoint(self):
        url = "https://snapshot.invalid/package.deb"
        mirror = "https://archive.invalid/package.deb"
        for final in (HTTPError(url, 504, "timeout", {}, None), TimeoutError("timed out")):
            with (self.subTest(final=final), tempfile.TemporaryDirectory() as directory,
                  patch.object(toolchain, "urlopen", side_effect=[
                      HTTPError(url, 503, "unavailable", {}, None), TimeoutError("timed out"), final,
                  ]) as fetch, patch("time.sleep")):
                with self.assertRaises(URLError) as raised:
                    toolchain.download(url, "0" * 64, Path(directory) / "archive", fallback_url=mirror)
                self.assertIs(raised.exception.__cause__, final)
                self.assertIn(url, str(raised.exception))
                self.assertEqual(fetch.call_args_list, [
                    call(url, timeout=60), call(mirror, timeout=60), call(url, timeout=60),
                ])

    def test_download_mirror_replaces_partial_snapshot_bytes(self):
        class InterruptedResponse(io.BytesIO):
            def read(self, size=-1):
                if self.tell():
                    raise TimeoutError("read timed out")
                return super().read(size)

        partial = InterruptedResponse(b"partial content longer than final archive")
        payload = b"LLVM archive"
        url = "https://snapshot.invalid/package.deb"
        mirror = "https://archive.invalid/package.deb"
        with (tempfile.TemporaryDirectory() as directory,
              patch.object(toolchain, "urlopen", side_effect=[partial, io.BytesIO(payload)]) as fetch,
              patch("time.sleep")):
            archive = Path(directory) / "archive"
            toolchain.download(url, hashlib.sha256(payload).hexdigest(), archive, fallback_url=mirror)
            self.assertEqual(archive.read_bytes(), payload)
            self.assertEqual(fetch.call_args_list, [call(url, timeout=60), call(mirror, timeout=60)])
            self.assertTrue(partial.closed)

    def test_download_does_not_retry_checksum_mismatches(self):
        with (tempfile.TemporaryDirectory() as directory,
              patch.object(toolchain, "urlopen", return_value=io.BytesIO(b"wrong archive")) as fetch,
              patch("time.sleep") as sleep):
            with self.assertRaisesRegex(ValueError, "checksum mismatch"):
                toolchain.download("https://example.invalid/llvm.tar", "0" * 64, Path(directory) / "archive",
                                   fallback_url="https://mirror.invalid/llvm.tar")
            fetch.assert_called_once()
            sleep.assert_not_called()

    def test_download_does_not_retry_permanent_network_errors(self):
        url = "https://example.invalid/llvm.tar"
        errors = (HTTPError(url, 404, "Not Found", {}, None),
                  URLError(ssl.SSLCertVerificationError("certificate verify failed")))
        for error in errors:
            with (self.subTest(error=error), tempfile.TemporaryDirectory() as directory,
                  patch.object(toolchain, "urlopen", side_effect=error) as fetch,
                  patch("time.sleep") as sleep):
                with self.assertRaises(URLError) as raised:
                    toolchain.download(url, "0" * 64, Path(directory) / "archive",
                                       fallback_url="https://mirror.invalid/llvm.tar")
                self.assertIs(raised.exception.__cause__, error)
                self.assertIn(url, str(raised.exception))
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
                    toolchain.download("https://example.invalid/llvm.tar", "0" * 64, Path(directory) / "archive",
                                       fallback_url="https://mirror.invalid/llvm.tar")
                self.assertIs(raised.exception, error)
                fetch.assert_called_once()
                sleep.assert_not_called()

    def test_download_mirror_certificate_error_stops_with_its_url(self):
        url = "https://snapshot.invalid/package.deb"
        mirror = "https://archive.invalid/package.deb"
        error = URLError(ssl.SSLCertVerificationError("certificate verify failed"))
        with (tempfile.TemporaryDirectory() as directory,
              patch.object(toolchain, "urlopen", side_effect=[TimeoutError("timed out"), error]) as fetch,
              patch("time.sleep") as sleep):
            with self.assertRaises(URLError) as raised:
                toolchain.download(url, "0" * 64, Path(directory) / "archive", fallback_url=mirror)
            self.assertIs(raised.exception.__cause__, error)
            self.assertIn(mirror, str(raised.exception))
            self.assertEqual(fetch.call_count, 2)
            sleep.assert_called_once_with(1)

    def test_ubuntu_mirrors_preserve_architecture_revision_and_hash(self):
        for arch, mirror, hash_index in (
            ("amd64", "https://archive.ubuntu.com/ubuntu", 2),
            ("arm64", "https://ports.ubuntu.com/ubuntu-ports", 3),
        ):
            with (self.subTest(arch=arch), tempfile.TemporaryDirectory() as directory,
                  patch.object(toolchain, "download") as download,
                  patch.object(toolchain.subprocess, "run") as extract):
                staging = Path(directory)
                payload = staging / "payload"
                self.assertEqual(toolchain.unpack_ubuntu(staging, payload, arch), payload / "usr/lib/llvm-18/bin")
                expected = []
                for package in toolchain.UBUNTU_PACKAGES:
                    component, name = package[:2]
                    path = (f"pool/{component}/l/llvm-toolchain-18/"
                            f"{name}_{toolchain.UBUNTU_REVISION}_{arch}.deb")
                    expected.append(call(f"{toolchain.UBUNTU_SNAPSHOT}/{path}", package[hash_index],
                                         staging / "package.deb", fallback_url=f"{mirror}/{path}"))
                self.assertEqual(download.call_args_list, expected)
                self.assertEqual(extract.call_count, len(toolchain.UBUNTU_PACKAGES))

    def test_ubuntu_never_extracts_a_mirror_checksum_mismatch(self):
        with (tempfile.TemporaryDirectory() as directory,
              patch.object(toolchain, "urlopen", side_effect=[TimeoutError("timed out"), io.BytesIO(b"wrong")]) as fetch,
              patch.object(toolchain.subprocess, "run") as extract,
              patch("time.sleep")):
            with self.assertRaisesRegex(ValueError, "checksum mismatch: https://archive.ubuntu.com"):
                toolchain.unpack_ubuntu(Path(directory), Path(directory) / "payload", "amd64")
            self.assertEqual(fetch.call_count, 2)
            extract.assert_not_called()

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
