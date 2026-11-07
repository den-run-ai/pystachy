"""Host/tag, payload and fail-closed publication checks for the repair wheel."""

import base64
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import hashlib
from importlib.machinery import ExtensionFileLoader, SourceFileLoader
import json
import os
from pathlib import Path
import signal
import struct
import subprocess
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest import mock
import zipfile

import build_json_repair_wheel as builder
import json_repair_wheel_smoke as smoke


READELF = """
 0x0000000000000001 (NEEDED) Shared library: [libc.so.6]
 0x000000006ffffffe (VERNEED) 0xae8
Version needs section '.gnu.version_r' contains 1 entry:
 000000: Version: 1 File: libc.so.6 Cnt: 1
 0x0010: Name: GLIBC_2.34 Flags: none Version: 2
"""


@contextmanager
def host(architecture="x86_64", implementation="cpython", version=(3, 13, 16),
         gil_disabled=0, gil_enabled=True, platform_name=None, system="linux", libc="glibc 2.39"):
    identity = SimpleNamespace(**(vars(sys.implementation) | {"name": implementation}))
    with (mock.patch.object(builder.sys, "implementation", identity),
          mock.patch.object(builder.sys, "version_info", version),
          mock.patch.object(builder.sys, "platform", system),
          mock.patch.object(builder.sys, "_is_gil_enabled", return_value=gil_enabled, create=True),
          mock.patch.object(builder.sysconfig, "get_config_var", return_value=gil_disabled),
          mock.patch.object(builder.sysconfig, "get_platform", return_value=platform_name or f"linux-{architecture}"),
          mock.patch.object(builder.platform, "machine", return_value=architecture),
          mock.patch.object(builder.os, "confstr", return_value=libc)):
        yield


def elf(path, machine=62, kind=3):
    path.parent.mkdir(parents=True, exist_ok=True)
    header = bytearray(64)
    header[:7] = b"\x7fELF\x02\x01\x01"
    struct.pack_into("<HH", header, 16, kind, machine)
    path.write_bytes(header)


class HostTests(unittest.TestCase):
    def test_native_platform_tags(self):
        for architecture in ("x86_64",):
            with self.subTest(architecture=architecture), host(architecture):
                self.assertEqual(builder.host_configuration(), {
                    "architecture": architecture, "tag": f"cp312-abi3-linux_{architecture}", "glibc": "glibc 2.39"})

    def test_unsupported_interpreters(self):
        for options in ({"implementation": "pypy"}, {"version": (3, 11, 12)},
                        {"gil_disabled": 1}, {"gil_enabled": False}):
            with self.subTest(options=options), host(**options), self.assertRaisesRegex(ValueError, "CPython"):
                builder.host_configuration()

    def test_unsupported_platforms_and_cross_configuration(self):
        for options in ({"architecture": "armv7l"}, {"architecture": "aarch64"}, {"system": "darwin"},
                        {"platform_name": "macosx-11.0-arm64", "architecture": "arm64"},
                        {"platform_name": "linux-aarch64"}, {"libc": None}, {"libc": "musl 1.2.5"}):
            with self.subTest(options=options), host(**options), self.assertRaisesRegex(ValueError, "glibc Linux"):
                builder.host_configuration()

    def test_missing_glibc_query(self):
        with host(), mock.patch.object(builder.os, "confstr", side_effect=ValueError("unsupported")):
            with self.assertRaisesRegex(ValueError, "glibc Linux"):
                builder.host_configuration()

    def test_missing_prerequisites(self):
        for missing in ("wheel", "ensurepip", "readelf"):
            with (self.subTest(missing=missing),
                  mock.patch.object(builder.importlib.util, "find_spec", side_effect=lambda name, target=missing: None if name == target else object()),
                  mock.patch.object(builder.shutil, "which", return_value=None if missing == "readelf" else "/usr/bin/readelf"),
                  self.assertRaisesRegex(ValueError, missing)):
                builder.prerequisites()


class WheelTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="pystachy-repair-wheel-test-")
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.out = self.directory / "dist"
        self.payload = self.directory / "payload"
        self.extension = self.payload / builder.PACKAGE / "_native.abi3.so"
        self.console = self.payload / f"{builder.DIST}.data/scripts/json-repair-native"
        self.host = {"architecture": "x86_64", "tag": "cp312-abi3-linux_x86_64", "glibc": "glibc 2.39"}

    def readelf(self):
        return mock.patch.object(builder.subprocess, "run", return_value=subprocess.CompletedProcess(
            ["readelf"], 0, READELF, ""))

    def test_report_covers_both_binaries_and_dependencies(self):
        elf(self.extension)
        elf(self.console)
        with self.readelf():
            report = builder.audit_payload(self.payload, self.host)
        self.assertEqual(report["elf_count"], 2)
        self.assertEqual(report["wheel_tag"], self.host["tag"])
        self.assertTrue(report["limitations"])
        for binary in report["binaries"]:
            self.assertEqual(binary["needed"], ["libc.so.6"])
            self.assertEqual(binary["glibc_symbol_floor"], "2.34")

    def test_missing_or_non_elf_payload_is_rejected(self):
        elf(self.extension)
        self.console.parent.mkdir(parents=True)
        self.console.write_text("a wrapper is not the standalone executable\n")
        with self.readelf(), self.assertRaisesRegex(ValueError, "exactly"):
            builder.audit_payload(self.payload, self.host)

    def test_mixed_architecture_is_rejected(self):
        elf(self.extension)
        elf(self.console, machine=183)
        with self.readelf(), self.assertRaisesRegex(ValueError, "architecture aarch64 differs from x86_64"):
            builder.audit_payload(self.payload, self.host)

    def test_extension_must_be_shared_object(self):
        elf(self.extension, kind=2)
        elf(self.console)
        with self.readelf(), self.assertRaisesRegex(ValueError, "shared object"):
            builder.audit_payload(self.payload, self.host)

    def test_unexpected_elf_is_not_omitted_from_audit(self):
        elf(self.extension)
        elf(self.console)
        elf(self.payload / "unexpected.so")
        with self.readelf(), self.assertRaisesRegex(ValueError, "exactly"):
            builder.audit_payload(self.payload, self.host)

    def fake_build(self, command, **kwargs):
        command = [str(value) for value in command]
        if command[0] == "readelf":
            return subprocess.CompletedProcess(command, 0, READELF, "")
        if command[2] in ("ext", "build"):
            elf(Path(command[-1]), machine=62 if self.host["architecture"] == "x86_64" else 183)
        elif command[1:4] == ["-m", "wheel", "pack"]:
            payload, staging = Path(command[4]), Path(command[-1])
            target = staging / f"{builder.DIST}-{self.host['tag']}.whl"
            with zipfile.ZipFile(target, "w") as archive:
                for path in sorted(payload.rglob("*")):
                    if path.is_file():
                        archive.write(path, path.relative_to(payload))
        else:
            self.fail(f"unexpected build command: {command}")
        return subprocess.CompletedProcess(command, 0)

    def test_unsupported_host_stops_before_build_or_output(self):
        with (mock.patch.object(builder, "host_configuration", side_effect=ValueError("unsupported host")),
              mock.patch.object(builder, "prerequisites") as prereqs,
              mock.patch.object(builder.subprocess, "run") as run,
              self.assertRaisesRegex(ValueError, "unsupported host")):
            builder.build(self.out)
        self.assertFalse(self.out.exists())
        prereqs.assert_not_called()
        run.assert_not_called()

    def test_failed_installed_check_preserves_previous_wheel_and_evidence(self):
        self.out.mkdir()
        wheel = self.out / f"{builder.DIST}-{self.host['tag']}.whl"
        wheel.write_bytes(b"previous wheel")
        evidence = wheel.with_suffix(".validation.json")
        evidence.write_bytes(b"previous evidence")
        with (mock.patch.object(builder, "host_configuration", return_value=self.host),
              mock.patch.object(builder, "prerequisites"),
              mock.patch.object(builder.subprocess, "run", side_effect=self.fake_build),
              mock.patch.object(builder, "smoke", side_effect=RuntimeError("incomplete replay")),
              self.assertRaisesRegex(RuntimeError, "incomplete replay")):
            builder.build(self.out)
        self.assertEqual(wheel.read_bytes(), b"previous wheel")
        self.assertEqual(evidence.read_bytes(), b"previous evidence")
        self.assertEqual(set(self.out.iterdir()), {wheel, evidence})

    def test_success_publishes_audited_native_host_tag_after_smoke(self):
        def checked(wheel):
            self.assertFalse((self.out / wheel.name).exists())
            with zipfile.ZipFile(wheel) as archive:
                report = json.loads(archive.read(f"{builder.DIST}.dist-info/native-abi.json"))
                self.assertEqual({entry["architecture"] for entry in report["binaries"]}, {"x86_64"})
                self.assertIn(self.host["tag"], archive.read(f"{builder.DIST}.dist-info/WHEEL").decode())
            return {"wheel": wheel.name, "wheel_sha256": smoke.sha256(wheel)}

        with (mock.patch.object(builder, "host_configuration", return_value=self.host),
              mock.patch.object(builder, "prerequisites"),
              mock.patch.object(builder.subprocess, "run", side_effect=self.fake_build),
              mock.patch.object(builder, "smoke", side_effect=checked) as check):
            wheel = builder.build(self.out)
        check.assert_called_once()
        report = json.loads(wheel.with_suffix(".validation.json").read_text())
        self.assertEqual(report["installation"]["wheel_sha256"], smoke.sha256(wheel))
        self.assertEqual(report["abi"]["wheel_tag"], "cp312-abi3-linux_x86_64")


class PublicationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="pystachy-repair-publish-test-")
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.out = self.directory / "dist"
        self.out.mkdir()

    def candidate(self, name):
        staging = self.directory / name
        staging.mkdir()
        wheel = staging / "fixture.whl"
        wheel.write_bytes(name.encode())
        evidence = wheel.with_suffix(".validation.json")
        evidence.write_text(json.dumps({"installation": {"wheel_sha256": smoke.sha256(wheel)}}))
        return wheel, evidence

    def assert_matching(self, expected):
        wheel = self.out / "fixture.whl"
        evidence = wheel.with_suffix(".validation.json")
        self.assertEqual(wheel.read_bytes(), expected.encode())
        self.assertEqual(json.loads(evidence.read_text())["installation"]["wheel_sha256"], smoke.sha256(wheel))

    def test_replacement_failures_preserve_the_previous_pair(self):
        for failed_name in ("fixture.whl", "fixture.validation.json"):
            with self.subTest(failed_name=failed_name):
                previous = self.candidate("old-" + failed_name)
                builder.publish(*previous, self.out)
                wheel, evidence = self.candidate("new-" + failed_name)
                replace = Path.replace

                def failed_replace(source, target, wheel=wheel, failed_name=failed_name, replace=replace):
                    if source.parent == wheel.parent and source.name == failed_name:
                        raise OSError("publication failed")
                    return replace(source, target)

                with mock.patch.object(Path, "replace", failed_replace), self.assertRaisesRegex(OSError, "publication failed"):
                    builder.publish(wheel, evidence, self.out)
                self.assert_matching("old-" + failed_name)
                self.assertFalse(list(self.out.glob(".json-repair-publish-*")))

    def test_failed_initial_publication_leaves_no_partial_artifact(self):
        wheel, evidence = self.candidate("new")
        replace = Path.replace

        def failed_replace(source, target):
            if source == evidence:
                raise OSError("report rename failed")
            return replace(source, target)

        with mock.patch.object(Path, "replace", failed_replace), self.assertRaisesRegex(OSError, "report rename failed"):
            builder.publish(wheel, evidence, self.out)
        self.assertFalse((self.out / wheel.name).exists())
        self.assertFalse((self.out / evidence.name).exists())
        self.assertFalse(list(self.out.glob(".json-repair-publish-*")))

    def test_changed_wheel_cannot_publish_its_old_validation(self):
        wheel, evidence = self.candidate("new")
        wheel.write_bytes(b"changed after validation")
        with self.assertRaisesRegex(ValueError, "changed after its installed validation"):
            builder.publish(wheel, evidence, self.out)
        self.assertFalse((self.out / wheel.name).exists())
        self.assertFalse((self.out / evidence.name).exists())

    def test_concurrent_publishers_cannot_interleave_replacements(self):
        first = self.candidate("first")
        second = self.candidate("second")
        first_wheel_written = threading.Event()
        release_first = threading.Event()
        second_started = threading.Event()
        second_write = threading.Event()
        replace = Path.replace

        def paused_replace(source, target):
            if source.parent == second[0].parent:
                second_write.set()
            result = replace(source, target)
            if source == first[0]:
                first_wheel_written.set()
                if not release_first.wait(5):
                    raise RuntimeError("test did not release the first publisher")
            return result

        def publish_second():
            second_started.set()
            builder.publish(*second, self.out)

        with mock.patch.object(Path, "replace", paused_replace), ThreadPoolExecutor(max_workers=2) as pool:
            first_result = pool.submit(builder.publish, *first, self.out)
            try:
                self.assertTrue(first_wheel_written.wait(5))
                second_result = pool.submit(publish_second)
                self.assertTrue(second_started.wait(5))
                self.assertFalse(second_write.wait(0.1), "another publisher wrote inside the locked pair")
            finally:
                release_first.set()
            first_result.result(timeout=5)
            second_result.result(timeout=5)
        self.assert_matching("second")


