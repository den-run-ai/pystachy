# pystachy: dynamic-any
"""Object-oriented filesystem paths.

This module provides classes to represent abstract paths and concrete
paths with operations that have semantics appropriate for different
operating systems.
"""
# Pystachy's subset implementation of CPython 3.13.16's Lib/pathlib (lib/compatibility.md#pathlib):
# its PurePosixPath and PosixPath, the classes CPython's PurePath and Path make on POSIX, which
# those names bind here, with the code of their methods. A path parses its parts as it is made,
# where CPython parses them when they are first read. Path.glob() and rglob() follow CPython's
# _StringGlobber, and the file system calls are the os module's and the compiler's primitives of
# this module (runtime.c's pys_stat_mode and pys_touch).
import fnmatch
import os
import posixpath
from typing import Any

__all__ = [
    "UnsupportedOperation",
    "PurePath", "PurePosixPath",
    "Path", "PosixPath",
]


class UnsupportedOperation(NotImplementedError):
    """An exception that is raised when an unsupported operation is attempted.
    """
    pass


def _parse_path(path: str) -> tuple[str, str, list[str]]:
    # CPython's PurePath._parse_path for posixpath: a path's drive (none on POSIX), root and parts
    if not path:
        return '', '', []
    drv, root, rel = posixpath.splitroot(path)
    parsed = [x for x in rel.split('/') if x and x != '.']
    return drv, root, parsed


def _format_parsed_parts(drv: str, root: str, tail: list[str]) -> str:
    if drv or root:
        return drv + root + '/'.join(tail)
    return '/'.join(tail)


def _is_magic(part: str) -> bool:
    # (glob's magic_check: a part with a wildcard)
    return '*' in part or '?' in part or '[' in part


def _add_slash(path: str) -> str:
    # (_StringGlobber.add_slash)
    if not path or path[-1] == '/':
        return path
    return path + '/'


def _entry_path(path: str, name: str) -> str:
    # (an os.scandir() entry's path: os.path.join() of the directory scanned and the name)
    return _add_slash(path) + name


def _stat_mode(path: str, follow: bool) -> int:
    # os.stat(path)'s (os.lstat(path)'s) st_mode, or -1 where pathlib ignores its error
    return __pys_stat_mode(path, follow)


def _isdir_mode(mode: int) -> bool:
    return mode >= 0 and (mode & 0o170000) == 0o040000


def _listdir(path: str) -> list[str]:
    # (the names an os.scandir() of path gives, or none where it raises OSError: _Globber)
    try:
        return os.listdir(path)
    except OSError:
        return []


def _select(path: str, parts: list[str], exists: bool, case_sensitive: bool, pedantic: bool):
    # the paths that _Globber's selector for parts (reversed, as it pops them) selects from path,
    # in its order: a literal part (and those after it) is joined to the path, a wildcard part
    # matches the directory's entries, and '**' selects the path and its subdirectories. Where
    # glob() was given case_sensitive (pedantic, CPython's case_pedantic), a literal part also
    # matches the entries, as the file system's case sensitivity is not known
    if len(parts) == 0:
        # (select_exists: an lstat() that raises OSError selects nothing)
        if exists or _ignore_oserror(path, False) >= 0:
            yield path
        return
    rest = parts[:-1]
    part = parts[-1]
    if part == '**':
        while len(rest) > 0 and rest[-1] == '**':
            rest = rest[:-1]
        dir_only = len(rest) > 0
        top = _add_slash(path)
        yield from _select(top, rest, exists, case_sensitive, pedantic)
        stack = [top]
        while len(stack) > 0:
            p = stack.pop()
            for name in _listdir(p):
                entry = _entry_path(p, name)
                is_dir = _isdir_mode(_ignore_oserror(entry, False))
                if is_dir or not dir_only:
                    if dir_only:
                        yield from _select(entry, rest, True, case_sensitive, pedantic)
                    else:
                        yield entry
                    if is_dir:
                        stack.append(entry)
    elif part == '' or part == '.' or part == '..':
        yield from _select(_add_slash(path) + part, rest, exists, case_sensitive, pedantic)
    elif not pedantic and not _is_magic(part):
        while len(rest) > 0 and not _is_magic(rest[-1]):
            part += '/' + rest[-1]
            rest = rest[:-1]
        yield from _select(_add_slash(path) + part, rest, False, case_sensitive, pedantic)
    else:
        dir_only = len(rest) > 0
        pat = part if case_sensitive else part.lower()
        for name in _listdir(path):
            if part == '*' or fnmatch.fnmatchcase(name if case_sensitive else name.lower(), pat):
                entry = _entry_path(path, name)
                if dir_only and not _isdir_mode(_ignore_oserror(entry, True)):
                    continue
                if dir_only:
                    yield from _select(entry, rest, True, case_sensitive, pedantic)
                else:
                    yield entry


