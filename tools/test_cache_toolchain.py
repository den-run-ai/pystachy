"""Search-layout invalidation controls; no compiler build is required."""
from __future__ import annotations
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from src.pystachy_compiler import cache_toolchain as ct


class SearchDiscovery(unittest.TestCase):
    def test_header_roots_include_missing_candidates(self) -> None:
        self.assertEqual(ct.include_roots('ignoring nonexistent directory "/missing"\n'
                                         '#include "..." search starts here:\n'
                                         '#include <...> search starts here:\n /usr/include\n'
                                         ' /path with spaces\nEnd of search list.\n'),
                         ['/missing', '/path with spaces', '/usr/include'])
        self.assertEqual(ct.include_roots('#include <...> search starts here:\n relative\nEnd of search list.'), [])
        self.assertEqual(ct.include_roots('/usr/include'), [])

    def test_library_roots_fail_closed(self) -> None:
        self.assertEqual(ct.library_roots('programs: =/bin\nlibraries: =/lib:/usr/lib:/absent\n'),
                         ['/absent', '/lib', '/usr/lib'])
        self.assertEqual(ct.library_roots('libraries: =/lib:relative'), [])
        self.assertEqual(ct.library_roots('programs: =/bin'), [])

    def test_actual_configuration_paths(self) -> None:
        text = ("clang: error: configuration file 'unused.cfg' cannot be found\n"
                'clang: note: was searched for in the directory: /custom/config\n'
                'clang: note: was searched for in the directory: /llvm/bin\n')
        self.assertEqual(ct.config_roots(text, 'unused.cfg'), ['/custom/config', '/llvm/bin'])
        self.assertEqual(ct.config_roots(text, 'other.cfg'), [])
        self.assertEqual(ct.config_roots('unrecognized --config', 'unused.cfg'), [])

    def test_linker_and_loader_search_roots(self) -> None:
        self.assertEqual(ct.linker_roots('SEARCH_DIR("=/usr/local/lib"); SEARCH_DIR("/lib");'),
                         ['/lib', '/usr/local/lib'])
        self.assertEqual(ct.linker_roots('SEARCH_DIR("relative");'), [])
        self.assertEqual(ct.loader_roots(' 12: search path=/custom/lib:/custom/lib/glibc-hwcaps/x86-64-v4\t(RUNPATH from file /tool)\n'),
                         ['/custom/lib', '/custom/lib/glibc-hwcaps/x86-64-v4'])
        self.assertEqual(ct.loader_roots(' 12: search path=relative\t(system search path)'), [])
        self.assertEqual(ct.loader_roots(' 12: search path=/lib\t(system search path)\n'
                                        '\tlibmissing.so => not found\n'), [])

    def test_gcc_candidates_include_unselected_versions(self) -> None:
        roots = ct.gcc_roots('/llvm/bin', 'Found candidate GCC installation: /custom/lib/gcc/triple/13\n')
        for root in ['/custom/lib/gcc', '/usr/lib/gcc', '/usr/lib/gcc-cross', '/llvm/lib/gcc', '/opt/rh']:
            self.assertIn(root, roots)
        roots = ct.gcc_roots('/llvm/bin', 'Found candidate GCC installation: /custom/lib64/gcc/triple/13\n')
        for root in ['/custom/lib/gcc', '/custom/lib32/gcc', '/custom/lib64/gcc-cross']:
            self.assertIn(root, roots)

    def test_custom_sysroot_bypasses_standard_discovery(self) -> None:
        for command in [' clang -cc1 -isysroot /custom ', ' "clang" "-cc1" "-isysroot" "/custom" ']:
            self.assertEqual(ct.gcc_roots('/llvm/bin', command), [])

    def test_parent_uses_supported_string_operations(self) -> None:
        self.assertEqual(ct._parent('/x/y'), '/x')
        self.assertEqual(ct._parent('/x'), '/')
        self.assertEqual(ct._parent('/'), '/')

    def test_existing_gentoo_configuration_bypasses_without_tools(self) -> None:
        with patch.object(os.path, 'exists', return_value=True), patch.object(os, 'system') as system:
            self.assertEqual(ct.capture('/llvm/bin'), {})
        system.assert_not_called()


