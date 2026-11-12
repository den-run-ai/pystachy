# Another module's class, read through a from-import and through the module.
import mods.opconsts
from mods.opconsts import Branch


class Printer:
    DEFAULT = Branch.BOOL
    QUALIFIED = mods.opconsts.Branch.IS_ERROR
    NAMES = {Branch.BOOL: "bool", mods.opconsts.Branch.IS_ERROR: "is_error"}

    def __init__(self) -> None:
        self.kind = mods.opconsts.Branch.BOOL
        self.reserved = Branch.RESERVED


p = Printer()
p.reserved.add("extra")
print(Printer.DEFAULT, Printer.QUALIFIED, Printer.NAMES[101], p.kind, sorted(p.reserved), sorted(Branch.RESERVED))
