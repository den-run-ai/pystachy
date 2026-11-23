# pystachy: dynamic-any
from inspect import Parameter
from typing import Any


def default_for(value: int) -> Any:
    return Parameter('size', Parameter.POSITIONAL_OR_KEYWORD, default=abs(value)).default


# Construct two equal, distinct integers outside the small-integer cache.
first = int('1042')
other = int('1042')
print(default_for(first) is first, default_for(first) is other)
print(default_for(first) is default_for(first))
negative = -first
a = default_for(negative)
b = default_for(negative)
print(a == first, a is first, a is b)
print(default_for(-7) is default_for(7))
truth: Any = abs(True)
print(type(truth).__name__, truth is True)
