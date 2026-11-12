"""A package with data files, for the tests of importlib.resources."""
from importlib.resources import files

NAME = "respkg"


def data_dir():
    # (the usual idiom: a package's own code names itself)
    return files(__name__) / "data"
