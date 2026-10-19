# Pystachy compiles to native code and has no specializing bytecode interpreter: _opcode's
# ENABLE_SPECIALIZATION is 0, where CPython 3.13's default build has 1. The opcode tables still
# describe CPython's bytecode, as opcode and _opcode_metadata do.
import _opcode
import opcode

print(_opcode.ENABLE_SPECIALIZATION, _opcode.get_specialization_stats())
print(opcode.opmap["LOAD_ATTR"], len(opcode._specializations["LOAD_ATTR"]))
