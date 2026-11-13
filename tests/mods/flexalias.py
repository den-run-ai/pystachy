# Type aliases as mypy's mypy/bogus_type.py binds Bogus (tests/programs/generics/flexible_alias*.py)
from typing import TypeVar

from mypy_extensions import FlexibleAlias

T = TypeVar("T")
Bogus = FlexibleAlias[T, T]
