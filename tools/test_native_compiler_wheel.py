"""Exercise the optional native package dispatch and hosted escape hatch."""
import hashlib
import json
import os
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import Mock, patch

import pystachy_cli
import build_native_compiler_wheel as wheel_builder


class NativeCompilerDispatchTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.native = self.directory / "native/pystachy"
        self.native.parent.mkdir()

    def add_native(self, mode=0o755):
        self.native.write_text("#!/bin/sh\nexit 0\n")
        self.native.chmod(mode)

    def test_ordinary_source_package_stays_hosted(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(pystachy_cli.native_compiler(self.directory))

    def test_auto_selects_native_when_bundled(self):
        self.add_native()
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(pystachy_cli.native_compiler(self.directory), self.native)

    def test_hosted_override_ignores_native_payload(self):
        self.add_native()
        with patch.dict(os.environ, {"PYSTACHY_COMPILER": "hosted"}, clear=True):
            self.assertIsNone(pystachy_cli.native_compiler(self.directory))

    def test_missing_forced_native_fails(self):
        with patch.dict(os.environ, {"PYSTACHY_COMPILER": "native"}, clear=True):
            with self.assertRaisesRegex(SystemExit, "missing or not executable"):
                pystachy_cli.native_compiler(self.directory)

    def test_broken_native_does_not_silently_fallback(self):
        self.add_native(mode=0o644)
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(SystemExit, "missing or not executable"):
                pystachy_cli.native_compiler(self.directory)

    def test_invalid_selector_fails(self):
        with patch.dict(os.environ, {"PYSTACHY_COMPILER": "unknown"}, clear=True):
            with self.assertRaisesRegex(SystemExit, "must be"):
                pystachy_cli.native_compiler(self.directory)

    def test_native_exec_preserves_arguments_and_user_cache(self):
        class Intercept(Exception):
            pass

        arguments = ["pystachy", "ir", "path with spaces.py", "-o", "IR with spaces.ll"]
        environment = {"PYSTACHY_CACHE": "user cache", "PYSTACHY_HOME": "user home"}
        with (patch.dict(os.environ, environment, clear=True),
              patch.object(pystachy_cli, "native_compiler", return_value=self.native),
              patch.object(pystachy_cli.sys, "argv", arguments),
              patch.object(pystachy_cli.os, "execv", side_effect=Intercept) as execute):
            with self.assertRaises(Intercept):
                pystachy_cli.main()
            execute.assert_called_once_with(str(self.native), [str(self.native), *arguments[1:]])
            self.assertEqual(os.environ["PYSTACHY_HOME"], "user home")
            self.assertEqual(os.environ["PYSTACHY_CACHE"], "user cache")


class NativeCompilerIdentityTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.binary = self.root / "native"
        header = bytearray(32)
        header[:7] = b"\x7fELF\x02\x01\x01"
        header[16:20] = struct.pack("<HH", 3, 62)
        self.binary.write_bytes(header)
        (self.root / "runtime.c").write_bytes(b"original runtime input")
        self.evidence = {
            "source": {"commit": "a" * 40, "files": {
                "runtime.c": hashlib.sha256(b"original runtime input").hexdigest(),
            }},
            "checks": {"ordinary-compiler-fixed-point": {"equal": True}},
            "bootstrap_binary_sha256": hashlib.sha256(header).hexdigest(),
        }
        self.manifest = self.root / "manifest.json"
        self.manifest.write_text(json.dumps(self.evidence))

    def validate(self, *, ancestor=True):
        with (patch.object(wheel_builder.subprocess, "check_output", return_value="b" * 40 + "\n"),
              patch.object(wheel_builder.subprocess, "run", return_value=Mock(returncode=0 if ancestor else 1))):
            return wheel_builder.verified_binary(self.root, self.binary, self.manifest)

    def test_packaging_commit_can_follow_identical_compiler_commit(self):
        _, compiler_commit, package_commit, _, _ = self.validate()
        self.assertEqual(compiler_commit, "a" * 40)
        self.assertEqual(package_commit, "b" * 40)

    def test_changed_native_bytes_rejected(self):
        self.binary.write_bytes(self.binary.read_bytes() + b"changed")
        with self.assertRaisesRegex(ValueError, "binary differs"):
            self.validate()

    def test_changed_consumed_source_rejected(self):
        (self.root / "runtime.c").write_bytes(b"changed runtime")
        with self.assertRaisesRegex(ValueError, "compiler/runtime source differs"):
            self.validate()

    def test_failed_fixed_point_rejected(self):
        self.evidence["checks"]["ordinary-compiler-fixed-point"]["equal"] = False
        self.manifest.write_text(json.dumps(self.evidence))
        with self.assertRaisesRegex(ValueError, "fixed-point"):
            self.validate()

    def test_unrelated_package_commit_rejected(self):
        with self.assertRaisesRegex(ValueError, "descend"):
            self.validate(ancestor=False)


if __name__ == "__main__":
    unittest.main()
