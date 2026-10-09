def register(cls):
    print("registered", cls.__name__)


class Plugin:
    __init_subclass__ = classmethod(register)


class Csv(Plugin):
    pass
