# A package's own version, as packages read it with importlib.metadata
# (tests/programs/optional/optional_subclass_unrun.py)
from loader.subimp.metadata import PackageNotFoundError, version

try:
    __version__ = version("absent")
except PackageNotFoundError:
    __version__ = "0+unknown"
