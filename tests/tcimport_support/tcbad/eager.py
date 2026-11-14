from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tcbad.model import Model


def describe(m: Model) -> str:
    return "model"
