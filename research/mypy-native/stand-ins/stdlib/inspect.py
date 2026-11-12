# Probe stub: the inspect.Parameter kinds that mypyc/ir/func_ir.py reads as it initializes,
# only to see past its import; building a Parameter or Signature raises.
class Parameter:
    POSITIONAL_ONLY = 0
    POSITIONAL_OR_KEYWORD = 1
    VAR_POSITIONAL = 2
    KEYWORD_ONLY = 3
    VAR_KEYWORD = 4
    empty = object()

    def __init__(self, name: str, kind: int, default: object = None) -> None:
        raise NotImplementedError("inspect.Parameter stub")


class Signature:
    def __init__(self, parameters: list[Parameter]) -> None:
        raise NotImplementedError("inspect.Signature stub")
