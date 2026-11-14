# importlib.resources.files() finds the modules that the program imports, which are those the
# compiler read: CPython imports the module that the name gives, here its own colorsys.
from importlib.resources import files

try:
    print(files("colorsys").is_dir())
except ModuleNotFoundError as e:
    print(type(e).__name__, e)
