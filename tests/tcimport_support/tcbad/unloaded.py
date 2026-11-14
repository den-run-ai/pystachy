from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tcbad.absent import Absent


class Holder:
    def __init__(self, item: Absent) -> None:
        self.item = item
