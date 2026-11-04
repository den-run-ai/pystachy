"""Filename globbing utility."""
# Pystachy's subset implementation of CPython 3.13.16's Lib/glob.py (lib/compatibility.md#glob):
# glob(), iglob() and escape(), with CPython's functions for them, which os.scandir() entries and
# the dir_fd arguments' descriptors are not for here (os.listdir() and os.path.isdir() list and
# test a directory's entries, in the same order); translate() and the globbers pathlib uses are
# not. Each function keeps CPython's name and order of results.
import fnmatch
import os
import posixpath

__all__ = ["glob", "iglob", "escape"]


def glob(pathname: str, *, root_dir: str | None = None, dir_fd: int | None = None, recursive: bool = False,
         include_hidden: bool = False) -> list[str]:
    """Return a list of paths matching a `pathname` pattern.

    The pattern may contain simple shell-style wildcards a la
    fnmatch. Unlike fnmatch, filenames starting with a
    dot are special cases that are not matched by '*' and '?'
    patterns by default.

    The order of the returned list is undefined. Sort it if you need a
    particular order.

    If `root_dir` is not None, it should be a path-like object specifying
    the root directory for searching.  It has the same effect as changing
    the current directory before calling it (without actually changing it).
    If pathname is relative, the result will contain paths relative to
    `root_dir`.

    If `dir_fd` is not None, it should be a file descriptor referring to a
    directory, and paths will then be relative to that directory.

    If `include_hidden` is true, wildcards can match path segments beginning
    with a dot ('.').

    If `recursive` is true, the pattern '**' will match any files and
    zero or more directories and subdirectories.
    """
    return list(iglob(pathname, root_dir=root_dir, dir_fd=dir_fd, recursive=recursive,
                      include_hidden=include_hidden))


def iglob(pathname: str, *, root_dir: str | None = None, dir_fd: int | None = None, recursive: bool = False,
          include_hidden: bool = False):
    """Return an iterator which yields the paths matching a `pathname` pattern.

    The pattern may contain simple shell-style wildcards a la
    fnmatch. However, unlike fnmatch, filenames starting with a
    dot are special cases that are not matched by '*' and '?'
    patterns.

    The order of the returned paths is undefined. Sort them if you need a
    particular order.

    If `root_dir` is not None, it should be a path-like object specifying
    the root directory for searching.  It has the same effect as changing
    the current directory before calling it (without actually changing it).
    If pathname is relative, the result will contain paths relative to
    `root_dir`.

    If `dir_fd` is not None, it should be a file descriptor referring to a
    directory, and paths will then be relative to that directory.

    If `include_hidden` is true, wildcards can match path segments beginning
    with a dot ('.').

    If `recursive` is true, the pattern '**' will match any files and
    zero or more directories and subdirectories.
    """
    if dir_fd is not None:
        raise NotImplementedError("glob.iglob() with dir_fd is not supported")
    root = root_dir if root_dir is not None else ''
    return _iglob_top(pathname, root, recursive, include_hidden)


def _iglob_top(pathname: str, root_dir: str, recursive: bool, include_hidden: bool):
    # (iglob()'s iterator: _iglob(), whose first path is skipped where it is empty)
    skip = not pathname or (recursive and _isrecursive(pathname[:2]))
    for s in _iglob(pathname, root_dir, recursive, False, include_hidden):
        if skip:
            skip = False
            if not s:
                continue
        yield s


def _iglob(pathname: str, root_dir: str, recursive: bool, dironly: bool, include_hidden: bool):
    dirname, basename = posixpath.split(pathname)
    if not has_magic(pathname):
        assert not dironly
        if basename:
            if _lexists(_join(root_dir, pathname)):
                yield pathname
        else:
            # Patterns ending with a slash should match only directories
            if _isdir(_join(root_dir, dirname)):
                yield pathname
        return
    if not dirname:
        if recursive and _isrecursive(basename):
            yield from _glob2(root_dir, basename, dironly, include_hidden)
        else:
            yield from _glob1(root_dir, basename, dironly, include_hidden)
        return
    if dirname != pathname and has_magic(dirname):
        dirs = list(_iglob(dirname, root_dir, recursive, True, include_hidden))
    else:
        dirs = [dirname]
    for d in dirs:
        if has_magic(basename) and recursive and _isrecursive(basename):
            names = list(_glob2(_join(root_dir, d), basename, dironly, include_hidden))
        elif has_magic(basename):
            names = _glob1(_join(root_dir, d), basename, dironly, include_hidden)
        else:
            names = _glob0(_join(root_dir, d), basename, dironly)
        for name in names:
            yield os.path.join(d, name)


