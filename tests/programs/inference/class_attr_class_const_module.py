# An imported module's classes and functions read other classes' attributes in class bodies,
# fields and parameter defaults (mypyc's pretty-printer does); its class that the program does
# not use, whose values have mixed types, is left out as before.
import mods.opprinter
from mods.opprinter import Branch, Mode, Printer, describe

p = Printer()
q = Printer(True)
print(Printer.DEFAULT, Printer.MODE, Printer.MODES, Printer.LABELS is Branch.LABELS, sorted(Printer.KINDS), Printer.PAIR, Printer.limit)
print(p.show(), p.show(Branch.IS_ERROR, Mode.FAST), p.kind, q.kind, p.mode, Mode.SAFE in p.seen, Mode.FAST in q.seen)
print(describe(), describe(3), describe(4, (Mode.SAFE,)), mods.opprinter.Printer.branch_op_names[101])
Branch.LABELS.append("extra")
p.seen.add(Mode.FAST)
print(Printer.LABELS, p.LABELS, len(p.seen), len(q.seen))
