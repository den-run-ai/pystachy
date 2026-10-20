# error: syntax_type_alias_default_order.py:2: error: non-default type parameter 'U' follows default type parameter
type Pair[T = int, U] = tuple[T, U]
