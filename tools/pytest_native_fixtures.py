"""Built-in fixtures for generated native tests: tmp_path, monkeypatch's environment and recwarn.

Generated modules import this only when a test or fixture requests one of them, so
suites without them do not compile pathlib. These are not pytest's implementations:
the collector rejects the monkeypatch methods this class lacks.
"""

import os
import pathlib
import tempfile
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


class MonkeyPatch:
    """monkeypatch.setenv/delenv, undone in reverse order after the test."""

    def __init__(self) -> None:
        self._saved: list[tuple[str, str | None]] = []

    def setenv(self, name: str, value: str, prepend: str | None = None) -> None:
        if prepend is not None and name in os.environ:
            value = value + prepend + os.environ[name]
        self._saved.append((name, os.environ.get(name)))
        os.environ[name] = value

    def delenv(self, name: str, raising: bool = True) -> None:
        if name not in os.environ:
            if raising:
                raise KeyError(name)
            return
        self._saved.append((name, os.environ.get(name)))
        del os.environ[name]

    def undo(self) -> None:
        while self._saved:
            name, previous = self._saved.pop()
            if previous is None:
                if name in os.environ:
                    del os.environ[name]
            else:
                os.environ[name] = previous


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
