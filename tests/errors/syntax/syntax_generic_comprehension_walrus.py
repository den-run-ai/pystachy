# error: syntax_generic_comprehension_walrus.py:2: error: assignment expression within a comprehension cannot be used within the definition of a generic
def f[T](x: [(y := 1) for z in [2]]) -> None:
    pass
