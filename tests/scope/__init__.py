# A package whose submodule reads a constant from it while it is still being imported, and
# whose from-import of a function binds the name of the submodule it comes from.
VERSION = "1.0"
from . import core
from .parse import parse
