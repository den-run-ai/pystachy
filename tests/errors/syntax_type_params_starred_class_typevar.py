# error: syntax_type_params_starred_class_typevar.py:4: error: invalid syntax
class Pair[
    T,
    U = *tuple[int],
]:
    pass


print("ran")
