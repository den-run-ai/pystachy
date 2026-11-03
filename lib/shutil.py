"""Utility functions for copying and archiving files and directory trees.

XXX The functions here don't copy the resource fork or other metadata on Mac.

"""
# Pystachy's subset implementation of CPython 3.13.16's Lib/shutil.py (lib/compatibility.md#shutil):
# copyfileobj(), copyfile(), copymode(), copy(), move() and rmtree() of files and directories
# given by str paths, with CPython's checks and errors. A file's bytes are copied by the
# compiler's primitive of this module (runtime.c's pys_copyfile), as Pystachy has no binary
# files; rmtree() removes a tree as CPython's _rmtree_safe_fd does on Linux, without file
# descriptors.
import os
import posixpath

__all__ = ["copyfileobj", "copyfile", "copymode", "copy", "move", "rmtree", "Error",
           "SameFileError", "SpecialFileError"]

COPY_BUFSIZE = 64 * 1024


class Error(OSError):
    pass


class SameFileError(Error):
    """Raised when source and destination are the same file."""


class SpecialFileError(OSError):
    """Raised when trying to do a kind of operation (e.g. copying) which is
    not supported on a special file (e.g. a named pipe)"""


def copyfileobj(fsrc, fdst, length: int = 0) -> None:
    """copy data from file-like object fsrc to file-like object fdst"""
    if not length:
        length = COPY_BUFSIZE
    while True:
        buf = fsrc.read(length)
        if not buf:
            break
        fdst.write(buf)


def _samefile(src: str, dst: str) -> bool:
    try:
        return os.path.samefile(src, dst)
    except OSError:
        return False


def copyfile(src: str, dst: str, *, follow_symlinks: bool = True) -> str:
    """Copy data from src to dst in the most efficient way possible.

    If follow_symlinks is not set and src is a symbolic link, a new
    symlink will be created instead of copying the file it points to.

    """
    if _samefile(src, dst):
        raise SameFileError("{!r} and {!r} are the same file".format(src, dst))
    for fn in [src, dst]:
        try:
            mode = __pys_stat_mode(fn, True)
        except OSError:
            # File most likely does not exist
            mode = -1
        if mode >= 0 and (mode & 0o170000) == 0o010000:
            raise SpecialFileError("`%s` is a named pipe" % fn)
    if not follow_symlinks and os.path.islink(src):
        raise NotImplementedError("shutil.copyfile() of a symbolic link with follow_symlinks=False is not supported")
    try:
        __pys_copyfile(src, dst)
    except IsADirectoryError:
        # Issue 43219, raise a less confusing exception
        if os.path.isdir(src) or os.path.exists(dst):
            raise
        raise FileNotFoundError(f'Directory does not exist: {dst}')
    return dst


def copymode(src: str, dst: str, *, follow_symlinks: bool = True) -> None:
    """Copy mode bits from src to dst.

    If follow_symlinks is not set, symlinks aren't followed if and only
    if both `src` and `dst` are symlinks.  If `lchmod` isn't available
    (e.g. Linux) this method does nothing.

    """
    if not follow_symlinks and os.path.islink(src) and os.path.islink(dst):
        return
    __pys_copymode(src, dst)


def copy(src: str, dst: str, *, follow_symlinks: bool = True) -> str:
    """Copy data and mode bits ("cp src dst"). Return the file's destination.

    The destination may be a directory.

    If follow_symlinks is false, symlinks won't be followed. This
    resembles GNU's "cp -P src dst".

    If source and destination are the same file, a SameFileError will be
    raised.

    """
    if os.path.isdir(dst):
        dst = os.path.join(dst, posixpath.basename(src))
    copyfile(src, dst, follow_symlinks=follow_symlinks)
    copymode(src, dst, follow_symlinks=follow_symlinks)
    return dst


def _rmtree_dir(path: str) -> None:
    # (_rmtree_safe_fd_step: the entries of directory path, then path itself, a subdirectory's
    # first; a link is removed, not followed)
    for name in os.listdir(path):
        full = os.path.join(path, name)
        mode = __pys_stat_mode(full, False)
        if mode >= 0 and (mode & 0o170000) == 0o040000:
            _rmtree_dir(full)
        else:
            try:
                os.remove(full)
            except FileNotFoundError:
                continue
    try:
        os.rmdir(path)
    except FileNotFoundError:
        pass


