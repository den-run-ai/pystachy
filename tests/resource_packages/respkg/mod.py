from importlib.resources import files


def where():
    return files(__name__)
