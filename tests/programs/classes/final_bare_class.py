# A class-body field annotated Final with a constant has the constant's type.
from typing import Final


class Limits:
    top: Final = 10


print(Limits().top)
