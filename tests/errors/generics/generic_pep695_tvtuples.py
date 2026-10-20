# error: generic_pep695_tvtuples.py:3: error: a generic class with more than one TypeVarTuple type parameter (*Ts) is not supported
# (as Generic[*Ts, *Us] is not; CPython accepts the class statement)
class Rows[*Ts, *Us]:
    def __init__(self, *cells: *Ts) -> None:
        self.cells = cells


print(Rows(1, "a").cells)
