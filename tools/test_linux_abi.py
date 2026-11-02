"""Negative controls for release ELF dependency and glibc ceiling diagnostics."""

from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import linux_abi


READELF = """
      [Requesting program interpreter: /lib64/ld-linux-x86-64.so.2]
 0x0000000000000001 (NEEDED)             Shared library: [libc.so.6]
 0x0000000000000001 (NEEDED)             Shared library: [libgcc_s.so.1]
 0x000000000000001d (RUNPATH)            Library runpath: [$ORIGIN/lib]
 0x000000006ffffffe (VERNEED)            0xae8
Version symbols section '.gnu.version' contains 3 entries:
  000:   0 (*local*)       2 (GLIBC_2.99)   3 (GLIBC_2.34)
Version definition section '.gnu.version_d' contains 1 entry:
  0x0000: Rev: 1  Flags: BASE  Index: 1  Cnt: 1  Name: GLIBC_2.99
Version needs section '.gnu.version_r' contains 2 entries:
  000000: Version: 1  File: libc.so.6  Cnt: 2
  0x0010:   Name: GLIBC_2.34  Flags: none  Version: 3
  0x0020:   Name: GLIBC_2.9  Flags: none  Version: 2
  000030: Version: 1  File: libgcc_s.so.1  Cnt: 1
  0x0040:   Name: GCC_3.0  Flags: none  Version: 4
"""


class LinuxAbiTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="pystachy-linux-abi-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def elf(self, name="pystachy", machine=62, kind=3):
        header = bytearray(64)
        header[:7] = b"\x7fELF\x02\x01\x01"
        struct.pack_into("<HH", header, 16, kind, machine)
        path = self.root / name
        path.write_bytes(header)
        return path

    def readelf(self, text=READELF):
        return mock.patch.object(linux_abi.subprocess, "run", return_value=subprocess.CompletedProcess(
            ["readelf"], 0, stdout=text, stderr=""))

    def test_parses_imports_not_exported_versions(self):
        result = linux_abi.parse_readelf(READELF)
        self.assertEqual(result["needed"], ["libc.so.6", "libgcc_s.so.1"])
        self.assertEqual(result["version_needs"], {"libc.so.6": ["GLIBC_2.34", "GLIBC_2.9"], "libgcc_s.so.1": ["GCC_3.0"]})
        self.assertEqual(result["interpreter"], "/lib64/ld-linux-x86-64.so.2")
        self.assertEqual(result["search_paths"], [{"tag": "RUNPATH", "path": "$ORIGIN/lib"}])

    def test_numeric_ceiling_and_required_versions(self):
        path = self.elf()
        with self.readelf():
            report = linux_abi.audit(path, "x86_64", "2.28")
            accepted = linux_abi.audit(path, "x86_64", "2.39")
        self.assertEqual(report["binaries"][0]["glibc_symbol_floor"], "2.34")
        self.assertEqual(len(report["violations"]), 1)
        self.assertIn("above ceiling GLIBC_2.28", report["violations"][0])
        self.assertEqual(accepted["violations"], [])

    def test_all_bundled_elfs_are_checked(self):
        self.elf()
        self.elf("helper.so", machine=183)
        (self.root / "source.py").write_text("print(42)\n")
        with self.readelf():
            report = linux_abi.audit(self.root, "x86_64")
        self.assertEqual(report["elf_count"], 2)
        self.assertEqual(len(report["violations"]), 1)
        self.assertIn("helper.so: architecture aarch64", report["violations"][0])

    def test_aarch64_header_and_foreign_architecture(self):
        path = self.elf(machine=183)
        with self.readelf():
            self.assertEqual(linux_abi.audit(path, "aarch64")["violations"], [])
        with self.assertRaisesRegex(ValueError, "unsupported ELF"):
            linux_abi.inspect_elf(self.elf("riscv", machine=243))

    def test_private_glibc_is_not_claimed_compatible(self):
        with self.readelf(READELF.replace("GLIBC_2.34", "GLIBC_PRIVATE")):
            report = linux_abi.audit(self.elf(), max_glibc="2.39")
        self.assertEqual(len(report["violations"]), 1)
        self.assertIn("private/non-numeric", report["violations"][0])

    def test_missing_version_needs_table_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "did not expose"):
            linux_abi.parse_readelf("0x000000006ffffffe (VERNEED) 0xae8\n")

    def test_bad_inputs_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "no ELF"):
            linux_abi.audit(self.root)
        path = self.elf()
        path.write_bytes(b"\x7fELF")
        with self.assertRaisesRegex(ValueError, "ELF64"):
            linux_abi.audit(path)
        with self.assertRaisesRegex(ValueError, "invalid version"):
            linux_abi.audit(path, max_glibc="not-a-version")

    def test_symlinks_cannot_hide_payloads(self):
        path = self.elf()
        (self.root / "helper.so").symlink_to(path)
        with self.assertRaisesRegex(ValueError, "symlinks"):
            linux_abi.audit(self.root)

    def test_explicit_file_symlink_is_rejected(self):
        alias = self.root / "compiler-alias"
        alias.symlink_to(self.elf())
        with self.readelf(), self.assertRaisesRegex(ValueError, "symlinks"):
            linux_abi.audit(alias)

    def test_explicit_directory_symlink_is_rejected(self):
        payload = self.root / "payload"
        payload.mkdir()
        self.elf("payload/compiler")
        alias = self.root / "payload-alias"
        alias.symlink_to(payload, target_is_directory=True)
        with self.readelf(), self.assertRaisesRegex(ValueError, "symlinks"):
            linux_abi.audit(alias)

    def test_parent_directory_alias_is_permitted(self):
        payload = self.root / "payload"
        payload.mkdir()
        self.elf("payload/compiler")
        alias = self.root / "parent-alias"
        alias.symlink_to(payload, target_is_directory=True)
        with self.readelf():
            report = linux_abi.audit(alias / "compiler")
        self.assertEqual(report["elf_count"], 1)
        self.assertEqual(report["binaries"][0]["path"], "compiler")

    def test_diagnostics_fail_instead_of_incomplete_evidence(self):
        path = self.elf()
        with mock.patch.object(linux_abi.subprocess, "run", return_value=subprocess.CompletedProcess(
                ["readelf"], 0, stdout="", stderr="corrupt version table")):
            with self.assertRaisesRegex(ValueError, "diagnostics"):
                linux_abi.inspect_elf(path)

    @unittest.skipUnless(sys.platform == "linux" and shutil.which("readelf"), "needs Linux GNU readelf")
    def test_real_elf_without_executing_it(self):
        executable = Path(shutil.which("true")).resolve()
        if linux_abi.inspect_elf(executable)["architecture"] not in linux_abi.MACHINES.values():
            self.skipTest("fixture has an unsupported architecture")
        target = self.root / "never-execute"
        shutil.copyfile(executable, target)
        target.chmod(0o600)
        report = linux_abi.audit(target)
        self.assertEqual(report["elf_count"], 1)
        self.assertIn("libc.so.6", report["binaries"][0]["needed"])
        self.assertIsNotNone(report["binaries"][0]["glibc_symbol_floor"])


if __name__ == "__main__":
    unittest.main()
