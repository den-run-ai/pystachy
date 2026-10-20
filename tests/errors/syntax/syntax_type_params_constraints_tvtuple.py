# error: syntax_type_params_constraints_tvtuple.py:2: error: cannot use constraints with TypeVarTuple
type Row[*Ts: (int, str)] = tuple[*Ts]
print("ran")
