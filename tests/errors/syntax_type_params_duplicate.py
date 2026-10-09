# error: syntax_type_params_duplicate.py:2: error: duplicate type parameter 'T'
def f[T, T](x: T) -> T:
    return x
