"""Release packaging integrity, reproducibility, and launcher relocation checks."""

import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tarfile
import tempfile
import unittest

import release
import release_smoke


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="pystachy-package-test-")
        self.addCleanup(temporary.cleanup)
        # macOS exposes /var through a symlink to /private/var; the launcher uses
        # physical paths (cd -P), so fixtures and expected paths must do the same.
        self.root = Path(temporary.name).resolve()
        self.source = self.root / "source"
        self.source.mkdir()
        for name in release.FILES:
            (self.source / name).write_text(f"fixture: {name}\n", encoding="utf-8")
        (self.source / "VERSION").write_text("v0.1.0-alpha.1\n", encoding="utf-8")
        # A native shell fixture verifies the launcher without Python. macOS's
        # system /bin/sh can be a universal Mach-O: compile a thin native helper
        # that forwards to it, keeping release validation restricted to thin files.
        native = self.source / "pystachy"
        if sys.platform == "darwin":
            architecture = release.host_target().rsplit("-", 1)[1]
            subprocess.run(["xcrun", "clang", "-arch", architecture, "-x", "c", "-", "-o", str(native)],
                           input='#include <unistd.h>\nint main(int argc, char **argv) {\n'
                                 '    (void)argc; argv[0] = "sh"; execv("/bin/sh", argv); return 127;\n}\n',
                           capture_output=True, text=True, check=True, timeout=30)
        else:
            shutil.copyfile(Path(shutil.which("sh")).resolve(), native)
        native.chmod(0o755)
        for name in release.DIRS:
            (self.source / name).mkdir()
        (self.source / "lib/module.py").write_text("print(42)\n", encoding="utf-8")
        (self.source / "ryu/ryu.h").write_text("/* fixture */\n", encoding="utf-8")
        (self.source / "ryu/LICENSE-Boost").write_text("fixture license\n", encoding="utf-8")
        self.target = release.binary_target(self.source / "pystachy")
        self.commit = "a" * 40
        self.epoch = 1700000000
        self.output = self.root / "dist"
        self.environment = {key: value for key, value in os.environ.items()
                            if not key.startswith("PYSTACHY_") and key != "XDG_CACHE_HOME"}
        self.environment["HOME"] = str(self.root / "user home")

    def package(self, **overrides):
        arguments = dict(source=self.source, output_dir=self.output, version="v0.1.0-alpha.1",
                         target=self.target, commit=self.commit, epoch=self.epoch)
        arguments.update(overrides)
        return release.package(**arguments)

    def unpack(self, archive):
        destination = self.root / "unpack"
        destination.mkdir()
        return release_smoke.extract(archive, destination)

    def launch(self, launcher, environment=None):
        script = 'printf "%s\\n" "$PYSTACHY_HOME" "$PYSTACHY_CACHE" "$PWD" "$@"'
        work = self.root / "outside checkout"
        work.mkdir(exist_ok=True)
        result = subprocess.run([str(launcher), "-c", script, "fixture", "name with spaces.py", "$literal", "'quote'"],
                                env=environment or self.environment, cwd=work,
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        return result.stdout.splitlines()

    def test_archive_contains_native_resources_licenses_and_matching_manifest(self):
        archive = self.package()
        directory = self.unpack(archive)
        manifest = release_smoke.verify_manifest(directory)
        self.assertEqual(manifest["version"], "v0.1.0-alpha.1")
        self.assertEqual(manifest["commit"], self.commit)
        self.assertEqual(manifest["target"], self.target)
        self.assertEqual(manifest["source_date_epoch"], self.epoch)
        self.assertIn("Python is not required", (directory / "README.txt").read_text())
        for name in release.FILES:
            self.assertEqual((directory / "libexec/pystachy" / name).read_bytes(), (self.source / name).read_bytes())
        self.assertEqual((directory / "libexec/pystachy/REVISION").read_text(), self.commit + "\n")
        self.assertTrue((directory / "libexec/pystachy/lib/module.py").is_file())
        self.assertTrue((directory / "libexec/pystachy/ryu/LICENSE-Boost").is_file())
        self.assertEqual((directory / "LICENSE").read_bytes(), (self.source / "LICENSE").read_bytes())
        self.assertTrue(os.access(directory / "bin/pystachy", os.X_OK))
        self.assertTrue(os.access(directory / "libexec/pystachy/pystachy", os.X_OK))
        checksum = Path(str(archive) + ".sha256").read_text()
        self.assertEqual(checksum, f"{release.sha256(archive)}  {archive.name}\n")

    def test_archive_bytes_ignore_source_mtimes_and_permissions(self):
        first = self.package().read_bytes()
        for path in self.source.rglob("*"):
            os.utime(path, (self.epoch + 86400, self.epoch + 86400))
            if path.is_file() and path.name != "pystachy":
                path.chmod(0o600)
        second = self.package().read_bytes()
        self.assertEqual(first, second)
        with tarfile.open(self.output / f"pystachy-v0.1.0-alpha.1-{self.target}.tar.gz") as handle:
            members = handle.getmembers()
            self.assertEqual([member.name for member in members], sorted(member.name for member in members))
            for member in members:
                self.assertEqual((member.uid, member.gid, member.uname, member.gname, member.mtime),
                                 (0, 0, "", "", self.epoch))
                self.assertIn(member.mode, (0o644, 0o755))

    def test_requested_version_replaces_source_metadata_and_is_hashed(self):
        directory = self.unpack(self.package(version="v1.2.3"))
        manifest = release_smoke.verify_manifest(directory)
        self.assertEqual((directory / "libexec/pystachy/VERSION").read_text(), "v1.2.3\n")
        self.assertEqual((directory / "libexec/pystachy/REVISION").read_text(), self.commit + "\n")
        for name in ("VERSION", "REVISION"):
            self.assertIn("libexec/pystachy/" + name, manifest["files_sha256"])

    def test_launcher_remains_usable_after_relocation_and_preserves_arguments(self):
        directory = self.unpack(self.package())
        moved = self.root / "moved 'release' $literal `literal`"
        directory.rename(moved)
        output = self.launch(moved / "bin/pystachy")
        self.assertEqual(output, [str(moved / "libexec/pystachy"),
                                 str(Path(self.environment["HOME"]) / ".cache/pystachy"),
                                 str(self.root / "outside checkout"), "name with spaces.py", "$literal", "'quote'"])

    def test_launcher_handles_relative_symlink_chain_on_path(self):
        directory = self.unpack(self.package())
        commands = self.root / "commands"
        commands.mkdir()
        first = commands / "native-link"
        first.symlink_to(os.path.relpath(directory / "bin/pystachy", commands))
        second = commands / "pystachy"
        second.symlink_to("native-link")
        environment = dict(self.environment, PATH=str(commands) + os.pathsep + self.environment["PATH"])
        output = self.launch("pystachy", environment)
        self.assertEqual(output[0], str(directory / "libexec/pystachy"))
        self.assertEqual(output[-3:], ["name with spaces.py", "$literal", "'quote'"])

    def test_launcher_preserves_home_cache_and_llvm_overrides(self):
        directory = self.unpack(self.package())
        environment = dict(self.environment, PYSTACHY_HOME="custom home", PYSTACHY_CACHE="custom cache", PYSTACHY_LLVM="custom llvm")
        self.assertEqual(self.launch(directory / "bin/pystachy", environment)[:2], ["custom home", "custom cache"])
        script = 'printf "%s\\n" "$PYSTACHY_LLVM"'
        result = subprocess.run([str(directory / "bin/pystachy"), "-c", script], env=environment,
                                capture_output=True, text=True, timeout=10, check=True)
        self.assertEqual(result.stdout, "custom llvm\n")
        environment = dict(self.environment, XDG_CACHE_HOME=str(self.root / "xdg cache"))
        self.assertEqual(self.launch(directory / "bin/pystachy", environment)[1], str(self.root / "xdg cache/pystachy"))

    def test_only_runtime_sources_and_provenance_are_packaged(self):
        (self.source / "lib/__pycache__").mkdir()
        (self.source / "lib/__pycache__/module.pyc").write_bytes(b"cache")
        (self.source / "lib/.private").write_bytes(b"private")
        (self.source / "lib/build.o").write_bytes(b"build")
        (self.source / "ryu/local.env").write_bytes(b"unrelated")
        directory = self.unpack(self.package())
        files = release_smoke.verify_manifest(directory)["files_sha256"]
        for name in ("__pycache__", ".private", "build.o", "local.env"):
            self.assertFalse(any(name in path for path in files), name)

    def test_rejects_symlinked_resources_without_output(self):
        (self.source / "lib/link.py").symlink_to(self.source / "runtime.py")
        with self.assertRaisesRegex(ValueError, "symlink"):
            self.package()
        self.assertFalse(list(self.output.glob("*.tar.gz")))

    def test_missing_and_nonexecutable_inputs_fail_without_archive(self):
        (self.source / "pystachy").chmod(0o644)
        with self.assertRaisesRegex(ValueError, "not executable"):
            self.package()
        (self.source / "pystachy").chmod(0o755)
        (self.source / "runtime.py").unlink()
        with self.assertRaisesRegex(ValueError, "missing"):
            self.package()
        self.assertFalse(list(self.output.glob("*.tar.gz")))

    def test_rejects_script_instead_of_native_compiler(self):
        (self.source / "pystachy").write_text("#!/usr/bin/env python3\nprint(42)\n")
        with self.assertRaisesRegex(ValueError, "native"):
            self.package()

    def test_rejects_target_mismatch_and_invalid_metadata(self):
        other = next(target for target in release.TARGETS if target != self.target)
        with self.assertRaisesRegex(ValueError, "architecture"):
            self.package(target=other)
        for version in ("../escape", "v1/escape", ".", "version with spaces"):
            with self.subTest(version=version), self.assertRaises(ValueError):
                self.package(version=version)
        for overrides in ({"commit": "abcdef"}, {"epoch": -1}, {"epoch": 2**32}, {"target": "windows-x86_64"}):
            with self.subTest(overrides=overrides), self.assertRaises(ValueError):
                self.package(**overrides)

    def test_header_reader_recognizes_macos_architectures(self):
        binary = self.root / "header"
        for cpu, target in ((0x01000007, "macos-x86_64"), (0x0100000C, "macos-arm64")):
            binary.write_bytes(b"\xcf\xfa\xed\xfe" + struct.pack("<III", cpu, 0, 2) + bytes(16))
            self.assertEqual(release.binary_target(binary), target)
        binary.write_bytes(b"\xcf\xfa\xed\xfe" + struct.pack("<III", 0x01000007, 0, 6) + bytes(16))
        with self.assertRaises(ValueError):
            release.binary_target(binary)

    def test_manifest_detects_corruption_and_extra_files(self):
        directory = self.unpack(self.package())
        (directory / "extra").write_text("unexpected")
        with self.assertRaisesRegex(ValueError, "hashes"):
            release_smoke.verify_manifest(directory)
        (directory / "extra").unlink()
        (directory / "libexec/pystachy/runtime.py").write_text("corrupt")
        with self.assertRaisesRegex(ValueError, "hashes"):
            release_smoke.verify_manifest(directory)

    def test_manifest_detects_incorrect_target(self):
        directory = self.unpack(self.package())
        path = directory / "manifest.json"
        manifest = json.loads(path.read_text())
        manifest["target"] = "incorrect"
        path.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, "target"):
            release_smoke.verify_manifest(directory)

    def test_manifest_metadata_matches_native_version_resources(self):
        directory = self.unpack(self.package())
        path = directory / "manifest.json"
        original = json.loads(path.read_text())
        for field, value in (("version", "v9.0.0"), ("commit", "b" * 40)):
            manifest = dict(original, **{field: value})
            path.write_text(json.dumps(manifest))
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "metadata"):
                release_smoke.verify_manifest(directory)

    def test_extractor_rejects_traversal_and_links(self):
        archive = self.root / "unsafe.tar.gz"
        for name, kind in (("../escape", tarfile.REGTYPE), ("/absolute", tarfile.REGTYPE),
                           ("root/link", tarfile.SYMTYPE), ("root/link", tarfile.LNKTYPE)):
            with self.subTest(name=name, kind=kind):
                with tarfile.open(archive, "w:gz") as handle:
                    member = tarfile.TarInfo(name)
                    member.type = kind
                    member.linkname = "../../escape"
                    handle.addfile(member)
                with self.assertRaises(ValueError):
                    release_smoke.extract(archive, self.root / "rejected")
        self.assertFalse((self.root / "rejected").exists())


if __name__ == "__main__":
    unittest.main()