def _ignore_oserror(path: str, follow: bool) -> int:
    # (an entry's is_dir(), which is false where it raises OSError)
    try:
        return _stat_mode(path, follow)
    except OSError:
        return -1


class _PurePathParents:
    """This object provides sequence-like access to the logical ancestors
    of a path.  Don't try to construct it yourself."""
    # (CPython's _PathParents, of a PurePosixPath; _PathParents below is a PosixPath's, whose
    # items are PosixPath objects)

    def __init__(self, path: "PurePosixPath") -> None:
        self._drv: str = path._drv
        self._root: str = path._root
        self._tail: list[str] = path._tail
        self._type: str = type(path).__name__

    def _make(self, tail: list[str]) -> "PurePosixPath":
        return PurePosixPath(_format_parsed_parts(self._drv, self._root, tail))

    def __len__(self) -> int:
        return len(self._tail)

    def __getitem__(self, idx: int):
        if idx >= len(self) or idx < -len(self):
            raise IndexError(idx)
        if idx < 0:
            idx += len(self)
        return self._make(self._tail[:-idx - 1])

    def __iter__(self):
        # (each item is an object of the path's class, which indexing gives as that type, but
        # iteration as a PurePosixPath: an iterator has one type of item in the class and its
        # subclass)
        items: list[PurePosixPath] = []
        for i in range(len(self)):
            items.append(self[i])
        return iter(items)

    def __contains__(self, value: object) -> bool:
        for i in range(len(self)):
            if self[i] == value:
                return True
        return False

    def __repr__(self) -> str:
        return "<{}.parents>".format(self._type)


class _PathParents(_PurePathParents):
    def _make(self, tail: list[str]) -> "PosixPath":
        return PosixPath(_format_parsed_parts(self._drv, self._root, tail))


class _NoArg:
    # (the default of a path's constructor's parameters past its arguments: see PurePosixPath)
    pass


_NOARG = _NoArg()


