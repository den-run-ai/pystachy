# TypeTranslator-style: visitor methods return the base type; default implementations in the base
class Type:
    def accept(self, v: "Translator") -> "Type":
        return v.visit_type(self)
class Instance(Type):
    def __init__(self, name: str) -> None:
        self.name = name
    def accept(self, v: "Translator") -> Type:
        return v.visit_instance(self)
class Translator:
    def visit_type(self, t: Type) -> Type:
        return t
    def visit_instance(self, t: Instance) -> Type:
        return t
class Renamer(Translator):
    def visit_instance(self, t: Instance) -> Type:
        return Instance(t.name + "'")
ts: list[Type] = [Type(), Instance("a")]
out = [t.accept(Renamer()) for t in ts]
print([o.name if isinstance(o, Instance) else "?" for o in out])
