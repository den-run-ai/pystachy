# error: syntax_type_params_starred_def_paramspec.py:2: error: invalid syntax
def wrap[**P = *tuple[int, str]](n: int) -> int:
    return n


print(wrap(1))
