# Documented deviation: None where complex is declared, stored as a union without None (which
# mypy rejects), raises TypeError; CPython stores None. Narrowed values store as CPython does.
from typing import Optional


def widen(c: complex) -> int | complex:
    return c


def pick(c: Optional[complex]) -> int | complex:
    if c is None:
        return 0
    return c


print(widen(1j), pick(None), pick(2j))
try:
    print(widen(None))  # type: ignore[arg-type]
except TypeError as e:
    print("TypeError:", e)
