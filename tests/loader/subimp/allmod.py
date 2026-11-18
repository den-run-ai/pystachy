# An optional import whose statements after the import bind __all__
# (tests/programs/optional/optional_subclass_all.py)
from loader.subimp.errors import require

a = 1
b = 2
try:
    import json

    __all__ = ["a"]
    require("json", True)
except ImportError:
    __all__ = ["a", "b"]
