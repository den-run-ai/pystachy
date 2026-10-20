# error: dataclasses.FrozenInstanceError is only supported in an except clause, which catches what assigning a field of a frozen dataclass raises
from dataclasses import FrozenInstanceError

try:
    raise FrozenInstanceError("cannot assign to field 'x'")
except AttributeError as e:
    print(e)
