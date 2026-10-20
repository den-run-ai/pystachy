# error: syntax_type_params_classdict.py:4: error: reserved name '__classdict__' cannot be used for type parameter
def f[
    T,
    __classdict__,
](x: T) -> T:
    return x


print(f(1))
