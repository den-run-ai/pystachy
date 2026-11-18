# A module's annotations may name what its if TYPE_CHECKING: imports bind, which CPython never
# runs, where the program imports their module anyway (tcpkg's class_ir and rtypes import each
# other through it, as mypyc's ir modules do): from-imports, aliases, import ... as, a relative
# import under typing.TYPE_CHECKING, a quoted annotation and a global's annotation; and, without
# postponed evaluation, those CPython does not evaluate (tcpkg.ops)
from tcpkg.class_ir import ClassIR, FuncIR
import tcpkg.rtypes as rtypes
from tcpkg.ops import first

c = ClassIR("C")
r = c.instance()
print(r.name, r.attr_type("x"), r.attr_type("y"), r.owner() is c, r.same(c), r.same(None))
print(rtypes.methods(c, [FuncIR("f"), FuncIR("g")]))
rtypes.remember(c)
print(rtypes.last is c)
b = first([ClassIR("b"), c, ClassIR("a")])
print(b.name if b is not None else None, first([]))
