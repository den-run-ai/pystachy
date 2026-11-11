# Probe stub: importlib.resources.files() only (mypy/util.py's TYPESHED_DIR).
class Traversable:
    def __truediv__(self, child: str) -> "Traversable":
        return self

    def __str__(self) -> str:
        return ""


def files(package: str) -> Traversable:
    return Traversable()
