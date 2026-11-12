from typing import Annotated, Final
X: Final[Annotated[int, "meta"]] = 3
Y: Annotated[Final[int], "meta"] = 4
print(X, Y)
