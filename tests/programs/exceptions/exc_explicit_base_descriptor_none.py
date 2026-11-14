class Child(Exception):
    def init(self):
        Exception.__init__(self, argument())
    def text(self) -> str:
        return Exception.__str__(self)
    def representation(self) -> str:
        return Exception.__repr__(self)

def absent() -> Child | None:
    return None

def argument() -> str:
    print('argument')
    return 'hello'

try:
    Child.init(absent())
except Exception as error:
    print(type(error).__name__, str(error))
try:
    print(Child.text(absent()))
except Exception as error:
    print(type(error).__name__, str(error))
try:
    print(Child.representation(absent()))
except Exception as error:
    print(type(error).__name__, str(error))

present = Child()
Child.init(present)
print(Child.text(present), Child.representation(present))


class KeyChild(KeyError):
    def text(self) -> str:
        return KeyError.__str__(self)


class FileChild(FileNotFoundError):
    def text(self) -> str:
        return FileNotFoundError.__str__(self)


class AttrChild(AttributeError):
    def text(self) -> str:
        return AttributeError.__str__(self)


class ImportChild(ModuleNotFoundError):
    def text(self) -> str:
        return ModuleNotFoundError.__str__(self)


class NameChild(UnboundLocalError):
    def text(self) -> str:
        return UnboundLocalError.__str__(self)


key: KeyChild | None = None
file: FileChild | None = None
attr: AttrChild | None = None
imported: ImportChild | None = None
name: NameChild | None = None
for kind in [0, 1, 2, 3, 4]:
    try:
        if kind == 0:
            print(KeyChild.text(key))
        elif kind == 1:
            print(FileChild.text(file))
        elif kind == 2:
            print(AttrChild.text(attr))
        elif kind == 3:
            print(ImportChild.text(imported))
        else:
            print(NameChild.text(name))
    except TypeError as error:
        print(str(error))


class Custom(Exception):
    def __init__(self, value: str) -> None:
        print("custom init", self is None, value)

    def __str__(self) -> str:
        return "custom none" if self is None else "custom object"

    def __repr__(self) -> str:
        return "repr none" if self is None else "repr object"


class Delegated(Custom):
    def initialize(self) -> None:
        Custom.__init__(self, argument())

    def text(self) -> str:
        return Custom.__str__(self)

    def representation(self) -> str:
        return Custom.__repr__(self)


custom: Delegated | None = None
Delegated.initialize(custom)
print(Delegated.text(custom), Delegated.representation(custom))
custom = Delegated("created")
Delegated.initialize(custom)
print(Delegated.text(custom), Delegated.representation(custom))


class Inherited(Exception):
    pass


class Indirect(Inherited):
    def initialize(self) -> None:
        Inherited.__init__(self, argument())


indirect: Indirect | None = None
try:
    Indirect.initialize(indirect)
except TypeError as error:
    print(str(error))
