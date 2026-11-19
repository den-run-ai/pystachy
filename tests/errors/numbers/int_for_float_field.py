# error: expected float, got int (write a float literal like 1.0, or use float())
# A constructor's float parameter types the field it fills, which holds floats: no int (#711)
from dataclasses import dataclass


@dataclass
class Vec:
    x: float
    y: float


print(Vec(0, 1.5))
