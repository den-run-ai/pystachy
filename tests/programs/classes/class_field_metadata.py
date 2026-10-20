# _fields and _field_defaults on ordinary classes are not NamedTuple metadata.
class Base:
    _fields: tuple[str, ...] = ()
    _field_defaults: dict[str, int] = {"left": 2}


class Child(Base):
    _fields: tuple[str, ...] = ("left", "right")


print(Base._fields, Base()._fields)
print(Base._field_defaults, Base()._field_defaults)
print(Child._fields, Child()._fields)
print(Child._field_defaults, Child()._field_defaults)
Base._field_defaults["left"] = 7
print(Base._field_defaults, Base()._field_defaults)
print(Child._field_defaults, Child()._field_defaults)
