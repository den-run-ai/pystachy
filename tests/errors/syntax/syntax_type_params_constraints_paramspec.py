# error: syntax_type_params_constraints_paramspec.py:5: error: cannot use constraints with ParamSpec
def f[
    T,
    **P
    : (int, str),
](x: T) -> T:
    return x


print(f(1))
