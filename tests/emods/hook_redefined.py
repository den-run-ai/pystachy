class Plugin:
    def __init_subclass__(cls, **kw):
        print("registered", cls.__name__)


class Csv(Plugin):
    pass


class Plugin:
    pass
