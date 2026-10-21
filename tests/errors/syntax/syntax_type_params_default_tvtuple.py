# error: syntax_type_params_default_tvtuple.py:2: error: non-default type parameter 'Ts' follows default type parameter
def f[T = int, *Ts](x: T) -> T:
    return x
