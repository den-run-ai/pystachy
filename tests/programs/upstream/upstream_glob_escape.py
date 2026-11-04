# CPython 3.13.16 Lib/test/test_glob.py, GlobTests.test_escape (cbc944f4bc59639a444dd971c737788ba2283a91,
# SHA-256 b3db2d9bc190ea67318be004605edd69c0cf219672e0948fada5c0100964c3d6).
# Preserve all POSIX inputs and results. The ASCII cases use encode() in place of os.fsencode().
import glob


def check(pattern: str, expected: str) -> None:
    assert glob.escape(pattern) == expected
    assert glob.escape(pattern.encode()) == expected.encode()


check('abc', 'abc')
check('[', '[[]')
check('?', '[?]')
check('*', '[*]')
check('[[_/*?*/_]]', '[[][[]_/[*][?][*]/_]]')
check('/[[_/*?*/_]]/', '/[[][[]_/[*][?][*]/_]]/')
assert glob.escape(b'\xff\x00[?*]') == b'\xff\x00[[][?][*]]'
unchanged = b'\xff\x00'
assert glob.escape(unchanged) is unchanged
assert glob.has_magic(b'\xff[')
assert glob.has_magic(b'\xff?')
assert glob.has_magic(b'\xff*')
assert not glob.has_magic(b'\xff\x00]')
print('ok')