class PurePosixPath:
    """Base class for manipulating paths without I/O.

    PurePath represents a filesystem path and offers operations which
    don't imply any actual filesystem I/O.  Depending on your system,
    instantiating a PurePath will return either a PurePosixPath or a
    PureWindowsPath object.  You can also instantiate either of these classes
    directly, regardless of your system.
    """
    # (CPython's PurePosixPath, whose methods are its base PurePath's: PurePath names it here.
    # Its constructor takes at most eight segments, as its parameters, so that the class is no
    # class template, whose subclasses Path and those of programs could not be)

    def __init__(self, p0: Any = _NOARG, p1: Any = _NOARG, p2: Any = _NOARG, p3: Any = _NOARG,
                 p4: Any = _NOARG, p5: Any = _NOARG, p6: Any = _NOARG, p7: Any = _NOARG) -> None:
        paths: list[str] = []
        for arg in [p0, p1, p2, p3, p4, p5, p6, p7]:
            if arg is _NOARG:
                break
            if isinstance(arg, PurePosixPath):
                paths.extend(arg._raw_paths)
            elif isinstance(arg, str):
                paths.append(arg)
            else:
                raise TypeError(
                    "argument should be a str or an os.PathLike "
                    "object where __fspath__ returns a str, "
                    f"not {type(arg).__name__!r}")
        self._raw_paths: list[str] = paths
        if len(paths) == 0:
            raw = ''
        elif len(paths) == 1:
            raw = paths[0]
        else:
            raw = paths[0]
            for path in paths[1:]:
                raw = posixpath.join(raw, path)  # (posixpath.join(*paths), whose segments it takes in turn)
        drv, root, tail = _parse_path(raw)
        self._drv: str = drv
        self._root: str = root
        self._tail: list[str] = tail
        self._str: str = _format_parsed_parts(drv, root, tail) or '.'

    def with_segments(self, *pathsegments):
        """Construct a new path object from any number of path-like objects.
        Subclasses may override this method to customize how new path objects
        are created from methods like `iterdir()`.
        """
        return PurePosixPath(*pathsegments)

    def _from_parsed_parts(self, drv: str, root: str, tail: list[str]):
        return self.with_segments(_format_parsed_parts(drv, root, tail))

    def joinpath(self, *pathsegments):
        """Combine this path with one or several arguments, and return a
        new path representing either a subpath (if all arguments are relative
        paths) or a totally different path (if one of the arguments is
        anchored).
        """
        return self.with_segments(self, *pathsegments)

    def __truediv__(self, key):
        return self.with_segments(self, key)

    def __repr__(self) -> str:
        return "{}({!r})".format(self.__class__.__name__, self.as_posix())

    def __fspath__(self) -> str:
        return str(self)

    def __str__(self) -> str:
        """Return the string representation of the path, suitable for
        passing to system calls."""
        return self._str

    def as_posix(self) -> str:
        """Return the string representation of the path with forward (/)
        slashes."""
        return str(self)

    def __hash__(self) -> int:
        return hash(self._str)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, PurePosixPath):
            return False
        return self._str == other._str

    def _parts_normcase(self) -> list[str]:
        return self._str.split('/')

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, PurePosixPath):
            raise TypeError("'<' not supported between instances of '%s' and '%s'" % (type(self).__name__, type(other).__name__))
        return self._parts_normcase() < other._parts_normcase()

    def __le__(self, other: object) -> bool:
        if not isinstance(other, PurePosixPath):
            raise TypeError("'<=' not supported between instances of '%s' and '%s'" % (type(self).__name__, type(other).__name__))
        return self._parts_normcase() <= other._parts_normcase()

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, PurePosixPath):
            raise TypeError("'>' not supported between instances of '%s' and '%s'" % (type(self).__name__, type(other).__name__))
        return self._parts_normcase() > other._parts_normcase()

    def __ge__(self, other: object) -> bool:
        if not isinstance(other, PurePosixPath):
            raise TypeError("'>=' not supported between instances of '%s' and '%s'" % (type(self).__name__, type(other).__name__))
        return self._parts_normcase() >= other._parts_normcase()

    @property
    def drive(self) -> str:
        """The drive prefix (letter or UNC path), if any."""
        return self._drv

    @property
    def root(self) -> str:
        """The root of the path, if any."""
        return self._root

    @property
    def anchor(self) -> str:
        """The concatenation of the drive and root, or ''."""
        return self._drv + self._root

    @property
    def parts(self) -> tuple[str, ...]:
        """An object providing sequence-like access to the
        components in the filesystem path."""
        if self._drv or self._root:
            return tuple([self._drv + self._root] + self._tail)
        else:
            return tuple(self._tail)

    @property
    def parent(self) -> "PurePosixPath":
        """The logical parent of the path."""
        if not self._tail:
            return self
        return self._from_parsed_parts(self._drv, self._root, self._tail[:-1])

    @property
    def parents(self) -> "_PurePathParents":
        """A sequence of this path's logical parents."""
        # The value of this property should not be cached on the path object,
        # as doing so would introduce a reference cycle.
        return _PurePathParents(self)

    @property
    def name(self) -> str:
        """The final path component, if any."""
        if not self._tail:
            return ''
        return self._tail[-1]

    @property
    def suffix(self) -> str:
        """
        The final component's last suffix, if any.

        This includes the leading period. For example: '.txt'
        """
        name = self.name
        i = name.rfind('.')
        if 0 < i < len(name) - 1:
            return name[i:]
        else:
            return ''

    @property
    def suffixes(self) -> list[str]:
        """
        A list of the final component's suffixes, if any.

        These include the leading periods. For example: ['.tar', '.gz']
        """
        name = self.name
        if name.endswith('.'):
            return []
        name = name.lstrip('.')
        return ['.' + suffix for suffix in name.split('.')[1:]]

    @property
    def stem(self) -> str:
        """The final path component, minus its last suffix."""
        name = self.name
        i = name.rfind('.')
        if 0 < i < len(name) - 1:
            return name[:i]
        else:
            return name

    def with_name(self, name: str):
        """Return a new path with the file name changed."""
        if not name or '/' in name or name == '.':
            raise ValueError(f"Invalid name {name!r}")
        tail = self._tail.copy()
        if not tail:
            raise ValueError(f"{self!r} has an empty name")
        tail[-1] = name
        return self._from_parsed_parts(self._drv, self._root, tail)

    def with_stem(self, stem: str):
        """Return a new path with the stem changed."""
        suffix = self.suffix
        if not suffix:
            return self.with_name(stem)
        elif not stem:
            # If the suffix is non-empty, we can't make the stem empty.
            raise ValueError(f"{self!r} has a non-empty suffix")
        else:
            return self.with_name(stem + suffix)

    def with_suffix(self, suffix: str):
        """Return a new path with the file suffix changed.  If the path
        has no suffix, add given suffix.  If the given suffix is an empty
        string, remove the suffix from the path.
        """
        stem = self.stem
        if not stem:
            # If the stem is empty, we can't make the suffix non-empty.
            raise ValueError(f"{self!r} has an empty name")
        elif suffix and not (suffix.startswith('.') and len(suffix) > 1):
            raise ValueError(f"Invalid suffix {suffix!r}")
        else:
            return self.with_name(stem + suffix)

    def relative_to(self, other: Any, *, walk_up: bool = False):
        """Return the relative path to another path identified by the passed
        arguments.  If the operation is not possible (because this is not
        related to the other path), raise ValueError.

        The *walk_up* parameter controls whether `..` may be used to resolve
        the path.
        """
        o = self.with_segments(other)
        steps = [o] + list(o.parents)
        mine = [self] + list(self.parents)
        for step in range(len(steps)):
            path = steps[step]
            if path in mine:
                parts = ['..'] * step + self._tail[len(path._tail):]
                return self._from_parsed_parts('', '', parts)
            elif not walk_up:
                raise ValueError(f"{str(self)!r} is not in the subpath of {str(o)!r}")
            elif path.name == '..':
                raise ValueError(f"'..' segment in {str(o)!r} cannot be walked")
        raise ValueError(f"{str(self)!r} and {str(o)!r} have different anchors")

    def is_relative_to(self, other: Any) -> bool:
        """Return True if the path is relative to another path or False.
        """
        o = self.with_segments(other)
        return o == self or o in self.parents

    def is_absolute(self) -> bool:
        """True if the path is absolute (has both a root and, if applicable,
        a drive)."""
        for path in self._raw_paths:
            if path.startswith('/'):
                return True
        return False

    def match(self, path_pattern: Any, *, case_sensitive: bool | None = None) -> bool:
        """
        Return True if this path matches the given pattern. If the pattern is
        relative, matching is done from the right; otherwise, the entire path
        is matched. The recursive wildcard '**' is *not* supported by this
        method.
        """
        pattern = self.with_segments(path_pattern)
        sensitive = True if case_sensitive is None else case_sensitive
        path_parts = list(self.parts)[::-1]
        pattern_parts = list(pattern.parts)[::-1]
        if not pattern_parts:
            raise ValueError("empty pattern")
        if len(path_parts) < len(pattern_parts):
            return False
        if len(path_parts) > len(pattern_parts) and pattern.anchor:
            return False
        for i in range(len(pattern_parts)):
            name = path_parts[i] if sensitive else path_parts[i].lower()
            pat = pattern_parts[i] if sensitive else pattern_parts[i].lower()
            if not fnmatch.fnmatchcase(name, pat):
                return False
        return True


