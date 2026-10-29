# Adapted from CPython 3.13.16 Lib/test/test_posixpath.py, commit
# cbc944f4bc59639a444dd971c737788ba2283a91, SHA-256
# 34ada45f0e4f0e2b8326404b7e7dbf1416a079081f6e0a1f90ab9d691e9a8be8.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# PosixPathTest methods test_join, test_split, test_splitext (splitextTest),
# test_splitroot, test_isabs, test_basename, test_dirname and test_normpath with all 50
# NORMPATH_CASES. Every str input and assertion is kept; unittest scaffolding becomes
# functions and assertions, and subTest becomes a loop. The bytes halves of these methods
# are not included: lib/posixpath supports str paths. The file-system, realpath,
# expanduser, relpath and commonpath methods are not included.
import posixpath

NORMPATH_CASES = [
    ("", "."),
    ("/", "/"),
    ("/.", "/"),
    ("/./", "/"),
    ("/.//.", "/"),
    ("/./foo/bar", "/foo/bar"),
    ("/foo", "/foo"),
    ("/foo/bar", "/foo/bar"),
    ("//", "//"),
    ("///", "/"),
    ("///foo/.//bar//", "/foo/bar"),
    ("///foo/.//bar//.//..//.//baz///", "/foo/baz"),
    ("///..//./foo/.//bar", "/foo/bar"),
    (".", "."),
    (".//.", "."),
    ("./foo/bar", "foo/bar"),
    ("..", ".."),
    ("../", ".."),
    ("../foo", "../foo"),
    ("../../foo", "../../foo"),
    ("../foo/../bar", "../bar"),
    ("../../foo/../bar/./baz/boom/..", "../../bar/baz"),
    ("/..", "/"),
    ("/..", "/"),
    ("/../", "/"),
    ("/..//", "/"),
    ("//.", "//"),
    ("//..", "//"),
    ("//...", "//..."),
    ("//../foo", "//foo"),
    ("//../../foo", "//foo"),
    ("/../foo", "/foo"),
    ("/../../foo", "/foo"),
    ("/../foo/../", "/"),
    ("/../foo/../bar", "/bar"),
    ("/../../foo/../bar/./baz/boom/..", "/bar/baz"),
    ("/../../foo/../bar/./baz/boom/.", "/bar/baz/boom"),
    ("foo/../bar/baz", "bar/baz"),
    ("foo/../../bar/baz", "../bar/baz"),
    ("foo/../../../bar/baz", "../../bar/baz"),
    ("foo///../bar/.././../baz/boom", "../baz/boom"),
    ("foo/bar/../..///../../baz/boom", "../../baz/boom"),
    ("/foo/..", "/"),
    ("/foo/../..", "/"),
    ("//foo/..", "//"),
    ("//foo/../..", "//"),
    ("///foo/..", "/"),
    ("///foo/../..", "/"),
    ("////foo/..", "/"),
    ("/////foo/..", "/"),
]


def test_join() -> None:
    fn = posixpath.join
    assert fn("/foo", "bar", "/bar", "baz") == "/bar/baz"
    assert fn("/foo", "bar", "baz") == "/foo/bar/baz"
    assert fn("/foo/", "bar/", "baz/") == "/foo/bar/baz/"

    assert fn("a", "") == "a/"
    assert fn("a", "", "") == "a/"
    assert fn("a", "b") == "a/b"
    assert fn("a", "b/") == "a/b/"
    assert fn("a/", "b") == "a/b"
    assert fn("a/", "b/") == "a/b/"
    assert fn("a", "b/c", "d") == "a/b/c/d"
    assert fn("a", "b//c", "d") == "a/b//c/d"
    assert fn("a", "b/c/", "d") == "a/b/c/d"
    assert fn("/a", "b") == "/a/b"
    assert fn("/a/", "b") == "/a/b"
    assert fn("a", "/b", "c") == "/b/c"
    assert fn("a", "/b", "/c") == "/c"
    print("join", fn("/foo", "bar", "/bar", "baz"), fn("a", "b//c", "d"))