def rmtree(path: str, ignore_errors: bool = False, onerror=None, *, onexc=None, dir_fd: int | None = None) -> None:
    """Recursively delete a directory tree.

    If dir_fd is not None, it should be a file descriptor open to a directory;
    path will then be relative to that directory.
    dir_fd may not be implemented on your platform.
    If it is unavailable, using it will raise a NotImplementedError.

    If ignore_errors is set, errors are ignored; otherwise, if onexc or
    onerror is set, it is called to handle the error with arguments (func,
    path, exc_info) where func is platform and implementation dependent;
    path is the argument to that function that caused it to fail; and
    the value of exc_info describes the exception. For onexc it is the
    exception instance, and for onerror it is a tuple as returned by
    sys.exc_info().  If ignore_errors is false and both onexc and
    onerror are None, the exception is reraised.

    onerror is deprecated and only remains for backwards compatibility.
    If both onerror and onexc are set, onerror is ignored and onexc is used.
    """
    if onerror is not None or onexc is not None or dir_fd is not None:
        raise NotImplementedError("shutil.rmtree() with onerror, onexc or dir_fd is not supported")
    try:
        mode = __pys_stat_mode(path, False)
        if mode < 0:
            raise FileNotFoundError(2, "No such file or directory", path)
        if (mode & 0o170000) == 0o120000:
            # symlinks to directories are forbidden, see bug #1669
            raise OSError("Cannot call rmtree on a symbolic link")
        if (mode & 0o170000) != 0o040000:
            raise NotADirectoryError(20, "Not a directory", path)
        _rmtree_dir(path)
    except OSError:
        if not ignore_errors:
            raise


def _basename(path: str) -> str:
    """A basename() variant which first strips the trailing slash, if present.
    Thus we always get the last component of the path, even for directories.

    path: Union[PathLike, str]

    e.g.
    >>> os.path.basename('/bar/foo')
    'foo'
    >>> os.path.basename('/bar/foo/')
    ''
    >>> _basename('/bar/foo/')
    'foo'
    """
    return posixpath.basename(path.rstrip('/'))


def move(src: str, dst: str) -> str | None:
    """Recursively move a file or directory to another location. This is
    similar to the Unix "mv" command. Return the file or directory's
    destination.

    If dst is an existing directory or a symlink to a directory, then src is
    moved inside that directory. The destination path in that directory must
    not already exist.

    If dst already exists but is not a directory, it may be overwritten
    depending on os.rename() semantics.

    os.rename() is preferably used if the source and destination are on the
    same filesystem. In case os.rename() fails due to OSError (e.g. the user
    has write permission to *dst* file but not to its parent directory),
    this method falls back to using *copy_function* silently.
    Symlinks are also recreated under the new name if os.rename() fails
    because of cross filesystem renames.

    It's recommended to use os.rename() if atomic move is strictly required.

    The optional `copy_function` argument is a callable that will be used
    to copy the source or it will be delegated to `copytree`.
    By default, copy2() is used, but any function that supports the same
    signature (like copy()) can be used.

    A lot more could be done here...  A look at a mv.c shows a lot of
    the issues this implementation glosses over.

    """
    real_dst = dst
    if os.path.isdir(dst):
        if _samefile(src, dst) and not os.path.islink(src):
            # We might be on a case insensitive filesystem,
            # perform the rename anyway.
            os.rename(src, dst)
            return None
        # Using _basename instead of os.path.basename is important, as we must
        # ignore any trailing slash to avoid the basename returning ''
        real_dst = os.path.join(dst, _basename(src))
        if os.path.exists(real_dst):
            raise Error("Destination path '%s' already exists" % real_dst)
    try:
        os.rename(src, real_dst)
    except OSError:
        if os.path.islink(src) or os.path.isdir(src):
            raise
        copy(src, real_dst)
        os.remove(src)
    return real_dst
