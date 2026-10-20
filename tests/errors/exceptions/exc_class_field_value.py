# error: a field 'value' of exception class S is not supported here: StopIteration.__init__() sets its attribute value as it runs, after what assigned the field before it
class S(StopIteration):
    def __init__(self) -> None:
        self.value = 5
        super().__init__()


print(S().value)
