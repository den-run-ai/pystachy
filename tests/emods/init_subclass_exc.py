class Failed(Exception):
    def __init_subclass__(cls) -> None:
        print("registered", cls.__name__)


class Retry(Failed):
    pass
