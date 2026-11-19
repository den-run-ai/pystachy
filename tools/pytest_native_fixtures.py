"""Built-in fixtures for generated native tests: tmp_path, tmp_path_factory, tmpdir, monkeypatch and recwarn.

Generated modules import this only when a test or fixture requests one of them, so
suites without them do not compile pathlib. These are not pytest's implementations:
the collector rejects the monkeypatch methods this class lacks, and writes
monkeypatch.setattr, setitem and delitem out where they are called.
"""

import os
import pathlib
import tempfile
from typing import Callable
import warnings

# The hosted runner sets a fresh directory it removes after the run; a generated
# program started on its own makes temporary directories instead.
tmp_base: list[str] = [""]
_tmp_counts: dict[str, int] = {}


def tmp_path(name: str) -> pathlib.Path:
    """A new empty directory per test, named as pytest names it: the test's name and a count."""
    base = tmp_base[0]
    if not base:
        return pathlib.Path(tempfile.mkdtemp())
    count = _tmp_counts.get(name, 0)
    _tmp_counts[name] = count + 1
    directory = os.path.join(base, name + str(count))
    os.mkdir(directory)
    return pathlib.Path(directory)


class TempPathFactory:
    """tmp_path_factory: directories under the run's base, numbered as tmp_path's are."""

    def getbasetemp(self) -> pathlib.Path:
        if not tmp_base[0]:
            tmp_base[0] = tempfile.mkdtemp()
        return pathlib.Path(tmp_base[0])

    def mktemp(self, basename: str, numbered: bool = True) -> pathlib.Path:
        base = str(self.getbasetemp())
        if numbered:
            count = _tmp_counts.get(basename, 0)
            _tmp_counts[basename] = count + 1
            basename = basename + str(count)
        directory = os.path.join(base, basename)
        os.mkdir(directory)
        return pathlib.Path(directory)


_factory = TempPathFactory()


def tmp_path_factory() -> TempPathFactory:
    return _factory


class LocalPath:
    """tmpdir: the part of py.path.local that tests of temporary files use."""

    def __init__(self, path: str) -> None:
        self.strpath = path

    def __str__(self) -> str:
        return self.strpath

    def __repr__(self) -> str:
        return "local(" + repr(self.strpath) + ")"

    def __fspath__(self) -> str:
        return self.strpath

    def __truediv__(self, name: str) -> "LocalPath":
        return LocalPath(os.path.join(self.strpath, name))

    def __eq__(self, other: object) -> bool:
        return isinstance(other, LocalPath) and other.strpath == self.strpath

    def __hash__(self) -> int:
        return hash(self.strpath)

    @property
    def basename(self) -> str:
        return os.path.basename(self.strpath)

    @property
    def dirname(self) -> str:
        return os.path.dirname(self.strpath)

    def dirpath(self) -> "LocalPath":
        return LocalPath(os.path.dirname(self.strpath))

    def join(self, *names: str) -> "LocalPath":
        path = self.strpath
        for name in names:
            path = os.path.join(path, name)
        return LocalPath(path)

    def exists(self) -> bool:
        return os.path.exists(self.strpath)

    def isdir(self) -> bool:
        return os.path.isdir(self.strpath)

    def isfile(self) -> bool:
        return os.path.isfile(self.strpath)

    def check(self) -> bool:
        return os.path.exists(self.strpath)

    def mkdir(self, name: str = "") -> "LocalPath":
        made = self.join(name) if name else self
        os.mkdir(made.strpath)
        return made

    def ensure(self, name: str = "") -> "LocalPath":
        """Make the file, and the directories above it, unless it exists."""
        made = self.join(name) if name else self
        parent = os.path.dirname(made.strpath)
        if parent and not os.path.isdir(parent):
            os.makedirs(parent)
        if not os.path.exists(made.strpath):
            with open(made.strpath, "w"):
                pass
        return made

    def write(self, data: str, mode: str = "w") -> None:
        with open(self.strpath, mode) as file:
            file.write(data)

    def write_text(self, data: str, encoding: str = "utf-8") -> None:
        with open(self.strpath, "w", encoding=encoding) as file:
            file.write(data)

    def read(self, mode: str = "r") -> str:
        with open(self.strpath, mode) as file:
            return file.read()

    def read_text(self, encoding: str = "utf-8") -> str:
        with open(self.strpath, encoding=encoding) as file:
            return file.read()

    def remove(self) -> None:
        os.remove(self.strpath)

    def listdir(self) -> list["LocalPath"]:
        return [LocalPath(os.path.join(self.strpath, name)) for name in sorted(os.listdir(self.strpath))]


