# error: module 'json' is not supported: it is not a builtin module and there is no json.py on the module path
try:
    import json
except ImportError:
    print("json is required")
    raise SystemExit(1)
