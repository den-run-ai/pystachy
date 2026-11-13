import mods.generic_signature_box as module
from mods.generic_signature_box import Box as Alias


def show(box: Alias[int]) -> None:
    print(box)


def qualified(box: module.Box[int]) -> None:
    print(box)


show(Alias(1))
module.READY = "changed"
qualified(Alias(2))