# These 2 helper functions non-recursively glob inside a literal directory.
# They return a list of basenames.  _glob1 accepts a pattern while _glob0
# takes a literal basename (so it only has to check for its existence).

def _glob1(dirname: str, pattern: str, dironly: bool, include_hidden: bool) -> list[str]:
    names = _listdir(dirname, dironly)
    if not (include_hidden or _ishidden(pattern)):
        names = [x for x in names if not _ishidden(x)]
    return fnmatch.filter(names, pattern)


def _glob0(dirname: str, basename: str, dironly: bool) -> list[str]:
    if basename:
        if _lexists(_join(dirname, basename)):
            return [basename]
    else:
        # `os.path.split()` returns an empty basename for paths ending with a
        # directory separator.  'q*x/' should match only directories.
        if _isdir(dirname):
            return [basename]
    return []


# This helper function recursively yields relative pathnames inside a literal
# directory.

def _glob2(dirname: str, pattern: str, dironly: bool, include_hidden: bool):
    assert _isrecursive(pattern)
    if not dirname or _isdir(dirname):
        yield pattern[:0]
    yield from _rlistdir(dirname, dironly, include_hidden)


def _listdir(dirname: str, dironly: bool) -> list[str]:
    # (_iterdir's names, as a list: those of the directory's entries, or of its subdirectories
    # where dironly; none where listing it raises OSError)
    try:
        names = os.listdir(dirname if dirname else os.curdir)
    except OSError:
        return []
    if not dironly:
        return names
    return [x for x in names if os.path.isdir(_join(dirname, x))]


# Recursively yields relative pathnames inside a literal directory.
def _rlistdir(dirname: str, dironly: bool, include_hidden: bool):
    names = _listdir(dirname, dironly)
    for x in names:
        if include_hidden or not _ishidden(x):
            yield x
            path = _join(dirname, x) if dirname else x
            for y in _rlistdir(path, dironly, include_hidden):
                yield _join(x, y)


def _lexists(pathname: str) -> bool:
    return os.path.lexists(pathname)


def _isdir(pathname: str) -> bool:
    return os.path.isdir(pathname)


def _join(dirname: str, basename: str) -> str:
    # It is common if dirname or basename is empty
    if not dirname or not basename:
        return dirname or basename
    return os.path.join(dirname, basename)


def has_magic(s) -> bool:
    if isinstance(s, bytes):
        return b'*' in s or b'?' in s or b'[' in s
    text: str = s
    return '*' in text or '?' in text or '[' in text


def _ishidden(path: str) -> bool:
    return path[0] == '.'


def _isrecursive(pattern: str) -> bool:
    return pattern == '**'


def escape(pathname):
    """Escape all special characters.
    """
    # Escaping is done by wrapping any of "*?[" between square brackets.
    # Metacharacters do not work in the drive part and shouldn't be escaped.
    if isinstance(pathname, bytes):
        if not has_magic(pathname):
            return pathname
        # POSIX has no drive prefix. Escape '[' first so newly inserted brackets stay literal.
        return pathname.replace(b'[', b'[[]').replace(b'*', b'[*]').replace(b'?', b'[?]')
    drive, rest = posixpath.splitdrive(pathname)
    if not has_magic(rest):
        return rest  # POSIX splitdrive preserves the original path.
    out = []
    for c in rest:
        out.append('[' + c + ']' if c == '*' or c == '?' or c == '[' else c)
    return drive + ''.join(out)
