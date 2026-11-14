from importlib import resources


def note() -> str:
    return resources.read_text(__name__, "note.txt")
