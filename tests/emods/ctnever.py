# a class template whose field no call can type: an error only where the program makes an object


class _Neg:
    def __neg__(self) -> int:
        return 0


class Never:
    def __init__(self, v):
        self.v = -_Neg()  # (what __neg__ returns types no field, as for unary_neg_method)


class Fine:
    def __init__(self, v):
        self.v = v
