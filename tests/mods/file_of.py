import os


def own() -> str:
    return os.path.basename(__file__)


def folder() -> str:
    return os.path.basename(os.path.dirname(__file__))