def test_split() -> None:
    assert posixpath.split("/foo/bar") == ("/foo", "bar")
    assert posixpath.split("/") == ("/", "")
    assert posixpath.split("foo") == ("", "foo")
    assert posixpath.split("////foo") == ("////", "foo")
    assert posixpath.split("//foo//bar") == ("//foo", "bar")
    print("split", posixpath.split("//foo//bar"))


def splitext_test(path: str, filename: str, ext: str) -> None:
    assert posixpath.splitext(path) == (filename, ext)
    assert posixpath.splitext("/" + path) == ("/" + filename, ext)
    assert posixpath.splitext("abc/" + path) == ("abc/" + filename, ext)
    assert posixpath.splitext("abc.def/" + path) == ("abc.def/" + filename, ext)
    assert posixpath.splitext("/abc.def/" + path) == ("/abc.def/" + filename, ext)
    assert posixpath.splitext(path + "/") == (filename + ext + "/", "")
    print("splitext", repr(path), posixpath.splitext(path))


def test_splitext() -> None:
    splitext_test("foo.bar", "foo", ".bar")
    splitext_test("foo.boo.bar", "foo.boo", ".bar")
    splitext_test("foo.boo.biff.bar", "foo.boo.biff", ".bar")
    splitext_test(".csh.rc", ".csh", ".rc")
    splitext_test("nodots", "nodots", "")
    splitext_test(".cshrc", ".cshrc", "")
    splitext_test("...manydots", "...manydots", "")
    splitext_test("...manydots.ext", "...manydots", ".ext")
    splitext_test(".", ".", "")
    splitext_test("..", "..", "")
    splitext_test("........", "........", "")
    splitext_test("", "", "")


def test_splitroot() -> None:
    f = posixpath.splitroot
    assert f('') == ('', '', '')
    assert f('a') == ('', '', 'a')
    assert f('a/b') == ('', '', 'a/b')
    assert f('a/b/') == ('', '', 'a/b/')
    assert f('/a') == ('', '/', 'a')
    assert f('/a/b') == ('', '/', 'a/b')
    assert f('/a/b/') == ('', '/', 'a/b/')
    # The root is collapsed when there are redundant slashes
    # except when there are exactly two leading slashes, which
    # is a special case in POSIX.
    assert f('//a') == ('', '//', 'a')
    assert f('///a') == ('', '/', '//a')
    assert f('///a/b') == ('', '/', '//a/b')
    # Paths which look like NT paths aren't treated specially.
    assert f('c:/a/b') == ('', '', 'c:/a/b')
    assert f('\\/a/b') == ('', '', '\\/a/b')
    assert f('\\a\\b') == ('', '', '\\a\\b')
    print("splitroot", f('//a'), f('///a/b'))


def test_isabs() -> None:
    assert posixpath.isabs("") is False
    assert posixpath.isabs("/") is True
    assert posixpath.isabs("/foo") is True
    assert posixpath.isabs("/foo/bar") is True
    assert posixpath.isabs("foo/bar") is False
    print("isabs ok")


def test_basename() -> None:
    assert posixpath.basename("/foo/bar") == "bar"
    assert posixpath.basename("/") == ""
    assert posixpath.basename("foo") == "foo"
    assert posixpath.basename("////foo") == "foo"
    assert posixpath.basename("//foo//bar") == "bar"
    print("basename ok")


def test_dirname() -> None:
    assert posixpath.dirname("/foo/bar") == "/foo"
    assert posixpath.dirname("/") == "/"
    assert posixpath.dirname("foo") == ""
    assert posixpath.dirname("////foo") == "////"
    assert posixpath.dirname("//foo//bar") == "//foo"
    print("dirname ok")


def test_normpath() -> None:
    for path, expected in NORMPATH_CASES:
        result = posixpath.normpath(path)
        assert result == expected, path
        print("normpath", repr(path), repr(result))


test_join()
test_split()
test_splitext()
test_splitroot()
test_isabs()
test_basename()
test_dirname()
test_normpath()
