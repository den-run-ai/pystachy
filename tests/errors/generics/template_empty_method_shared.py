# error: got list[int]
# An empty field is existing mutable storage, not a fresh result to retype.
class Factory:
    def __init__(self) -> None:
        self.items: list[int] = []

    def shared(self, value):
        return self.items


result: list[str] = Factory().shared(1)
