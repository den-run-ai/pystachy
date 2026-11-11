from typing import Final
LDEF: Final = 0
GDEF: Final = 1
NAMES: Final[dict[int, str]] = {LDEF: "Ldef", GDEF: "Gdef"}
print(NAMES[GDEF])
