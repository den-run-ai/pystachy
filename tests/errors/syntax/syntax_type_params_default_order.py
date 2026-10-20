# error: syntax_type_params_default_order.py:4: error: non-default type parameter 'U' follows default type parameter
class Pair[
    T = int,
    U,
]:
    pass
