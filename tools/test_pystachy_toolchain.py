"""Check the integrity and publication of managed LLVM installations."""

import ast
from contextlib import ExitStack
import errno
import hashlib
import http.client
import io
import os
from pathlib import Path
import re
import socket
import socketserver
import ssl
import subprocess
import sys
import tarfile
import tempfile
import threading
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
        errors.extend((TimeoutError("timed out"), URLError(TimeoutError("timed out")),
                       URLError(socket.gaierror(socket.EAI_AGAIN, "Temporary failure in name resolution"))))
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
        for final in (HTTPError(url, 504, "timeout", {}, None), TimeoutError("timed out"),
                      URLError(socket.gaierror(socket.EAI_AGAIN, "Temporary failure in name resolution"))):
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

    def test_download_temporary_dns_failure_uses_mirror(self):
        url = "https://snapshot.invalid/package.deb"
        mirror = "https://archive.invalid/package.deb"
        payload = b"LLVM archive"
        error = URLError(socket.gaierror(socket.EAI_AGAIN, "Temporary failure in name resolution"))
        with (tempfile.TemporaryDirectory() as directory,
              patch.object(toolchain, "urlopen", side_effect=[error, io.BytesIO(payload)]) as fetch,
              patch("time.sleep") as sleep):
            archive = Path(directory) / "archive"
            toolchain.download(url, hashlib.sha256(payload).hexdigest(), archive, fallback_url=mirror)
            self.assertEqual(archive.read_bytes(), payload)
            self.assertEqual(fetch.call_args_list, [call(url, timeout=60), call(mirror, timeout=60)])
            sleep.assert_called_once_with(1)

    def test_download_failure_preserves_each_endpoint_and_reason(self):
        url = "https://snapshot.invalid/package.deb"
        mirror = "https://archive.invalid/package.deb"
        errors = [
            HTTPError(url, 503, "snapshot unavailable", {}, None),
            HTTPError(mirror, 404, "mirror package missing", {}, None),
            URLError(socket.gaierror(socket.EAI_AGAIN, "Temporary failure in name resolution")),
        ]
        with (tempfile.TemporaryDirectory() as directory,
              patch.object(toolchain, "urlopen", side_effect=errors) as fetch,
              patch("time.sleep")):
            with self.assertRaises(URLError) as raised:
                toolchain.download(url, "0" * 64, Path(directory) / "archive", fallback_url=mirror)
            message = str(raised.exception)
            self.assertIn(f"attempt 1 {url}: HTTP Error 503: snapshot unavailable", message)
            self.assertIn(f"attempt 2 {mirror}: HTTP Error 404: mirror package missing", message)
            self.assertIn(f"attempt 3 {url}: <urlopen error [Errno {socket.EAI_AGAIN}]", message)
            self.assertIn("Temporary failure in name resolution", message)
            self.assertIs(raised.exception.__cause__, errors[-1])
            self.assertEqual(fetch.call_count, 3)

    def test_download_temporary_dns_failures_keep_three_attempt_budget(self):
        url = "https://snapshot.invalid/package.deb"
        mirror = "https://archive.invalid/package.deb"
        errors = [URLError(socket.gaierror(socket.EAI_AGAIN, "Temporary failure in name resolution"))
                  for _ in range(3)]
        with (tempfile.TemporaryDirectory() as directory,
              patch.object(toolchain, "urlopen", side_effect=errors) as fetch,
              patch("time.sleep") as sleep):
            with self.assertRaises(URLError) as raised:
                toolchain.download(url, "0" * 64, Path(directory) / "archive", fallback_url=mirror)
            self.assertIs(raised.exception.__cause__, errors[-1])
            self.assertIn(url, str(raised.exception))
            self.assertEqual(fetch.call_args_list, [
                call(url, timeout=60), call(mirror, timeout=60), call(url, timeout=60),
            ])
            self.assertEqual(sleep.call_args_list, [call(1), call(2)])

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

    def test_download_connection_failures_use_mirror(self):
        url = "https://snapshot.invalid/package.deb"
        mirror = "https://archive.invalid/package.deb"
        payload = b"LLVM archive"
        digest = hashlib.sha256(payload).hexdigest()
        reset = (errno.ECONNRESET, "Connection reset by peer")
        failures = (
            URLError(ConnectionResetError(*reset)),
            URLError(ConnectionRefusedError(errno.ECONNREFUSED, "Connection refused")),
            URLError(ssl.SSLEOFError(ssl.SSL_ERROR_EOF, "EOF occurred in violation of protocol")),
            ConnectionResetError(*reset),
            http.client.RemoteDisconnected("Remote end closed connection without response"),
            http.client.IncompleteRead(b"partial", 1000),
            http.client.BadStatusLine(""),
            ssl.SSLZeroReturnError(ssl.SSL_ERROR_ZERO_RETURN, "TLS/SSL connection has been closed"),
        )
        for failure in failures:
            with (self.subTest(failure=failure), tempfile.TemporaryDirectory() as directory,
                  patch.object(toolchain, "urlopen", side_effect=[failure, io.BytesIO(payload)]) as fetch,
                  patch("time.sleep") as sleep):
                archive = Path(directory) / "archive"
                toolchain.download(url, digest, archive, fallback_url=mirror)
                self.assertEqual(archive.read_bytes(), payload)
                self.assertEqual(fetch.call_args_list, [call(url, timeout=60), call(mirror, timeout=60)])
                sleep.assert_called_once_with(1)

    def test_download_connection_drop_mid_stream_uses_mirror(self):
        def dropped_response(failure):
            class DroppedResponse(io.BytesIO):
                def read(self, size=-1):
                    if self.tell():
                        raise failure
                    return super().read(size)

            return DroppedResponse(b"partial content longer than final archive")

        payload = b"LLVM archive"
        url = "https://snapshot.invalid/package.deb"
        mirror = "https://archive.invalid/package.deb"
        for failure in (ConnectionResetError(errno.ECONNRESET, "Connection reset by peer"),
                        http.client.IncompleteRead(b"partial", 1000)):
            dropped = dropped_response(failure)
            with (self.subTest(failure=failure), tempfile.TemporaryDirectory() as directory,
                  patch.object(toolchain, "urlopen", side_effect=[dropped, io.BytesIO(payload)]) as fetch,
                  patch("time.sleep")):
                archive = Path(directory) / "archive"
                toolchain.download(url, hashlib.sha256(payload).hexdigest(), archive, fallback_url=mirror)
                self.assertEqual(archive.read_bytes(), payload)
                self.assertEqual(fetch.call_args_list, [call(url, timeout=60), call(mirror, timeout=60)])
                self.assertTrue(dropped.closed)

    def test_download_connection_failures_keep_three_attempt_budget_and_diagnostics(self):
        url = "https://snapshot.invalid/package.deb"
        mirror = "https://archive.invalid/package.deb"
        errors = [http.client.RemoteDisconnected("Remote end closed connection without response"),
                  URLError(ConnectionRefusedError(errno.ECONNREFUSED, "Connection refused")),
                  ConnectionResetError(errno.ECONNRESET, "Connection reset by peer")]
        with (tempfile.TemporaryDirectory() as directory,
              patch.object(toolchain, "urlopen", side_effect=errors) as fetch,
              patch("time.sleep") as sleep):
            with self.assertRaises(URLError) as raised:
                toolchain.download(url, "0" * 64, Path(directory) / "archive", fallback_url=mirror)
            message = str(raised.exception)
            self.assertIn(f"attempt 1 {url}: Remote end closed connection without response", message)
            self.assertIn(f"attempt 2 {mirror}: <urlopen error [Errno {errno.ECONNREFUSED}] Connection refused>",
                          message)
            self.assertIn(f"attempt 3 {url}: [Errno {errno.ECONNRESET}] Connection reset by peer", message)
            self.assertIs(raised.exception.__cause__, errors[-1])
            self.assertEqual(fetch.call_args_list, [
                call(url, timeout=60), call(mirror, timeout=60), call(url, timeout=60),
            ])
            self.assertEqual(sleep.call_args_list, [call(1), call(2)])

    def test_download_proxy_policy_rejections_stay_terminal(self):
        # A proxy refusing the tunnel is a policy decision, not an unavailable endpoint.
        url = "https://snapshot.invalid/package.deb"
        error = URLError(OSError("Tunnel connection failed: 403 Forbidden"))
        with (tempfile.TemporaryDirectory() as directory,
              patch.object(toolchain, "urlopen", side_effect=error) as fetch,
              patch("time.sleep") as sleep):
            with self.assertRaises(URLError) as raised:
                toolchain.download(url, "0" * 64, Path(directory) / "archive",
                                   fallback_url="https://archive.invalid/package.deb")
            self.assertIs(raised.exception.__cause__, error)
            fetch.assert_called_once()
            sleep.assert_not_called()

    def test_download_real_dropped_connection_uses_mirror(self):
        # Mocks encode assumptions about urllib's exceptions; real sockets show which ones escape.
        payload = b"LLVM archive"

        class Drop(socketserver.BaseRequestHandler):
            def handle(self):
                self.request.recv(4096)  # read the request, answer nothing, close

        class Serve(socketserver.BaseRequestHandler):
            def handle(self):
                self.request.recv(4096)
                self.request.sendall(
                    b"HTTP/1.1 200 OK\r\nContent-Length: %d\r\nConnection: close\r\n\r\n%b"
                    % (len(payload), payload))

        with (socketserver.ThreadingTCPServer(("127.0.0.1", 0), Drop) as dropping,
              socketserver.ThreadingTCPServer(("127.0.0.1", 0), Serve) as serving,
              tempfile.TemporaryDirectory() as directory,
              patch.dict(toolchain.os.environ, {"no_proxy": "127.0.0.1", "NO_PROXY": "127.0.0.1"}),
              patch("time.sleep")):
            for server in (dropping, serving):
                threading.Thread(target=server.serve_forever, daemon=True).start()
            archive = Path(directory) / "archive"
            try:
                toolchain.download(
                    f"http://127.0.0.1:{dropping.server_address[1]}/package.deb",
                    hashlib.sha256(payload).hexdigest(), archive,
                    fallback_url=f"http://127.0.0.1:{serving.server_address[1]}/package.deb")
            finally:
                for server in (dropping, serving):
                    server.shutdown()
            self.assertEqual(archive.read_bytes(), payload)

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
                  URLError(socket.gaierror(socket.EAI_NONAME, "Name or service not known")),
                  URLError(socket.gaierror(socket.EAI_FAIL, "Non-recoverable failure in name resolution")),
                  URLError("Temporary failure in name resolution"),
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

    def test_doctor_observes_missing_partial_and_complete_managed_installs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "_pystachy_source").symlink_to(Path(toolchain.__file__).parent)
            cache = root / "managed"
            dest = cache / f"ubuntu-{toolchain.UBUNTU_REVISION}-amd64"
            env = {key: val for key, val in os.environ.items() if not key.startswith("PYSTACHY_")}
            env.update(PYSTACHY_LLVM_CACHE=str(cache), PYSTACHY_CACHE=str(root / "runtime"))
            script = """from unittest.mock import patch
from _pystachy_source import pystachy_cli, pystachy_toolchain as tc
with (patch.object(tc.sys, 'platform', 'linux'), patch.object(tc.platform, 'machine', return_value='x86_64'),
      patch.object(tc.platform, 'freedesktop_os_release', return_value={'ID': 'ubuntu', 'VERSION_ID': '24.04'}),
      patch.object(tc, 'ensure_toolchain', side_effect=AssertionError('doctor tried to install LLVM'))):
    pystachy_cli.main()
"""

            def doctor():
                result = subprocess.run([sys.executable, "-B", "-c", script, "doctor"],
                                        cwd=root, env=env, text=True, capture_output=True, timeout=20)
                self.assertEqual(result.stderr, "")
                self.assertFalse((root / "runtime").exists())
                return result

            first = doctor()
            self.assertEqual(first.returncode, 1)
            self.assertIn("pending download on first compile", first.stdout)
            self.assertFalse(cache.exists())
            (dest / "bin").mkdir(parents=True)
            for tool in toolchain.TOOLS:
                binary = dest / "bin" / tool
                binary.write_text("#!/bin/sh\necho 'LLVM version 18.1.3'\n")
                binary.chmod(0o700)
            partial = doctor()
            self.assertEqual(partial.returncode, 1)
            self.assertIn("clang: 18.1.3", partial.stdout)
            self.assertIn("pending download on first compile", partial.stdout)
            header = dest / "lib/clang/18/include/stddef.h"
            header.parent.mkdir(parents=True)
            header.touch()
            ready = doctor()
            self.assertEqual(ready.returncode, 0, ready.stdout)
            self.assertIn("Managed LLVM 18.1.3: cached", ready.stdout)

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


