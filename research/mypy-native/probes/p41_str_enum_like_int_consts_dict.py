from typing import Final
ARG_POS: Final = 0
ARG_STAR: Final = 2
kinds: Final[list[int]] = [ARG_POS, ARG_STAR]
inverse: Final[dict[str, int]] = {"pos": ARG_POS, "star": ARG_STAR}
print(kinds, inverse["star"])
