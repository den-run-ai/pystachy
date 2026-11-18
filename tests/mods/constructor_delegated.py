class Aliased:
    def __init__(self, value=None):
        self.value: int = 1
        receiver = self
        if value is not None:
            receiver.initialize(value)

    def initialize(self, value):
        pass

    def get(self) -> int:
        return self.value


class AliasedChild(Aliased):
    def initialize(self, value):
        self.hidden = value

    def get(self) -> int:
        return self.hidden


def initialize(receiver, value) -> None:
    if value is not None:
        receiver.initialize(value)


class Escaped:
    def __init__(self, value=None):
        self.value: int = 2
        initialize(self, value)

    def initialize(self, value):
        pass

    def get(self) -> int:
        return self.value


class EscapedChild(Escaped):
    def initialize(self, value):
        self.hidden = value

    def get(self) -> int:
        return self.hidden
