# error: optional_missing_raises.py:4: error: module 'yaml' is not supported: it is not a builtin module and there is no yaml.py on the module path
# A handler that raises makes the module required: CPython may find it (an installed package)
# where Pystachy does not.
try:
    import yaml
except ImportError:
    raise ImportError("this program needs PyYAML")
print("have yaml")
