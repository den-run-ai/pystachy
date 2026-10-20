# error: syntax_type_params_bound_paramspec.py:2: error: cannot use bound with ParamSpec
class Box[**P: int]:
    pass


print("ran")
