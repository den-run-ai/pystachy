# error: argument 1 of os.remove() may be None (str | None); test it with 'is not None' first
import os


def drop(path: str | None) -> None:
    os.remove(path)


drop(None)