class WorkerCleanupTests(unittest.TestCase):
    def worker(self, pid, stubborn=False):
        worker = mock.Mock(pid=pid)
        alive = [pid is not None]
        worker.is_alive.side_effect = lambda: alive[0]

        def terminate():
            if not stubborn:
                alive[0] = False

        def kill():
            alive[0] = False

        def close():
            if alive[0]:
                raise ValueError("cannot close a live process")

        worker.terminate.side_effect = terminate
        worker.kill.side_effect = kill
        worker.close.side_effect = close
        return worker

    def context(self, workers):
        receivers = [mock.Mock(), mock.Mock()]
        senders = [mock.Mock(), mock.Mock()]
        context = mock.Mock()
        context.Pipe.side_effect = list(zip(receivers, senders))
        context.Process.side_effect = workers
        return context, receivers, senders

    def test_stubborn_worker_is_killed_and_reaped_before_all_workers_close(self):
        workers = [self.worker(101, stubborn=True), self.worker(102)]
        context, receivers, senders = self.context(workers)
        receivers[0].poll.return_value = False
        with mock.patch.object(smoke.multiprocessing, "get_context", return_value=context):
            with self.assertRaisesRegex(RuntimeError, "did not return a result"):
                smoke.process_checks(Path("/fixture/venv"), {})
        workers[0].kill.assert_called_once_with()
        self.assertEqual(workers[0].join.call_args_list, [mock.call(5), mock.call()])
        workers[1].kill.assert_not_called()
        for worker, receive, send in zip(workers, receivers, senders):
            worker.close.assert_called_once_with()
            receive.close.assert_called_once_with()
            send.close.assert_called_once_with()

    def test_failed_start_closes_pipes_and_stops_started_workers(self):
        workers = [self.worker(101), self.worker(None)]
        workers[1].start.side_effect = OSError("spawn failed")
        context, receivers, senders = self.context(workers)
        with mock.patch.object(smoke.multiprocessing, "get_context", return_value=context):
            with self.assertRaisesRegex(OSError, "spawn failed"):
                smoke.process_checks(Path("/fixture/venv"), {})
        workers[0].terminate.assert_called_once_with()
        workers[1].join.assert_not_called()
        for worker, receive, send in zip(workers, receivers, senders):
            worker.close.assert_called_once_with()
            receive.close.assert_called_once_with()
            send.close.assert_called_once_with()

    def test_cleanup_failure_does_not_skip_the_other_worker_or_mask_the_original(self):
        workers = [self.worker(101), self.worker(102)]
        workers[0].close.side_effect = ValueError("cleanup control")
        context, receivers, senders = self.context(workers)
        receivers[0].poll.return_value = False
        with mock.patch.object(smoke.multiprocessing, "get_context", return_value=context):
            with self.assertRaisesRegex(RuntimeError, "did not return a result") as failure:
                smoke.process_checks(Path("/fixture/venv"), {})
        self.assertIn("cleanup control", " ".join(failure.exception.__notes__))
        workers[1].terminate.assert_called_once_with()
        workers[1].close.assert_called_once_with()
        for receive, send in zip(receivers, senders):
            receive.close.assert_called_once_with()
            send.close.assert_called_once_with()


