"""Installation layout and launcher behavior, without requiring LLVM."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

import install as installer


class InstallTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="pystachy-install-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / "source"
        self.source.mkdir()
        for name in ("runtime.c", "runtime.py", "pyext.c", "pyembed.c", "LICENSE", "THIRD_PARTY_NOTICES"):
            (self.source / name).write_text(f"fixture: {name}\n")
        (self.source / "VERSION").write_text("v0.1.0-alpha.1\n")
        for name in ("lib", "ryu"):
            (self.source / name).mkdir()
            (self.source / name / "fixture.txt").write_text(name)
        self.native = self.source / "pystachy"
        self.native.write_text(
            f"#!{sys.executable}\n"
            "import json, os, sys\n"
            "print(json.dumps({'args': sys.argv[1:], 'cwd': os.getcwd(), "
            "'home': os.getenv('PYSTACHY_HOME'), 'cache': os.getenv('PYSTACHY_CACHE'), "
            "'llvm': os.getenv('PYSTACHY_LLVM')}))\n"
        )
        self.native.chmod(0o755)
        self.prefix = self.root / "install 'quoted' $cash `literal`"
        self.work = self.root / "outside checkout"
        self.work.mkdir()
        self.environment = dict(os.environ)
        for key in ("PYSTACHY_HOME", "PYSTACHY_CACHE", "PYSTACHY_LLVM", "XDG_CACHE_HOME"):
            self.environment.pop(key, None)
        self.environment["HOME"] = str(self.root / "user home")

    def install(self, destdir=None):
        installer.install(self.prefix, destdir=destdir, source=self.source)

    def run_launcher(self, environment=None):
        result = subprocess.run(
            [str(self.prefix / "bin/pystachy"), "run", "name with spaces.py", "'quoted'", "$cash"],
            cwd=self.work, env=environment or self.environment, capture_output=True, text=True,
            timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        return json.loads(result.stdout)

    def test_install_preserves_arguments_and_resolves_data_outside_checkout(self):
        self.install()
        data = self.prefix / "libexec/pystachy"
        for name in installer.FILES:
            self.assertEqual((data / name).read_bytes(), (self.source / name).read_bytes())
        self.assertEqual((data / "REVISION").read_text(), "unknown\n")
        for name in ("lib", "ryu"):
            self.assertEqual((data / name / "fixture.txt").read_text(), name)
        self.assertTrue(os.access(data / "pystachy", os.X_OK))
        self.assertTrue(os.access(self.prefix / "bin/pystachy", os.X_OK))
        result = self.run_launcher()
        self.assertEqual(result["args"], ["run", "name with spaces.py", "'quoted'", "$cash"])
        self.assertEqual(result["cwd"], str(self.work.resolve()))
        self.assertEqual(result["home"], str(data))
        self.assertEqual(result["cache"], str(Path(self.environment["HOME"]) / ".cache/pystachy"))
        self.assertIsNone(result["llvm"])

    def test_install_records_explicit_release_version_and_commit(self):
        revision = "a" * 40
        installer.install(self.prefix, source=self.source, version="v1.2.3-beta.1", revision=revision)
        data = self.prefix / "libexec/pystachy"
        self.assertEqual((data / "VERSION").read_text(), "v1.2.3-beta.1\n")
        self.assertEqual((data / "REVISION").read_text(), revision + "\n")

    def test_install_preserves_packaged_commit_metadata(self):
        (self.source / "REVISION").write_text("b" * 40 + "\n")
        self.install()
        self.assertEqual((self.prefix / "libexec/pystachy/REVISION").read_text(), "b" * 40 + "\n")

    @unittest.skipUnless(shutil.which("git"), "Git is unavailable")
    def test_source_commit_is_exact_only_for_a_clean_checkout(self):
        def git(*arguments):
            return subprocess.check_output(["git", "-C", str(self.source), *arguments],
                                           text=True, stderr=subprocess.DEVNULL).strip()

        git("init")
        git("add", ".")
        git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "-c", "commit.gpgsign=false",
            "commit", "-m", "fixture")
        self.assertEqual(installer.source_revision(self.source), git("rev-parse", "HEAD"))
        (self.source / "runtime.py").write_text("modified\n")
        self.assertEqual(installer.source_revision(self.source), "unknown")

    def test_hosted_version_needs_no_llvm_and_reports_metadata(self):
        (self.source / "REVISION").write_text("c" * 40 + "\n")
        expected = "pystachy v0.1.0-alpha.1 (commit " + "c" * 40 + ")\n"
        environment = dict(self.environment, PYSTACHY_HOME=str(self.source), PATH="",
                           PYSTACHY_LLVM="/unavailable", PYSTACHY_CACHE=str(self.root / "unused cache"))
        for option in ("--version", "-V"):
            result = subprocess.run([sys.executable, str(installer.ROOT / "pystachy.py"), option],
                                    cwd=self.work, env=environment, capture_output=True, text=True, timeout=10)
            self.assertEqual((result.returncode, result.stdout, result.stderr), (0, expected, ""))
        self.assertFalse((self.root / "unused cache").exists())

    def test_invalid_release_metadata_creates_no_partial_installation(self):
        for overrides in ({"version": "../escape"}, {"version": "v01.2.3"}, {"revision": "abcdef"}):
            with self.subTest(overrides=overrides), self.assertRaises(ValueError):
                installer.install(self.prefix, source=self.source, **overrides)
            self.assertFalse(self.prefix.exists())

    def test_development_docker_metadata_needs_no_git_identity(self):
        installer.install(self.prefix, source=self.source, version="dev", revision="unknown")
        data = self.prefix / "libexec/pystachy"
        self.assertEqual((data / "VERSION").read_text(), "dev\n")
        self.assertEqual((data / "REVISION").read_text(), "unknown\n")

    def test_cache_uses_xdg_and_preserves_environment_overrides(self):
        self.install()
        environment = dict(self.environment, XDG_CACHE_HOME=str(self.root / "XDG cache"))
        self.assertEqual(self.run_launcher(environment)["cache"], environment["XDG_CACHE_HOME"] + "/pystachy")
        environment.update(PYSTACHY_HOME=str(self.root / "custom home"),
                           PYSTACHY_CACHE=str(self.root / "custom cache"),
                           PYSTACHY_LLVM=str(self.root / "custom LLVM"))
        result = self.run_launcher(environment)
        for field, variable in (("home", "PYSTACHY_HOME"), ("cache", "PYSTACHY_CACHE"), ("llvm", "PYSTACHY_LLVM")):
            self.assertEqual(result[field], environment[variable])

    def test_destdir_stages_files_but_launcher_uses_final_prefix(self):
        stage = self.root / "package staging"
        self.install(stage)
        staged_prefix = stage / self.prefix.relative_to(self.prefix.anchor)
        self.assertTrue((staged_prefix / "libexec/pystachy/runtime.c").is_file())
        self.assertFalse(self.prefix.exists())
        launcher = staged_prefix / "bin/pystachy"
        self.assertNotIn(str(stage), launcher.read_text())
        self.prefix.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(staged_prefix), self.prefix)
        self.assertEqual(self.run_launcher()["home"], str(self.prefix / "libexec/pystachy"))

    def test_destdir_normalizes_parent_components_within_staging(self):
        stage = self.root / "package staging"
        launcher, data, final = installer.paths(Path("/../../opt/pystachy"), stage)
        self.assertEqual(launcher, stage / "opt/pystachy/bin/pystachy")
        self.assertEqual(data, stage / "opt/pystachy/libexec/pystachy")
        self.assertEqual(final, Path("/opt/pystachy/libexec/pystachy"))

    def test_reinstall_updates_existing_files(self):
        self.install()
        (self.source / "runtime.c").write_text("updated runtime\n")
        (self.source / "lib/fixture.txt").write_text("updated library\n")
        self.install()
        self.assertEqual((self.prefix / "libexec/pystachy/runtime.c").read_text(), "updated runtime\n")
        self.assertEqual((self.prefix / "libexec/pystachy/lib/fixture.txt").read_text(), "updated library\n")
        self.run_launcher()

    def test_uninstall_keeps_other_commands_data_and_user_cache(self):
        self.install()
        siblings = [self.prefix / "bin/another-command", self.prefix / "libexec/another-project/data"]
        cache = Path(self.environment["HOME"]) / ".cache/pystachy/user-cache"
        for path in [*siblings, cache]:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("keep\n")
        installer.uninstall(self.prefix)
        self.assertFalse((self.prefix / "bin/pystachy").exists())
        self.assertFalse((self.prefix / "libexec/pystachy").exists())
        for path in [*siblings, cache]:
            self.assertEqual(path.read_text(), "keep\n")
        installer.uninstall(self.prefix)

    def test_staged_uninstall_leaves_live_installation(self):
        self.install()
        stage = self.root / "staging"
        self.install(stage)
        installer.uninstall(self.prefix, destdir=stage)
        staged_prefix = stage / self.prefix.relative_to(self.prefix.anchor)
        self.assertFalse((staged_prefix / "bin/pystachy").exists())
        self.assertFalse((staged_prefix / "libexec/pystachy").exists())
        self.run_launcher()

    def test_missing_native_compiler_creates_no_partial_install(self):
        self.native.unlink()
        with self.assertRaises(ValueError):
            self.install()
        self.assertFalse(self.prefix.exists())

    def test_install_and_uninstall_refuse_unrelated_existing_paths(self):
        for path in (self.prefix / "bin/pystachy", self.prefix / "libexec/pystachy/foreign-data"):
            with self.subTest(path=path):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("keep unrelated installation\n")
                with self.assertRaises(ValueError):
                    self.install()
                with self.assertRaises(ValueError):
                    installer.uninstall(self.prefix)
                self.assertEqual(path.read_text(), "keep unrelated installation\n")
                shutil.rmtree(self.prefix)

    def test_install_and_uninstall_preserve_unmanaged_dangling_launcher_symlink(self):
        launcher = self.prefix / "bin/pystachy"
        launcher.parent.mkdir(parents=True)
        target = self.root / "missing compiler"
        launcher.symlink_to(target)
        for operation in (self.install, lambda: installer.uninstall(self.prefix)):
            with self.subTest(operation=operation):
                with self.assertRaises(ValueError):
                    operation()
                self.assertTrue(launcher.is_symlink())
                self.assertEqual(launcher.readlink(), target)
                self.assertFalse((self.prefix / "libexec/pystachy").exists())


if __name__ == "__main__":
    unittest.main()
