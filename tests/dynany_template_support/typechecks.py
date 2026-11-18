from templateboxes import Box as ImportedBox
import templateboxes


class Box:
    def __init__(self, value):
        self.value = value


class Base:
    pass


class Child(Base):
    pass


class Unused:
    def __init__(self, value):
        self.value = value

    def unused(self):
        return memoryview(self.value)


Alias = ImportedBox


def exact(value):
    print(type(value) is ImportedBox, ImportedBox is type(value),
          type(value) == templateboxes.Box, templateboxes.Box != type(value),
          type(value) is not Alias, Alias == type(value),
          type(value) is Box, type(value) is Unused,
          type(value) is Base, type(value) is Child)


def same(left, right):
    print(type(left) is type(right), type(right) == type(left),
          type(left) is not type(right), type(right) != type(left))


def marked(value, label: str):
    print(label)
    return value


def ordered(left, right):
    print(type(marked(left, "left")) is type(marked(right, "right")))
    print(ImportedBox is type(marked(left, "named-first")))
    print(type(marked(right, "named-last")) is ImportedBox)


def append(value):
    if type(value) is ImportedBox:
        value.value.append(5)