class PosixPath(PurePosixPath):
    """PurePath subclass that can make system calls.

    Path represents a filesystem path but unlike PurePath, also offers
    methods to do system calls on path objects. Depending on your system,
    instantiating a Path will return either a PosixPath or a WindowsPath
    object. You can also instantiate a PosixPath or WindowsPath directly,
    but cannot instantiate a WindowsPath on a POSIX system or vice versa.
    """
    # (CPython's PosixPath, whose methods are its base Path's: Path names it here)

    def with_segments(self, *pathsegments):
        """Construct a new path object from any number of path-like objects.
        Subclasses may override this method to customize how new path objects
        are created from methods like `iterdir()`.
        """
        return PosixPath(*pathsegments)

    @property
    def parent(self) -> "PosixPath":
        """The logical parent of the path."""
        if not self._tail:
            return self
        return self._from_parsed_parts(self._drv, self._root, self._tail[:-1])

    @property
    def parents(self) -> "_PathParents":
        """A sequence of this path's logical parents."""
        return _PathParents(self)

    def exists(self, *, follow_symlinks: bool = True) -> bool:
        """
        Whether this path exists.

        This method normally follows symlinks; to check whether a symlink exists,
        add the argument follow_symlinks=False.
        """
        return _stat_mode(str(self), follow_symlinks) >= 0

    def is_dir(self, *, follow_symlinks: bool = True) -> bool:
        """
        Whether this path is a directory.
        """
        return _isdir_mode(_stat_mode(str(self), follow_symlinks))

    def is_file(self, *, follow_symlinks: bool = True) -> bool:
        """
        Whether this path is a regular file (also True for symlinks pointing
        to regular files).
        """
        mode = _stat_mode(str(self), follow_symlinks)
        return mode >= 0 and (mode & 0o170000) == 0o100000

    def is_symlink(self) -> bool:
        """
        Whether this path is a symbolic link.
        """
        mode = _stat_mode(str(self), False)
        return mode >= 0 and (mode & 0o170000) == 0o120000

    def open(self, mode: str = 'r', buffering: int = -1, encoding: str | None = None,
             errors: str | None = None, newline: str | None = None):
        """
        Open the file pointed to by this path and return a file object, as
        the built-in open() function does.
        """
        if buffering != -1 or errors is not None or newline is not None:
            raise UnsupportedOperation("Path.open() with buffering, errors or newline is not supported")
        return open(str(self), mode, encoding=encoding)

    def read_text(self, encoding: str | None = None, errors: str | None = None, newline: str | None = None) -> str:
        """
        Open the file in text mode, read it, and close the file.
        """
        with self.open(mode='r', encoding=encoding, errors=errors, newline=newline) as f:
            return f.read()

    def write_text(self, data: str, encoding: str | None = None, errors: str | None = None, newline: str | None = None) -> int:
        """
        Open the file in text mode, write to it, and close the file.
        """
        with self.open(mode='w', encoding=encoding, errors=errors, newline=newline) as f:
            return f.write(data)

    def read_bytes(self) -> bytes:
        """
        Open the file in bytes mode, read it, and close the file.
        """
        with open(str(self), 'rb') as f:
            return f.read()

    def write_bytes(self, data: bytes) -> int:
        """
        Open the file in bytes mode, write to it, and close the file.
        """
        with open(str(self), 'wb') as f:
            return f.write(data)

    def iterdir(self):
        """Yield path objects of the directory contents.

        The children are yielded in arbitrary order, and the
        special entries '.' and '..' are not included.
        """
        root_dir = str(self)
        names = os.listdir(root_dir)
        return iter([self.with_segments(_entry_path(root_dir, name)[2:] if root_dir == '.' else _entry_path(root_dir, name)) for name in names])

    def glob(self, pattern: Any, *, case_sensitive: bool | None = None, recurse_symlinks: bool = False):
        """Iterate over this subtree and yield all existing files (of any
        kind, including directories) matching the given relative pattern.
        """
        pat = self.with_segments(pattern)
        if pat.anchor:
            raise NotImplementedError("Non-relative patterns are unsupported")
        parts = pat._tail.copy()
        if not parts:
            raise ValueError("Unacceptable pattern: {!r}".format(pat))
        if recurse_symlinks:
            raise UnsupportedOperation("Path.glob() with recurse_symlinks=True is not supported")
        raw = pat._raw_paths[-1] if len(pat._raw_paths) > 0 else ''
        if raw.endswith('/'):
            # GH-65238: pathlib doesn't preserve trailing slash. Add it back.
            parts.append('')
        root = str(self)
        out = []
        for p in _select(root, parts[::-1], False, True if case_sensitive is None else case_sensitive, case_sensitive is not None):
            if root == '.':
                p = p[2:]
            if parts[-1] == '':
                p = p[:-1]
            elif parts[-1] == '**' and len(p) > len(self.anchor) and p[-1] == '/':
                p = p[:-1]
            out.append(self.with_segments(p))
        return iter(out)

    def rglob(self, pattern: Any, *, case_sensitive: bool | None = None, recurse_symlinks: bool = False):
        """Recursively yield all existing files (of any kind, including
        directories) matching the given relative pattern, anywhere in
        this subtree.
        """
        return self.glob(PurePosixPath('**', pattern), case_sensitive=case_sensitive, recurse_symlinks=recurse_symlinks)

    def absolute(self):
        """Return an absolute version of this path
        No normalization or symlink resolution is performed.

        Use resolve() to resolve symlinks and remove '..' segments.
        """
        if self.is_absolute():
            return self
        cwd = os.getcwd()
        if not self._tail:
            return self.with_segments(cwd)
        drive, root, rel = posixpath.splitroot(cwd)
        if not rel:
            return self._from_parsed_parts(drive, root, self._tail)
        tail = rel.split('/')
        tail.extend(self._tail)
        return self._from_parsed_parts(drive, root, tail)

    def resolve(self, strict: bool = False):
        """
        Make the path absolute, resolving all symlinks on the way and also
        normalizing it.
        """
        if strict:
            raise UnsupportedOperation("Path.resolve(strict=True) is not supported")
        return self.with_segments(os.path.realpath(str(self)))

    def expanduser(self):
        """ Return a new path with expanded ~ and ~user constructs
        (as returned by os.path.expanduser)
        """
        if not (self._drv or self._root) and self._tail and self._tail[0][:1] == '~':
            if self._tail[0] != '~':
                raise UnsupportedOperation("Path.expanduser() of ~user is not supported")
            homedir = os.getenv('HOME', '')
            if not homedir:
                raise RuntimeError("Could not determine home directory.")
            drv, root, tail = _parse_path(homedir)
            return self._from_parsed_parts(drv, root, tail + self._tail[1:])
        return self

    @classmethod
    def cwd(cls) -> "PosixPath":
        """Return a new path pointing to the current working directory."""
        return PosixPath(os.getcwd())

    @classmethod
    def home(cls) -> "PosixPath":
        """Return a new path pointing to expanduser('~').
        """
        return PosixPath("~").expanduser()

    def touch(self, mode: int = 0o666, exist_ok: bool = True) -> None:
        """
        Create this file with the given access mode, if it doesn't exist.
        """
        __pys_touch(str(self), mode, exist_ok)

    def mkdir(self, mode: int = 0o777, parents: bool = False, exist_ok: bool = False) -> None:
        """
        Create a new directory at this given path.
        """
        try:
            os.mkdir(str(self), mode)
        except FileNotFoundError:
            if not parents or self.parent == self:
                raise
            self.parent.mkdir(parents=True, exist_ok=True)
            self.mkdir(mode, parents=False, exist_ok=exist_ok)
        except OSError:
            # Cannot rely on checking for EEXIST, since the operating system
            # could give priority to other errors like EACCES or EROFS
            if not exist_ok or not self.is_dir():
                raise

    def unlink(self, missing_ok: bool = False) -> None:
        """
        Remove this file or link.
        If the path is a directory, use rmdir() instead.
        """
        try:
            os.remove(str(self))
        except FileNotFoundError:
            if not missing_ok:
                raise

    def rmdir(self) -> None:
        """
        Remove this directory.  The directory must be empty.
        """
        os.rmdir(str(self))

    def rename(self, target: Any):
        """
        Rename this path to the target path.

        The target path may be absolute or relative. Relative paths are
        interpreted relative to the current working directory, *not* the
        directory of the Path object.

        Returns the new Path instance pointing to the target path.
        """
        t = self.with_segments(target)
        os.rename(str(self), str(t))
        return t

    def replace(self, target: Any):
        """
        Rename this path to the target path, overwriting if that path exists.

        The target path may be absolute or relative. Relative paths are
        interpreted relative to the current working directory, *not* the
        directory of the Path object.

        Returns the new Path instance pointing to the target path.
        """
        t = self.with_segments(target)
        os.replace(str(self), str(t))
        return t


PurePath = PurePosixPath
Path = PosixPath
