# mypy node classes declare class-level defaults overridden in subclasses and read via instances
class Type:
    can_be_true = True
    def flag(self) -> bool:
        return self.can_be_true
class NoneType(Type):
    can_be_true = False
ts: list[Type] = [Type(), NoneType()]
print([t.flag() for t in ts])
