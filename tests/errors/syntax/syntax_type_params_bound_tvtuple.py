# error: syntax_type_params_bound_tvtuple.py:2: error: cannot use bound with TypeVarTuple
def f[*Ts: int](*args: *Ts) -> None:
    pass


print("ran")
