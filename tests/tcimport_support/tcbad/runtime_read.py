from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tcbad.model import Model


def make() -> Model:
    return Model()
