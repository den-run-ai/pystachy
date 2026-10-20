# error: syntax_type_params_starred_alias_paramspec.py:4: error: invalid syntax
type Alias[
    T,
    **P = *tuple[int, str],
] = int


print("ran")