class SearchSnapshots(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.include = self.root / 'include'
        self.include.mkdir()
        (self.include / 'old.h').write_text('old')

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_add_shadow_header(self) -> None:
        records = ct.collect([str(self.include)], [], [])
        self.assertTrue(ct.valid(records))
        (self.include / 'new.h').write_text('new')
        self.assertFalse(ct.valid(records))

    def test_missing_root_and_new_gcc_version(self) -> None:
        gcc = self.root / 'gcc'
        records = ct.collect([str(gcc)], [], [])
        self.assertTrue(ct.valid(records))
        (gcc / 'triple' / '14').mkdir(parents=True)
        self.assertFalse(ct.valid(records))
        records = ct.collect([str(gcc)], [], [])
        (gcc / 'triple' / '15').mkdir()
        self.assertFalse(ct.valid(records))

    def test_in_place_candidate_replacement(self) -> None:
        path = self.include / 'old.h'
        records = ct.collect([str(self.include)], [], [])
        parent_before = self.include.stat().st_mtime_ns
        path.write_text('new content')
        self.assertEqual(self.include.stat().st_mtime_ns, parent_before)
        self.assertFalse(ct.valid(records))

    def test_chmod_candidate_and_dangling_symlink(self) -> None:
        path = self.include / 'old.h'
        records = ct.collect([str(self.include)], [], [])
        path.chmod(0o000)
        self.assertFalse(ct.valid(records))
        path.chmod(0o600)
        target = self.root / 'external.h'
        (self.include / 'linked.h').symlink_to(target)
        records = ct.collect([str(self.include)], [], [])
        self.assertTrue(ct.valid(records))
        target.write_text('now available')
        self.assertFalse(ct.valid(records))

    def test_directory_symlink_cycle_is_bounded(self) -> None:
        (self.include / 'loop').symlink_to(self.include, target_is_directory=True)
        records = ct.collect([str(self.include)], [], [])
        self.assertTrue(ct.valid(records))
        self.assertLess(len(records), 6)
        with patch.object(ct, 'MAX_ENTRIES', 1):
            self.assertEqual(ct.collect([str(self.include)], [], []), {})

    def test_config_addition_and_existing_config_bypass(self) -> None:
        config = self.root / 'config'
        records = ct.collect([str(self.include)], [], [str(config)])
        config.mkdir()
        self.assertFalse(ct.valid(records))
        (config / 'target-clang.cfg').write_text('-DCHANGED')
        self.assertEqual(ct.collect([str(self.include)], [], [str(config)]), {})

    def test_loader_file_and_stable_token(self) -> None:
        loader = self.root / 'ld.so.cache'
        loader.write_bytes(b'old')
        records = ct.collect([str(self.include)], [str(loader)], [])
        self.assertTrue(ct.valid(records))
        self.assertEqual(ct.token(records), ct.token(dict(reversed(list(records.items())))))
        loader.write_bytes(b'new content')
        self.assertFalse(ct.valid(records))

    def test_root_ancestor_symlink_retarget(self) -> None:
        first = self.root / 'first'
        second = self.root / 'second'
        (first / 'include').mkdir(parents=True)
        (second / 'include').mkdir(parents=True)
        alias = self.root / 'alias'
        alias.symlink_to(first, target_is_directory=True)
        records = ct.collect([str(alias / 'include')], [], [])
        self.assertIn(str(alias), records)
        alias.unlink()
        alias.symlink_to(second, target_is_directory=True)
        self.assertFalse(ct.valid(records))

    def test_snapshot_keeps_symlink_identity_with_equal_metadata(self) -> None:
        first = self.root / 'first:123 456\n789'
        second = self.root / 'second:123 456\n789'
        first.write_text('same')
        second.write_text('same')
        alias = self.include / 'alias.h'
        alias.symlink_to(first)
        # Isolate canonical identity from timestamps: metadata equality must
        # not conceal retargeting, and path separators must stay unambiguous.
        with patch.object(os.path, 'getmtime', return_value=1.0), \
                patch.object(os.path, 'getctime', return_value=2.0):
            before = ct.snapshot(str(alias))
            self.assertEqual(before.split('\0')[1], str(first))
            alias.unlink()
            alias.symlink_to(second)
            self.assertNotEqual(ct.snapshot(str(alias)), before)

    def test_shallow_libraries_exclude_unrelated_package_subtrees(self) -> None:
        lib = self.root / 'lib'
        nested = lib / 'python-package'
        nested.mkdir(parents=True)
        module = nested / 'module.py'
        module.write_text('old')
        library = lib / 'libc.so'
        library.write_text('old')
        records = ct.collect([], [str(lib)], [])
        self.assertNotIn(str(module), records)
        module.write_text('new content')
        self.assertTrue(ct.valid(records))
        library.write_text('new content')
        self.assertFalse(ct.valid(records))

    def test_invalid_roots_and_read_failures_bypass(self) -> None:
        self.assertEqual(ct.collect(['relative'], [], []), {})
        with patch.object(os, 'listdir', side_effect=PermissionError):
            self.assertEqual(ct.collect([str(self.include)], [], []), {})


class SearchCapture(unittest.TestCase):
    def fake_output(self, path: str) -> str:
        name = Path(path).name
        if name == 'verbose':
            return '#include <...> search starts here:\n /headers\nEnd of search list.\n'
        if name == 'search':
            return 'programs: =/unrelated-tools\nlibraries: =/libraries\n'
        if name == 'config':
            missing = 'pystachy-' + Path(path).parent.name + '.cfg'
            return ("clang: error: configuration file '" + missing + "' cannot be found\n"
                    'clang: note: was searched for in the directory: /configuration\n')
        if name == 'linker':
            return 'SEARCH_DIR("=/default-libraries");\n'
        if name == 'loader':
            return self.loader_output
        raise AssertionError(name)

    def setUp(self) -> None:
        self.loader_output = ' 12: search path=/runtime-libraries\t(system search path)\n'

    def test_capture_tracks_distro_files_and_missing_configuration(self) -> None:
        with patch.object(os.path, 'exists', return_value=False), \
                patch.object(os, 'system', side_effect=[0, 0, 256, 0, 0]), \
                patch.object(ct, '_read', side_effect=self.fake_output), \
                patch.object(ct, 'collect', return_value={'/headers': 'stamp'}) as collect:
            self.assertEqual(ct.capture('/llvm/bin'), {'/headers': 'stamp'})
        recursive, shallow, configs = collect.call_args.args
        self.assertIn('/headers', recursive)
        self.assertIn('/default-libraries', shallow)
        self.assertIn('/runtime-libraries', shallow)
        self.assertIn('/etc/os-release', shallow)
        self.assertIn('/etc/lsb-release', shallow)
        self.assertIn('/etc/env.d/gcc', shallow)
        self.assertNotIn('/unrelated-tools', shallow)
        self.assertEqual(configs, ['/configuration'])

    def test_successful_ldd_status_does_not_hide_missing_library(self) -> None:
        self.loader_output += '\tlibmissing.so => not found\n'
        with patch.object(os.path, 'exists', return_value=False), \
                patch.object(os, 'system', side_effect=[0, 0, 256, 0, 0]), \
                patch.object(ct, '_read', side_effect=self.fake_output), \
                patch.object(ct, 'collect') as collect:
            self.assertEqual(ct.capture('/llvm/bin'), {})
        collect.assert_not_called()

    def test_configuration_appearing_during_discovery_bypasses(self) -> None:
        with patch.object(os.path, 'exists', side_effect=[False, True]), \
                patch.object(os, 'system', side_effect=[0, 0, 256, 0, 0]), \
                patch.object(ct, '_read', side_effect=self.fake_output), \
                patch.object(ct, 'collect', return_value={'/headers': 'stamp'}):
            self.assertEqual(ct.capture('/llvm/bin'), {})

    def test_linker_failure_bypasses(self) -> None:
        with patch.object(os.path, 'exists', return_value=False), \
                patch.object(os, 'system', side_effect=[0, 0, 256, 256, 0]), \
                patch.object(ct, '_read') as read:
            self.assertEqual(ct.capture('/llvm/bin'), {})
        read.assert_not_called()

    def test_loader_failure_without_declared_wrapper_bypasses(self) -> None:
        with patch.dict(os.environ, {'PYSTACHY_PROGRAM_CACHE_INPUTS': ''}), \
                patch.object(os.path, 'exists', return_value=False), \
                patch.object(os, 'system', side_effect=[0, 0, 256, 0, 256]), \
                patch.object(ct, '_read') as read:
            self.assertEqual(ct.capture('/llvm/bin'), {})
        read.assert_not_called()


if __name__ == '__main__':
    unittest.main()
