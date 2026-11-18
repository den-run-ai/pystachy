from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tcbad.model import Model


def run(m: "Model") -> int:
    def inner(z: Model) -> int:
        return 1

    return inner(m)