class MinimalToolchainTests(unittest.TestCase):
    """The archive of docs/llvm-toolchain.md, on Linux that has no LLVM of its own."""

    DEBIAN = {"ID": "debian", "VERSION_ID": "12"}

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.cache = self.root / "cache"

    def archive(self, tools=toolchain.TOOLS, release=toolchain.MINIMAL_VERSION, machine="x86_64") -> Path:
        """Laid out as the published archive: tools that print their release, and clang's headers."""
        directory = Path(tempfile.mkdtemp(dir=self.root))
        root = toolchain.minimal_archive(machine)
        tree = directory / root
        for name in tools:
            path = tree / "bin" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            # (clang finds the host's GCC, as on the distributions it knows)
            path.write_text(f"#!/bin/sh\ncase \"$1\" in --print-file-name=*) echo \"/gcc/${{1#*=}}\" ;; "
                            f"*) echo '{name} version {release}' ;; esac\n")
            path.chmod(0o755)
        header = tree / "lib/clang/18/include/stddef.h"
        header.parent.mkdir(parents=True)
        header.touch()
        archive = directory / f"{root}.tar.xz"
        with tarfile.open(archive, "w:xz") as packed:
            packed.add(tree, arcname=root)
        return archive

    def host(self, stack: ExitStack, *, machine="x86_64", distro=DEBIAN, glibc=(2, 36), llvm=False, archive=None):
        """Stand on a Linux host of this kind; the release is the archive, where one is given."""
        release = {"side_effect": distro} if isinstance(distro, Exception) else {"return_value": distro}
        patches = [patch.dict(toolchain.os.environ, {"PYSTACHY_LLVM_CACHE": str(self.cache)}),
                   patch.object(toolchain.sys, "platform", "linux"),
                   patch.object(toolchain.platform, "machine", return_value=machine),
                   patch.object(toolchain.platform, "freedesktop_os_release", **release),
                   patch.object(toolchain, "glibc", return_value=glibc),
                   patch.object(toolchain, "host_llvm", return_value=llvm)]
        if archive is not None:
            patches += [patch.object(toolchain, "MINIMAL_RELEASE", archive.parent.as_uri()),
                        patch.dict(toolchain.MINIMAL_SHA256, {machine: hashlib.sha256(archive.read_bytes()).hexdigest()})]
        for each in patches:
            stack.enter_context(each)

    def test_first_use_downloads_the_machine_s_archive_and_later_uses_do_not(self):
        for machine in ("x86_64", "aarch64"):
            archive = self.archive(machine=machine)
            with self.subTest(machine=machine), ExitStack() as stack:
                self.host(stack, machine=machine, archive=archive)
                bin_dir = toolchain.ensure_toolchain()
                key = f"minimal-{toolchain.MINIMAL_VERSION}-{toolchain.MINIMAL_REVISION}-{machine}"
                self.assertEqual(bin_dir, self.cache.resolve() / key / "bin")
                self.assertEqual(bin_dir.resolve().parent.name, f"pystachy-llvm-{toolchain.MINIMAL_VERSION}-linux-{machine}")
                for name in toolchain.TOOLS:
                    self.assertEqual(subprocess.check_output([str(bin_dir / name), "--version"], text=True),
                                     f"{name} version {toolchain.MINIMAL_VERSION}\n")
                self.assertTrue((bin_dir.resolve().parent / "lib/clang/18/include/stddef.h").is_file())
                archive.unlink()
                self.assertEqual(toolchain.ensure_toolchain(), bin_dir)

    def test_host_gcc_that_clang_does_not_find_is_named_beside_it(self):
        tools = self.root / "bin"
        tools.mkdir()
        clang, gcc, config = tools / "clang", tools / "gcc", tools / "clang.cfg"
        for found, libgcc, expected in (
            ("crtbeginS.o", "/usr/lib/gcc/aarch64-amazon-linux/11/libgcc.a", "--gcc-triple=aarch64-amazon-linux\n"),
            ("/usr/lib/gcc/aarch64-redhat-linux/11/crtbeginS.o", "/usr/lib/gcc/aarch64-redhat-linux/11/libgcc.a", None),
            ("crtbeginS.o", "libgcc.a", None),  # a GCC that does not find its own library either
            ("crtbeginS.o", None, None),  # no GCC
        ):
            with self.subTest(found=found, libgcc=libgcc):
                config.unlink(missing_ok=True)
                gcc.unlink(missing_ok=True)
                clang.write_text(f"#!/bin/sh\n[ \"$1\" = --print-file-name=crtbeginS.o ] && echo {found}\n")
                clang.chmod(0o755)
                if libgcc is not None:
                    gcc.write_text(f"#!/bin/sh\n[ \"$1\" = -print-libgcc-file-name ] && echo {libgcc}\n")
                    gcc.chmod(0o755)
                with patch.dict(toolchain.os.environ, {"PATH": str(tools)}):
                    toolchain.name_host_gcc(tools)
                self.assertEqual(config.read_text() if config.exists() else None, expected)

    def test_only_the_downloaded_archive_is_told_the_host_s_gcc(self):
        archive = self.archive()
        with ExitStack() as stack:
            self.host(stack, archive=archive)
            named = stack.enter_context(patch.object(toolchain, "name_host_gcc"))
            bin_dir = toolchain.ensure_toolchain()
            # (before the directory is published to the cache, where it does not change again)
            named.assert_called_once()
            self.assertEqual(named.call_args.args[0].name, "bin")
            self.assertNotEqual(named.call_args.args[0], bin_dir.resolve())

    def test_archive_with_another_digest_is_not_extracted(self):
        archive = self.archive()
        with ExitStack() as stack:
            self.host(stack, archive=archive)
            stack.enter_context(patch.dict(toolchain.MINIMAL_SHA256, {"x86_64": "0" * 64}))
            extract = stack.enter_context(patch.object(toolchain.tarfile, "open"))
            with self.assertRaisesRegex(ValueError, "checksum mismatch"):
                toolchain.ensure_toolchain()
            extract.assert_not_called()
            self.assertEqual(list(self.cache.glob("*/bin")), [])

    def test_incomplete_or_other_release_is_not_published_to_the_cache(self):
        for archive, message in ((self.archive(tools=toolchain.TOOLS[:-1]), "missing required tools"),
                                 (self.archive(release="18.1.3"), "expected LLVM 18.1.8 from clang")):
            with self.subTest(message=message), ExitStack() as stack:
                self.host(stack, archive=archive)
                with self.assertRaisesRegex(ValueError, message):
                    toolchain.ensure_toolchain()
                self.assertEqual(list(self.cache.glob("*/bin")), [])

    def test_only_glibc_linux_without_a_host_llvm_selects_it(self):
        ubuntu_22 = {"ID": "ubuntu", "VERSION_ID": "22.04"}
        hosts = (
            ({}, True),
            ({"glibc": toolchain.MINIMAL_GLIBC}, True),
            ({"distro": ubuntu_22, "glibc": (2, 35)}, True),
            ({"distro": OSError("no os-release")}, True),
            ({"glibc": (2, 33)}, False),  # the runtime does not link there
            ({"glibc": ()}, False),  # musl
            ({"llvm": True}, False),  # the host's LLVM keeps serving
            ({"machine": "aarch64"}, True),
            ({"machine": "aarch64", "glibc": (2, 33)}, False),
            ({"machine": "riscv64"}, False),  # no archive is published
        )
        for host, selected in hosts:
            with self.subTest(host=host), ExitStack() as stack:
                self.host(stack, **host)
                unpack = stack.enter_context(patch.object(toolchain, "unpack_minimal", side_effect=ValueError("selected")))
                if selected:
                    with self.assertRaisesRegex(ValueError, "selected"):
                        toolchain.ensure_toolchain()
                else:
                    self.assertIsNone(toolchain.ensure_toolchain())
                    unpack.assert_not_called()

    def test_ubuntu_24_04_keeps_its_packages(self):
        ubuntu = {"ID": "ubuntu", "VERSION_ID": "24.04"}
        for llvm, machine in ((False, "x86_64"), (True, "x86_64"), (False, "aarch64")):
            with self.subTest(llvm=llvm, machine=machine), ExitStack() as stack:
                self.host(stack, machine=machine, distro=ubuntu, glibc=(2, 39), llvm=llvm)
                minimal = stack.enter_context(patch.object(toolchain, "unpack_minimal"))
                named = stack.enter_context(patch.object(toolchain, "name_host_gcc"))
                stack.enter_context(patch.object(toolchain, "unpack_ubuntu", side_effect=ValueError("packages")))
                with self.assertRaisesRegex(ValueError, "packages"):
                    toolchain.ensure_toolchain()
                minimal.assert_not_called()
                named.assert_not_called()

    def test_macos_keeps_the_upstream_release(self):
        with ExitStack() as stack:
            for each in (patch.dict(toolchain.os.environ, {"PYSTACHY_LLVM_CACHE": str(self.cache)}),
                         patch.object(toolchain.sys, "platform", "darwin"),
                         patch.object(toolchain.platform, "machine", return_value="arm64")):
                stack.enter_context(each)
            others = [stack.enter_context(patch.object(toolchain, name))
                      for name in ("unpack_ubuntu", "unpack_minimal", "name_host_gcc")]
            stack.enter_context(patch.object(toolchain, "unpack_macos", side_effect=ValueError("upstream")))
            with self.assertRaisesRegex(ValueError, "upstream"):
                toolchain.ensure_toolchain()
            for other in others:
                other.assert_not_called()

    def test_doctor_is_told_of_the_archive_only_where_it_would_be_downloaded(self):
        for machine in ("x86_64", "aarch64"):
            with self.subTest(machine=machine), ExitStack() as stack:
                self.host(stack, machine=machine)
                key = f"minimal-{toolchain.MINIMAL_VERSION}-{toolchain.MINIMAL_REVISION}-{machine}"
                self.assertEqual(toolchain.managed_toolchain(),
                                 (self.cache.resolve() / key, toolchain.MINIMAL_VERSION, machine))
        for host in ({"llvm": True}, {"glibc": (2, 33)}, {"glibc": ()}, {"machine": "riscv64"}):
            with self.subTest(host=host), ExitStack() as stack:
                self.host(stack, **host)
                self.assertIsNone(toolchain.managed_toolchain())
        self.assertFalse(self.cache.exists())  # asking installs nothing

    def test_glibc_is_the_running_c_library_s_release(self):
        for answer, expected in (("glibc 2.39", (2, 39)), ("glibc 2.4", (2, 4)), ("glibc 2.41.9000", (2, 41, 9000)),
                                 ("musl 1.2.5", ()), ("glibc", ()), ("glibc 2.x", ()), ("", ()), (None, ())):
            with self.subTest(answer=answer), patch.object(toolchain.os, "confstr", return_value=answer, create=True):
                self.assertEqual(toolchain.glibc(), expected)
        for error in (ValueError("unrecognized configuration name"), OSError(errno.EINVAL, "Invalid argument")):
            with self.subTest(error=error), patch.object(toolchain.os, "confstr", side_effect=error, create=True):
                self.assertEqual(toolchain.glibc(), ())

    def test_host_llvm_is_what_the_driver_finds_without_a_setting(self):
        driver = (Path(toolchain.__file__).parent / "src/pystachy_compiler/driver.py").read_text()
        found = re.search(r'def llvm_dir\(\).*?for d in \[(.*?)\]:\s+if all\(\[os\.path\.exists\(d \+ "/" \+ t\) for t in \[(.*?)\]\]\)',
                          driver, re.S)
        self.assertIsNotNone(found, "llvm_dir no longer reads as a list of directories and a list of tools")
        self.assertEqual(ast.literal_eval(f"({found[1]},)"), toolchain.HOST_LLVM)
        self.assertEqual(sorted(ast.literal_eval(f"({found[2]},)")), sorted(toolchain.TOOLS))

        tools = self.root / "tools"
        tools.mkdir()
        for name in toolchain.TOOLS[:-1]:
            (tools / name).touch(mode=0o755)
        elsewhere = str(self.root / "none")
        for places, path in (((str(tools),), elsewhere), ((elsewhere,), str(tools))):
            with self.subTest(places=places), patch.object(toolchain, "HOST_LLVM", places), \
                    patch.dict(toolchain.os.environ, {"PATH": path}):
                last = tools / toolchain.TOOLS[-1]
                self.assertFalse(toolchain.host_llvm())
                last.touch(mode=0o755)
                self.assertTrue(toolchain.host_llvm())
                last.unlink()
