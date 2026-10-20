# error: a TypeVar's constraints, and a bound other than a string, are not supported
from typing import TypeVar

S = TypeVar("S", int, str)
