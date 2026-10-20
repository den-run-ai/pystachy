# error: _lru_cache_wrapper() cannot bind its type variables from the argument for 'user_function', a <function <lambda> (tests/errors/library/lib_functools_lambda.py:4)>: the lambda's parameter 'x' has no annotation
from functools import cache

sq = cache(lambda x: x * x)
print(sq(3))
