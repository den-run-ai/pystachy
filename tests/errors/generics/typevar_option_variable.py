# error: typevar_option_variable.py:7: error: a TypeVar's arguments other than its name, constraints and bound must be constants
# A TypeVar's other arguments (covariant=, contravariant=, infer_variance=, default=) must be
# constants.
from typing import TypeVar

flag = True
T = TypeVar("T", covariant=flag)
print("T")