def tmpdir(name: str) -> LocalPath:
    return LocalPath(str(tmp_path(name)))


class MonkeyPatch:
    """monkeypatch, undone in reverse order after the test.

    setenv and delenv are methods. The collector writes setattr, setitem and delitem
    out where the test calls them, typed by their arguments, and hands the statements
    that put the old value back to later().
    """

    def __init__(self) -> None:
        self._undo: list[Callable[[], None]] = []

    def later(self, undo: Callable[[], None]) -> None:
        self._undo.append(undo)

    def setenv(self, name: str, value: str, prepend: str | None = None) -> None:
        if prepend is not None and name in os.environ:
            value = value + prepend + os.environ[name]
        previous = os.environ.get(name)

        def restore() -> None:
            _restore_environment(name, previous)
        self._undo.append(restore)
        os.environ[name] = value

    def delenv(self, name: str, raising: bool = True) -> None:
        if name not in os.environ:
            if raising:
                raise KeyError(name)
            return
        previous = os.environ.get(name)

        def restore() -> None:
            _restore_environment(name, previous)
        self._undo.append(restore)
        del os.environ[name]

    def context(self) -> "MonkeyPatchContext":
        return MonkeyPatchContext()

    def undo(self) -> None:
        while self._undo:
            self._undo.pop()()


def _restore_environment(name: str, previous: str | None) -> None:
    if previous is None:
        if name in os.environ:
            del os.environ[name]
    else:
        os.environ[name] = previous


class MonkeyPatchContext:
    """`with monkeypatch.context() as m:` a MonkeyPatch undone where the block ends."""

    def __init__(self) -> None:
        self.patch = MonkeyPatch()

    def __enter__(self) -> MonkeyPatch:
        return self.patch

    def __exit__(self, kind: object, value: object, traceback: object) -> None:
        self.patch.undo()


def monkeypatch():
    patch = MonkeyPatch()
    yield patch
    patch.undo()


class WarningsRecorder:
    """recwarn: the warnings raised since the fixture was set up, oldest first."""

    def __init__(self, caught: list[warnings.WarningMessage]) -> None:
        self.list = caught

    def __len__(self) -> int:
        return len(self.list)

    def __getitem__(self, index: int) -> warnings.WarningMessage:
        return self.list[index]

    def __iter__(self):
        return iter(self.list)

    def pop(self, category: type[Warning] = Warning) -> warnings.WarningMessage:
        """Remove the first warning of exactly that class, or else the most general subclass's."""
        best = -1
        for index in range(len(self.list)):
            found = self.list[index].category
            if found is category:
                return self.list.pop(index)
            if issubclass(found, category) and (best < 0 or not issubclass(found, self.list[best].category)):
                best = index
        if best < 0:
            raise AssertionError(category.__name__ + " not found in warning list")
        return self.list.pop(best)

    def clear(self) -> None:
        self.list.clear()


def _recorded(caught: list[warnings.WarningMessage] | None) -> list[warnings.WarningMessage]:
    if caught is None:
        raise RuntimeError("warnings were not recorded")
    return caught


def recwarn():
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("default")
        yield WarningsRecorder(_recorded(caught))
