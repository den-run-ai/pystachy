# Probe stub: a throwing pprint, only to see past mypy/options.py's import.
def pformat(o: object) -> str:
    raise NotImplementedError("pprint.pformat stub")