class SmokeTests(unittest.TestCase):
    def test_requires_complete_current_corpus_not_just_zero_exit(self):
        self.assertEqual(smoke.corpus_summary("Checking native.so\n837/837 match; 0 problems\n", 837),
                         {"cases": 837, "matched": 837, "problems": 0})
        for output, count in [("", 837), ("645/645 match; 0 problems\n", 837),
                              ("836/837 match; 1 problems\n", 837), ("0/0 match; 0 problems\n", 0),
                              ("837/837 match; 0 problems\n837/837 match; 0 problems\n", 837)]:
            with self.subTest(output=output), self.assertRaisesRegex(ValueError, "did not confirm"):
                smoke.corpus_summary(output, count)

    def test_consumer_environment_does_not_inherit_source_or_runtime_settings(self):
        with mock.patch.dict(smoke.os.environ, {"PYTHONPATH": "source", "PYTHONHOME": "home",
                                               "PYSTACHY_HOME": "checkout", "PYSTACHY_GC_STRESS": "1",
                                               "VIRTUAL_ENV": "existing", "PATH": "tools"}, clear=True):
            self.assertEqual(smoke.clean_environment(), {"PATH": "tools", "LC_ALL": "C"})

    def test_subprocess_failure_is_not_accepted_as_validation(self):
        with self.assertRaisesRegex(RuntimeError, "native failure"):
            smoke.execute([sys.executable, "-I", "-c",
                           "import sys; print('partial output'); sys.exit('native failure')"],
                          Path.cwd(), smoke.clean_environment())

    @unittest.skipUnless(sys.platform == "linux", "requires Linux process groups and /proc")
    def test_timeout_stops_spawned_descendants_and_reaps_the_probe(self):
        def running(pid):
            try:
                state = (Path("/proc") / str(pid) / "stat").read_text().rsplit(")", 1)[1].split()[0]
            except FileNotFoundError:
                return False
            return state not in ("Z", "X")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pids = root / "pids.json"
            source = root / "probe.py"
            source.write_text(
                "import json, os, pathlib, signal, subprocess, sys, time\n"
                "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
                "child = subprocess.Popen([sys.executable, '-I', '-c', 'import time; time.sleep(30)'])\n"
                "pathlib.Path(sys.argv[1]).write_text(json.dumps([os.getpid(), child.pid]))\n"
                "time.sleep(30)\n")
            owned = []
            try:
                with self.assertRaises(subprocess.TimeoutExpired):
                    smoke.execute([sys.executable, "-I", str(source), str(pids)], root,
                                  smoke.clean_environment(), timeout=1)
                owned = json.loads(pids.read_text())
                deadline = time.monotonic() + 5
                while any(running(pid) for pid in owned) and time.monotonic() < deadline:
                    time.sleep(0.01)
                self.assertFalse(any(running(pid) for pid in owned), "timed-out probe left a running descendant")
                with self.assertRaises(ChildProcessError):
                    os.waitpid(owned[0], os.WNOHANG)
            finally:
                if not owned and pids.exists():
                    owned = json.loads(pids.read_text())
                for pid in owned:
                    if running(pid):
                        try:
                            os.kill(pid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass

    def test_changed_validation_inputs_invalidate_the_result(self):
        for changed in (None, "cases", "probe"):
            with self.subTest(changed=changed), tempfile.TemporaryDirectory() as directory:
                root = Path(directory) / "checkout"
                suite = root / "tests/upstream/json_repair"
                suite.mkdir(parents=True)
                (root / "tools").mkdir()
                cases = suite / "cases.json"
                cases.write_text('[{"id": 0}]\n')
                probe = root / "tools/json_repair_wheel_smoke.py"
                for path in (suite / "extension.py", suite / "replay.py", root / "tools/json_repair_parity.py", probe):
                    path.write_text("# fixture\n")
                (suite / "cli.py").write_text(
                    "from types import SimpleNamespace\nCASES = [SimpleNamespace(status=0, args=[])]\n"
                    "def run_case(command, case, env): return b'', b''\n")
                wheel = Path(directory) / "fixture.whl"
                wheel.write_bytes(b"fixture")

                def execute(command, cwd, env, changed=changed, root=root, suite=suite, cases=cases, probe=probe):
                    self.assertFalse(cwd.is_relative_to(root))
                    self.assertEqual(command[1], "-I")
                    if "--installed-prefix" in command:
                        self.assertEqual(command[2], str(probe))
                        return json.dumps({"spawned_processes": 2, "thread_rejections": 2})
                    if command[-1] == str(suite / "extension.py"):
                        if env.get("PYSTACHY_GC_STRESS") == "1" and changed:
                            target = cases if changed == "cases" else probe
                            target.write_bytes(target.read_bytes() + b" \n")
                        return "1/1 match; 0 problems\n"
                    return ""

                with mock.patch.object(smoke, "__file__", str(probe)), mock.patch.object(smoke, "execute", side_effect=execute):
                    if changed:
                        with self.assertRaisesRegex(ValueError, "validation inputs changed"):
                            smoke.smoke(wheel, root)
                    else:
                        report = smoke.smoke(wheel, root)
                        self.assertEqual(report["validation_inputs"]["tools/json_repair_wheel_smoke.py"], smoke.sha256(probe))

    def test_source_fallback_and_wrong_record_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            prefix = Path(directory)
            package = prefix / builder.PACKAGE
            package.mkdir()
            init = package / "__init__.py"
            init.write_text("# installed wrapper\n")
            native = package / "_native.abi3.so"
            native.write_bytes(b"fixture")
            extension = SimpleNamespace(__file__=str(native), __spec__=SimpleNamespace(
                loader=ExtensionFileLoader("_native", str(native))))
            companion = SimpleNamespace(__file__=str(init), _native=extension)

            class Record:
                def __init__(self, path):
                    self.path = path
                    digest = base64.urlsafe_b64encode(hashlib.sha256(path.read_bytes()).digest()).rstrip(b"=").decode()
                    self.hash = SimpleNamespace(mode="sha256", value=digest)

                def __str__(self):
                    return str(self.path.relative_to(prefix))

            records = [Record(init), Record(native)]
            distribution = SimpleNamespace(version="fixture", files=records, locate_file=lambda record: record.path)
            with (mock.patch.object(smoke.sys, "prefix", str(prefix)),
                  mock.patch.object(smoke.sys, "base_prefix", str(prefix / "base")),
                  mock.patch.object(smoke.sys, "flags", SimpleNamespace(isolated=1)),
                  mock.patch.dict(sys.modules, {builder.PACKAGE: companion}),
                  mock.patch.object(smoke.metadata, "distribution", return_value=distribution)):
                self.assertEqual(smoke.installed_package(prefix)[1]["package_version"], "fixture")
                extension.__spec__.loader = SourceFileLoader("_native", str(native))
                with self.assertRaisesRegex(ValueError, "real compiled extension"):
                    smoke.installed_package(prefix)
                extension.__spec__.loader = ExtensionFileLoader("_native", str(native))
                distribution.files = records[:1]
                with self.assertRaisesRegex(ValueError, "not owned"):
                    smoke.installed_package(prefix)
                distribution.files = records
                init.write_text("# changed after installation\n")
                with self.assertRaisesRegex(ValueError, "differs from its wheel RECORD"):
                    smoke.installed_package(prefix)


if __name__ == "__main__":
    unittest.main()
