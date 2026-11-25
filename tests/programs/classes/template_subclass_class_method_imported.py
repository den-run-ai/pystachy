from mods.template_class_defaults import Base


class Sub(Base):
    pass


class Child(Sub):
    pass


x = Sub(1)
y = Child(2)
print(x.name(), y.name())
print(Base.count, Sub.count, Child.count)
