class Plugin:
    def __init_subclass__(cls) -> None:
        print("registered", cls.__name__)


class Csv(Plugin):
    pass
